#!/usr/bin/env python3
"""W7（続けて行う作業での学習効果）の採点。grade_w7.py の結果 JSON から、W7a → W7b の組ごとに 100 点満点の点数を計算し、
W7/scores.json に書き出す。

配点（docs/poc/PLAN.md §5.1 の W7。詳細は docs/poc/answer-key/W7/grading.md）:
  W7b で同じ落とし穴を避けられた数 50 = P1・P2 それぞれ 25。W7b の pitfalls-1（指摘を受ける前）で判定
  W7b の所要時間の W7a 比 15         = 15 × min(1, max(0, 1.5 − W7b / W7a))
  W7b の介入回数の W7a 比 15         = W7b が 0 回なら 15、それ以外は 15 × max(0, 1 − W7b /（W7a + 1））。介入 = 「お任せします」+ 落とし穴の指摘
  W7b の受け入れテスト 20            = 20 × 合格数 / 総数
  正解データを読んだ形跡があれば、落とし穴の 50 点は 0
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W7"


def first_pitfalls(t):
    p = (t["w7"]["pitfalls"] or [{}])[0]
    return {"P1": bool(p.get("P1")), "P2": bool(p.get("P2"))}


def final_pitfalls(t):
    p = (t["w7"]["pitfalls"] or [{}])[-1]
    return {"P1": bool(p.get("P1")), "P2": bool(p.get("P2"))}


def interventions(t):
    return t.get("interventions", 0) + t.get("feedback_rounds", 0)


def e2e(t):
    return sum(1 for c in t["e2e"] if c["pass"]), len(t["e2e"])


def half_facts(t):
    tr = t["transcript"]
    files = t["diff"]["files"]
    p, n = e2e(t)
    return {
        "e2e_pass": p, "e2e_total": n, "e2e_failed": [c["name"] for c in t["e2e"] if not c["pass"]],
        "checks": {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")},
        "pitfalls_first": first_pitfalls(t), "pitfalls_final": final_pitfalls(t),
        "nudges": t.get("interventions", 0), "feedback": t.get("feedback_rounds", 0),
        "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
        "check_seconds": t["w7"].get("check_seconds", 0),
        "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
        "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
        "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
        "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
        "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
        "answer_key_access": tr.get("answer_key_access", []),
        "isolation_suspects": len(tr.get("isolation_suspects", [])),
        "budget_stopped": t.get("budget_stopped", ""),
        "errors": t.get("errors", ""),
    }


def score(a, b):
    peeked = bool(a["transcript"].get("answer_key_access") or b["transcript"].get("answer_key_access"))
    pit = first_pitfalls(b)
    pit_pts = 0 if peeked else 25 * pit["P1"] + 25 * pit["P2"]
    r = b["elapsed_seconds"] / max(1, a["elapsed_seconds"])
    time_pts = round(15 * min(1, max(0, 1.5 - r)), 1)
    ia, ib = interventions(a), interventions(b)
    int_pts = 15.0 if ib == 0 else round(15 * max(0, 1 - ib / (ia + 1)), 1)
    p, n = e2e(b)
    acc_pts = round(20 * p / n, 1) if n else 0
    return {
        "pair": f"{b['candidate']}-{b['run']}", "trial_a": a["trial"], "trial_b": b["trial"],
        "candidate": b["candidate"], "run": b["run"],
        "total": round(pit_pts + time_pts + int_pts + acc_pts, 1),
        "pitfalls": pit_pts, "time": time_pts, "interventions": int_pts, "acceptance": acc_pts,
        "time_ratio": round(r, 2), "interventions_a": ia, "interventions_b": ib,
        "a": half_facts(a), "b": half_facts(b),
        "memory": a["w7"].get("memory", {}), "memory_reads": b["w7"].get("memory_reads", []),
    }


def main():
    trials = {p.stem: json.loads(p.read_text()) for p in sorted(DIR.glob("W7[ab]-*.json"))}
    scores = []
    for tid, b in sorted(trials.items()):
        if not tid.startswith("W7b-"):
            continue
        a = trials.get("W7a-" + tid[4:])
        if a:
            scores.append(score(a, b))
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['pair']:26} total={s['total']:5} pit={s['pitfalls']:2} time={s['time']:4} (r={s['time_ratio']}) "
              f"int={s['interventions']:4} ({s['interventions_a']}→{s['interventions_b']}) acc={s['acceptance']:4} "
              f"W7a first={s['a']['pitfalls_first']} W7b first={s['b']['pitfalls_first']}")


if __name__ == "__main__":
    main()
