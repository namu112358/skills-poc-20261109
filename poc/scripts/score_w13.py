#!/usr/bin/env python3
"""W13（途中で要件が変わる）の採点。grade_w13.py の結果とブラインドレビューから品質 100 点を計算し、W13/scores.json に書く。

配点は poc/answer-key/W13/grading.md（計算は grade_w13.points()）。
正解データを読んだ形跡があれば、テスト（P・K・C・マイグレーションの動かす判定）は 0。
質問（ask-po・メッセージ）は品質に入れず、別の指標として questions に書く（段階 v1 / v2 別）。
手戻りの大きさ（変更のステップの費用・時間・変更行数）を rework に書く。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIR = ROOT / "poc" / "results" / "workflow" / "W13"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
sys.path.insert(0, str(HERE))
import grade_w13  # noqa: E402


def review(trial):
    p = DIR / "blind" / "scores.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("by_trial", {}).get(trial)


def questions(trial):
    p = RAW / trial / "po-questions.jsonl"
    recs = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    items = []
    for r in recs:
        its = r.get("items") or []
        if r["route"] == "ask-po" and not its:
            its = [{"question": r["message"][:200], "kind": "other", "sheet_ids": [], "answer": r.get("reply", "")}]
        if r["route"] == "message" and not r.get("has_questions"):
            continue
        for it in its:
            items.append({**it, "route": r["route"], "phase": r.get("phase", "v1"), "before": r["before_implementation"],
                          "asked_at": r["asked_at"]})

    def stats(xs):
        n = len(xs)
        hit = [i for i in xs if any(s[:1] in "QC" for s in i["sheet_ids"])]
        ids = {s for i in xs for s in i["sheet_ids"]}
        return {
            "total": n,
            "by_route": {k: sum(1 for i in xs if i["route"] == k) for k in ("ask-po", "message")},
            "hit": len(hit), "hit_rate": round(len(hit) / n, 2) if n else None,
            "reask": sum(1 for i in xs if i["kind"] == "documented" or any(s.startswith("D") for s in i["sheet_ids"])),
            "before_impl": sum(1 for i in xs if i["before"]),
            "before_impl_rate": round(sum(1 for i in xs if i["before"]) / n, 2) if n else None,
            "q_ids": sorted((s for s in ids if s.startswith("Q")), key=lambda s: int(s[1:])),
            "c_ids": sorted((s for s in ids if s.startswith("C")), key=lambda s: int(s[1:])),
        }
    out = {"all": stats(items), "v1": stats([i for i in items if i["phase"] == "v1"]), "v2": stats([i for i in items if i["phase"] == "v2"])}
    out["asked_c11"] = "C11" in out["v2"]["c_ids"]
    out["persona_cost_usd"] = round(sum(r.get("cost_usd") or 0 for r in recs), 4)
    out["errors"] = [r["error"][:200] for r in recs if r.get("error")]
    out["items"] = [{k: i[k] for k in ("route", "phase", "kind", "sheet_ids", "before", "question", "answer")} for i in items]
    return out


def read(trial, name, cast=float, default=None):
    p = RAW / trial / name
    try:
        return cast(p.read_text().strip())
    except (OSError, ValueError):
        return default


def score(t):
    tr = t["transcript"]
    w = dict(t["w13"])
    peeked = bool(tr.get("answer_key_access"))
    if peeked:
        w = {**w, "v1_tests": [], "final_tests": [], "migration": {"checks": {k: v for k, v in w.get("migration", {}).get("checks", {}).items() if k in ("N1", "N2")}}}
    rv = review(t["trial"])
    pts = grade_w13.points(w, rv["mean"] if rv else None)
    trial = t["trial"]
    v1_cost, v1_sec = read(trial, "v1-cost"), read(trial, "v1-seconds", int)
    ivs = (RAW / trial / "interventions.log").read_text().splitlines() if (RAW / trial / "interventions.log").exists() else []
    st = w.get("static", {})
    rework = {
        "change_cost_usd": round(tr["cost_usd"] - v1_cost, 4) if v1_cost is not None else None,
        "change_seconds": t["elapsed_seconds"] - v1_sec if v1_sec is not None else None,
        "v1_cost_usd": v1_cost, "v1_seconds": v1_sec,
        "change_lines": st.get("change_lines"), "v1_lines_added": st.get("v1_lines_added"),
        "interventions_v1": sum(1 for l in ivs if "phase=v2" not in l), "interventions_v2": sum(1 for l in ivs if "phase=v2" in l),
        "v1_leftovers": (RAW / trial / "v1-leftovers").exists(),
    }
    def items(tests, ids):
        d = {x["id"]: x["pass"] for x in tests}
        return {k: d.get(k, False) for k in ids}
    mig = w.get("migration", {})
    return {
        "trial": trial, "candidate": t["candidate"], "run": t["run"],
        "total": round(pts["total"], 1), **{k: v for k, v in pts.items() if k not in ("total",)},
        "v1_items": items(w.get("v1_tests", []), ["P01", "P02"] + grade_w13.K_ITEMS),
        "final_items": items(w.get("final_tests", []), ["P02", "P03"] + grade_w13.K_ITEMS + grade_w13.C_ITEMS),
        "migration_items": {k: bool(mig.get("checks", {}).get(k)) for k in ("N1", "N2", "N3", "N4", "N5", "N6", "S1")},
        "migration_static": {k: st.get(k) for k in ("versions", "v1_rewrote_base", "final_rewrote_shipped", "final_added", "stale_status_values", "stale_hits")},
        "prod": mig.get("prod"),
        "review_detail": rv,
        "questions": questions(trial),
        "rework": rework,
        "facts": {
            "v1_checks": {k: v for k, v in w.get("v1_checks", {}).items() if k != "logs"},
            "checks": {k: v for k, v in w.get("checks", {}).items() if k != "logs"},
            "peeked": peeked, "adapters_drafted": w.get("adapters", {}).get("drafted", []),
            "failed": [{"phase": ph, "id": x["id"], "detail": x["detail"][:200]}
                       for ph, key in (("v1", "v1_tests"), ("v2", "final_tests")) for x in w.get(key, []) if not x["pass"]],
            "mutants": w.get("mutation", {}).get("mutants", 0), "killed": w.get("mutation", {}).get("killed", 0),
            "interventions": t.get("interventions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "denials": len(tr["permission_denials"]), "denial_list": tr["permission_denials"][:12],
            "commits": t["diff"]["commits"], "errors": t.get("errors", ""),
            "questions": None,
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W13-*.json"))]
    scores = [score(t) for t in trials]
    for s in scores:
        s["facts"]["questions"] = s["questions"]["all"]["total"]
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        q, rw = s["questions"], s["rework"]
        print(f"{s['trial']:34} total={s['total']:5} v1={s['v1']:5} chg={s['change']:5} keep={s['unchanged']:5} mig={s['migration']:2} "
              f"stale={s['stale']:3} design={s['design']:5} test={s['test_strength']:4} | Q v1={q['v1']['total']} v2={q['v2']['total']} "
              f"C11={q['asked_c11']} | ${s['facts']['cost_usd']} (変更 ${rw['change_cost_usd']}) {s['facts']['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
