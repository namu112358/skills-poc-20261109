#!/usr/bin/env python3
"""W10 のコードのブラインドレビュー（docs/poc/answer-key/W10/grading.md の「ブラインドレビュー」）の資料作りと集計。

使い方:
  python3 scripts/poc/blind_w10.py prepare <出力先ディレクトリ>
    - 出力先に R01.diff〜 を書く。各ファイルは、その試行の差分（raw/<ID>/diff.patch）から、package-lock.json・文書（.md など）・
      候補のツールが作る管理用ファイル（docs/plans/ など）を除いたもの。候補名・ツール名は [redacted] に置き換える。
    - 共通の資料として、課題文（wf-W10.md）と評価用アプリの規約（poc-app/CLAUDE.md）を CONTEXT.md に書く。
    - 記号と試行 ID の対応は docs/poc/results/workflow/W10/blind/mapping.json に書く（レビュー担当には渡さない）。
    - 出力先はレビュー担当が読む場所なので、リポジトリの外（スクラッチ領域）にする。
  python3 scripts/poc/blind_w10.py collect
    - W10/blind/reviewer-1.json・reviewer-2.json（{"R01": {"a": 0-3, "b": .., "c": .., "d": .., "e": .., "comment": ".."}, ...}）を
      集計し、W10/blind/scores.json（試行ごとの 2 名の合計の平均と、2 点以上ずれた項目）を書く。
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W10"
RAW = ROOT / "docs" / "poc" / "results" / "workflow" / "raw"
BLIND = RESULTS / "blind"
SEED = 20261109
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound(?:[-_ ]?engineering)?|\bce-[a-z-]+|ponytail|claude", re.I)
ITEMS = ["a", "b", "c", "d", "e"]
SKIP = re.compile(r"^(package-lock\.json|docs/|\.compound-engineering/|\.claude/|.*\.(md|mdx|txt)$|AGENTS\.md$|\.playwright-mcp/)")


def filtered_diff(text):
    out, keep = [], True
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", chunk)
        if not m:
            continue
        keep = not SKIP.match(m.group(2))
        if keep:
            out.append(chunk)
    return "".join(out)


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W10-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        diff = filtered_diff((RAW / trial / "diff.patch").read_text())
        (out / f"{code}.diff").write_text(NAMES.sub("[redacted]", diff) or "（コードの変更なし）\n")
    ctx = ("# 課題文\n\n" + (ROOT / "docs" / "poc" / "tasks" / "wf-W10.md").read_text()
           + "\n\n# 評価用アプリの規約（poc-app/CLAUDE.md）\n\n" + (ROOT / "poc-app" / "CLAUDE.md").read_text())
    (out / "CONTEXT.md").write_text(ctx)
    BLIND.mkdir(parents=True, exist_ok=True)
    (BLIND / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} files -> {out}")


def collect():
    mapping = json.loads((BLIND / "mapping.json").read_text())
    revs = [json.loads((BLIND / f"reviewer-{i}.json").read_text()) for i in (1, 2)]
    by_trial = {}
    for code, trial in mapping.items():
        totals = [sum(int(r[code][k]) for k in ITEMS) for r in revs]
        gaps = [k for k in ITEMS if abs(int(revs[0][code][k]) - int(revs[1][code][k])) >= 2]
        by_trial[trial] = {"code": code, "totals": totals, "mean": sum(totals) / 2,
                           "items": {k: [int(r[code][k]) for r in revs] for k in ITEMS}, "gaps": gaps,
                           "comments": [r[code].get("comment", "") for r in revs]}
    (BLIND / "scores.json").write_text(json.dumps({"by_trial": by_trial}, ensure_ascii=False, indent=2) + "\n")
    for trial, v in sorted(by_trial.items()):
        print(f"{trial:30} {v['code']} totals={v['totals']} mean={v['mean']} gaps={v['gaps']}")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    else:
        collect()
