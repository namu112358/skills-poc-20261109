#!/usr/bin/env python3
"""W3（曖昧な要望から要件を固める）の採点。grade_w3.py の結果 JSON と採点者の判定から 100 点満点の点数を計算する。

配点（docs/poc/PLAN.md §5.1 の W3。詳細は docs/poc/answer-key/W3/grading.md）:
  隠れ要件の引き出し 40 = H1〜H10 × 0/2/4 点。採点者 2 名の平均。正解データを読んだ形跡があれば 0
  要件文書の質 25      = Q1〜Q5 × 0〜5 点。採点者 2 名の平均
  スコープ判断 20      = SC1〜SC4 × 0〜5 点。採点者 2 名の平均。アプリのコードを変更していたら SC4 = 0
  質問の負担 15        = 15 − max(0, 質問数 − 12) − 2 × 重複数（0 未満にしない）
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W3"
HIDDEN = [f"H{i}" for i in range(1, 11)]
QUALITY = [f"Q{i}" for i in range(1, 6)]
SCOPE = [f"SC{i}" for i in range(1, 5)]


def load_reviews():
    rdir = DIR / "review"
    if not (rdir / "mapping.json").exists():
        return {}, []
    mapping = json.loads((rdir / "mapping.json").read_text())
    out, gaps = {}, []
    for rp in sorted(rdir.glob("reviewer-*.json")):
        for code, entry in json.loads(rp.read_text()).items():
            out.setdefault(mapping[code], []).append(entry)
    for trial, rs in out.items():
        if len(rs) < 2:
            continue
        for group, keys, limit in (("hidden", HIDDEN, 4), ("quality", QUALITY, 3), ("scope", SCOPE, 3)):
            for k in keys:
                vals = [r[group][k] for r in rs]
                if max(vals) - min(vals) >= limit:
                    gaps.append({"trial": trial, "item": k, "scores": vals})
    return out, gaps


def score(t, reviews):
    rs = reviews.get(t["trial"], [])
    tr = t["transcript"]
    peeked = bool(tr.get("answer_key_access"))
    code_changed = bool(t["code_changed"])

    def avg(group, keys, fix=None):
        if not rs:
            return 0, {}
        detail = {}
        for k in keys:
            vals = [r[group][k] for r in rs]
            detail[k] = round(statistics.mean(vals), 1)
        if fix:
            detail.update(fix)
        return round(sum(detail.values()), 1), detail

    hidden, hidden_d = avg("hidden", HIDDEN)
    if peeked:
        hidden = 0
    quality, quality_d = avg("quality", QUALITY)
    scope, scope_d = avg("scope", SCOPE, {"SC4": 0} if code_changed else None)
    qa = t["qa"]
    nq, nd = qa["questions"], len(qa["duplicates"])
    burden = max(0, 15 - max(0, nq - 12) - 2 * nd)
    total = round(hidden + quality + scope + burden, 1)
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"], "total": total,
        "hidden": hidden, "hidden_detail": hidden_d,
        "quality": quality, "quality_detail": quality_d,
        "scope": scope, "scope_detail": scope_d,
        "burden": burden,
        "comments": [r.get("comment", "") for r in rs],
        "facts": {
            "questions": nq, "duplicates": nd, "rounds": qa["rounds"], "by_kind": qa["by_kind"],
            "elicited_ids": qa["elicited_ids"], "closed_by_limit": qa["closed_by_limit"],
            "doc_source": t["doc_source"], "doc_lines": t["doc_lines"], "code_changed": t["code_changed"],
            "interventions": t["interventions"], "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": tr.get("isolation_suspects", []),
            "cost_usd": tr["cost_usd"], "answerer_cost_usd": qa["answerer_cost_usd"],
            "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
            "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W3-*.json"))]
    reviews, gaps = load_reviews()
    scores = [score(t, reviews) for t in trials]
    (DIR / "scores.json").write_text(json.dumps({"scores": scores, "review_gaps": gaps}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        f = s["facts"]
        print(f"{s['trial']:32} total={s['total']:5}  hid={s['hidden']:4} qual={s['quality']:4} scope={s['scope']:4} "
              f"burden={s['burden']:2}  (q={f['questions']} dup={f['duplicates']} ${f['cost_usd']}, {f['elapsed_seconds']}s)")
    if gaps:
        print("採点者の差が大きい項目:", gaps)


if __name__ == "__main__":
    main()
