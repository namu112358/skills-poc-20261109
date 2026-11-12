#!/usr/bin/env python3
"""W3 の結果から HTML レポート（report.html）と、同じ内容の Markdown（report.md）を作る。"""
import html
import json
import re
import statistics
from pathlib import Path

import two_axis

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W3"
NOTES = json.loads((DIR / "notes.json").read_text())

LABEL = {
    "baseline": "baseline（候補なし）",
    "superpowers": "Superpowers",
    "feature-dev": "Feature Dev",
    "compound-engineering": "Compound Engineering",
    "gstack": "gstack",
}
ORDER = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]
HIDDEN = {
    "H1": "利用者と目的", "H2": "担当者×状態の件数", "H3": "期限切れ", "H4": "7 日以内", "H5": "今週の完了数・完了日時",
    "H6": "JST 基準", "H7": "見られる人", "H8": "画面の置き場所", "H9": "件数から一覧へ", "H10": "スマホ",
}
QUALITY = {"Q1": "目的と利用者", "Q2": "検証できる書き方", "Q3": "対象と対象外", "Q4": "前提・未決事項", "Q5": "既存アプリとの整合"}
SCOPE = {"SC1": "最初の版の範囲", "SC2": "不要とされた機能", "SC3": "既存の制約", "SC4": "規模の妥当さ"}


def e(s):
    return html.escape(str(s))


def md(s):
    s = str(s)
    s = re.sub(r"<code>(.*?)</code>", lambda m: "`" + m.group(1) + "`", s, flags=re.S)
    s = re.sub(r"<strong>(.*?)</strong>", lambda m: "**" + m.group(1) + "**", s, flags=re.S)
    s = re.sub(r"<li>", "\n- ", s)
    s = re.sub(r"</p>\s*", "\n\n", s)
    s = re.sub(r"<ul>\s*", "\n", s)
    s = re.sub(r"</ul>\s*", "\n\n", s)
    s = re.sub(r"</?(p|li)>", "", s)
    return html.unescape(s).strip()


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def bar(value, maximum, cls=""):
    pct = 0 if maximum == 0 else max(0, min(100, value / maximum * 100))
    return f'<div class="bar {cls}"><span style="width:{pct:.0f}%"></span></div>'


def main():
    data = json.loads((DIR / "scores.json").read_text())
    scores, gaps = data["scores"], data["review_gaps"]
    by_cand = {}
    for s in scores:
        by_cand.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by_cand]

    def mean(c, key):
        return float(round(statistics.mean(s[key] for s in by_cand[c]), 1))

    def mean_fact(c, key):
        return statistics.mean(s["facts"][key] for s in by_cand[c])

    def mean_detail(c, group, k):
        vals = [s[group][k] for s in by_cand[c] if k in s[group]]
        return round(statistics.mean(vals), 1) if vals else "—"

    ranked = sorted([c for c in cands if c != "baseline"], key=lambda c: -mean(c, "total"))
    runs_sorted = [(c, s) for c in cands for s in sorted(by_cand[c], key=lambda s: s["run"])]

    # ---------- HTML ----------
    cards = []
    for c in cands:
        cards.append(f"""
      <article class="card{' top' if ranked and c == ranked[0] else ''}">
        <header><h3>{e(LABEL[c])}</h3><span class="runs">{len(by_cand[c])} 回</span></header>
        <p class="score"><strong>{mean(c, 'total')}</strong><small> / 100</small></p>
        <dl>
          <div><dt>隠れ要件</dt><dd>{mean(c, 'hidden')} / 40</dd></div>
          <div><dt>文書の質</dt><dd>{mean(c, 'quality')} / 25</dd></div>
          <div><dt>スコープ</dt><dd>{mean(c, 'scope')} / 20</dd></div>
          <div><dt>質問の負担</dt><dd>{mean(c, 'burden')} / 15</dd></div>
        </dl>
        <p class="meta">平均 ${mean_fact(c, 'cost_usd'):.2f} ・ {mean_fact(c, 'elapsed_seconds') / 60:.1f} 分 ・ 質問 {mean_fact(c, 'questions'):.1f} 件</p>
      </article>""")

    breakdown = []
    for c in cands:
        breakdown.append(f"""
        <div class="bd-row">
          <span class="bd-name">{e(LABEL[c])}</span>
          <div class="bd-bars">
            <div><small>隠れ要件 {mean(c, 'hidden')} / 40</small>{bar(mean(c, 'hidden'), 40, 'a')}</div>
            <div><small>文書の質 {mean(c, 'quality')} / 25</small>{bar(mean(c, 'quality'), 25, 'b')}</div>
            <div><small>スコープ {mean(c, 'scope')} / 20</small>{bar(mean(c, 'scope'), 20, 'c')}</div>
            <div><small>質問の負担 {mean(c, 'burden')} / 15</small>{bar(mean(c, 'burden'), 15, 'd')}</div>
          </div>
        </div>""")

    rows = []
    for c, s in runs_sorted:
        f = s["facts"]
        rows.append(f"""
        <tr>
          <th scope="row">{e(LABEL[c])} #{s['run']}</th>
          <td class="num">{s['total']:.1f}</td><td class="num">{s['hidden']:.1f}</td><td class="num">{s['quality']:.1f}</td>
          <td class="num">{s['scope']:.1f}</td><td class="num">{s['burden']}</td>
          <td class="num">{f['questions']}</td><td class="num">{f['duplicates']}</td><td class="num">{f['rounds']}</td>
          <td>{e(f['doc_source'])}（{f['doc_lines']} 行）</td>
          <td class="num">{f['interventions']}</td>
          <td class="num">${f['cost_usd']:.2f}</td><td class="num">{f['elapsed_seconds'] / 60:.1f}</td>
          <td class="num">{f['turns']}</td><td class="num">{f['subagents']}</td>
          <td>{e(', '.join(f['skills_used']) or '—')}</td>
        </tr>""")

    def heat(v, mx):
        if v == "—":
            return '<td class="num">—</td>'
        return f'<td class="num heat" style="--p:{v / mx:.2f}">{v}</td>'

    hidden_rows = "".join(
        f'<tr><th scope="row">{e(LABEL[c])}</th>' + "".join(heat(mean_detail(c, "hidden_detail", k), 4) for k in HIDDEN) + "</tr>"
        for c in cands)
    qs_rows = "".join(
        f'<tr><th scope="row">{e(LABEL[c])}</th>'
        + "".join(heat(mean_detail(c, "quality_detail", k), 5) for k in QUALITY)
        + "".join(heat(mean_detail(c, "scope_detail", k), 5) for k in SCOPE) + "</tr>"
        for c in cands)
    gap_text = ("採点者 2 名の差が大きかった項目（隠れ要件 4 点以上・ほか 3 点以上）: "
                + "、".join(f"{g['trial']} の {g['item']}（{'・'.join(map(str, g['scores']))}）" for g in gaps)) \
        if gaps else "採点者 2 名の差が大きかった項目（隠れ要件 4 点以上・ほか 3 点以上）はありませんでした。"

    findings = []
    for c, s in runs_sorted:
        t = json.loads((DIR / f"{s['trial']}.json").read_text())
        qa_items = "".join(
            f"<li><span class=\"kind\">{e(i['round'])} 回目・{e(i['kind'])}"
            f"{'・' + e(','.join(i['sheet_ids'])) if i['sheet_ids'] else ''}</span> {e(i['question'])}</li>"
            for i in t["qa"]["items"])
        findings.append(f"""
      <details>
        <summary><strong>{e(LABEL[c])} #{s['run']}</strong> — {s['total']} 点</summary>
        <p>{NOTES['trials'].get(s['trial'], '')}</p>
        <p class="sub">隠れ要件（{' ・ '.join(f'{k} {v}' for k, v in s['hidden_detail'].items()) or '未採点'}）</p>
        <p class="sub">文書の質（{' ・ '.join(f'{QUALITY[k]} {v}' for k, v in s['quality_detail'].items()) or '未採点'}）
           ・ スコープ（{' ・ '.join(f'{SCOPE[k]} {v}' for k, v in s['scope_detail'].items()) or '未採点'}）</p>
        <ul class="files">{''.join(f'<li>{e(x)}</li>' for x in s['comments'])}</ul>
        <p class="sub">依頼者への質問（{s['facts']['questions']} 件・{s['facts']['rounds']} 回。引き出した項目: {e(', '.join(s['facts']['elicited_ids']) or 'なし')}）</p>
        <ul class="files">{qa_items or '<li>なし</li>'}</ul>
        <p class="sub">コミット</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in t['diff']['commits']) or '<li>なし</li>'}</ul>
      </details>""")

    ul = lambda xs: "".join(f"<li>{x}</li>" for x in xs)  # noqa: E731
    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W3 結果</title>
<style>
:root {{
  --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df;
  --accent:#2f5bd3; --a:#2f5bd3; --b:#1f8a70; --c:#b7791f; --d:#8e44ad; --top:#eef3ff; --heat:47,91,211;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
    --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --top:#1f2738; --heat:124,156,255;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
  --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --top:#1f2738; --heat:124,156,255;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.7 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:19px; margin:40px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
.lead {{ color:var(--muted); margin:0 0 20px; }}
.summary {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:8px; padding:14px 18px; }}
.summary p {{ margin:4px 0; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.card.top {{ background:var(--top); border-color:var(--accent); }}
.card header {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; }}
.card h3 {{ font-size:15px; margin:0; }}
.runs, .meta {{ color:var(--muted); font-size:12px; }}
.score {{ margin:6px 0; }} .score strong {{ font-size:30px; }}
dl {{ margin:0; display:grid; gap:2px; font-size:13px; }}
dl div {{ display:flex; justify-content:space-between; }} dt {{ color:var(--muted); }} dd {{ margin:0; }}
.table-wrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; min-width:760px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.heat {{ background:rgba(var(--heat), calc(var(--p) * 0.45)); }}
.bd-row {{ display:grid; grid-template-columns:180px 1fr; gap:12px; padding:8px 0; border-bottom:1px solid var(--line); }}
.bd-bars {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
.bd-name {{ font-weight:600; font-size:14px; }}
.bar {{ height:8px; background:var(--line); border-radius:4px; overflow:hidden; margin-top:2px; }}
.bar span {{ display:block; height:100%; background:var(--a); }}
.bar.b span {{ background:var(--b); }} .bar.c span {{ background:var(--c); }} .bar.d span {{ background:var(--d); }}
small {{ color:var(--muted); font-size:12px; }}
details {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:10px 14px; margin:8px 0; }}
summary {{ cursor:pointer; }}
.sub {{ color:var(--muted); font-size:12px; margin:10px 0 2px; }}
ul {{ padding-left:20px; }} .files {{ font-size:13px; margin:0; }}
.kind {{ color:var(--muted); font-size:11px; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
.cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }}
.box {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 18px; }}
@media (max-width:640px) {{ .bd-row {{ grid-template-columns:1fr; }} .bd-bars {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main>
  <h1>開発ワークフロー PoC — W3 曖昧な要望から要件を固める</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 poc/PLAN.md §5.1</p>
  <section class="summary">{''.join(f'<p>{x}</p>' for x in NOTES['summary'])}</section>

  <h2>課題</h2>
  <p>{NOTES['task_html']}</p>

  <h2>結果の概要（平均点）</h2>
  <div class="cards">{''.join(cards)}</div>

  <h2>配点ごとの内訳</h2>
  <div class="box">{''.join(breakdown)}</div>

  <h2>試行ごとの結果</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>試行</th><th>点数</th><th>隠れ要件</th><th>文書</th><th>スコープ</th><th>負担</th><th>質問数</th><th>重複</th>
      <th>回答回数</th><th>採点した文書</th><th>介入</th><th>費用</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th><th>使われた Skill</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>

  <h2>隠れ要件ごとの反映（平均。各 4 点）</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>候補</th>{''.join(f'<th title="{e(v)}">{k}<br><small>{e(v)}</small></th>' for k, v in HIDDEN.items())}</tr></thead>
    <tbody>{hidden_rows}</tbody>
  </table></div>

  <h2>文書の質・スコープ判断の項目別平均（各 5 点）</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>候補</th>{''.join(f'<th>{e(v)}</th>' for v in QUALITY.values())}{''.join(f'<th>{e(v)}</th>' for v in SCOPE.values())}</tr></thead>
    <tbody>{qs_rows}</tbody>
  </table></div>
  <p class="sub">{e(gap_text)}</p>

  <h2>所見</h2>
  <div class="box"><ul>{ul(NOTES['observations'])}</ul></div>

  <h2>試行の詳細</h2>
  {''.join(findings)}

  <div class="cols">
    <section><h2>採点方法</h2><div class="box">{NOTES['scoring_html']}</div></section>
    <section><h2>この結果の制約</h2><div class="box"><ul>{ul(NOTES['limitations'])}</ul></div></section>
  </div>

  <h2>判断の記録</h2>
  <div class="box"><ul>{ul(NOTES['decisions'])}</ul></div>

  <h2>次の対応</h2>
  <div class="box"><ul>{ul(NOTES['next'])}</ul></div>{two_axis.html_section("W3", DIR)}</main>
</body>
</html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.html'}")

    # ---------- Markdown（同じデータ・同じ構成） ----------
    out = ["# 開発ワークフロー PoC — W3 曖昧な要望から要件を固める", "",
           f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 poc/PLAN.md §5.1", "",
           "> HTML 版: [report.html](report.html)（同じデータから `poc/scripts/report_w3.py` で生成）", ""]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点）", "",
            "| 候補 | 回数 | 合計 / 100 | 隠れ要件 / 40 | 文書の質 / 25 | スコープ / 20 | 質問の負担 / 15 | 平均質問数 | 平均費用 | 平均時間（分） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        name = f"**{LABEL[c]}**" if ranked and c == ranked[0] else LABEL[c]
        out.append(f"| {name} | {len(by_cand[c])} | {mean(c, 'total')} | {mean(c, 'hidden')} | {mean(c, 'quality')} | {mean(c, 'scope')} | "
                   f"{mean(c, 'burden')} | {mean_fact(c, 'questions'):.1f} | ${mean_fact(c, 'cost_usd'):.2f} | {mean_fact(c, 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## 試行ごとの結果", "",
            "| 試行 | 点数 | 隠れ要件 | 文書 | スコープ | 負担 | 質問数 | 重複 | 回答回数 | 採点した文書 | 介入 | 費用 | 時間（分） | ターン | サブエージェント | 使われた Skill |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for c, s in runs_sorted:
        f = s["facts"]
        out.append(f"| {LABEL[c]} #{s['run']} | {s['total']:.1f} | {s['hidden']:.1f} | {s['quality']:.1f} | {s['scope']:.1f} | {s['burden']} | "
                   f"{f['questions']} | {f['duplicates']} | {f['rounds']} | {cell(f['doc_source'])}（{f['doc_lines']} 行） | {f['interventions']} | "
                   f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} | {f['turns']} | {f['subagents']} | {cell(', '.join(f['skills_used']) or '—')} |")
    out += ["", "## 隠れ要件ごとの反映（平均。各 4 点）", "",
            "| 候補 | " + " | ".join(f"{k} {v}" for k, v in HIDDEN.items()) + " |", "|---|" + "---:|" * len(HIDDEN)]
    for c in cands:
        out.append(f"| {LABEL[c]} | " + " | ".join(str(mean_detail(c, "hidden_detail", k)) for k in HIDDEN) + " |")
    out += ["", "## 文書の質・スコープ判断の項目別平均（各 5 点）", "",
            "| 候補 | " + " | ".join(list(QUALITY.values()) + list(SCOPE.values())) + " |", "|---|" + "---:|" * (len(QUALITY) + len(SCOPE))]
    for c in cands:
        out.append(f"| {LABEL[c]} | " + " | ".join(
            [str(mean_detail(c, "quality_detail", k)) for k in QUALITY] + [str(mean_detail(c, "scope_detail", k)) for k in SCOPE]) + " |")
    out += ["", gap_text, "", "## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 試行の詳細", ""]
    for c, s in runs_sorted:
        t = json.loads((DIR / f"{s['trial']}.json").read_text())
        out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["trial"], "")), ""]
        out += [f"- 隠れ要件: {' ・ '.join(f'{k} {v}' for k, v in s['hidden_detail'].items()) or '未採点'}",
                f"- 文書の質: {' ・ '.join(f'{QUALITY[k]} {v}' for k, v in s['quality_detail'].items()) or '未採点'}",
                f"- スコープ: {' ・ '.join(f'{SCOPE[k]} {v}' for k, v in s['scope_detail'].items()) or '未採点'}", ""]
        out += ["採点者のコメント:", ""] + [f"- {cell(x)}" for x in s["comments"]] + [""]
        out += [f"依頼者への質問（{s['facts']['questions']} 件・{s['facts']['rounds']} 回。引き出した項目: {', '.join(s['facts']['elicited_ids']) or 'なし'}）:", ""]
        out += [f"- {i['round']} 回目・{i['kind']}{'・' + ','.join(i['sheet_ids']) if i['sheet_ids'] else ''}: {cell(i['question'])}"
                for i in t["qa"]["items"]] or ["- なし"]
        out += ["", "コミット:", ""] + ([f"- `{x}`" for x in t["diff"]["commits"]] or ["- なし"]) + [""]
    out += ["## 採点方法", "", md(NOTES["scoring_html"]), ""]
    out += ["## この結果の制約", ""] + [f"- {md(x)}" for x in NOTES["limitations"]]
    out += ["", "## 判断の記録", ""] + [
        "- " + "\n".join(l if i == 0 or l.startswith("  ") else "  " + l
                         for i, l in enumerate(re.sub(r"\n+- ", "\n  - ", md(x)).replace("\n\n", "\n").split("\n")))
        for x in NOTES["decisions"]]
    out += ["", "## 次の対応", ""] + [f"- {md(x)}" for x in NOTES["next"]]
    out += [""] + two_axis.md_section("W3", DIR)[:-1]  # 2 本立ての点数（PLAN.md §4.4）。既存の節の後ろに足す
    (DIR / "report.md").write_text("\n".join(out) + "\n")
    print(f"wrote {DIR / 'report.md'}")


if __name__ == "__main__":
    main()
