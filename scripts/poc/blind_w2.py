#!/usr/bin/env python3
"""W2 のブラインドレビュー用の資料を作る（docs/poc/answer-key/W2/grading.md の手順 1）。

使い方: python3 scripts/poc/blind_w2.py <出力先ディレクトリ>
  - 出力先に R01.patch〜 を書く（候補の管理用ファイル・文書・package-lock.json を除いた差分。候補名は伏せる）。
  - 記号と試行 ID の対応は docs/poc/results/workflow/W2/review/mapping.json に書く（レビュー担当には渡さない）。
  - 出力先はレビュー担当が読む場所なので、リポジトリの外（スクラッチ領域）にする。
"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W2"
SEED = 20261109
EXCLUDE = [":!package-lock.json", ":!*.md", ":!*.mdx", ":!docs/", ":!.compound-engineering/", ":!.claude/",
           ":!.gstack/", ":!.superpowers/"]
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound[-_ ]?engineering|\bce-[a-z-]+|ponytail", re.I)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W2-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        app = ROOT / ".poc-work" / "trials" / trial / "app"
        base = (ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / trial / "baseline-commit").read_text().strip()
        diff = subprocess.run(["git", "diff", base, "HEAD", "--", ".", *EXCLUDE], cwd=app,
                              capture_output=True, text=True, check=True).stdout
        (out / f"{code}.patch").write_text(NAMES.sub("[redacted]", diff))
    (RESULTS / "review").mkdir(parents=True, exist_ok=True)
    (RESULTS / "review" / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} patches -> {out}")


if __name__ == "__main__":
    main()
