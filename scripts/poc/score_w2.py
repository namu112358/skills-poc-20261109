#!/usr/bin/env python3
"""W2（仕様が明確な機能追加）の採点。grade.py の結果 JSON とブラインドレビューの結果から 100 点満点の点数を計算する。

配点（docs/poc/PLAN.md §5.1 の W2。詳細は docs/poc/answer-key/W2/grading.md）:
  受け入れテスト 40 = 隠しの E2E 16 件 × 1.875（30）+ 型チェック・単体テスト・ビルド（10）
                     正解データを読んだ形跡があれば 0
  介入回数 20      = 20 − 5 ×（介入回数 + AskUserQuestion の回数）。最後までコミットが無ければ 0
  設計・テストの質 25 = ブラインドレビュー（review/reviewer-*.json）。採点者ごとの 5 項目合計（0〜25）の平均
  費用 15          = 15 × (最安 / 自分)  ※W2 の全試行の中で比較

--supplement: 補足の再試行（supplement/W2-*.json、ブラインドレビューは supplement/review/）を採点して supplement/scores.json に書く。
  費用の基準（最安）は元の試行の値に固定し（それより安い場合は 15 点で頭打ち）、元の scores.json は変えない。
"""
import sys
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W2"
SUPP = DIR / "supplement"
ITEMS = ["conventions", "design", "security", "tests", "scope"]


def load_reviews(d=DIR):
    """{試行 ID: [採点者ごとの {項目: 点}]}。review/mapping.json で記号を試行 ID に戻す。"""
    rdir = d / "review"
    if not (rdir / "mapping.json").exists():
        return {}, []
    mapping = json.loads((rdir / "mapping.json").read_text())  # {記号: 試行 ID}
    out, gaps = {}, []
    reviewers = sorted(rdir.glob("reviewer-*.json"))
    for rp in reviewers:
        data = json.loads(rp.read_text())
        for code, entry in data.items():
            out.setdefault(mapping[code], []).append({k: entry["scores"][k] for k in ITEMS} | {"_comment": entry.get("comment", "")})
    for trial, rs in out.items():
        if len(rs) >= 2:
            for k in ITEMS:
                vals = [r[k] for r in rs]
                if max(vals) - min(vals) >= 3:
                    gaps.append({"trial": trial, "item": k, "scores": vals})
    return out, gaps


def score(t, min_cost, reviews):
    e2e_pass = sum(1 for c in t["e2e"] if c["pass"])
    checks = t["checks"]
    tr = t["transcript"]
    peeked = bool(tr.get("answer_key_access"))
    acc = {
        "e2e": 0 if peeked else round(e2e_pass * 30 / 16, 1),
        "checks": 0 if peeked else round(sum(10 / 3 for k in ("typecheck", "test", "build") if checks[k]["pass"]), 1),
    }
    nudges = t.get("interventions", 0)
    questions = tr.get("questions", 0)
    # 候補自身のコミットがあるか（run-trial.sh が最後に残りを拾う "poc: uncommitted leftovers" は数えない）
    completed = any("poc: uncommitted leftovers" not in c for c in t["diff"]["commits"])
    intervention = 0 if not completed else max(0, 20 - 5 * (nudges + questions))
    rs = reviews.get(t["trial"], [])
    per_reviewer = [sum(r[k] for k in ITEMS) for r in rs]
    quality = round(statistics.mean(per_reviewer), 1) if per_reviewer else 0
    cost = tr["cost_usd"] or 1e-9
    eff = round(min(15.0, 15 * min_cost / cost), 1)
    files = t["diff"]["files"]
    total = round(sum(acc.values()) + intervention + quality + eff, 1)
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": total,
        "acceptance": round(sum(acc.values()), 1), "acceptance_detail": acc,
        "intervention": intervention,
        "quality": quality,
        "quality_detail": {k: round(statistics.mean(r[k] for r in rs), 1) for k in ITEMS} if rs else {},
        "quality_comments": [r["_comment"] for r in rs],
        "cost": eff,
        "facts": {
            "e2e_pass": e2e_pass, "e2e_total": len(t["e2e"]),
            "e2e_failed": [c["name"] for c in t["e2e"] if not c["pass"]],
            "checks": {k: checks[k]["pass"] for k in ("typecheck", "test", "build")},
            "interventions": nudges, "questions": questions, "completed": completed,
            "answer_key_access": tr.get("answer_key_access", []),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
            "package_json_changed": t["diff"]["package_json_changed"],
            "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W2-*.json"))]
    reviews, gaps = load_reviews()
    min_cost = min(t["transcript"]["cost_usd"] for t in trials)
    out = DIR
    if "--supplement" in sys.argv[1:]:
        trials = [json.loads(p.read_text()) for p in sorted(SUPP.glob("W2-*.json"))]
        reviews, gaps = load_reviews(SUPP)
        out = SUPP
    scores = [score(t, min_cost, reviews) for t in trials]
    (out / "scores.json").write_text(json.dumps({"scores": scores, "review_gaps": gaps}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:32} total={s['total']:5}  acc={s['acceptance']:4} int={s['intervention']:2} "
              f"qual={s['quality']:4} cost={s['cost']:4}  (${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s)")
    if gaps:
        print("採点者の差が 3 点以上:", gaps)


if __name__ == "__main__":
    main()
