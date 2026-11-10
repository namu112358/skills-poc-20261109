#!/usr/bin/env python3
"""W18 の系列ごとの点数（docs/poc/answer-key/W18/grading.md の「配点」）と、回を追った推移を集計する。

使い方:
  python3 scripts/poc/score_w18.py <系列ID>...      （系列 ID は <候補>-<系列>。例 baseline-1 reference-1）
    results/workflow/W18/W18r<回>-<系列ID>.json・W18h<番号>-<系列ID>.json と raw/<試行ID>/ を読み、
    results/workflow/W18/series/<系列ID>.json に書く。標準出力に 1 行の要約。
  python3 scripts/poc/score_w18.py --all
    results/workflow/W18/ にある系列をすべて集計し、results/workflow/W18/scores.json に書く。
ブラインドレビューの点は results/workflow/W18/blind/scores.json があれば使う（無ければ設計の筋は 0 点で、その旨を書く）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W18"
RAW = ROOT / "docs" / "poc" / "results" / "workflow" / "raw"


def load(trial):
    p = RESULTS / f"{trial}.json"
    return json.loads(p.read_text()) if p.exists() else None


def raw_num(trial, name, cast=float):
    p = RAW / trial / name
    try:
        return cast(p.read_text().strip())
    except (OSError, ValueError):
        return None


def cost_of(trial):
    """候補のセッションの費用（最後の result の total_cost_usd。--resume しないので回の中の最後のステップの累計）"""
    best = 0.0
    for f in sorted((RAW / trial).glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1))):
        for line in f.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result" and d.get("total_cost_usd") is not None:
                best = d["total_cost_usd"]
    return best


def questions(trial):
    p = RAW / trial / "po-questions.jsonl"
    if not p.exists():
        return {"asked": 0, "items": 0, "cost_usd": 0.0}
    recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    asked = [r for r in recs if r.get("has_questions")]
    items = [i for r in asked for i in r.get("items", [])]
    return {"asked": len(asked), "items": len(items), "before_impl": sum(1 for r in asked if r.get("before_implementation")),
            "hits": sorted({s for i in items for s in i.get("sheet_ids", []) if re.match(r"^Q\d+$", s)}),
            "previous": sum(1 for i in items if i.get("kind") == "previous"),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 4)}


def cc_version(trial):
    """その試行の Claude Code の版（最初のステップの init）"""
    f = RAW / trial / "step1.jsonl"
    if not f.exists():
        return None
    for line in f.open():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            return d.get("claude_code_version")
    return None


def interventions(trial):
    p = RAW / trial / "interventions.log"
    return len([l for l in p.read_text().splitlines() if l.strip()]) if p.exists() else None


def passed_keys(r, prefixes):
    return {k for k, v in (r.get("points", {}).get("passed") or {}).items() if v and k.split(":")[0] in prefixes}


def all_keys(r, prefixes):
    return {k for k in (r.get("points", {}).get("passed") or {}) if k.split(":")[0] in prefixes}


def rate(xs):
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def series(sid):
    rounds = {k: load(f"W18r{k}-{sid}") for k in range(1, 7)}
    hand = {h: load(f"W18{h}-{sid}") for h in ("h1", "h2", "h3")}
    out = {"series": sid, "rounds": [], "handover": {}}
    prev_pass = None
    accept, keep = [], []
    for k in range(1, 7):
        r = rounds[k]
        tid = f"W18r{k}-{sid}"
        row = {"round": k, "graded": r is not None, "cost_usd": round(cost_of(tid), 4), "seconds": raw_num(tid, "elapsed-seconds", int),
               "interventions": interventions(tid), "questions": questions(tid), "claude_code": cc_version(tid)}
        if r:
            feat = f"f{k}"
            cur = [v for key, v in r["points"]["passed"].items() if key.split(":")[0] == feat or (k == 3 and key.startswith("f3-upgrade:"))]
            row["accept"] = rate(cur)
            row["all"] = r["points"]["all"]
            now_pass = passed_keys(r, {"base", "f1", "f2", "f3", "f4", "f5", "f6", "f3-upgrade"})
            if prev_pass is not None:
                kept = prev_pass & now_pass
                row["regressed"] = sorted(prev_pass - now_pass)
                row["kept"] = round(len(kept) / len(prev_pass), 4) if prev_pass else 1.0
                keep.append(row["kept"])
            prev_pass = now_pass
            accept.append(row["accept"])
            c = r.get("checks", {})
            m = r.get("metrics", {})
            row["checks"] = {x: c.get(x) for x in ("typecheck", "test", "build", "tests_pass", "tests_fail")}
            row["metrics"] = {
                "files": m.get("files"), "lines": m.get("lines"),
                "cx_mean": m.get("complexity", {}).get("mean"), "cx_p90": m.get("complexity", {}).get("p90"),
                "cx_max": m.get("complexity", {}).get("max"), "cx_over10": m.get("complexity", {}).get("over10"),
                "dup_pct": m.get("duplication", {}).get("percentage"), "dup_clones": m.get("duplication", {}).get("clones"),
                "max_file_lines": m.get("size", {}).get("maxFileLines"), "files_over300": len(m.get("size", {}).get("filesOver300") or []),
                "max_function_lines": m.get("size", {}).get("maxFunctionLines"),
                "lint_warnings": m.get("lint", {}).get("warnings"), "lint_errors": m.get("lint", {}).get("errors"),
                "test_cases": m.get("tests", {}).get("cases"),
            }
            row["mutation"] = (r.get("mutation") or {}).get("kill_rate")
            row["migrations_rewritten"] = r.get("static", {}).get("migrations", {}).get("rewritten")
        else:
            accept.append(0.0)
            if prev_pass is not None:
                keep.append(0.0)
        out["rounds"].append(row)
    r6 = rounds[6]
    final_pass = passed_keys(r6, {"base", "f1", "f2", "f3", "f4", "f5", "f6", "f3-upgrade"}) if r6 else set()
    hpts = {}
    for h, r in hand.items():
        tid = f"W18{h}-{sid}"
        row = {"graded": r is not None, "cost_usd": round(cost_of(tid), 4), "seconds": raw_num(tid, "elapsed-seconds", int),
               "interventions": interventions(tid), "claude_code": cc_version(tid)}
        if r:
            items = [v for key, v in r["points"]["passed"].items() if key.split(":")[0] == h]
            after = passed_keys(r, {"base", "f1", "f2", "f3", "f4", "f5", "f6", "f3-upgrade"})
            row["task"] = rate(items)
            row["regressed"] = sorted(final_pass - after)
            row["kept"] = round(len(final_pass & after) / len(final_pass), 4) if final_pass else 0.0
            row["items"] = {key.split(":")[1]: v for key, v in r["points"]["passed"].items() if key.split(":")[0] == h}
            # 引き継ぎ 25 点を 3 つの課題で分ける（各 25/3 = 課題の通過率 × 20/3 + 後退の無さ × 5/3。2026-11-10 コーディネーター承認）
            hpts[h] = 20 / 3 * row["task"] + 5 / 3 * row["kept"]
        else:
            hpts[h] = 0.0
        out["handover"][h] = row
    blind = {}
    bp = RESULTS / "blind" / "scores.json"
    if bp.exists():
        blind = json.loads(bp.read_text()).get("by_series", {}).get(sid, {})
    mut = (r6.get("mutation") or {}).get("kill_rate") if r6 else None
    pts = {
        "accept": round(25 * rate(accept), 2),
        "final_all": round(20 * (r6["points"]["all"] if r6 else 0), 2),
        "no_regression": round(10 * rate(keep), 2),
        "handover": round(hpts["h1"] + hpts["h2"] + hpts["h3"], 2),
        "design": round(10 * blind["mean"] / 18, 2) if blind.get("mean") is not None else 0.0,
        "test_strength": round(10 * (mut or 0), 2),
    }
    pts["total"] = round(sum(pts.values()), 2)
    out["points"] = pts
    out["design_reviewed"] = bool(blind)
    out["dev_cost_usd"] = round(sum(r["cost_usd"] for r in out["rounds"]), 4)
    out["dev_seconds"] = sum(r["seconds"] or 0 for r in out["rounds"])
    out["maint_cost_usd"] = round(sum(h["cost_usd"] for h in out["handover"].values()), 4)
    out["maint_seconds"] = sum(h["seconds"] or 0 for h in out["handover"].values())
    return out


def summary(s):
    p = s["points"]
    rs = " ".join(f"r{r['round']}:{r.get('accept', 0):.2f}/{r.get('all', 0):.2f}" for r in s["rounds"])
    hs = " ".join(f"{h}:{v.get('task', 0):.2f}(kept {v.get('kept', 0):.2f})" for h, v in s["handover"].items())
    return (f"{s['series']:28} total {p['total']:6.2f} | accept {p['accept']} final {p['final_all']} noreg {p['no_regression']} "
            f"hand {p['handover']} design {p['design']} test {p['test_strength']} | {rs} | {hs} | dev ${s['dev_cost_usd']} {s['dev_seconds']}s "
            f"maint ${s['maint_cost_usd']} {s['maint_seconds']}s")


def main():
    args = sys.argv[1:]
    if args == ["--all"]:
        sids = sorted({re.sub(r"^W18(r[1-6]|h[123])-", "", p.stem) for p in RESULTS.glob("W18*.json")})
    else:
        sids = args
    outs = {}
    (RESULTS / "series").mkdir(parents=True, exist_ok=True)
    for sid in sids:
        s = series(sid)
        outs[sid] = s
        (RESULTS / "series" / f"{sid}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n")
        print(summary(s))
    if args == ["--all"]:
        (RESULTS / "scores.json").write_text(json.dumps(outs, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
