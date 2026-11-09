#!/usr/bin/env python3
"""W6（UI 実装からブラウザ検証・PR 作成まで）の採点。grade_w6.py の結果 JSON から 100 点満点の点数を計算し、W6/scores.json に書き出す。

配点（docs/poc/PLAN.md §5.1 の W6。詳細は docs/poc/answer-key/W6/grading.md）:
  UI チェックリスト 40 = 不具合の残っていない項目（[U1]〜[U8] のチェックがすべて通過）1 つにつき 5 点
  検証の証跡 15        = E1（ブラウザで /my-tasks を開いた 3 + 操作した 2）+ E2（画像をコミット 5 / 撮影のみ 3）+ E3（幅 480px 以下 5）
                         （notes.json の evidence_override で採点者が直せる。理由はレポートに書く）
  PR の完成度 30       = PR の説明 12（blind/scores.json の 2 名の平均。PR.md が無ければ 0）
                         + テスト 8（tests/ の追加・変更あり・npm test 通過 8 / 失敗 3 / なし 0）+ CI 10（型チェック・単体テスト・ビルド 各 10/3）
  費用 15              = 15 × (最安 / 自分)
  正解データを読んだ形跡があれば、UI チェックリストは 0

品質と効率（2026-11-09 コーディネーター経由のユーザー指示。レポートの主表示）:
  品質 100 = (UI チェックリスト + 検証の証跡 + PR の完成度) / 85 × 100
  効率 100 = 費用 50 + 時間 30 + 介入 20。費用・時間は W6 baseline の実額・実時間に対する倍率の段階で
             2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。
             介入 0 回 = 20、1 回 = 10、2 回以上 = 0。質問は引かず、回数を参考値として表示する。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W6"
ITEMS = [f"U{i}" for i in range(1, 9)]
ITEM_LABELS = {
    "U1": "表示内容と並び順", "U2": "空状態", "U3": "追加と二重送信の防止", "U4": "入力エラー",
    "U5": "通信・サーバーエラー", "U6": "ステータスの変更", "U7": "レスポンシブ", "U8": "導線・ラベル",
}


def item_status(t):
    out = {}
    for u in ITEMS:
        rows = [c for c in t["e2e"] if c["name"].startswith(f"[{u}]")]
        out[u] = bool(rows) and all(c["pass"] for c in rows)
    return out


def pr_review(trial):
    p = DIR / "blind" / "scores.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data.get("by_trial", {}).get(trial)


def tier(ratio):
    for limit, frac in ((2, 1.0), (3, 0.8), (5, 0.6), (10, 0.3)):
        if ratio <= limit:
            return frac
    return 0.0


def score(t, min_cost, overrides, base):
    tr = t["transcript"]
    w = t["w6"]
    peeked = bool(tr.get("answer_key_access"))
    items = item_status(t)
    ui = 0 if peeked else 5 * sum(items.values())
    ev = dict(w["evidence"]["points"])
    for k, v in (overrides.get(t["trial"]) or {}).items():
        if k in ev:
            ev[k] = v["value"]
    evidence = sum(ev.values())
    review = pr_review(t["trial"])
    has_pr = bool(w["pr"]["pr_md"].strip())
    desc = round(review["mean"], 1) if (review and has_pr) else 0.0
    checks = {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")}
    tests = 0 if not w["pr"]["tests_changed"] else (8 if checks["test"] else 3)
    ci = round(10 / 3 * sum(checks.values()), 1)
    pr = round(desc + tests + ci, 1)
    cost = round(15 * min_cost / max(0.0001, tr["cost_usd"]), 1)
    files = t["diff"]["files"]
    quality = round((ui + evidence + pr) / 85 * 100, 1)
    cost_ratio = tr["cost_usd"] / base["cost"]
    time_ratio = t["elapsed_seconds"] / base["time"]
    n_int = t.get("interventions", 0)
    eff = {"cost": round(50 * tier(cost_ratio), 1), "time": round(30 * tier(time_ratio), 1),
           "interventions": 20 if n_int == 0 else (10 if n_int == 1 else 0),
           "cost_ratio": round(cost_ratio, 2), "time_ratio": round(time_ratio, 2)}
    efficiency = round(eff["cost"] + eff["time"] + eff["interventions"], 1)
    return {
        "quality": quality, "efficiency": efficiency, "efficiency_parts": eff,
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": round(ui + evidence + pr + cost, 1),
        "ui": ui, "evidence": evidence, "pr": pr, "cost": cost,
        "items": items, "evidence_points": ev,
        "pr_parts": {"description": desc, "tests": tests, "ci": ci, "review": review},
        "facts": {
            "e2e_pass": sum(1 for c in t["e2e"] if c["pass"]), "e2e_total": len(t["e2e"]),
            "e2e_failed": [{"name": c["name"], "detail": c["detail"][:200]} for c in t["e2e"] if not c["pass"]],
            "checks": checks,
            "pr_md": has_pr, "pr_md_by_candidate": w["pr"]["pr_md_committed_by_candidate"],
            "tests_changed": w["pr"]["tests_changed"],
            "push_or_gh_attempts": w["pr"]["push_or_gh_attempts"], "push_or_gh_denied": w["pr"]["push_or_gh_denied"],
            "browser_calls": w["evidence"]["browser_calls"], "committed_images": w["evidence"]["committed_images"],
            "screenshot_taken": w["evidence"]["screenshot_taken"], "narrow_viewport": w["evidence"]["narrow_viewport"],
            "interventions": t.get("interventions", 0), "questions": tr.get("questions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "budget_stopped": t.get("budget_stopped", ""),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "tool_calls": tr["tool_calls"],
            "denials": len(tr["permission_denials"]), "denial_list": tr["permission_denials"][:12],
            "commits": t["diff"]["commits"], "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W6-*.json"))]
    notes = json.loads((DIR / "notes.json").read_text()) if (DIR / "notes.json").exists() else {}
    overrides = notes.get("evidence_override", {})
    min_cost = min(t["transcript"]["cost_usd"] for t in trials)
    b = next(t for t in trials if t["candidate"] == "baseline")
    base = {"cost": b["transcript"]["cost_usd"], "time": b["elapsed_seconds"]}
    scores = [score(t, min_cost, overrides, base) for t in trials]
    (DIR / "scores.json").write_text(json.dumps({"baseline": base, "scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:30} Q={s['quality']:5} E={s['efficiency']:5} total={s['total']:5} ui={s['ui']:3} ev={s['evidence']:3} pr={s['pr']:5} cost={s['cost']:4} "
              f"items={''.join('o' if v else 'x' for v in s['items'].values())} (${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
