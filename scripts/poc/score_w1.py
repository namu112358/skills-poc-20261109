#!/usr/bin/env python3
"""W1（小さな変更）の採点。grade.py の結果 JSON から 100 点満点の点数を計算する。

配点（docs/poc/PLAN.md §5.1 の W1）:
  受け入れテスト 50 = 隠しの E2E 6 件 × 5 点（30）+ 型チェック・単体テスト・ビルド（10）
                     + 規約（CLAUDE.md）: ロジック変更に単体テストを追加（5）、外部ライブラリを追加しない（5）
  所要時間・費用 30 = 費用 15 × (最安 / 自分) + 時間 15 × (最速 / 自分)  ※W1 の全試行の中で比較
  過剰さ 20      = 20 から減点
                     コードの追加行数（テスト・管理ファイル除く）41〜80 行: −4、81 行以上: −8
                     テスト以外の新規ファイル: 1 つにつき −2（最大 −4）
                     計画書・設計書などの文書や候補の管理ファイルをコミット: −4
                     依頼範囲外の変更（人の確認による。manual-review.json）: −4

--supplement: 補足の再試行（supplement/W1-*.json）を採点して supplement/scores.json に書く。
  費用・時間の基準（最安・最速）は元の試行の値に固定し（それより安い・速い場合は 15 点で頭打ち）、元の scores.json は変えない。
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W1"
SUPP = DIR / "supplement"


def load(d=DIR):
    trials = [json.loads(p.read_text()) for p in sorted(d.glob("W1-*.json"))]
    review_path = d / "manual-review.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    return trials, review


def score(t, min_cost, min_time, review):
    e2e_pass = sum(1 for c in t["e2e"] if c["pass"])
    checks = t["checks"]
    files = t["diff"]["files"]
    code_added = sum(f["added"] for f in files if f["kind"] == "code")
    test_added = sum(f["added"] for f in files if f["kind"] == "test")
    new_code_files = [p for p in t["diff"]["new_files"]
                      if not p.startswith("tests/") and not any(f["path"] == p and f["kind"] in ("doc", "tool-artifact") for f in files)]
    docs = [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")]
    out_of_scope = review.get(t["trial"], {}).get("out_of_scope", False)

    acc = {
        "e2e": e2e_pass * 5,
        "checks": round(sum(10 / 3 for k in ("typecheck", "test", "build") if checks[k]["pass"]), 1),
        "unit_test_added": 5 if test_added > 0 else 0,
        "no_new_dependency": 0 if t["diff"]["package_json_changed"] else 5,
    }
    cost = t["transcript"]["cost_usd"] or 1e-9
    eff = {
        "cost": round(min(15.0, 15 * min_cost / cost), 1),
        "time": round(min(15.0, 15 * min_time / max(t["elapsed_seconds"], 1)), 1),
    }
    deduct = {
        "code_lines": -8 if code_added > 80 else (-4 if code_added > 40 else 0),
        "new_files": -min(4, 2 * len(new_code_files)),
        "docs": -4 if docs else 0,
        "out_of_scope": -4 if out_of_scope else 0,
    }
    over = max(0, 20 + sum(deduct.values()))
    total = round(sum(acc.values()) + sum(eff.values()) + over, 1)
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": total,
        "acceptance": round(sum(acc.values()), 1), "acceptance_detail": acc,
        "efficiency": round(sum(eff.values()), 1), "efficiency_detail": eff,
        "overengineering": over, "overengineering_detail": deduct,
        "facts": {
            "e2e_pass": e2e_pass, "e2e_total": len(t["e2e"]),
            "code_added": code_added, "test_added": test_added,
            "new_code_files": new_code_files, "docs": docs,
            "cost_usd": t["transcript"]["cost_usd"], "elapsed_seconds": t["elapsed_seconds"],
            "turns": t["transcript"]["turns"], "subagents": t["transcript"]["subagents"],
            "skills_used": t["transcript"]["skills_used"],
            "denials": len(t["transcript"]["permission_denials"]),
            "commits": len(t["diff"]["commits"]),
            "out_of_scope_note": review.get(t["trial"], {}).get("note", ""),
        },
    }


def main():
    trials, review = load()
    min_cost = min(t["transcript"]["cost_usd"] for t in trials)
    min_time = min(t["elapsed_seconds"] for t in trials)
    out = DIR
    if "--supplement" in sys.argv[1:]:
        trials, review = load(SUPP)
        out = SUPP
    scores = [score(t, min_cost, min_time, review) for t in trials]
    (out / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:32} total={s['total']:5}  acc={s['acceptance']:4} eff={s['efficiency']:4} over={s['overengineering']}")


if __name__ == "__main__":
    main()
