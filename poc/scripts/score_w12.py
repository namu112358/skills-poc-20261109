#!/usr/bin/env python3
"""W12（短い要件から、運用まで考えて作る）の採点。grade_w12.py の結果から品質 100 点を計算し、W12/scores.json に書く。

配点（poc/answer-key/W12/grading.md）:
  業務の受け入れ 30 = 公開 8（P01〜P04 各 1.25 + 型チェック・単体テスト・ビルド 各 1）+ 隠し 22（H01〜H13 × 22/13）
  DB マイグレーション 20 = M1 4・M2 4・M3 4・M4 3・M5 3・M6 2
  外部呼び出しの堅牢さ 15 = R01〜R11 × 15/11
  運用 10 = O1 3・O2 3・O3 2・O4 2
  設計の筋 15 = ブラインドレビュー（2 名の合計の平均 × 15/18）
  テストの強さ 10 = ミューテーションの検出率 × 10
  正解データを読んだ形跡があれば、公開・隠し・堅牢さのテストは 0
質問（ask-po・メッセージ）は品質に入れず、別の指標として questions に書く。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W12"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
M_WEIGHTS = {"M1": 4, "M2": 4, "M3": 4, "M4": 3, "M5": 3, "M6": 2}
N_HIDDEN, N_ROBUST = 13, 11
HIDDEN_LABELS = {
    "H01": "3 段階・既存は B", "H02": "重要度で絞り込み", "H03": "期限は月末", "H04": "30 日前から", "H05": "日本時間",
    "H06": "A だけ", "H07": "校正中などは除く", "H08": "借りている人にも", "H09": "1 期限 1 回", "H10": "期限が変われば再通知",
    "H11": "期限切れを 1 回", "H12": "無効なら部署の代表者", "H13": "cron から API",
}
ROBUST_LABELS = {
    "R01": "503 で再試行", "R02": "指数バックオフ", "R03": "Retry-After", "R04": "回数の上限", "R05": "400 は再試行しない",
    "R06": "タイムアウト", "R07": "二重に届けない", "R08": "次の実行で送り直す", "R09": "1 件の失敗で止まらない",
    "R10": "通知の失敗で保存が壊れない", "R11": "Idempotency-Key",
}
M_LABELS = {"M1": "新しいマイグレーションを末尾に追加", "M2": "既存のマイグレーションを書き換えない", "M3": "旧 DB で起動しデータが残る",
            "M4": "既存の行に重要度（B）が入る", "M5": "重要度が自分の列に保存され再起動後も残る", "M6": "2 回起動しても壊れない"}
Q_IDS = [f"Q{i}" for i in range(1, 14)]
O_IDS = [f"O{i}" for i in range(1, 7)]


def models_used(trial):
    """トランスクリプトの最後の result の modelUsage（セッションの累計）から、実際に使われたモデルと費用を返す。"""
    last = None
    for f in (RAW / trial).glob("step*.jsonl"):
        n = int(f.stem[4:])
        for line in f.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result" and d.get("modelUsage") and (last is None or n >= last[0]):
                last = (n, d["modelUsage"])
    if not last:
        return {}
    return {m: round(u.get("costUSD", 0.0), 4) for m, u in last[1].items()}


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
            items.append({**it, "route": r["route"], "before": r["before_implementation"], "asked_at": r["asked_at"]})
    hit = [i for i in items if any(s[:1] in "QO" for s in i["sheet_ids"])]
    reask = [i for i in items if i["kind"] == "documented" or any(s.startswith("D") for s in i["sheet_ids"])]
    ids = {s for i in items for s in i["sheet_ids"]}
    n = len(items)
    return {
        "total": n,
        "by_route": {k: sum(1 for i in items if i["route"] == k) for k in ("ask-po", "message")},
        "ask_po_calls": sum(1 for r in recs if r["route"] == "ask-po"),
        "message_rounds": sum(1 for r in recs if r["route"] == "message" and r.get("has_questions")),
        "hit": len(hit), "hit_rate": round(len(hit) / n, 2) if n else None,
        "reask": len(reask),
        "before_impl": sum(1 for i in items if i["before"]), "before_impl_rate": round(sum(1 for i in items if i["before"]) / n, 2) if n else None,
        "q_ids": sorted((s for s in ids if s.startswith("Q")), key=lambda s: int(s[1:])),
        "o_ids": sorted((s for s in ids if s.startswith("O")), key=lambda s: int(s[1:])),
        "d_ids": sorted(s for s in ids if s.startswith("D")),
        "kinds": {k: sum(1 for i in items if i["kind"] == k) for k in ("requirement", "operations", "documented", "confirmation", "other")},
        "persona_cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 4),
        "errors": [r["error"][:200] for r in recs if r.get("error")],
        "items": [{k: i[k] for k in ("route", "kind", "sheet_ids", "before", "question", "answer")} for i in items],
    }


def score(t):
    tr = t["transcript"]
    w = t["w12"]
    peeked = bool(tr.get("answer_key_access"))
    checks = w["checks"]
    pub = {r["id"]: r["pass"] for r in w.get("public", [])}
    hid = {r["id"]: r["pass"] for r in w.get("hidden", [])}
    rob = {r["id"]: r["pass"] for r in w.get("robust", [])}
    if peeked:
        pub = {k: False for k in pub}; hid = {k: False for k in hid}; rob = {k: False for k in rob}
    public_pts = round(1.25 * sum(pub.get(k, False) for k in ("P01", "P02", "P03", "P04")) + sum(1 for v in checks.values() if v), 2)
    hidden_pts = round(22 * sum(hid.get(k, False) for k in HIDDEN_LABELS) / N_HIDDEN, 2)
    mc = w.get("migration", {}).get("checks", {})
    migration = sum(v for k, v in M_WEIGHTS.items() if mc.get(k))
    robustness = round(15 * sum(rob.get(k, False) for k in ROBUST_LABELS) / N_ROBUST, 2)
    # 感度の確認用: 旧版（v1）の堅牢さのテストの結果で計算した場合（点数には使わない）
    rob1 = {r["id"]: r["pass"] and not peeked for r in w.get("robust_v1", [])}
    robustness_v1 = round(15 * sum(rob1.get(k, False) for k in ROBUST_LABELS) / N_ROBUST, 2) if rob1 else None
    ops = w.get("ops", {}).get("total", 0)
    m = w.get("mutation", {})
    strength = round(10 * m.get("kill_rate", 0), 2) if m.get("mutants") else 0.0
    rv = review(t["trial"])
    design = round(rv["mean"] * 15 / 18, 2) if rv else 0.0
    business = round(public_pts + hidden_pts, 2)
    files = t["diff"]["files"]
    # 汎用の開発標準を CLAUDE.md に足した試行（POC_STANDARD=generic、回の番号 11・12）は、別の条件「<候補>+std」として扱う
    standard = (RAW / t["trial"] / "standard").exists()
    # Haiku の追加条件（試行する側のモデルだけを変える。回の番号 21・22）と、乱れた初期状態の追加条件（回の番号 31・32）
    model = (RAW / t["trial"] / "model").read_text().strip() if (RAW / t["trial"] / "model").exists() else "claude-sonnet-5-5"
    messy = (RAW / t["trial"] / "base-variant").exists()
    cond = t["candidate"] + ("+std" if standard else "") + ("@haiku" if "haiku" in model else "") + ("+messy" if messy else "")
    return {
        "trial": t["trial"], "candidate": cond, "base_candidate": t["candidate"],
        "standard": standard, "model": model, "messy": messy, "models_used": models_used(t["trial"]), "run": t["run"],
        "total": round(business + migration + robustness + ops + design + strength, 1),
        "business": business, "business_public": public_pts, "business_hidden": hidden_pts,
        "migration": migration, "robustness": robustness, "robustness_v1": robustness_v1,
        "robust_v1_items": {k: rob1.get(k, False) for k in ROBUST_LABELS} if rob1 else None, "ops": ops, "design": design, "test_strength": strength,
        "hidden_items": {k: hid.get(k, False) for k in HIDDEN_LABELS},
        "public_items": {k: pub.get(k, False) for k in ("P01", "P02", "P03", "P04")},
        "robust_items": {k: rob.get(k, False) for k in ROBUST_LABELS},
        "migration_items": {k: bool(mc.get(k)) for k in M_WEIGHTS},
        "escape": w.get("migration", {}).get("escape", {}),
        "ops_detail": {k: v for k, v in w.get("ops", {}).items() if k != "facts"},
        "ops_facts": w.get("ops", {}).get("facts", {}),
        "adapter": w.get("adapter", {}),
        "review_detail": rv,
        "questions": questions(t["trial"]),
        "facts": {
            "checks": checks, "peeked": peeked,
            "public_failed": [{"id": r["id"], "detail": r["detail"][:200]} for r in w.get("public", []) if not r["pass"]],
            "hidden_failed": [{"id": r["id"], "detail": r["detail"][:200]} for r in w.get("hidden", []) if not r["pass"]],
            "robust_failed": [{"id": r["id"], "detail": r["detail"][:200]} for r in w.get("robust", []) if not r["pass"]],
            "mutants": m.get("mutants", 0), "killed": m.get("killed", 0), "kill_rate": m.get("kill_rate", 0.0),
            "static": {k: w.get("static", {}).get(k) for k in ("inProcessScheduler", "console_lines", "logger_used", "env_names", "hardcoded_urls", "new_deps")},
            "migrations_static": w.get("static", {}).get("migrations"),
            "interventions": t.get("interventions", 0),
            "answer_key_access": tr.get("answer_key_access", []),
            "isolation_suspects": len(tr.get("isolation_suspects", [])),
            "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
            "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
            "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
            "cost_usd": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
            "turns": tr["turns"], "subagents": tr["subagents"], "subagent_types": tr.get("subagent_types", {}),
            "skills_used": tr["skills_used"], "tool_calls": tr["tool_calls"],
            "denials": len(tr["permission_denials"]), "denial_list": tr["permission_denials"][:12],
            "commits": t["diff"]["commits"], "errors": t.get("errors", ""),
            # 効率の表示用（two_axis.py は facts.questions を参考値として出す）
            "questions": None,
        },
    }


def main():
    trials = [json.loads(p.read_text()) for p in sorted(DIR.glob("W12-*.json"))]
    trials = [t for t in trials if "w12" in t]  # 採点の途中（grade.py の分だけ書かれたもの）は除く
    scores = [score(t) for t in trials]
    for s in scores:
        s["facts"]["questions"] = s["questions"]["total"]
        s["total_v1"] = None if s["robustness_v1"] is None else round(s["total"] - s["robustness"] + s["robustness_v1"], 1)
    (DIR / "scores.json").write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n")
    for s in scores:
        q = s["questions"]
        print(f"{s['trial']:34} total={s['total']:5} biz={s['business']:5} mig={s['migration']:2} rob={s['robustness']:5} ops={s['ops']:4} "
              f"design={s['design']:5} test={s['test_strength']:5} | Q={q['total']} hit={q['hit_rate']} pre={q['before_impl_rate']} "
              f"(${s['facts']['cost_usd']}, {s['facts']['elapsed_seconds']}s, int={s['facts']['interventions']})")


if __name__ == "__main__":
    main()
