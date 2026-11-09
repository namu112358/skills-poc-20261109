#!/usr/bin/env python3
"""W7（続けて行う作業での学習効果）の採点。grade_w7.py の結果 JSON から、W7a → W7b の組ごとに 100 点満点の点数を計算し、
W7/scores.json に書き出す。

配点（docs/poc/PLAN.md §5.1 の W7。詳細は docs/poc/answer-key/W7/grading.md）:
  W7b で同じ落とし穴を避けられた数 50 = P1・P2 それぞれ 25。W7b の pitfalls-1（指摘を受ける前）で判定
  W7b の所要時間の W7a 比 15         = 15 × min(1, max(0, 1.5 − W7b / W7a))
  W7b の介入回数の W7a 比 15         = W7b が 0 回なら 15、それ以外は 15 × max(0, 1 − W7b /（W7a + 1））。介入 = 「お任せします」+ 落とし穴の指摘
  W7b の受け入れテスト 20            = 20 × 合格数 / 総数
  正解データを読んだ形跡があれば、落とし穴の 50 点は 0

品質と効率（2026-11-09 コーディネーターの指示。主表示。上の合計は「総合」として並記する）:
  品質（100）= （W7b の落とし穴 50 + W7b の受け入れテスト 20）/ 70 × 100
  効率（100）= 費用 50 + 時間 30 + 介入 20。W7b の費用・時間を、W7b baseline の実額・実時間に対する倍率で段階評価する
               （2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0）。
               介入（W7b の「お任せします」+ 落とし穴の指摘）0 回 = 20、1 回 = 10、2 回以上 = 0。質問は引かず、回数を参考値にする

学習の効き目を直接見る記録（点数には入れない）:
  memory_used: W7a が残したもの（作業用コピーの変更ファイル・専用 HOME のファイル）を W7b で読んだ形跡
  repeated:    W7a で指摘を受けた落とし穴を、W7b でも指摘の前に避けられなかったもの（同じ間違いの繰り返し）
  control:     前の段階を引き継がない対照（W7b を新しい作業用コピー + W7a の参照実装で実行。run-trial.sh の POC_W7_CONTROL=1）
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W7"


def first_pitfalls(t):
    p = (t["w7"]["pitfalls"] or [{}])[0]
    return {"P1": bool(p.get("P1")), "P2": bool(p.get("P2"))}


def final_pitfalls(t):
    p = (t["w7"]["pitfalls"] or [{}])[-1]
    return {"P1": bool(p.get("P1")), "P2": bool(p.get("P2"))}


def interventions(t):
    return t.get("interventions", 0) + t.get("feedback_rounds", 0)


def e2e(t):
    return sum(1 for c in t["e2e"] if c["pass"]), len(t["e2e"])


def cost(t):
    """費用。watch の上限で止めたステップの費用は result に入らないため、止めたときは見積額（budget_stopped）との大きい方を使う。"""
    c = t["transcript"]["cost_usd"]
    m = re.search(r"est=\$([0-9.]+)", t.get("budget_stopped") or "")
    return max(c, float(m.group(1))) if m else c


def half_facts(t):
    tr = t["transcript"]
    files = t["diff"]["files"]
    p, n = e2e(t)
    return {
        "e2e_pass": p, "e2e_total": n, "e2e_failed": [c["name"] for c in t["e2e"] if not c["pass"]],
        "checks": {k: t["checks"][k]["pass"] for k in ("typecheck", "test", "build")},
        "pitfalls_first": first_pitfalls(t), "pitfalls_final": final_pitfalls(t),
        "nudges": t.get("interventions", 0), "feedback": t.get("feedback_rounds", 0),
        "cost_usd": round(cost(t), 4), "cost_usd_result": tr["cost_usd"], "elapsed_seconds": t["elapsed_seconds"], "active_seconds": tr.get("active_seconds"),
        "check_seconds": t["w7"].get("check_seconds", 0),
        "turns": tr["turns"], "subagents": tr["subagents"], "skills_used": tr["skills_used"], "questions": tr.get("questions", 0),
        "denials": len(tr["permission_denials"]), "commits": len(t["diff"]["commits"]),
        "code_added": sum(f["added"] for f in files if f["kind"] == "code"),
        "test_added": sum(f["added"] for f in files if f["kind"] == "test"),
        "artifacts": [f["path"] for f in files if f["kind"] in ("doc", "tool-artifact")],
        "answer_key_access": tr.get("answer_key_access", []),
        "isolation_suspects": len(tr.get("isolation_suspects", [])),
        "budget_stopped": t.get("budget_stopped", ""),
        "errors": t.get("errors", ""),
    }


def memory_used(a, b):
    """W7a が残したもの（変更ファイル・HOME のファイル）を、W7b のツール入力が名指しした件数。"""
    mem = a["w7"].get("memory", {})
    names = set(mem.get("in_app", []))
    names |= {Path(x).name for x in mem.get("in_home", []) if Path(x).suffix in (".md", ".jsonl", ".json", ".yaml", ".yml")}
    hits = []
    for r in b["w7"].get("memory_reads", []):
        for n in names:
            if n and n in r["input"]:
                hits.append({"file": n, "tool": r["tool"], "step": r["step"]})
                break
    return hits


def score(a, b):
    peeked = bool(a["transcript"].get("answer_key_access") or b["transcript"].get("answer_key_access"))
    pit = first_pitfalls(b)
    pit_pts = 0 if peeked else 25 * pit["P1"] + 25 * pit["P2"]
    r = b["elapsed_seconds"] / max(1, a["elapsed_seconds"])
    time_pts = round(15 * min(1, max(0, 1.5 - r)), 1)
    ia, ib = interventions(a), interventions(b)
    int_pts = 15.0 if ib == 0 else round(15 * max(0, 1 - ib / (ia + 1)), 1)
    p, n = e2e(b)
    acc_pts = round(20 * p / n, 1) if n else 0
    hb = half_facts(b)
    return {
        "pair": f"{b['candidate']}-{b['run']}", "trial_a": a["trial"], "trial_b": b["trial"],
        # 2 本立ての共通部品（scripts/poc/two_axis.py）が読む形: 試行 ID と W7b の費用・時間・介入（「お任せします」+ 落とし穴の指摘）・質問
        "trial": b["trial"],
        "facts": {"cost_usd": hb["cost_usd"], "elapsed_seconds": hb["elapsed_seconds"],
                  "interventions": interventions(b), "questions": hb["questions"]},
        "candidate": b["candidate"], "run": b["run"],
        "total": round(pit_pts + time_pts + int_pts + acc_pts, 1),
        "pitfalls": pit_pts, "time": time_pts, "interventions": int_pts, "acceptance": acc_pts,
        "time_ratio": round(r, 2), "interventions_a": ia, "interventions_b": ib,
        "a": half_facts(a), "b": half_facts(b),
        "memory": a["w7"].get("memory", {}), "memory_reads": b["w7"].get("memory_reads", []),
        "memory_used": memory_used(a, b),
        "repeated": [p for p in ("P1", "P2") if not first_pitfalls(a)[p] and not first_pitfalls(b)[p]],
        "learned": [p for p in ("P1", "P2") if not first_pitfalls(a)[p] and first_pitfalls(b)[p]],
    }


def control(b):
    p, n = e2e(b)
    return {"trial": b["trial"], "candidate": b["candidate"], "run": b["run"], "b": half_facts(b),
            "pitfalls": 25 * first_pitfalls(b)["P1"] + 25 * first_pitfalls(b)["P2"],
            "acceptance": round(20 * p / n, 1) if n else 0, "interventions_b": interventions(b)}


def tier(ratio):
    for limit, rate in ((2, 1.0), (3, 0.8), (5, 0.6), (10, 0.3)):
        if ratio <= limit:
            return rate
    return 0.0


def quality_efficiency(s, base):
    s["quality"] = round((s["pitfalls"] + s["acceptance"]) / 70 * 100, 1)
    b = s["b"]
    cr = b["cost_usd"] / base["cost_usd"] if base["cost_usd"] else 1
    tr = b["elapsed_seconds"] / max(1, base["elapsed_seconds"])
    ib = s["interventions_b"]
    s["efficiency_detail"] = {"cost": round(50 * tier(cr), 1), "time": round(30 * tier(tr), 1),
                              "interventions": 20 if ib == 0 else 10 if ib == 1 else 0,
                              "cost_ratio": round(cr, 2), "time_ratio": round(tr, 2)}
    d = s["efficiency_detail"]
    s["efficiency"] = round(d["cost"] + d["time"] + d["interventions"], 1)


def main():
    trials = {p.stem: json.loads(p.read_text()) for p in sorted(DIR.glob("W7[ab]-*.json"))}
    scores, controls = [], []
    for tid, b in sorted(trials.items()):
        if not tid.startswith("W7b-"):
            continue
        if b["w7"].get("control"):
            controls.append(control(b))
            continue
        a = trials.get("W7a-" + tid[4:])
        if a:
            scores.append(score(a, b))
    # 効率の基準は baseline の W7b の平均（two_axis.py と同じ。baseline が 1 組だけのときはその値）
    bs = [s["b"] for s in scores if s["candidate"] == "baseline"]
    base = bs and {"cost_usd": sum(x["cost_usd"] for x in bs) / len(bs), "elapsed_seconds": sum(x["elapsed_seconds"] for x in bs) / len(bs)}
    if base:
        for s in scores + controls:
            s.setdefault("pitfalls", 0)
            quality_efficiency(s, base)
    (DIR / "scores.json").write_text(json.dumps({"scores": scores, "controls": controls,
                                                 "efficiency_base": base and {"cost_usd": round(base["cost_usd"], 4), "elapsed_seconds": round(base["elapsed_seconds"], 1)}},
                                                ensure_ascii=False, indent=2) + "\n")
    for c in controls:
        print(f"control {c['trial']:24} pit={c['pitfalls']} acc={c['acceptance']} time={c['b']['elapsed_seconds']}s first={c['b']['pitfalls_first']}")
    for s in scores:
        print(f"{s['pair']:26} total={s['total']:5} pit={s['pitfalls']:2} time={s['time']:4} (r={s['time_ratio']}) "
              f"int={s['interventions']:4} ({s['interventions_a']}→{s['interventions_b']}) acc={s['acceptance']:4} "
              f"W7a first={s['a']['pitfalls_first']} W7b first={s['b']['pitfalls_first']} quality={s.get('quality')} efficiency={s.get('efficiency')}")


if __name__ == "__main__":
    main()
