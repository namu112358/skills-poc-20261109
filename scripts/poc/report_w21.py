#!/usr/bin/env python3
"""W21（見つけにくい問題でのレビューの比較）の集計表を作る。docs/poc/tasks/wf-W21-design.md の「測るもの」。

使い方: python3 scripts/poc/report_w21.py > docs/poc/results/workflow/W21/tables.md
        POC_E2_SCENARIO=W22 python3 scripts/poc/report_w21.py > docs/poc/results/workflow/W22/tables.md（W22。同じ題材の W21 の設定と並べる）
  - 入力: results/workflow/W21/judge/scores.json（POC_E2_SCENARIO=W21 python3 scripts/poc/judge_w20.py collect の出力）と、
    各試行の結果（results/workflow/W21/W21-*.json。費用・時間・サブエージェントの数）。
  - 正解の ID の種類: B = 不具合、P = 設計の問題（c7）、I = レビューへの指示への対応（c6）、D = おとり。
"""
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = os.environ.get("POC_E2_SCENARIO", "W21")
RES = ROOT / "docs" / "poc" / "results" / "workflow" / SCENARIO
CONFIGS = {
    "W21": ["baseline", "cr-high", "review-pr", "principles", "ce-review"],
    "W22": ["hk-baseline", "hk-cr-high", "hk-review-pr", "hk-principles", "hk-ce-review", "review-pr-full", "ce-full"],
    "W23": ["baseline", "hk-baseline", "cr-high", "review-pr", "ce-review"],
    "W24": ["baseline", "baseline-run", "hk-baseline", "hk-baseline-run"],
    "W25": ["baseline-run", "hk-baseline-run"],
    "W26": ["baseline-std"],
    "W27": ["baseline", "baseline-run"],
    "W28": ["baseline-e2e"],
    "W29": ["baseline-req"],
}[SCENARIO]
CASES = {"W23": ["d1", "d2", "d3"], "W24": ["c4", "d1", "d3"], "W26": ["c4", "d1", "d3"], "W27": ["c2", "c3", "c4"], "W28": ["c2", "c3", "c4"], "W29": ["c2", "c3", "c4"]}.get(SCENARIO, ["c1", "c2", "c3", "c4", "c5", "c6", "c7"])
LABEL = {"baseline": "baseline（道具なし）", "cr-high": "内蔵 `/code-review high`", "review-pr": "PR Review Toolkit `/review-pr`",
         "principles": "自作 `design-principles-review`", "ce-review": "CE `ce-code-review`",
         "review-pr-full": "`/review-pr`（専門エージェントの起動を明示）", "baseline-run": "道具なし + 動かして確かめる指示", "baseline-std": "道具なし + CLAUDE.md の規約に動かして確かめる", "baseline-e2e": "道具なし + 本番で起動して画面・API を確かめる", "baseline-req": "道具なし + 要件を 1 つずつ照らす", "ce-full": "CE `ce-code-review depth:full`"}
for _k in ["baseline", "cr-high", "review-pr", "principles", "ce-review", "baseline-run"]:
    LABEL["hk-" + _k] = "Haiku: " + LABEL[_k]


def main():
    scores = json.loads((RES / "judge" / "scores.json").read_text())
    by = scores["by_trial"]
    trials = {}
    for t in by:
        trials[t] = json.loads((RES / f"{t}.json").read_text())
    cell = defaultdict(list)  # (config, case) -> [score]
    for t, s in by.items():
        cell[(s["config"], s["case"])].append((s, trials[t]))

    def ids(s, prefix):
        return [m for m in s["matched"] if m.startswith(prefix)]

    out = []
    out.append(f"判定の一致率（2 回判定した {len(scores['agreement']['pairs'])} 件で、正解の一致・おとりが同じだった割合）: "
               f"{scores['agreement']['rate']}\n")
    # 題材ごとの見つけた数（回ごと）
    out.append("## 題材ごとの結果（見つけた正解 / 正解の数。1 回目・2 回目）\n")
    head = "| 設定 | " + " | ".join(CASES) + " | 不具合（B）の計 | 設計（P）の計 | 指示（I1） |"
    out.append(head)
    out.append("|" + "---|" * (len(CASES) + 4))
    summary = {}
    for c in CONFIGS:
        row, b_hit, b_all, p_hit, p_all, i_hit, i_all = [], 0, 0, 0, 0, 0, 0
        for case in CASES:
            items = sorted(cell[(c, case)], key=lambda x: x[0]["rep"])
            parts = []
            for s, _ in items:
                bugs = s["bugs"]
                if not bugs:
                    parts.append(f"{s['findings']} 件")
                else:
                    parts.append(f"{len(s['matched'])}/{len(bugs)}")
                b_hit += len(ids(s, "B")); b_all += len([x for x in bugs if x.startswith("B")])
                p_hit += len(ids(s, "P")); p_all += len([x for x in bugs if x.startswith("P")])
                i_hit += len(ids(s, "I")); i_all += len([x for x in bugs if x.startswith("I")])
            row.append("・".join(parts) or "—")
        summary[c] = {"b": (b_hit, b_all), "p": (p_hit, p_all), "i": (i_hit, i_all)}
        out.append(f"| {LABEL[c]} | " + " | ".join(row) + f" | {b_hit}/{b_all} | {p_hit}/{p_all} | {i_hit}/{i_all} |")
    if "c2" in CASES:
        out.append("\n- c2 は不具合の無い差分なので、指摘の件数を書いた（少ないほど良い。中身は下の「誤った指摘・雑音」）。\n")

    # 不具合ごとの見つけた回数
    out.append("## 正解ごとの見つけた回数（見つけた回数 / 回数）\n")
    keys = []
    for case in CASES:
        any_s = next(iter(cell[(CONFIGS[0], case)]))[0]
        keys += [(case, b) for b in any_s["bugs"]]
    out.append("| 正解 | " + " | ".join(LABEL[c] for c in CONFIGS) + " |")
    out.append("|" + "---|" * (len(CONFIGS) + 1))
    for case, b in keys:
        cells = []
        for c in CONFIGS:
            n = sum(1 for s, _ in cell[(c, case)] if b in s["matched"])
            cells.append(f"{n}/{len(cell[(c, case)])}")
        out.append(f"| {case} {b} | " + " | ".join(cells) + " |")

    # 誤った指摘・雑音・費用
    out.append("\n## 誤った指摘・雑音・費用\n")
    out.append("| 設定 | 誤った指摘（おとり + 事実と違う） | おとりへの指摘 | 正解外の本当らしい指摘 | 細かい点（nit） | 重要度「高」の nit・誤り | c2 の指摘の数 | 1 回の費用 | 1 回の時間（秒） | サブエージェント |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for c in CONFIGS:
        rows = [(s, t) for (cc, _), v in cell.items() if cc == c for s, t in v]
        n = len(rows)
        if n == 0:
            continue
        false = sum(s["false"] for s, _ in rows)
        decoys = sum(len(s["decoy_hits"]) for s, _ in rows)
        real = sum(s["off_truth"]["real"] for s, _ in rows)
        nit = sum(s["off_truth"]["nit"] for s, _ in rows)
        hn = sum(s["high_noise"] for s, _ in rows)
        c2 = "・".join(str(s["findings"]) for s, _ in sorted(cell[(c, "c2")], key=lambda x: x[0]["rep"]))
        cost = sum(t["transcript"]["cost_usd"] for _, t in rows) / n
        sec = sum(t["transcript"].get("active_seconds") or 0 for _, t in rows) / n
        sub = sum(t["transcript"].get("subagents") or 0 for _, t in rows)
        out.append(f"| {LABEL[c]} | {false} | {decoys} | {real} | {nit} | {hn} | {c2} | ${cost:.2f} | {sec:.0f} | 計 {sub} |")
    out.append(f"\n- 誤った指摘・おとり・正解外・nit は、設定ごとの全試行（{len(CASES)} 題材 × 回数）の合計。費用・時間は 1 本の平均。\n")
    (RES / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
