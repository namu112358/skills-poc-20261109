#!/usr/bin/env python3
"""W3 の採点者用の資料を作る（poc/answer-key/W3/grading.md の「採点者による判定」の手順 1）。

使い方: python3 poc/scripts/blind_w3.py <出力先ディレクトリ>
  - grade_w3.py が保存した採点する文書（results/workflow/W3/docs/<試行ID>.md）を R01.md〜 として書き出す（候補名は伏せる）。
  - 記号と試行 ID の対応は poc/results/workflow/W3/review/mapping.json に書く（採点者には渡さない）。
  - 出力先は採点者が読む場所なので、リポジトリの外（スクラッチ領域）にする。
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W3"
SEED = 20261109
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|g-stack|compound[-_ ]?engineering|\bce-[a-z-]+|office[-_ ]hours|"
                   r"plan-ceo-review|brainstorm(ing)?|ponytail", re.I)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W3-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        text = (RESULTS / "docs" / f"{trial}.md").read_text()
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", text))
    (RESULTS / "review").mkdir(parents=True, exist_ok=True)
    (RESULTS / "review" / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} docs -> {out}")


if __name__ == "__main__":
    main()
