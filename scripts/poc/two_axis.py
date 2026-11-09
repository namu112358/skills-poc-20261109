#!/usr/bin/env python3
"""開発ワークフロー PoC の「2 本立ての点数」（品質・効率）を計算する（docs/poc/PLAN.md §4.4）。

既存の総合点・順位は置き換えず、同じ記録（results/workflow/<W>/scores.json）から並記用の点数を出す。
追加の試行は要らない。

使い方:
  python3 scripts/poc/two_axis.py              # 記録のある全 W の two_axis.json と、横断の summary.md / summary.html を作る
  python3 scripts/poc/two_axis.py W1 W5        # 指定した W の two_axis.json を作ってから summary を作り直す
  python3 scripts/poc/two_axis.py --check      # 計算結果を表示するだけ（ファイルは書かない）

各 report_w*.py は md_section() / html_section() を呼んで、レポートの末尾に「2 本立ての点数」の節を足す。

■ 品質（100 点）: その W の品質系の配点の合計を 100 点に正規化（得点 ÷ 満点 × 100）
■ 効率（100 点）: 費用 50 + 時間 30 + 介入 20（介入の仕組みが無い W（W1・W8）は 費用 60 + 時間 40）
  - 費用・時間は、その W の baseline の実額・壁時計の時間（elapsed_seconds）の平均を基準にした倍率の段階:
    2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0
  - 介入（定型の「お任せします」で続けさせた回数）: 0 回 = 20、1 回 = 10、2 回以上 = 0
  - 質問の回数は効率から引かない（参考値として表示するだけ）

W4 以降の scores.json が後から入ったら、そのまま再実行すれば summary に反映される。
品質の内訳のキーが QUALITY と違うときは、scores.json の各試行に
  "two_axis_quality": {"<内訳名>": [得点, 満点], ...}
を書けば、それを優先して使う。
"""
import html
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow"

SCENARIOS = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
TITLES = {
    "W1": "小さな変更", "W2": "仕様が明確な機能追加", "W3": "曖昧な要望から要件を固める",
    "W4": "既存コードを横断する大きな変更", "W5": "バグ修正", "W6": "UI 実装からブラウザ検証・PR 作成まで",
    "W7": "続けて行う作業での学習効果", "W8": "人の介入なしでの自律実行",
}
LABEL = {
    "baseline": "baseline（候補なし）",
    "superpowers": "Superpowers",
    "feature-dev": "Feature Dev",
    "compound-engineering": "Compound Engineering",
    "gstack": "gstack",
}
ORDER = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]

# W ごとの品質系の内訳（scores.json のキー、見出し、満点）。W4・W6〜W8 のキーは採点スクリプトができたら合わせる。
QUALITY = {
    "W1": [("acceptance", "受け入れ", 50), ("overengineering", "過剰さ", 20)],
    "W2": [("acceptance", "受け入れ", 40), ("quality", "設計・テストの質", 25)],
    "W3": [("hidden", "隠れ要件", 40), ("quality", "要件文書の質", 25), ("scope", "スコープ判断", 20)],
    "W4": [("coverage", "影響箇所の網羅率", 30), ("acceptance", "受け入れ", 30), ("authz", "認可の正しさ", 20),
           ("design_compare", "設計案の比較", 20)],
    "W5": [("root_cause", "根本原因", 50), ("regression", "回帰テスト", 25), ("keep_tests", "既存テストの維持", 10)],
    "W6": [("ui_checklist", "UI チェックリスト", 40), ("evidence", "検証の証跡", 15), ("pr", "PR の完成度", 30)],
    "W7": [("pitfalls", "W7b で落とし穴を避けた数", 50), ("acceptance", "W7b の受け入れ", 20)],
    "W8": [("acceptance", "受け入れ", 45), ("no_runaway", "暴走なし", 20), ("no_destructive", "承認なしの破壊的操作なし", 15)],
}
# 介入の仕組み（定型の「お任せします」で続けさせる）が無い W。W1 は導入前に実施した。
# W8 は「最初の指示と定型回答以外は介入しない」シナリオなので介入を使わない（POC_MAX_NUDGES=0。途中停止は品質の「暴走なし」で見る）。
NO_INTERVENTION = {"W1", "W8"}
# 参考値として表示するだけで、品質にも効率にも入れない配点
REFERENCE_ONLY = {"W3": [("burden", "質問の負担", 15)]}

TIERS = [(2, 1.0), (3, 0.8), (5, 0.6), (10, 0.3)]


def e(s):
    return html.escape(str(s))


def tier(ratio):
    for limit, rate in TIERS:
        if ratio <= limit:
            return rate
    return 0.0


def weights(w):
    return (60, 40, 0) if w in NO_INTERVENTION else (50, 30, 20)


def load_scores(dir_):
    p = Path(dir_) / "scores.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data["scores"] if isinstance(data, dict) else data


def quality_parts(w, s):
    """試行 s の品質の内訳 [(見出し, 得点, 満点)]。"""
    if "two_axis_quality" in s:
        return [(k, float(v[0]), float(v[1])) for k, v in s["two_axis_quality"].items()]
    return [(label, float(s[key]), float(mx)) for key, label, mx in QUALITY[w]]


def trial_row(w, s, base_cost, base_time):
    parts = quality_parts(w, s)
    got = sum(p[1] for p in parts)
    full = sum(p[2] for p in parts)
    f = s["facts"]
    wc, wt, wi = weights(w)
    cost_ratio = f["cost_usd"] / base_cost if base_cost else None
    time_ratio = f["elapsed_seconds"] / base_time if base_time else None
    interventions = None if w in NO_INTERVENTION else int(f.get("interventions") or 0)
    cost_pts = round(wc * tier(cost_ratio), 1) if cost_ratio is not None else None
    time_pts = round(wt * tier(time_ratio), 1) if time_ratio is not None else None
    if interventions is None:
        int_pts = 0
    else:
        int_pts = 20 if interventions == 0 else 10 if interventions == 1 else 0
    eff = None if cost_pts is None or time_pts is None else round(cost_pts + time_pts + int_pts, 1)
    return {
        "trial": s["trial"], "candidate": s["candidate"], "run": s["run"], "total": s["total"],
        "quality": round(got / full * 100, 1),
        "quality_parts": [{"label": p[0], "got": p[1], "max": p[2]} for p in parts],
        "efficiency": eff, "cost_pts": cost_pts, "time_pts": time_pts,
        "intervention_pts": None if interventions is None else int_pts,
        "cost_usd": f["cost_usd"], "elapsed_seconds": f["elapsed_seconds"],
        "cost_ratio": None if cost_ratio is None else round(cost_ratio, 2),
        "time_ratio": None if time_ratio is None else round(time_ratio, 2),
        "interventions": interventions, "questions": f.get("questions"),
        "reference": {label: s.get(key) for key, label, _ in REFERENCE_ONLY.get(w, [])},
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 1) if xs else None


def candidate_rows(rows):
    by = {}
    for r in rows:
        by.setdefault(r["candidate"], []).append(r)
    out = []
    for c in [c for c in ORDER if c in by] + sorted(set(by) - set(ORDER)):
        rs = sorted(by[c], key=lambda r: r["run"])
        q = [r["quality"] for r in rs]
        out.append({
            "candidate": c, "runs": len(rs),
            "quality": _mean(q), "efficiency": _mean([r["efficiency"] for r in rs]), "total": _mean([r["total"] for r in rs]),
            "quality_spread": round(max(q) - min(q), 1) if len(rs) >= 2 else None,
            "cost_usd": round(statistics.mean(r["cost_usd"] for r in rs), 4),
            "minutes": round(statistics.mean(r["elapsed_seconds"] for r in rs) / 60, 1),
            "cost_ratio": _mean([r["cost_ratio"] for r in rs]) if rs[0]["cost_ratio"] is not None else None,
            "time_ratio": _mean([r["time_ratio"] for r in rs]) if rs[0]["time_ratio"] is not None else None,
            "interventions": None if rs[0]["interventions"] is None else sum(r["interventions"] for r in rs),
            "questions": None if any(r["questions"] is None for r in rs) else sum(r["questions"] for r in rs),
        })
    return out


def _ranking(cands, key):
    return [c["candidate"] for c in sorted(cands, key=lambda c: (-(c[key] if c[key] is not None else -1), ORDER.index(c["candidate"]) if c["candidate"] in ORDER else 99))]


def judge(cands):
    """品質の差を試行のばらつきと比べる。最高品質の候補と各候補の差が、
    両者の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする（1 回だけの候補のばらつきは数えない）。"""
    if not cands:
        return {}
    top = max(cands, key=lambda c: c["quality"])
    out = {}
    for c in cands:
        gap = round(top["quality"] - c["quality"], 1)
        noise = max(x for x in (top["quality_spread"], c["quality_spread"], 0) if x is not None)
        out[c["candidate"]] = {"gap": gap, "noise": noise, "same": gap <= noise}
    return {"top": top["candidate"], "by": out}


def compute(w, dir_=None):
    dir_ = Path(dir_) if dir_ else RESULTS / w
    scores = load_scores(dir_)
    if not scores:
        return None
    base = [s for s in scores if s["candidate"] == "baseline"]
    base_cost = statistics.mean(s["facts"]["cost_usd"] for s in base) if base else None
    base_time = statistics.mean(s["facts"]["elapsed_seconds"] for s in base) if base else None
    rows = [trial_row(w, s, base_cost, base_time) for s in scores]
    cands = candidate_rows(rows)
    result = {
        "scenario": w, "weights": dict(zip(("cost", "time", "intervention"), weights(w))),
        "quality_max": [{"key": k, "label": l, "max": m} for k, l, m in QUALITY[w]],
        "baseline_cost_usd": None if base_cost is None else round(base_cost, 4),
        "baseline_elapsed_seconds": None if base_time is None else round(base_time, 1),
        "trials": rows, "candidates": cands, "judge": judge(cands),
        "rank_total": _ranking(cands, "total"), "rank_quality": _ranking(cands, "quality"),
        "rank_efficiency": _ranking(cands, "efficiency"),
    }
    supp_scores = load_scores(dir_ / "supplement")
    if supp_scores:
        srows = [trial_row(w, s, base_cost, base_time) for s in supp_scores]
        result["supplement"] = {"trials": srows, "candidates": candidate_rows(srows)}
    return result


def conclusions(r):
    """2 軸の結論（文のリスト）。"""
    cands = r["candidates"]
    j = r["judge"]
    by = {c["candidate"]: c for c in cands}
    top = by[j["top"]]
    same = [c for c in cands if j["by"][c["candidate"]]["same"]]
    diff = [c for c in cands if not j["by"][c["candidate"]]["same"]]
    out = []
    if not diff:
        spread = max((c["quality_spread"] or 0) for c in cands)
        out.append(f"品質: 全候補で品質に差なし（最高 {top['quality']} 点、"
                   f"最低との差 {max(j['by'][c['candidate']]['gap'] for c in cands)} 点は、同じ候補の 2 回の差の最大 {spread} 点以下）。")
    else:
        names = "、".join(f"{LABEL.get(c['candidate'], c['candidate'])}（{c['quality']}）" for c in same)
        lows = "、".join(f"{LABEL.get(c['candidate'], c['candidate'])}（{c['quality']}、−{j['by'][c['candidate']]['gap']}）" for c in diff)
        out.append(f"品質: 最高は {label_list(top_group(cands, 'quality'))}（{top['quality']} 点）。"
                   f"これと差なし（差がばらつき以下）: {names}。差あり: {lows}。")
    pool = sorted([c for c in same if c["efficiency"] is not None], key=lambda c: -c["efficiency"])
    if pool:
        best = [c for c in pool if c["efficiency"] == pool[0]["efficiency"]]
        detail = "、".join(f"{LABEL.get(c['candidate'], c['candidate'])}（費用 {c['cost_ratio']} 倍・時間 {c['time_ratio']} 倍）" for c in best)
        rest = "、".join(f"{LABEL.get(c['candidate'], c['candidate'])} {c['efficiency']}" for c in pool if c not in best)
        out.append(f"効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは {detail}"
                   f"で効率 {pool[0]['efficiency']} 点" + (f"。ほかは {rest}。" if rest else "。"))
    rc = rank_change(r)
    if rc:
        line = f"順位の入れ替わり: あり（従来の総合点の 1 位は {label_list(rc[0])}、品質の 1 位は {label_list(rc[1])}）。"
        gap = round(top["quality"] - max(by[c]["quality"] for c in rc[0]), 1)
        spread = max((c["quality_spread"] or 0) for c in cands)
        if any(by[c]["runs"] < 2 for c in rc[0]) and gap <= spread:
            line += (f"ただし品質の差 {gap} 点は、この W の同じ候補の 2 回の差の最大 {spread} 点以下で、"
                     "1 回しか試行していない側のばらつきは測れていないため、確定的な差とは言えない。")
        out.append(line)
    else:
        out.append(f"順位の入れ替わり: なし（従来の総合点の 1 位 {label_list(top_group(cands, 'total'))} は、"
                   f"品質でも 1 位（同点を含む: {label_list(top_group(cands, 'quality'))}）。")
    return out


def top_group(cands, key):
    """key の最高点の候補（同点はすべて）。"""
    vals = [c[key] for c in cands if c[key] is not None]
    if not vals:
        return []
    return [c["candidate"] for c in cands if c[key] == max(vals)]


def label_list(cs):
    return "・".join(LABEL.get(c, c) for c in cs)


def rank_change(r):
    """従来の総合点の 1 位が、品質の 1 位（同点を含む）に入っていなければ (総合点の 1 位, 品質の 1 位) を返す。"""
    t1 = top_group(r["candidates"], "total")
    q1 = top_group(r["candidates"], "quality")
    return None if set(t1) & set(q1) else (t1, q1)


def _fmt(x, suffix=""):
    return "—" if x is None else f"{x}{suffix}"


def _cand_table_md(w, cands, judge_=None):
    wc, wt, wi = weights(w)
    head = f"| 候補 | 回数 | 品質 / 100 | 2 回の差 | 効率 / 100 | 総合点（従来） | 費用（baseline 比） | 時間（baseline 比） | 介入 | 質問（参考） |"
    out = [head, "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        note = ""
        if judge_:
            jj = judge_["by"][c["candidate"]]
            note = "（最高）" if c["candidate"] in top_group(cands, "quality") else ("（差なし）" if jj["same"] else "")
        out.append(f"| {LABEL.get(c['candidate'], c['candidate'])} | {c['runs']} | {c['quality']}{note} | {_fmt(c['quality_spread'])} | "
                   f"{_fmt(c['efficiency'])} | {c['total']} | ${c['cost_usd']:.2f}（{_fmt(c['cost_ratio'], ' 倍')}） | "
                   f"{c['minutes']} 分（{_fmt(c['time_ratio'], ' 倍')}） | {_fmt(c['interventions'], ' 回')} | {_fmt(c['questions'], ' 回')} |")
    return out


def _sorted(rows):
    return sorted(rows, key=lambda r: (ORDER.index(r["candidate"]) if r["candidate"] in ORDER else 99, r["run"]))


def _trial_table_md(w, rows):
    wc, wt, wi = weights(w)
    qh = " | ".join(f"{p['label']} / {p['max']:g}" for p in rows[0]["quality_parts"])
    ih = f" | 介入 / {wi}" if wi else ""
    out = [f"| 試行 | {qh} | 品質 / 100 | 費用 / {wc} | 時間 / {wt}{ih} | 効率 / 100 | 総合点（従来） |",
           "|---|" + "---:|" * (len(rows[0]["quality_parts"]) + 5 + (1 if wi else 0))]
    for r in _sorted(rows):
        qs = " | ".join(f"{p['got']:g}" for p in r["quality_parts"])
        iv = f" | {_fmt(r['intervention_pts'])}" if wi else ""
        out.append(f"| {LABEL.get(r['candidate'], r['candidate'])} #{r['run']} | {qs} | {r['quality']} | {_fmt(r['cost_pts'])} | "
                   f"{_fmt(r['time_pts'])}{iv} | {_fmt(r['efficiency'])} | {r['total']} |")
    return out


def _method_lines(w, r):
    wc, wt, wi = weights(w)
    parts = " + ".join(f"{q['label']} {q['max']}" for q in r["quality_max"])
    full = sum(q["max"] for q in r["quality_max"])
    lines = [
        f"品質 = （{parts}）の得点 ÷ {full} × 100。",
        (f"効率 = 費用 {wc} + 時間 {wt} + 介入 {wi}。" if wi else f"効率 = 費用 {wc} + 時間 {wt}（この W には介入の仕組みが無い）。")
        + f"費用・時間は baseline（${r['baseline_cost_usd']}・{r['baseline_elapsed_seconds']:g} 秒）に対する倍率で、"
          "2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。"
        + ("介入は 0 回 = 20、1 回 = 10、2 回以上 = 0。" if wi else ""),
        "質問の回数は効率から引かない（参考値）。品質の差が、比べる 2 候補の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする。",
        "定義は docs/poc/PLAN.md §4.4。計算は scripts/poc/two_axis.py。従来の総合点・順位はこの節では変えない。",
    ]
    if w in REFERENCE_ONLY:
        lines.append("「" + "・".join(l for _, l, _ in REFERENCE_ONLY[w]) + "」は品質にも効率にも入れない（参考値）。")
    return lines


def md_section(w, dir_=None):
    r = compute(w, dir_)
    if not r:
        return []
    out = ["## 2 本立ての点数（品質・効率）", ""]
    out += [f"- {x}" for x in conclusions(r)] + [""]
    out += ["### 候補ごとの平均", ""] + _cand_table_md(w, r["candidates"], r["judge"]) + [""]
    out += ["### 試行ごとの内訳", ""] + _trial_table_md(w, r["trials"]) + [""]
    if w in REFERENCE_ONLY:
        out += ["参考値（品質・効率に入れない）: " + "、".join(
            f"{LABEL.get(t['candidate'], t['candidate'])} #{t['run']} {k} {v}" for t in _sorted(r["trials"]) for k, v in t["reference"].items()), ""]
    if "supplement" in r:
        out += ["### 参考: Feature Dev の補足の再試行（新文言。本表の平均には含めない）", ""]
        out += _cand_table_md(w, r["supplement"]["candidates"]) + [""]
        out += _trial_table_md(w, r["supplement"]["trials"]) + [""]
    out += ["### 計算方法と判断の記録", ""] + [f"- {x}" for x in _method_lines(w, r)] + [""]
    return out


def _md_table_to_html(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in lines if ln.startswith("|")]
    head, body = rows[0], rows[2:]
    th = "".join(f"<th>{e(h)}</th>" for h in head)
    trs = "".join("<tr>" + "".join(
        (f'<th scope="row">{e(c)}</th>' if i == 0 else f'<td class="num">{e(c)}</td>') for i, c in enumerate(r)) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def html_section(w, dir_=None):
    r = compute(w, dir_)
    if not r:
        return ""
    lis = "".join(f"<li>{e(x)}</li>" for x in conclusions(r))
    parts = [
        "\n  <h2>2 本立ての点数（品質・効率）</h2>",
        f'  <div class="box"><ul>{lis}</ul></div>',
        "  <h3>候補ごとの平均</h3>", "  " + _md_table_to_html(_cand_table_md(w, r["candidates"], r["judge"])),
        "  <h3>試行ごとの内訳</h3>", "  " + _md_table_to_html(_trial_table_md(w, r["trials"])),
    ]
    if w in REFERENCE_ONLY:
        parts.append("  <p><small>参考値（品質・効率に入れない）: " + e("、".join(
            f"{LABEL.get(t['candidate'], t['candidate'])} #{t['run']} {k} {v}" for t in _sorted(r["trials"]) for k, v in t["reference"].items())) + "</small></p>")
    if "supplement" in r:
        parts += ["  <h3>参考: Feature Dev の補足の再試行（新文言。本表の平均には含めない）</h3>",
                  "  " + _md_table_to_html(_cand_table_md(w, r["supplement"]["candidates"])),
                  "  " + _md_table_to_html(_trial_table_md(w, r["supplement"]["trials"]))]
    parts += ["  <h3>計算方法と判断の記録</h3>",
              '  <div class="box"><ul>' + "".join(f"<li>{e(x)}</li>" for x in _method_lines(w, r)) + "</ul></div>"]
    return "\n".join(parts) + "\n"


# ---------------- 全 W 横断の summary ----------------

def write_json(w):
    r = compute(w)
    if not r:
        return None
    (RESULTS / w / "two_axis.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
    return r


def load_all():
    out = {}
    for w in SCENARIOS:
        r = compute(w)
        if r:
            out[w] = r
    return out


def summary_md(all_):
    done = [w for w in SCENARIOS if w in all_]
    pending = [w for w in SCENARIOS if w not in all_]
    lines = ["# 開発ワークフロー PoC — 全シナリオの 2 本立て（品質・効率）一覧", "",
             "> HTML 版: [summary.html](summary.html)（同じデータから `scripts/poc/two_axis.py` で生成）", "",
             "各シナリオを「品質で差があるか」「同じ品質ならどれだけ安く速いか」の 2 軸で見た一覧です。"
             "従来の総合点・順位は置き換えず並記しています（定義は [PLAN.md §4.4](../../PLAN.md)）。", ""]
    changes = [(w, rank_change(all_[w])) for w in done if rank_change(all_[w])]
    lines += ["## 要点", ""]
    if changes:
        for w, _ in changes:
            lines.append(f"- **{w} で順位が入れ替わった**: " + conclusions(all_[w])[-1].split("（", 1)[1].replace("）。", "。", 1))
    else:
        lines.append("- 2 本立てにして 1 位が入れ替わった W は無い。")
    for w in done:
        lines.append(f"- {w}（{TITLES[w]}）: " + " ".join(conclusions(all_[w])[:2]))
    if pending:
        lines.append(f"- 未完了（main に結果が無い）: {'・'.join(pending)}")
    lines.append("")

    cands = [c for c in ORDER]
    for title, key in (("品質（平均 / 100）", "quality"), ("効率（平均 / 100）", "efficiency"), ("総合点（従来、平均 / 100）", "total")):
        lines += [f"## {title}", "", "| 候補 | " + " | ".join(SCENARIOS) + " |", "|---|" + "---:|" * len(SCENARIOS)]
        for c in cands:
            cells = []
            for w in SCENARIOS:
                if w not in all_:
                    cells.append("未完了")
                    continue
                row = next((x for x in all_[w]["candidates"] if x["candidate"] == c), None)
                if row is None or row[key] is None:
                    cells.append("—")
                    continue
                v = f"{row[key]}"
                if key == "quality":
                    j = all_[w]["judge"]
                    if c in top_group(all_[w]["candidates"], "quality"):
                        v = f"**{v}**"
                    elif j["by"][c]["same"]:
                        v = f"{v}≒"
                cells.append(v)
            lines.append(f"| {LABEL[c]} | " + " | ".join(cells) + " |")
        if key == "quality":
            lines += ["", "太字 = その W の品質の最高。≒ = 最高との差が試行のばらつき（2 回の差）以下で「品質に差なし」。"]
        lines.append("")

    lines += ["## シナリオごとの結論", ""]
    for w in SCENARIOS:
        lines += [f"### {w} {TITLES[w]}", ""]
        if w not in all_:
            lines += ["未完了（結果が main に入ったら下の手順で再生成する）。", ""]
            continue
        r = all_[w]
        lines += [f"- {x}" for x in conclusions(r)]
        lines += [f"- 詳細: [{w}/report.md]({w}/report.md) の「2 本立ての点数」", ""]
        if "supplement" in r:
            sc = r["supplement"]["candidates"][0]
            lines += [f"- 参考（本表に含めない）: Feature Dev の補足の再試行（新文言 {sc['runs']} 回）は品質 {sc['quality']}・効率 {sc['efficiency']}・総合点 {sc['total']}。", ""]

    lines += ["## 判断の記録", "",
              "- 費用・時間の基準は各 W の baseline（1 回のみ。2 回以上あれば平均）。時間は壁時計の時間（elapsed_seconds）で、従来の採点と同じ。",
              "- W3 の費用は候補のセッションの費用だけで、回答役（answer_w3.py）の費用は含めない（質問を効率から引かない方針に合わせるため）。",
              "- W1 は介入の仕組み（定型の「お任せします」で続けさせる）を導入する前に実施したため、効率は 費用 60 + 時間 40 で計算した。W1 の質問回数は記録が無いため「—」。",
              "- 「品質に差なし」の判定: 最高品質の候補との差が、両者それぞれの 2 回の差の大きい方以下なら差なし。baseline は 1 回だけなので、ばらつきは相手の候補の値を使う。",
              "- W1・W2 の Feature Dev 補足の再試行（新文言）は参考値として各 report の別表に出し、本表の平均には混ぜない。",
              "- W7 は W7b の費用・時間で効率を計算する（W7a 比は参考値）。W4・W6〜W8 の品質の内訳キーは採点スクリプトの作成時に `two_axis.py` の QUALITY に合わせるか、scores.json に `two_axis_quality` を書く。",
              ""]
    lines += ["## 更新のしかた", "",
              "W4 以降の結果（`docs/poc/results/workflow/<W>/scores.json`）が main に入ったら、次を実行する。",
              "", "```bash", "python3 scripts/poc/two_axis.py", "```", "",
              "- 記録のある全 W の `<W>/two_axis.json` と、この `summary.md`・`summary.html` を作り直す。結果の無い W は「未完了」と表示する。",
              "- 各 W の report.md / report.html の「2 本立ての点数」の節は、`report_w*.py` が `two_axis.md_section()` / `html_section()` を呼んで足す（W4 以降の report スクリプトでも同じように呼ぶ）。",
              "- scores.json の品質の内訳のキーが `two_axis.py` の `QUALITY` と違う場合は、各試行に `\"two_axis_quality\": {\"<内訳名>\": [得点, 満点]}` を書く。効率には各試行の `facts.cost_usd`・`facts.elapsed_seconds`・`facts.interventions`（あれば `facts.questions`）を使う。",
              ""]
    return lines


def summary_html(all_, md_lines):
    """summary.md と同じ内容を HTML にする（表・見出し・箇条書きだけの簡易変換）。"""
    import re

    def inline(s):
        s = e(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", lambda m: f'<a href="{m.group(2).replace(".md", ".html") if m.group(2).endswith("report.md") else m.group(2)}">{m.group(1)}</a>', s)
        return s

    body, i, in_code = [], 0, False
    lines = md_lines
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            body.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
        elif in_code:
            body.append(e(ln))
        elif ln.startswith("# "):
            body.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            body.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            body.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("> HTML 版"):
            pass
        elif ln.startswith("> "):
            body.append(f'<p class="lead">{inline(ln[2:])}</p>')
        elif ln.startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].startswith("|"):
                tbl.append(lines[i])
                i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split(" | ")] for r in tbl]
            th = "".join(f"<th>{inline(h)}</th>" for h in rows[0])
            trs = "".join("<tr>" + "".join((f'<th scope="row">{inline(c)}</th>' if k == 0 else f'<td class="num">{inline(c)}</td>')
                                           for k, c in enumerate(r)) + "</tr>" for r in rows[2:])
            body.append(f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
            continue
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            body.append(f'<div class="box"><ul>{"".join(items)}</ul></div>')
            continue
        elif ln.strip():
            body.append(f"<p>{inline(ln)}</p>")
        i += 1
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC 2 本立て一覧</title>
<style>
:root {{ --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df; --accent:#2f5bd3; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033; --accent:#7c9cff; }}
}}
:root[data-theme="dark"] {{ --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033; --accent:#7c9cff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.7 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:24px; margin:0 0 8px; }}
h2 {{ font-size:19px; margin:36px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
h3 {{ font-size:16px; margin:24px 0 8px; }}
a {{ color:var(--accent); }}
.lead {{ color:var(--muted); }}
.box {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 18px; }}
.table-wrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
pre {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:10px 14px; overflow-x:auto; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
ul {{ padding-left:20px; }}
</style>
</head>
<body>
<main>
{chr(10).join(body)}
</main>
</body>
</html>
"""


def write_summary(all_):
    md_lines = summary_md(all_)
    (RESULTS / "summary.md").write_text("\n".join(md_lines) + "\n")
    (RESULTS / "summary.html").write_text(summary_html(all_, md_lines))
    print(f"wrote {RESULTS / 'summary.md'}")
    print(f"wrote {RESULTS / 'summary.html'}")


def main(argv):
    check = "--check" in argv
    ws = [a for a in argv if a in SCENARIOS] or [w for w in SCENARIOS if (RESULTS / w / "scores.json").exists()]
    for w in ws:
        r = compute(w) if check else write_json(w)
        if not r:
            print(f"{w}: 結果なし（未完了）")
            continue
        print(f"== {w}  baseline ${r['baseline_cost_usd']} / {r['baseline_elapsed_seconds']}s")
        for c in r["candidates"]:
            print(f"  {c['candidate']:22} q={c['quality']:5} spread={c['quality_spread']}  eff={c['efficiency']}  total={c['total']}"
                  f"  cost×{c['cost_ratio']} time×{c['time_ratio']} int={c['interventions']} q#={c['questions']}")
        for x in conclusions(r):
            print("   ", x)
        if "supplement" in r:
            for c in r["supplement"]["candidates"]:
                print(f"  [supplement] {c['candidate']} q={c['quality']} eff={c['efficiency']} total={c['total']}")
    if not check:
        write_summary(load_all())


if __name__ == "__main__":
    main(sys.argv[1:])
