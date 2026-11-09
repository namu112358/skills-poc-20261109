#!/usr/bin/env python3
"""W9（レビューで不具合を見つける）の採点。grade_w9.py の結果 JSON とブラインド判定（blind/scores.json）から
100 点満点の点数を計算し、W9/scores.json に書き出す。

配点（docs/poc/answer-key/W9/grading.md）:
  再現率 40 = 40 × 一致した不具合の数 / 10
  適合率 25 = 25 × 正しい指摘 /（正しい指摘 + 誤った指摘）
  具体性 20 = 一致した不具合ごとの 0〜2 点の合計
  （上の 3 つは判定者 2 名それぞれの点数の平均。正解データを読んだ形跡があれば 0）
  費用 15   = 15 × (最安 / 自分)
品質と効率（PLAN.md §4.4）は scripts/poc/two_axis.py が QUALITY["W9"]（recall / precision / specificity）で計算する。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W9"


def score(t, min_cost, blind):
    tr = t["transcript"]
    w = t["w9"]
    b = blind.get(t["trial"]) or {}
    peeked = bool(tr.get("answer_key_access"))
    recall = 0 if peeked else b.get("recall", 0)
    precision = 0 if peeked else b.get("precision", 0)
    specificity = 0 if peeked else b.get("specificity", 0)
    cost = round(15 * min_cost / max(0.0001, tr["cost_usd"]), 1)
    files = t["diff"]["files"]
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": round(recall + precision + specificity + cost, 1),
        "recall": recall, "precision": precision, "specificity": specificity, "cost": cost,
        "blind": b,
        "facts": {
            "review_committed": w["review_committed"], "review_chars": w["review_chars"],
            "code_changed": w["code_changed"], "artifacts": w["artifacts"],
            "checks": {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")},
            "interventions": t.get("interventions", 0), "questions": tr.get("questions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "budget_stopped": t.get("budget_stopped", ""),
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "subagent_types": tr.get("subagent_types", {}),
            "skills_used": tr["skills_used"], "tool_calls": tr["tool_calls"],
            "denials": len(tr["permission_denials"]), "denial_list": tr["permission_denials"][:12],
            "commits": t["diff"]["commits"], "errors": t.get("errors", ""),
            "files": [f["path"] for f in files],
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W9-*.json"))]
    bp = DIR / "blind" / "scores.json"
    blind = json.loads(bp.read_text())["by_trial"] if bp.exists() else {}
    min_cost = min(t["transcript"]["cost_usd"] for t in trials)
    scores = [score(t, min_cost, blind) for t in trials]
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:30} total={s['total']:5} recall={s['recall']:4} precision={s['precision']:4} "
              f"spec={s['specificity']:4} cost={s['cost']:4} (${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
