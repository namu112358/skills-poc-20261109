#!/usr/bin/env python3
"""W5（バグ修正）の採点。grade_w5.py の結果 JSON から 100 点満点の点数を計算し、W5/scores.json に書き出す。

配点（poc/PLAN.md §5.1 の W5。詳細は poc/answer-key/W5/grading.md）:
  根本原因を正しく直せた数 50 = バグごとに 50/3。隠しの E2E（そのバグの番号のチェックすべて）と隠しの単体テストの両方が通ったら「直せた」
  回帰テストの追加 25        = バグごとに 25/3。参照用のコードで通り、そのバグを戻すと落ちるテストがあれば「ある」
                               （notes.json の regression_override で採点者が判断を上書きできる。理由はレポートに書く）
  既存テストの維持 10        = 10 × 元の単体テストの合格率。候補自身の npm test が失敗していれば半分
  所要時間 15                = 15 × (最短 / 自分)  ※W5 の全試行の壁時計の時間で比較
  正解データを読んだ形跡があれば、根本原因と回帰テストは 0
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W5"
BUGS = ["B1", "B2", "B3"]


def bug_status(t, b):
    e2e = [c for c in t["e2e"] if c["name"].startswith(f"[{b}]")]
    symptom = bool(e2e) and all(c["pass"] for c in e2e)
    root = t["w5"]["hidden"]["by_bug"][b]
    if symptom and root:
        return "fixed"
    if symptom:
        return "symptom-only"
    if root:
        return "lib-only"
    return "not-fixed"


def score(t, min_time, overrides):
    tr = t["transcript"]
    w = t["w5"]
    peeked = bool(tr.get("answer_key_access"))
    status = {b: bug_status(t, b) for b in BUGS}
    fixed = [b for b in BUGS if status[b] == "fixed"]
    reg = dict(w["regression"]["by_bug"])
    for b, v in (overrides.get(t["trial"]) or {}).items():
        if b in reg:
            reg[b] = bool(v["value"])
    reg_bugs = [b for b in BUGS if reg[b]]
    root_pts = 0 if peeked else round(len(fixed) * 50 / 3, 1)
    reg_pts = 0 if peeked else round(len(reg_bugs) * 25 / 3, 1)
    orig = w["original_tests"]
    ratio = orig["pass"] / orig["total"] if orig["total"] else 0
    keep = round(10 * ratio * (1 if t["checks"]["test"]["pass"] else 0.5), 1)
    time_pts = round(15 * min_time / max(1, t["elapsed_seconds"]), 1)
    files = t["diff"]["files"]
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": round(root_pts + reg_pts + keep + time_pts, 1),
        "root_cause": root_pts, "regression": reg_pts, "keep_tests": keep, "time": time_pts,
        "bugs": status, "regression_by_bug": reg,
        "facts": {
            "e2e_pass": sum(1 for c in t["e2e"] if c["pass"]), "e2e_total": len(t["e2e"]),
            "e2e_failed": [c["name"] for c in t["e2e"] if not c["pass"]],
            "checks": {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")},
            "original_tests": f"{orig['pass']}/{orig['total']}",
            "regression_files": w["regression"]["files"],
            "regression_evidence": w["regression"]["evidence"],
            "regression_ref_failures": w["regression"]["ref_failures"],
            "interventions": t.get("interventions", 0), "questions": tr.get("questions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
            "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W5-*.json"))]
    notes = json.loads((DIR / "notes.json").read_text()) if (DIR / "notes.json").exists() else {}
    overrides = notes.get("regression_override", {})
    min_time = min(t["elapsed_seconds"] for t in trials)
    scores = [score(t, min_time, overrides) for t in trials]
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:30} total={s['total']:5} root={s['root_cause']:4} reg={s['regression']:4} keep={s['keep_tests']:4} "
              f"time={s['time']:4} bugs={s['bugs']} (${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
