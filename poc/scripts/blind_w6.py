#!/usr/bin/env python3
"""W6 の PR の説明のブラインドレビュー（poc/answer-key/W6/grading.md）の資料作りと集計。

使い方:
  python3 poc/scripts/blind_w6.py prepare <出力先ディレクトリ>
    - 出力先に R01.md〜 を書く。各ファイルは、その試行の PR.md と、試行の事実の要約（grade_w6.py が集めたもの）。
      候補名は [redacted] に置き換える。E2E の結果・費用は載せない。
    - 記号と試行 ID の対応は poc/results/workflow/W6/blind/mapping.json に書く（レビュー担当には渡さない）。
    - 出力先はレビュー担当が読む場所なので、リポジトリの外（スクラッチ領域）にする。
  python3 poc/scripts/blind_w6.py collect
    - W6/blind/reviewer-1.json・reviewer-2.json（{"R01": {"a": 0-3, "b": .., "c": .., "d": .., "comment": ".."}, ...}）を
      集計し、W6/blind/scores.json（試行ごとの 2 名の合計の平均と、2 点以上ずれた項目）を書く。
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W6"
BLIND = RESULTS / "blind"
SEED = 20261109
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound(?:[-_ ]?engineering)?|\bce-[a-z-]+|ponytail|/ship\b|/qa\b", re.I)
ITEMS = ["a", "b", "c", "d"]


def facts(t):
    w = t["w6"]
    ev = w["evidence"]
    lines = [
        "## 試行の事実（実行記録から自動で集めたもの）",
        "",
        f"- 子セッションが実行したチェックのコマンド: {', '.join(sorted(set(w['checks_run']))[:15]) or 'なし'}",
        f"- ブラウザで /my-tasks を開いた: {'はい' if ev['opened_page'] else 'いいえ'}、画面を操作した: {'はい' if ev['interacted'] else 'いいえ'}",
        f"- 幅 480px 以下で確認した: {'はい' if ev['narrow_viewport'] else 'いいえ'}",
        f"- スクリーンショットを撮った: {'はい' if ev['screenshot_taken'] else 'いいえ'}、コミットされた画像: {', '.join(ev['committed_images']) or 'なし'}",
        f"- tests/ で追加・変更したファイル: {', '.join(w['pr']['tests_changed']) or 'なし'}",
        f"- 採点者が再実行した結果: 型チェック {'成功' if t['checks']['typecheck']['pass'] else '失敗'}、"
        f"単体テスト {'成功' if t['checks']['test']['pass'] else '失敗'}、ビルド {'成功' if t['checks']['build']['pass'] else '失敗'}",
    ]
    return "\n".join(lines)


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W6-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        t = json.loads((RESULTS / f"{trial}.json").read_text())
        body = t["w6"]["pr"]["pr_md"].strip() or "（PR.md はコミットされていない）"
        doc = f"# {code}\n\n## PR.md\n\n{body}\n\n{facts(t)}\n"
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", doc))
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
