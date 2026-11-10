#!/usr/bin/env python3
"""W10（仕様に書かれていない落とし穴がある機能追加）の試行を採点用に調べ、results/workflow/W10/<試行ID>.json に書き出す。

使い方:
  python3 scripts/poc/grade_w10.py <試行ID> [--cleanup]
    1. grade.py と同じ集計（型チェック・単体テスト・ビルド・公開の受け入れテスト acceptance.cjs・差分・トランスクリプト）
    2. W10 固有の事実（docs/poc/answer-key/W10/grading.md）を w10 に足す
       - hidden:   隠しテスト（hidden.cjs）。サーバーは fake-clock.cjs で時計を 2026-11-09T15:30Z（日本時間 11-10 00:30）にして起動する
       - mutation: 候補が書いたテストの強さ。候補が src/lib/ に追加・変更した行をわざと壊し（ミューテーション）、
                   候補の作業用コピーの npm test が検出できた割合
  python3 scripts/poc/grade_w10.py --app <アプリのディレクトリ> [--base <コミット>]
    試行前の検証用（参照実装・わざと不具合を入れた版・変更なしの poc-app）。型チェック・単体テスト・ビルド・
    公開の受け入れテスト・隠しテスト・ミューテーション（--base があるとき）の結果を標準出力に JSON で出す。
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W10"
MAX_MUTANTS = 60
MUTANT_TIMEOUT = 120


def sh(cmd, cwd, timeout=600, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout + p.stderr


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_cjs(app, name, fake_clock=False):
    """next start で起動したばかりのサーバー（インメモリ DB）に、正解データの検査スクリプトを実行する。"""
    port = free_port()
    env = dict(os.environ)
    env.pop("DATABASE_PATH", None)
    if fake_clock:
        env["NODE_OPTIONS"] = (env.get("NODE_OPTIONS", "") + f" --require {KEY / 'fake-clock.cjs'}").strip()
    server = subprocess.Popen(f"npx next start -p {port}", cwd=app, shell=True, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(1)
        cenv = dict(os.environ, NODE_PATH=subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip())
        p = subprocess.run(f"node {KEY / name} http://127.0.0.1:{port}", cwd=app, shell=True, capture_output=True,
                           text=True, timeout=600, env=cenv)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return [{"id": "X", "name": f"{name} の実行", "pass": False, "detail": (p.stdout + p.stderr)[-500:]}]
    finally:
        os.killpg(server.pid, 15)
        time.sleep(2)


# ---- ミューテーション（候補のテストの強さ） ----
# 演算子の置き換え（コードの部分だけ。文字列・コメントの中は対象外）
CODE_OPS = [
    ("===", "!=="), ("!==", "==="), (" <= ", " < "), (" >= ", " > "), (" < ", " <= "), (" > ", " >= "),
    ("&&", "||"), ("||", "&&"), ("true", "false"), ("false", "true"), (".trim()", ""),
]
# SQL（文字列の中）の条件の置き換え
STRING_OPS = [(" AND ", " OR "), ("'pending'", "'approved'")]
NUM = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
NEG = re.compile(r"!(?=[\w(])")


def code_mask(src):
    """各文字が「コード」なら True、文字列・テンプレート・コメントの中なら False（簡易の字句解析）。"""
    mask = [True] * len(src)
    i, n = 0, len(src)
    stack = []  # テンプレートの ${ } の入れ子
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                mask[k] = False
            i = j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                mask[k] = False
            i = j
            continue
        if c in "'\"`":
            q = c
            mask[i] = False
            i += 1
            while i < n:
                if src[i] == "\\":
                    mask[i] = False
                    if i + 1 < n:
                        mask[i + 1] = False
                    i += 2
                    continue
                if q == "`" and src.startswith("${", i):
                    # ${ … } の中はコードとして扱う（括弧の対応を数える）
                    depth, i = 1, i + 2
                    while i < n and depth:
                        if src[i] == "{":
                            depth += 1
                        elif src[i] == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    i += 1
                    continue
                mask[i] = False
                if src[i] == q:
                    i += 1
                    break
                if q != "`" and src[i] == "\n":
                    break
                i += 1
            continue
        i += 1
    del stack
    return mask


def added_lines(app, base, path):
    out = subprocess.run(["git", "diff", "-U0", base, "HEAD", "--", path], cwd=app, capture_output=True, text=True).stdout
    lines = set()
    for m in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + count))
    return lines


SKIP_LINE = re.compile(r"^\s*(import |export type |type |interface |//|\*|/\*)")


def mutants_for(app, base):
    names = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", base, "HEAD", "--", "src/lib"],
                           cwd=app, capture_output=True, text=True).stdout.split()
    files = [f for f in names if f.endswith(".ts") and not f.endswith(".d.ts") and ".test." not in f]
    out = []
    for f in sorted(files):
        src = (Path(app) / f).read_text()
        mask = code_mask(src)
        want = added_lines(app, base, f)
        offs = [0]
        for line in src.splitlines(keepends=True):
            offs.append(offs[-1] + len(line))
        for ln in sorted(want):
            if ln - 1 >= len(offs) - 1:
                continue
            a, b = offs[ln - 1], offs[ln]
            text = src[a:b]
            if SKIP_LINE.match(text) or not text.strip():
                continue
            cands = []
            for old, new in CODE_OPS:
                for m in re.finditer(re.escape(old), text):
                    p = a + m.start()
                    if all(mask[p:p + len(old)]):
                        if old in (" < ", " > ") and re.search(r"[<>]=?$", text[:m.start()].rstrip()):
                            continue
                        cands.append((p, old, new))
            for old, new in STRING_OPS:
                for m in re.finditer(re.escape(old), text):
                    p = a + m.start()
                    if not any(mask[p:p + len(old)]):
                        cands.append((p, old, new))
            for m in NUM.finditer(text):
                p = a + m.start()
                if all(mask[p:p + len(m.group(1))]):
                    v = int(m.group(1))
                    cands.append((p, m.group(1), str(v + 1)))
            for m in NEG.finditer(text):
                p = a + m.start()
                if mask[p] and not text[m.start():].startswith("!="):
                    cands.append((p, "!", ""))
            for p, old, new in cands:
                out.append({"file": f, "line": ln, "pos": p, "old": old, "new": new,
                            "snippet": text.strip()[:160]})
    # 同じ位置・同じ置き換えの重複を除き、多すぎるときは全体から等間隔に選ぶ（決定的）
    seen, uniq = set(), []
    for m in out:
        k = (m["file"], m["pos"], m["old"], m["new"])
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    if len(uniq) > MAX_MUTANTS:
        step = len(uniq) / MAX_MUTANTS
        uniq = [uniq[int(i * step)] for i in range(MAX_MUTANTS)]
    return uniq


def test_run(cwd):
    """npm test を実行し、(終了コード, 失敗した数, 出力の末尾) を返す。時間切れは失敗扱い（-1）。"""
    try:
        code, log = sh("npm test", cwd, timeout=MUTANT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return -1, 10**6, "timeout"
    fails = len(re.findall(r"^\s*not ok \d+", log, re.M))
    m = re.search(r"^# fail (\d+)", log, re.M)
    if m:
        fails = max(fails, int(m.group(1)))
    return code, fails, log[-400:]


def mutation(app, base, scratch):
    """候補の src/lib/ の変更行をわざと壊し、候補の npm test で検出できた割合を返す。作業は scratch のコピーで行う。"""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    work = scratch / "app"
    if not work.exists():
        shutil.copytree(app, work, symlinks=True, ignore=shutil.ignore_patterns("node_modules", ".next", ".git"))
        os.symlink(Path(app) / "node_modules", work / "node_modules")
    muts = mutants_for(app, base)
    base_code, base_fails, base_log = test_run(work)
    results = []
    for m in muts:
        path = work / m["file"]
        orig = path.read_text()
        p = m["pos"]
        assert orig[p:p + len(m["old"])] == m["old"], m
        path.write_text(orig[:p] + m["new"] + orig[p + len(m["old"]):])
        try:
            code, fails, _ = test_run(work)
        finally:
            path.write_text(orig)
        killed = (code != 0) if base_code == 0 else (code == -1 or fails > base_fails)
        results.append({**m, "killed": killed})
    killed = sum(1 for r in results if r["killed"])
    return {
        "baseline_tests_pass": base_code == 0, "baseline_fails": base_fails,
        "baseline_log": "" if base_code == 0 else base_log,
        "mutants": len(results), "killed": killed,
        "kill_rate": round(killed / len(results), 3) if results else 0.0,
        "files": sorted({r["file"] for r in results}),
        "survivors": [{k: r[k] for k in ("file", "line", "old", "new", "snippet")} for r in results if not r["killed"]][:40],
        "details": [{k: r[k] for k in ("file", "line", "old", "new", "killed")} for r in results],
    }


def checks(app):
    out = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = sh(cmd, app)
        out[name] = {"pass": code == 0, "log": log[-800:]}
    return out


def validate(app, base):
    c = checks(app)
    res = {"checks": {k: v["pass"] for k, v in c.items()}}
    if c["build"]["pass"]:
        res["acceptance"] = run_cjs(app, "acceptance.cjs")
        res["hidden"] = run_cjs(app, "hidden.cjs", fake_clock=True)
    if base:
        import tempfile
        res["mutation"] = mutation(app, base, tempfile.mkdtemp(prefix="w10-mut-"))
        res["mutation"].pop("details")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    for k in ("acceptance", "hidden"):
        if k in res:
            print(k, "".join("o" if r["pass"] else "x" for r in res[k]), file=sys.stderr)
    if "mutation" in res:
        m = res["mutation"]
        print(f"mutation {m['killed']}/{m['mutants']} base_pass={m['baseline_tests_pass']}", file=sys.stderr)


def recount(raw):
    """ターン数・実際に動いた時間を、各ステップの result をすべて足して数え直す。

    grade.py はステップごとに最後の result だけを数える。子セッションが裏で待機用の監視などを起動すると、
    その終了通知のたびに 1 ステップの中に result が増える（W10 の Feature Dev で、最後の result が 1 ターン・4 秒だった）。
    各 result の num_turns・duration_ms はその応答の分なので、すべて足すと全体になる。費用は累計なので数え直さない。
    """
    turns = ms = 0
    for step in raw.glob("step*.jsonl"):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result":
                turns += d.get("num_turns") or 0
                ms += d.get("duration_ms") or 0
    return turns, round(ms / 1000)


def apply_recount(out_path, raw):
    r = json.loads(out_path.read_text())
    turns, active = recount(raw)
    tr = r["transcript"]
    tr["turns_last_result_only"], tr["active_seconds_last_result_only"] = tr["turns"], tr["active_seconds"]
    tr["turns"], tr["active_seconds"] = turns, active
    out_path.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--recount":
        # 採点済みの結果のターン数・時間だけを数え直す（採点はやり直さない）
        for p in sorted((ROOT / "docs" / "poc" / "results" / "workflow" / "W10").glob("W10-*.json")):
            if "turns_last_result_only" not in json.loads(p.read_text())["transcript"]:
                apply_recount(p, ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / p.stem)
                print("recounted", p.stem)
        return
    if args and args[0] == "--app":
        base = args[args.index("--base") + 1] if "--base" in args else None
        validate(args[1], base)
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W10", trial]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
    sys.path.insert(0, str(HERE))
    import grade  # noqa: E402
    grade.main()  # 型チェック・単体テスト・ビルド・acceptance.cjs・差分・トランスクリプト → W10/<試行ID>.json
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    w10 = {}
    w10["hidden"] = run_cjs(grade.APP, "hidden.cjs", fake_clock=True) if result["checks"]["build"]["pass"] else []
    w10["mutation"] = mutation(grade.APP, base, grade.WORK / "mutation")
    w10["tests_changed"] = [f["path"] for f in result["diff"]["files"] if f["kind"] == "test"]
    result["w10"] = w10
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    apply_recount(grade.OUT, grade.RAW)
    hp =sum(1 for r in w10["hidden"] if r["pass"])
    m = w10["mutation"]
    print(f"{trial}: hidden {hp}/{len(w10['hidden'])} "
          f"{''.join('o' if r['pass'] else 'x' for r in w10['hidden'])} mutation {m['killed']}/{m['mutants']} "
          f"(base tests pass={m['baseline_tests_pass']})")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
