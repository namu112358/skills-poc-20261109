#!/usr/bin/env python3
"""W9（レビューで不具合を見つける）の試行を採点用に調べ、results/workflow/W9/<試行ID>.json に書き出す。

使い方: python3 scripts/poc/grade_w9.py <試行ID> [--cleanup]
  1. grade.py と同じ集計（型チェック・単体テスト・ビルド・差分・トランスクリプト）を行う（W9 は隠しの E2E なし）。
  2. 次の W9 固有の事実を足す（docs/poc/answer-key/W9/grading.md）。
     - review_md:        レビューの指摘（REVIEW.md）の本文。採点はこれだけで行う
     - review_committed: 候補が REVIEW.md をコミットしたか（run-trial.sh が最後に残りをコミットした分は含めない）
     - code_changed:     REVIEW.md 以外に変えたファイル（課題では「コードは直さない」と指示している。点数には入れず記録する）
  --cleanup: 書き出した後、その試行の作業用コピーを片付ける
"""
import json
import subprocess
import sys
from pathlib import Path

TRIAL = sys.argv[1]
FLAGS = set(sys.argv[2:])
sys.argv = [sys.argv[0], "W9", TRIAL]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

APP, RAW, OUT = grade.APP, grade.RAW, grade.OUT


def git(*args):
    return subprocess.run(["git", *args], cwd=APP, capture_output=True, text=True)


def review_facts(result):
    base = (RAW / "baseline-commit").read_text().strip()
    body = git("show", "HEAD:REVIEW.md")
    review_md = body.stdout if body.returncode == 0 else ""
    # 候補自身のコミット（run-trial.sh の「poc: uncommitted leftovers」より前）に REVIEW.md があるか
    by_candidate = False
    for line in git("log", "--format=%H %s", f"{base}..HEAD").stdout.splitlines():
        sha, _, subject = line.partition(" ")
        if subject == "poc: uncommitted leftovers":
            continue
        if git("cat-file", "-e", f"{sha}:REVIEW.md").returncode == 0:
            by_candidate = True
            break
    changed = [f["path"] for f in result["diff"]["files"] if f["path"] != "REVIEW.md"]
    return {
        "review_md": review_md,
        "review_committed": by_candidate,
        "review_chars": len(review_md),
        "code_changed": [p for p in changed if not grade.TOOL_ARTIFACT.match(p)],
        "artifacts": [p for p in changed if grade.TOOL_ARTIFACT.match(p)],
    }


def main():
    grade.main()  # 共通の採点（OUT に書き出す）
    result = json.loads(OUT.read_text())
    result["w9"] = review_facts(result)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    w = result["w9"]
    print(f"{TRIAL}: REVIEW.md={w['review_chars']} chars committed={w['review_committed']} "
          f"code_changed={len(w['code_changed'])}")
    if "--cleanup" in FLAGS:
        grade.cleanup()


if __name__ == "__main__":
    main()
