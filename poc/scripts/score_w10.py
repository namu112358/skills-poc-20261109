#!/usr/bin/env python3
"""W10（仕様に書かれていない落とし穴がある機能追加）の採点。grade_w10.py の結果から 100 点満点の点数を計算し、W10/scores.json に書く。

配点（poc/answer-key/W10/grading.md。PLAN.md §5.1 の W10）:
  公開の受け入れテスト 25 = acceptance.cjs の通過数 × 19/13 + 型チェック・単体テスト・ビルド 各 2
  隠しテスト 40         = hidden.cjs の通過数 × 40/12
  テストの強さ 20       = ミューテーションの検出率 × 20（src/lib/ に変更が無ければ 0）
  ブラインドレビュー 15 = W10/blind/scores.json の 2 名の合計の平均
  正解データを読んだ形跡があれば、公開の受け入れテストの E2E と隠しテストは 0
総合点 = 上の合計（品質だけ。費用・時間は two_axis.py の効率で見る）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W10"
N_ACCEPT, N_HIDDEN = 13, 12
HIDDEN_LABELS = {
    "H01": "担当者以外の申請", "H02": "本人の承認", "H03": "別タスクの申請", "H04": "本文のなりすまし",
    "H05": "実在しない日付", "H06": "壊れた入力で 500", "H07": "期限の境界", "H08": "理由の境界",
    "H09": "過去の日付", "H10": "時差（日本時間）", "H11": "判断済みの再判断", "H12": "古い申請で短縮",
}


def review(trial):
    p = DIR / "blind" / "scores.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("by_trial", {}).get(trial)


def score(t):
    tr = t["transcript"]
    w = t["w10"]
    peeked = bool(tr.get("answer_key_access"))
    checks = {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")}
    e2e_pass = 0 if peeked else sum(1 for c in t["e2e"] if c["pass"])
    hidden = {r["id"]: r["pass"] for r in w["hidden"]}
    hidden_pass = 0 if peeked else sum(1 for v in hidden.values() if v)
    acceptance = round(19 * e2e_pass / N_ACCEPT + 2 * sum(checks.values()), 1)
    hidden_pts = round(40 * hidden_pass / N_HIDDEN, 1)
    m = w["mutation"]
    strength = round(20 * m["kill_rate"], 1) if m["mutants"] else 0.0
    rv = review(t["trial"])
    review_pts = round(rv["mean"], 1) if rv else 0.0
    files = t["diff"]["files"]
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": round(acceptance + hidden_pts + strength + review_pts, 1),
        "acceptance": acceptance, "hidden": hidden_pts, "test_strength": strength, "review": review_pts,
        "hidden_items": {k: hidden.get(k, False) for k in HIDDEN_LABELS},
        "review_detail": rv,
        "facts": {
            "e2e_pass": e2e_pass, "e2e_total": len(t["e2e"]),
            "e2e_failed": [{"id": c.get("id"), "name": c["name"], "detail": c["detail"][:200]} for c in t["e2e"] if not c["pass"]],
            "hidden_pass": hidden_pass, "hidden_total": len(w["hidden"]),
            "hidden_failed": [{"id": r["id"], "detail": r["detail"][:200]} for r in w["hidden"] if not r["pass"]],
            "checks": checks,
            "mutants": m["mutants"], "killed": m["killed"], "kill_rate": m["kill_rate"],
            "mutation_files": m["files"], "baseline_tests_pass": m["baseline_tests_pass"],
            "tests_changed": w["tests_changed"],
            "interventions": t.get("interventions", 0), "questions": tr.get("questions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "budget_stopped": t.get("budget_stopped", ""),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "subagent_types": tr.get("subagent_types", {}),
            "skills_used": tr["skills_used"], "tool_calls": tr["tool_calls"],
            "denials": len(tr["permission_denials"]), "denial_list": tr["permission_denials"][:12],
            "commits": t["diff"]["commits"], "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W10-*.json"))]
    scores = [score(t) for t in trials]
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        hid = "".join("o" if v else "x" for v in s["hidden_items"].values())
        print(f"{s['trial']:30} total={s['total']:5} acc={s['acceptance']:4} hidden={s['hidden']:4} ({hid}) "
              f"strength={s['test_strength']:4} ({s['facts']['killed']}/{s['facts']['mutants']}) review={s['review']:4} "
              f"(${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s, int={s['facts']['interventions']})")


if __name__ == "__main__":
    main()
