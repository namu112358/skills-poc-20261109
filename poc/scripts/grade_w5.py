#!/usr/bin/env python3
"""W5（バグ修正）の試行を採点用に調べ、results/workflow/W5/<試行ID>.json に書き出す。

使い方: python3 poc/scripts/grade_w5.py <試行ID> [--cleanup]
  1. grade.py と同じ集計（型チェック・単体テスト・ビルド・隠しの E2E・差分・トランスクリプト）を行う。
  2. 次の W5 固有の事実を足す（poc/answer-key/W5/grading.md）。
     - hidden:     隠しの単体テスト（answer-key/W5/hidden.test.ts）を試行のコードに対して実行した結果（バグごと）
     - original:   元からある単体テスト（poc/app/tests/*.test.ts。候補が書き換えていても元の版）を試行のコードに対して実行した結果
     - regression: 候補が追加・変更したテストを、参照用のコード（仕込みバグ + 正解の修正）と、そこからバグを 1 つだけ戻したコードで
                   実行した結果。正解の修正では通り、バグを戻すと落ちるテストがあれば、そのバグの回帰テストがあるとみなす
  --cleanup: 書き出した後、その試行の作業用コピーを片付ける
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TRIAL = sys.argv[1]
FLAGS = set(sys.argv[2:])
sys.argv = [sys.argv[0], "W5", TRIAL]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

ROOT, APP, RAW, OUT = grade.ROOT, grade.APP, grade.RAW, grade.OUT
KEY = ROOT / "poc" / "answer-key" / "W5"
BUGS = ["B1", "B2", "B3"]
NODE_TEST = ["node", "--experimental-strip-types", "--no-warnings", "--test", "--test-reporter=tap"]


def tap(cwd, files, timeout=300):
    """node:test を TAP で実行し、[(字下げ, テスト名, 成否)] を返す（入れ子のテストも 1 件ずつ）。"""
    try:
        p = subprocess.run(NODE_TEST + files, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    rows = []
    for line in out.splitlines():
        m = re.match(r"^(\s*)(not ok|ok) \d+ - (.*?)(?: # (?:SKIP|TODO).*)?$", line)
        if m:
            rows.append((len(m.group(1)), m.group(3).strip(), m.group(2) == "ok"))
    return rows


def leaves(rows):
    """入れ子の親（直後に子より浅い行が来る行）を除き、末端のテストだけにする。"""
    out = []
    for i, (ind, name, ok) in enumerate(rows):
        # TAP では子が親より先に出力される。直前の行が自分より深ければ、自分は親
        if i > 0 and rows[i - 1][0] > ind:
            continue
        out.append((ind, name, ok))
    return out


def hidden():
    d = APP / ".poc-hidden"
    d.mkdir(exist_ok=True)
    shutil.copy(KEY / "hidden.test.ts", d / "w5.test.ts")
    rows = leaves(tap(APP, [".poc-hidden/w5.test.ts"]))
    shutil.rmtree(d)
    res = {}
    for b in BUGS:
        hit = [ok for _, name, ok in rows if name.startswith(f"[{b}]")]
        res[b] = bool(hit) and all(hit)
    return {"by_bug": res, "rows": [{"name": n, "pass": ok} for _, n, ok in rows]}


def original():
    """元の単体テスト（poc/app/tests/）を、候補の src に対して実行する。"""
    d = APP / ".poc-orig-tests"  # tests/ と同じ深さに置き、../src/ の import をそのまま使う
    d.mkdir(exist_ok=True)
    files = []
    for f in sorted((ROOT / "poc" / "app" / "tests").glob("*.test.ts")):
        shutil.copy(f, d / f.name)
        files.append(f".poc-orig-tests/{f.name}")
    rows = leaves(tap(APP, files))
    shutil.rmtree(d)
    return {"pass": sum(1 for r in rows if r[2]), "total": sum(1 for _ in rows),
            "failed": [n for _, n, ok in rows if not ok]}


def changed_tests():
    base = (RAW / "baseline-commit").read_text().strip()
    out = subprocess.run(["git", "diff", "--name-status", base, "HEAD", "--", "tests/"],
                         cwd=APP, capture_output=True, text=True).stdout
    files = []
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0].startswith("D"):
            continue
        path = parts[-1]
        if path.endswith(".test.ts"):
            files.append(path)
    return files


def make_ref(dst, skip=None):
    """参照用のコード: poc-app + 仕込みバグ + 正解の修正（skip のバグの修正だけ当てない）。"""
    shutil.copytree(ROOT / "poc" / "app", dst, ignore=shutil.ignore_patterns("node_modules", ".next", "tests"), symlinks=True)
    (dst / "node_modules").symlink_to(ROOT / "poc" / "app" / "node_modules")
    (dst / "tests").mkdir()
    patches = [KEY / "bugs.patch"] + [KEY / f"fix{i}.patch" for i in (1, 2, 3) if f"B{i}" != skip]
    for p in patches:
        subprocess.run(["git", "apply", str(p)], cwd=dst, check=True)


def regression():
    files = changed_tests()
    if not files:
        return {"files": [], "by_bug": {b: False for b in BUGS}, "evidence": {}, "ref_failures": []}
    results = {}
    with tempfile.TemporaryDirectory(prefix="poc-w5-ref-") as tmp:
        for variant in ["ref"] + BUGS:
            dst = Path(tmp) / variant
            make_ref(dst, skip=None if variant == "ref" else variant)
            for f in files:
                (dst / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(APP / f, dst / f)
            # 候補が tests/ に置いた補助ファイル（.ts だがテストでないもの）もコピーする
            for extra in (APP / "tests").rglob("*"):
                rel = extra.relative_to(APP)
                if extra.is_file() and not (dst / rel).exists():
                    (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(extra, dst / rel)
            results[variant] = {}
            for f in files:
                results[variant][f] = leaves(tap(dst, [f]))
    by_bug, evidence = {}, {}
    ref_failures = []
    for f in files:
        ref_ok = {(i, n): ok for i, n, ok in results["ref"][f]}
        ref_failures += [f"{f}: {n}" for (i, n), ok in ref_ok.items() if not ok]
    for b in BUGS:
        hits = []
        for f in files:
            ref_ok = {(i, n): ok for i, n, ok in results["ref"][f]}
            for i, n, ok in results[b][f]:
                if ref_ok.get((i, n)) and not ok:
                    hits.append(f"{f}: {n}")
        by_bug[b] = bool(hits)
        evidence[b] = hits[:10]
    return {"files": files, "by_bug": by_bug, "evidence": evidence, "ref_failures": ref_failures[:20]}


def main():
    grade.main()  # 共通の採点（OUT に書き出す）
    result = json.loads(OUT.read_text())
    result["w5"] = {"hidden": hidden(), "original_tests": original(), "regression": regression()}
    if (RAW / "injected-patch").exists():
        result["w5"]["injected_patch"] = (RAW / "injected-patch").read_text().strip()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    w = result["w5"]
    print(f"{TRIAL}: hidden={w['hidden']['by_bug']} original={w['original_tests']['pass']}/{w['original_tests']['total']} "
          f"regression={w['regression']['by_bug']} ref_failures={len(w['regression']['ref_failures'])}")
    if "--cleanup" in FLAGS:
        grade.cleanup()


if __name__ == "__main__":
    main()
