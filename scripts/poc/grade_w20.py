#!/usr/bin/env python3
"""W20（レビューの組み合わせの評価）・W21（見つけにくい問題でのレビューの比較）の試行の事実を集め、
results/workflow/<W>/<試行ID>.json に書き出す。

使い方: python3 scripts/poc/grade_w20.py <試行ID> [--cleanup]
  - 試行 ID は <W>-<設定>-<題材>-<繰り返し>（例 W20-cr-low-c2-1・W21-ce-review-c3-1）。
    設定は W20 が cr-low・cr-high・review-pr・combo・sp-review、W21 が baseline・cr-high・review-pr・principles・ce-review。
  - 費用・ターン数などは grade.py の transcript_stats を使う。W20 はコードを変えないので、型チェック・テスト・ビルドはしない。
  - レビューの指摘（REVIEW.md）の本文を保存する。指摘と正解の突き合わせは judge_w20.py（判定役）で行う。
  --cleanup: 書き出した後、その試行の作業用コピーを片付ける（grade.py の cleanup）
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TRIAL = sys.argv[1]
FLAGS = set(sys.argv[2:])
SCENARIO = TRIAL.split("-", 1)[0]
sys.argv = [sys.argv[0], SCENARIO, TRIAL]  # grade.py は読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

APP, RAW, OUT = grade.APP, grade.RAW, grade.OUT
CONFIGS = ("cr-low", "cr-high", "review-pr", "combo", "sp-review", "baseline", "principles", "ce-review")


def git(*args):
    return subprocess.run(["git", *args], cwd=APP, capture_output=True, text=True)


def parse_id(trial):
    m = re.fullmatch(r"W2[01]-(" + "|".join(map(re.escape, CONFIGS)) + r")-(c\d+)-(\d+)", trial)
    if not m:
        sys.exit(f"W20・W21 の試行 ID ではない: {trial}")
    return m.group(1), m.group(2), int(m.group(3))


def main():
    config, case, rep = parse_id(TRIAL)
    stats = grade.transcript_stats()
    base = (RAW / "baseline-commit").read_text().strip()
    body = git("show", "HEAD:REVIEW.md")
    review_md = body.stdout if body.returncode == 0 else ""
    by_candidate = False
    for line in git("log", "--format=%H %s", f"{base}..HEAD").stdout.splitlines():
        sha, _, subject = line.partition(" ")
        if subject != "poc: uncommitted leftovers" and git("cat-file", "-e", f"{sha}:REVIEW.md").returncode == 0:
            by_candidate = True
            break
    # 片付けの前に成果（REVIEW.md の差分）を保存する（grade.cleanup は diff.patch があるときだけ片付ける）
    (RAW / "diff.patch").write_text(git("diff", base, "HEAD", "--", "REVIEW.md").stdout)
    result = {
        "trial": TRIAL, "scenario": SCENARIO, "config": config, "case": case, "rep": rep,
        "review_md": review_md, "review_chars": len(review_md), "review_committed": by_candidate,
        "transcript": stats,
        "interventions": len((RAW / "interventions.log").read_text().splitlines()) if (RAW / "interventions.log").exists() else 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{TRIAL}: REVIEW.md={len(review_md)} chars committed={by_candidate} cost=${stats.get('cost_usd', 0):.2f}")
    if "--cleanup" in FLAGS:
        grade.cleanup()


if __name__ == "__main__":
    main()
