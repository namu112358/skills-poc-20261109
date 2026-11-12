#!/usr/bin/env python3
"""W2 のブラインドレビュー用の資料を作る（poc/answer-key/W2/grading.md の手順 1）。

使い方: python3 poc/scripts/blind_w2.py <出力先ディレクトリ> [--supplement]
  - 出力先に R01.patch〜 を書く（候補の管理用ファイル・文書・package-lock.json を除いた差分。候補名は伏せる）。
  - 記号と試行 ID の対応は poc/results/workflow/W2/review/mapping.json に書く（レビュー担当には渡さない）。
  - 出力先はレビュー担当が読む場所なので、リポジトリの外（スクラッチ領域）にする。
  - --supplement: 補足の再試行（W2/supplement/W2-*.json）だけを対象にし、記号は S01〜、対応表は W2/supplement/review/mapping.json に書く。
"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W2"
SEED = 20261109
EXCLUDE = [":!package-lock.json", ":!*.md", ":!*.mdx", ":!docs/", ":!.compound-engineering/", ":!.claude/",
           ":!.gstack/", ":!.superpowers/"]
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound[-_ ]?engineering|\bce-[a-z-]+|ponytail", re.I)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    supplement = "--supplement" in sys.argv[2:]
    results = RESULTS / "supplement" if supplement else RESULTS
    trials = sorted(p.stem for p in results.glob("W2-*.json"))
    codes = [f"{'S' if supplement else 'R'}{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        raw = ROOT / "poc" / "results" / "workflow" / "raw" / trial
        # 作業用コピーの場所は run-trial.sh が workdir に記録する（無ければ旧来の .poc-work/trials/<ID>）
        work = Path((raw / "workdir").read_text().strip()) if (raw / "workdir").exists() else ROOT / ".poc-work" / "trials" / trial
        app = work / "app"
        base = (ROOT / "poc" / "results" / "workflow" / "raw" / trial / "baseline-commit").read_text().strip()
        diff = subprocess.run(["git", "diff", base, "HEAD", "--", ".", *EXCLUDE], cwd=app,
                              capture_output=True, text=True, check=True).stdout
        (out / f"{code}.patch").write_text(NAMES.sub("[redacted]", diff))
    (results / "review").mkdir(parents=True, exist_ok=True)
    (results / "review" / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} patches -> {out}")


if __name__ == "__main__":
    main()
