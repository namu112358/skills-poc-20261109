#!/usr/bin/env python3
"""W4（既存コードを横断する大きな変更）の採点。grade.py の結果 JSON とブラインドレビューの結果から 100 点満点の点数を計算する。

配点（poc/PLAN.md §5.1 の W4。詳細は poc/answer-key/W4/grading.md）:
  影響箇所の網羅率 30 = コードの採点者ごとの (16 項目の合計 / 16) × 30 の平均
  受け入れテスト 30   = 隠しの E2E 26 件 × 22.5/26 + 型チェック・単体テスト・ビルド 各 2.5。正解データを読んだ形跡があれば 0
  認可の正しさ 20     = 認可プローブ 9 件 × 10/9（正解データを読んだ形跡があれば 0）+ コードの採点者ごとの A + B（0〜10）の平均
  設計案の比較 20     = 設計の採点者ごとの D1〜D4 の合計（0〜20）の平均
レビューの結果: review/code-reviewer-*.json（{記号: {"impact": {"1": 1, ...}, "authz": {"A": 5, "B": 4}, "comment": ...}}）、
               review/design-reviewer-*.json（{記号: {"design": {"D1": 3, ...}, "comment": ...}}）。記号は review/mapping.json で試行 ID に戻す。
"""
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W4"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
IMPACT_ITEMS = [str(i) for i in range(1, 17)]
AUTHZ_ITEMS = ["A", "B"]
DESIGN_ITEMS = ["D1", "D2", "D3", "D4"]
SG_MARK = re.compile(r"Security review found issues|Background security review")


def load(kind):
    """{試行 ID: [採点者ごとの結果]}"""
    rdir = DIR / "review"
    if not (rdir / "mapping.json").exists():
        return {}
    mapping = json.loads((rdir / "mapping.json").read_text())
    out = {}
    for rp in sorted(rdir.glob(f"{kind}-reviewer-*.json")):
        for code, entry in json.loads(rp.read_text()).items():
            out.setdefault(mapping[code], []).append(entry)
    return out


def gaps(trial, rs, key, items, limit):
    found = []
    for k in items:
        vals = [r[key][k] for r in rs]
        if len(vals) >= 2 and max(vals) - min(vals) >= limit:
            found.append({"trial": trial, "item": f"{key}:{k}", "scores": vals})
    return found


def security_guidance_findings(trial):
    """試行中に security-guidance が返した指摘（バックグラウンドのレビュー）の件数と冒頭"""
    hits = []
    for step in sorted((RAW / trial).glob("step*.jsonl")):
        for line in step.open():
            if SG_MARK.search(line):
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                text = json.dumps(d.get("message") or d, ensure_ascii=False)
                m = SG_MARK.search(text)
                hits.append(text[m.start():m.start() + 300] if m else "")
    return hits


BUDGET_MARK = re.compile(r"予算|budget|remaining|残額|費用の上限|コスト.{0,6}(節約|抑え)", re.I)


def budget_mentions(trial):
    """親セッションの文章のうち、打ち切り額・予算に触れたもの（1 回目の flag と 2 回目の watch の比較用）"""
    hits = []
    for step in sorted((RAW / trial).glob("step*.jsonl")):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant" or d.get("parent_tool_use_id"):
                continue
            for c in (d.get("message") or {}).get("content") or []:
                text = c.get("text", "") if c.get("type") == "text" else ""
                m = BUDGET_MARK.search(text)
                if m:
                    hits.append(text[max(0, m.start() - 80):m.end() + 80].replace("\n", " "))
    return hits


def stopped_estimate(t):
    m = re.findall(r"est=\$([0-9.]+)", t.get("budget_stopped", "") or t.get("errors", ""))
    return round(max(map(float, m)), 4) if m else 0.0


def score(t, code_reviews, design_reviews):
    e2e_pass = sum(1 for c in t["e2e"] if c["pass"])
    authz_pass = sum(1 for c in t.get("authz", []) if c["pass"])
    checks = t["checks"]
    tr = t["transcript"]
    peeked = bool(tr.get("answer_key_access"))
    acc = {
        "e2e": 0 if peeked else round(e2e_pass * 22.5 / 26, 1),
        "checks": 0 if peeked else round(sum(2.5 for k in ("typecheck", "test", "build") if checks[k]["pass"]), 1),
    }
    cr = code_reviews.get(t["trial"], [])
    dr = design_reviews.get(t["trial"], [])
    impact = round(statistics.mean(sum(r["impact"][k] for k in IMPACT_ITEMS) / 16 * 30 for r in cr), 1) if cr else 0
    authz_review = round(statistics.mean(sum(r["authz"][k] for k in AUTHZ_ITEMS) for r in cr), 1) if cr else 0
    authz_probe = 0 if peeked else round(authz_pass * 10 / 9, 1)
    design = round(statistics.mean(sum(r["design"][k] for k in DESIGN_ITEMS) for r in dr), 1) if dr else 0
    files = t["diff"]["files"]
    completed = any("poc: uncommitted leftovers" not in c for c in t["diff"]["commits"])
    total = round(impact + sum(acc.values()) + authz_probe + authz_review + design, 1)
    return {
        "trial": t["trial"], "candidate": t["candidate"], "run": t["run"],
        "total": total,
        # 2 本立ての品質（poc/scripts/two_axis.py が使う）。W4 は PLAN §5.1 の配点そのものが品質（100 点）。
        # 効率（費用・時間・介入）は two_axis.py が facts から計算する。
        "two_axis_quality": {"影響箇所の網羅率": [impact, 30], "受け入れ": [round(sum(acc.values()), 1), 30],
                             "認可の正しさ": [round(authz_probe + authz_review, 1), 20], "設計案の比較": [design, 20]},
        "budget_mode": t.get("budget_mode", ""),
        "impact": impact,
        "impact_detail": {k: round(statistics.mean(r["impact"][k] for r in cr), 2) for k in IMPACT_ITEMS} if cr else {},
        "acceptance": round(sum(acc.values()), 1), "acceptance_detail": acc,
        "authz": round(authz_probe + authz_review, 1),
        "authz_detail": {"probe": authz_probe, "review": authz_review,
                         **({k: round(statistics.mean(r["authz"][k] for r in cr), 1) for k in AUTHZ_ITEMS} if cr else {})},
        "design": design,
        "design_detail": {k: round(statistics.mean(r["design"][k] for r in dr), 1) for k in DESIGN_ITEMS} if dr else {},
        "code_comments": [r.get("comment", "") for r in cr],
        "design_comments": [r.get("comment", "") for r in dr],
        "facts": {
            "e2e_pass": e2e_pass, "e2e_total": len(t["e2e"]),
            "e2e_failed": [c["name"] for c in t["e2e"] if not c["pass"]],
            "authz_pass": authz_pass, "authz_total": len(t.get("authz", [])),
            "authz_failed": [c["name"] for c in t.get("authz", []) if not c["pass"]],
            "checks": {k: checks[k]["pass"] for k in ("typecheck", "test", "build")},
            "interventions": t.get("interventions", 0), "questions": tr.get("questions", 0), "completed": completed,
            "answer_key_access": tr.get("answer_key_access", []),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "code_deleted": sum(f["deleted"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "files_changed": sum(1 for f in files if f["kind"] in ("code", "test")),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            # 打ち切りで result が出なかった試行は、run-trial.sh の見積額（budget-stopped の est=$…）を使う
            "cost_usd": tr["cost_usd"] or stopped_estimate(t),
            "cost_estimated": not tr["cost_usd"] and bool(stopped_estimate(t)),
            "budget_stopped": t.get("budget_stopped", ""), "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"],
            "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
            "package_json_changed": t["diff"]["package_json_changed"],
            "security_guidance": security_guidance_findings(t["trial"]),
            "budget_mentions": budget_mentions(t["trial"]),
            "isolation_suspects": len(tr.get("isolation_suspects") or []),
            "errors": t.get("errors", ""),
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W4-*.json"))]
    for t in trials:
        mode = RAW / t["trial"] / "budget-mode"
        t["budget_mode"] = mode.read_text().strip() if mode.exists() else ""
    code_reviews, design_reviews = load("code"), load("design")
    scores = [score(t, code_reviews, design_reviews) for t in trials]
    review_gaps = []
    for trial, rs in code_reviews.items():
        review_gaps += gaps(trial, rs, "impact", IMPACT_ITEMS, 1) + gaps(trial, rs, "authz", AUTHZ_ITEMS, 3)
    for trial, rs in design_reviews.items():
        review_gaps += gaps(trial, rs, "design", DESIGN_ITEMS, 3)
    (DIR / "scores.json").write_text(json.dumps({"scores": scores, "review_gaps": review_gaps}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        print(f"{s['trial']:32} total={s['total']:5}  impact={s['impact']:4} acc={s['acceptance']:4} authz={s['authz']:4} "
              f"design={s['design']:4}  (${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s)")
    if review_gaps:
        print("採点者の差が大きい項目:", review_gaps)


if __name__ == "__main__":
    main()
