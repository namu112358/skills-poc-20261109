#!/usr/bin/env python3
"""W16: 再発防止のテスト（grading.md の「再発防止のテスト」）。候補の修正後のコードに、2 つの原因をそれぞれ戻した版（再注入）を作り、
候補のテスト（npm test）がそれを検出するかを調べる。

使い方:
  python3 scripts/poc/reinject_w16.py <試行ID>
  python3 scripts/poc/reinject_w16.py --app <ディレクトリ> --name <名前> [--base <コミット>]   試行前の確認用
手順（原因 A・B のそれぞれ）:
  1. 候補のコードがその原因を直していない（隠しテストの I1・I2 がどちらも不合格＝A、I3・I4 がどちらも不合格＝B）なら、再注入しない（not_fixed、0 点）。
  2. 別の claude -p（ツールなし）に、候補の差分（src/ だけ）を渡し、「その原因だけを戻す最小の書き換え」（ファイル・置き換え前・置き換え後）を作らせる。
     採点者の補正があれば（results/workflow/W16/reinject/<名前>.override.json の {"A": [...], "B": [...]}）それを使う。
  3. 作業用コピーの写しに書き換えを当ててビルドし、隠しテスト（incident.cjs）で、その原因の項目（A は I1・I2、B は I3・I4）の
     どちらかが不合格になることを確かめる（戻せていなければ、1 回だけ作り直させる。それでも駄目なら needs_review）。
  4. 書き換えた版で候補の npm test を実行し、書き換える前より失敗が増えれば（または実行が失敗すれば）「検出した」。
結果は results/workflow/W16/reinject/<名前>.json。削除はしない（写しは一時ディレクトリに作って残す）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import grade_w16 as G  # noqa: E402

OUTDIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W16" / "reinject"
MODEL = os.environ.get("POC_JUDGE_MODEL", "claude-sonnet-5-5")
CAUSE = {
    "A": ("ジョブの多重起動を防いでいない",
          "候補が足した『同じジョブ・同じお知らせを、重なった 2 つの実行が両方送らないようにする仕組み』（ロック・排他・送信中の記録の確認・"
          "取り合い（claim）・一意制約など）だけを働かなくする。Idempotency-Key の作り方・再試行・ログ・ほかの振る舞いは変えない。"
          "例: ロックを取る処理が常に成功するようにする／送信中の記録を確認しないようにする／取り合いの条件を外す。",
          ["I1", "I2"]),
    "B": ("タイムアウトの再試行で冪等性キーを変えている",
          "候補が直した『同じお知らせの再試行・次の実行での送り直しで、同じ Idempotency-Key を使う』ことだけを元に戻し、"
          "試行のたびに違うキーを送るようにする（例: ヘッダーのキーの末尾に試行回数を付ける）。ロック・排他・ログ・ほかの振る舞いは変えない。",
          ["I3", "I4"]),
}
SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {"type": "array", "items": {"type": "object", "properties": {
            "file": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, "required": ["file", "old", "new"]}},
        "explanation": {"type": "string"},
    },
    "required": ["edits", "explanation"],
}


def sh(cmd, cwd, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def copy_app(app):
    d = Path(tempfile.mkdtemp(prefix="w16-reinject-")) / "app"
    shutil.copytree(app, d, symlinks=True, ignore=shutil.ignore_patterns("node_modules", ".next", ".git"))
    subprocess.run(["cp", "-al", str(Path(app) / "node_modules"), str(d / "node_modules")], check=True)
    return d


def draft(app, base, cause, feedback=""):
    name, how, _ = CAUSE[cause]
    diff = subprocess.run(["git", "-C", str(app), "diff", base, "HEAD", "--", "src", ":!*.test.*"], capture_output=True, text=True).stdout
    files = sorted(set(re.findall(r"^\+\+\+ b/(\S+)", diff, re.M)))
    current = "\n\n".join(f"=== {f} ===\n{(Path(app) / f).read_text()}" for f in files if (Path(app) / f).exists())
    prompt = (f"障害の原因「{name}」を直した変更（差分）と、変更後のファイルの全文です。\n\n--- 差分 ---\n{diff[:40000]}\n\n"
              f"--- 変更後のファイル ---\n{current[:60000]}\n\n"
              f"採点のために、この修正のうち原因「{name}」に効いている部分だけを元に戻す、最小の書き換えを作ってください。{how}\n"
              "書き換えは、変更後のファイルの中に 1 回だけ現れる文字列 old を new に置き換える形で、必要な数だけ並べてください（型チェックが通る形に）。"
              "テストのファイル（tests/ や *.test.*）は書き換えないでください。" + (f"\n\n前回の書き換えの結果: {feedback}" if feedback else ""))
    home = Path(tempfile.mkdtemp(prefix="w16-reinject-home-"))
    p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                        "--no-session-persistence", "--json-schema", json.dumps(SCHEMA), "--output-format", "json"],
                       cwd=home, env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    try:
        o = json.loads(p.stdout)
        so = o.get("structured_output") or json.loads(o.get("result") or "{}")
        return so["edits"], so.get("explanation", ""), o.get("total_cost_usd") or 0.0
    except (ValueError, KeyError, TypeError) as ex:
        return [], f"作れなかった: {ex} {p.stdout[-300:]}", 0.0


def apply_edits(d, edits):
    for e in edits:
        f = d / e["file"]
        if not f.exists() or re.search(r"(^|/)tests?/|\.test\.", e["file"]):
            return f"対象外のファイル: {e['file']}"
        s = f.read_text()
        if s.count(e["old"]) != 1:
            return f"{e['file']} に old が {s.count(e['old'])} 回ある"
        f.write_text(s.replace(e["old"], e["new"]))
    return ""


def test_failures(d):
    code, out = sh("npm test", d, timeout=900)
    m = re.search(r"^# fail (\d+)", out, re.M)
    return code, int(m.group(1)) if m else -1, out[-1500:]


def check_mutant(app, edits, cause, work):
    d = copy_app(app)
    err = apply_edits(d, edits)
    if err:
        return {"ok": False, "why": err}
    code, out = sh("npm run build", d)
    if code != 0:
        return {"ok": False, "why": "ビルドに失敗: " + out[-400:]}
    res, _, _ = G.suite(d, work, f"reinject-{cause}", "incident.cjs", G.ADAPTER, ["main"], server_env=G.TIMEOUT_ENV)
    by = {r["id"]: r["pass"] for r in res}
    ids = CAUSE[cause][2]
    reverted = any(by.get(i) is False for i in ids)
    return {"ok": reverted, "why": "" if reverted else f"{'・'.join(ids)} が不合格にならない: {by}", "incident": by, "dir": str(d)}


def evaluate(app, base, name, incident):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ov_path = OUTDIR / f"{name}.override.json"
    override = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    by = {r["id"]: r["pass"] for r in incident}
    work = Path(tempfile.mkdtemp(prefix=f"w16-reinject-{name}-"))
    code0, fail0, _ = test_failures(app)
    out = {"name": name, "tests_before": {"exit": code0, "fail": fail0}, "causes": {}, "cost_usd": 0.0}
    for cause, (_, _, ids) in CAUSE.items():
        r = {"fixed": any(by.get(i) for i in ids)}
        if not r["fixed"]:
            r.update(status="not_fixed", guarded=False)
            out["causes"][cause] = r
            continue
        tries = []
        if cause in override:
            edits, expl = override[cause], "採点者の補正"
            chk = check_mutant(app, edits, cause, work)
            tries.append({"edits": edits, "explanation": expl, **chk})
        else:
            feedback = ""
            for _ in range(2):
                edits, expl, cost = draft(app, base, cause, feedback)
                out["cost_usd"] += cost
                chk = check_mutant(app, edits, cause, work) if edits else {"ok": False, "why": expl}
                tries.append({"edits": edits, "explanation": expl, **chk})
                if chk["ok"]:
                    break
                feedback = chk["why"]
        last = tries[-1]
        r["tries"] = tries
        if not last["ok"]:
            r.update(status="needs_review", guarded=None)
        else:
            code, fail, log = test_failures(Path(last["dir"]))
            guarded = (code != 0) if code0 == 0 else (fail > fail0 or fail == -1)
            r.update(status="checked", guarded=guarded, tests_after={"exit": code, "fail": fail}, log=log if guarded else "")
        out["causes"][cause] = r
    return out


def main():
    args = sys.argv[1:]
    if args[0] == "--app":
        app = Path(args[1])
        name = args[args.index("--name") + 1]
        base = args[args.index("--base") + 1]
        incident = json.loads(Path(args[args.index("--grade") + 1]).read_text())["incident"]
    else:
        name = args[0]
        raw = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / name
        app = Path((raw / "workdir").read_text().strip()) / "app"
        base = (raw / "baseline-commit").read_text().strip()
        incident = json.loads((G.RESULTS / f"{name}.json").read_text())["w16"]["incident"]
    res = evaluate(app, base, name, incident)
    (OUTDIR / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(name, {k: (v["status"], v.get("guarded")) for k, v in res["causes"].items()}, f"${res['cost_usd']:.2f}")


if __name__ == "__main__":
    main()
