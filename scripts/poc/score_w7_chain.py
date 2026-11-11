#!/usr/bin/env python3
"""W7 の 5 段階（W7a〜W7e、回 21・22）と W7e の対照（回 31）の集計。W7/scores-5stages.json に書き出す。

手順は docs/poc/answer-key/W7/grading.md の「5 段階への延長」（試行前に固定）。
  品質（主表示）: 組ごとに、W7b〜W7e の各段階の（指摘前に避けた落とし穴 P1・P2 各 25 + 受け入れ 20 × 合格率）/ 70 × 100 の平均
  効率（主表示）: 各段階の費用・時間を、その段階の baseline（2 組の平均）に対する倍率で段階評価（費用 50 + 時間 30 + 介入 20）し、W7b〜W7e で平均
  学習の記録（点数に入れない）: 段階ごとの落とし穴（学習曲線）・費用・時間・ターン数、繰り返し、前の段階の知見を読んだか、W7e の対照との差
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_w7 import DIR, e2e, first_pitfalls, half_facts, interventions, tier  # noqa: E402

STAGES = ["W7a", "W7b", "W7c", "W7d", "W7e"]
SCORED = STAGES[1:]
RUNS = (21, 22)
CONTROL_RUN = 31
CANDS = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]


def load(stage, cand, run):
    p = DIR / f"{stage}-{cand}-{run}.json"
    return json.loads(p.read_text()) if p.exists() else None


def stage_quality(t):
    peeked = bool(t["transcript"].get("answer_key_access"))
    pit = first_pitfalls(t)
    pit_pts = 0 if peeked else 25 * pit["P1"] + 25 * pit["P2"]
    p, n = e2e(t)
    acc = 20 * p / n if n else 0
    return round((pit_pts + acc) / 70 * 100, 1)


def memory_names(prev_trials):
    """それより前の段階が残したもの（作業用コピーで変えた記憶になりうるファイル・専用 HOME のファイル）の名前。"""
    names = set()
    for t in prev_trials:
        mem = t["w7"].get("memory", {})
        names |= set(mem.get("in_app", []))
        names |= {Path(x).name for x in mem.get("in_home", [])
                  if Path(x).suffix in (".md", ".jsonl", ".json", ".yaml", ".yml")
                  and not (x.startswith(".claude/projects/") and "/memory/" not in x)}
    return {n for n in names if n}


def memory_used(prev_trials, t):
    names = memory_names(prev_trials)
    hits = []
    for r in t["w7"].get("memory_reads", []):
        for n in sorted(names):
            if n in r["input"]:
                hits.append({"file": n, "tool": r["tool"], "step": r["step"]})
                break
    return hits


def efficiency(f, base):
    cr = f["cost_usd"] / base["cost_usd"] if base and base["cost_usd"] else 1
    tr = f["elapsed_seconds"] / max(1, base["elapsed_seconds"]) if base else 1
    iv = f["nudges"] + f["feedback"]
    pts = 50 * tier(cr) + 30 * tier(tr) + (20 if iv == 0 else 10 if iv == 1 else 0)
    return round(pts, 1), round(cr, 2), round(tr, 2)


def main():
    chains = []
    for cand in CANDS:
        for run in RUNS:
            trials = [load(s, cand, run) for s in STAGES]
            if not all(trials):
                continue
            chains.append({"candidate": cand, "run": run, "trials": trials})
    # 段階ごとの baseline（2 組の平均）
    base = {}
    for s_i, s in enumerate(STAGES):
        bs = [half_facts(c["trials"][s_i]) for c in chains if c["candidate"] == "baseline"]
        if bs:
            base[s] = {"cost_usd": statistics.mean(b["cost_usd"] for b in bs), "elapsed_seconds": statistics.mean(b["elapsed_seconds"] for b in bs)}
    out_chains = []
    for c in chains:
        stages = []
        missed_before = set()
        for i, (s, t) in enumerate(zip(STAGES, c["trials"])):
            f = half_facts(t)
            pit = f["pitfalls_first"]
            eff, cr, tr = efficiency(f, base.get(s))
            row = {"stage": s, "trial": t["trial"], **f, "quality": stage_quality(t), "efficiency": eff, "cost_ratio": cr, "time_ratio": tr,
                   "interventions": interventions(t),
                   "repeated": sorted(p for p in missed_before if not pit[p]),
                   "learned": sorted(p for p in missed_before if pit[p]),
                   "memory": t["w7"].get("memory", {}),
                   "memory_used": memory_used(c["trials"][:i], t) if i > 0 else []}
            stages.append(row)
            missed_before |= {p for p in ("P1", "P2") if not pit[p]}
        scored = [r for r in stages if r["stage"] in SCORED]
        out_chains.append({
            "candidate": c["candidate"], "run": c["run"], "chain": f"{c['candidate']}-{c['run']}",
            "quality": round(statistics.mean(r["quality"] for r in scored), 1),
            "efficiency": round(statistics.mean(r["efficiency"] for r in scored), 1),
            "cost_total": round(sum(r["cost_usd"] for r in stages), 4),
            "elapsed_total": sum(r["elapsed_seconds"] for r in stages),
            "repeated_total": sum(len(r["repeated"]) for r in stages),
            "missed_first_total": sum(int(not r["pitfalls_first"][p]) for r in stages for p in ("P1", "P2")),
            "stages": stages,
        })
    controls = []
    for cand in CANDS:
        t = load("W7e", cand, CONTROL_RUN)
        if not t:
            continue
        f = half_facts(t)
        eff, cr, tr = efficiency(f, base.get("W7e"))
        controls.append({"candidate": cand, "run": CONTROL_RUN, "trial": t["trial"], **f, "quality": stage_quality(t),
                         "efficiency": eff, "cost_ratio": cr, "time_ratio": tr, "interventions": interventions(t),
                         "control": bool(t["w7"].get("control"))})
    result = {"stages": STAGES, "scored_stages": SCORED, "baseline_by_stage": {k: {"cost_usd": round(v["cost_usd"], 4), "elapsed_seconds": round(v["elapsed_seconds"], 1)} for k, v in base.items()},
              "chains": out_chains, "controls": controls}
    (DIR / "scores-5stages.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for c in out_chains:
        curve = " ".join(f"{r['stage'][-1]}:{'P1' if r['pitfalls_first']['P1'] else '--'}{'P2' if r['pitfalls_first']['P2'] else '--'}" for r in c["stages"])
        print(f"{c['chain']:26} quality={c['quality']:5} efficiency={c['efficiency']:5} cost=${c['cost_total']:.2f} repeated={c['repeated_total']} {curve}")
    for x in controls:
        print(f"control {x['trial']:28} quality={x['quality']} efficiency={x['efficiency']} cost=${x['cost_usd']:.2f} first={x['pitfalls_first']}")


if __name__ == "__main__":
    main()
