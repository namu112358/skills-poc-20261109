#!/usr/bin/env python3
"""W1 の結果から HTML レポート（poc/results/workflow/W1/report.html）を作る。"""
import html
import json
import re
import statistics
from pathlib import Path

import supplement_report
import two_axis

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W1"
NOTES = json.loads((DIR / "notes.json").read_text())

LABEL = {
    "baseline": "baseline（候補なし）",
    "superpowers": "Superpowers",
    "feature-dev": "Feature Dev",
    "compound-engineering": "Compound Engineering",
    "gstack": "gstack",
}
ORDER = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]


def e(s):
    return html.escape(str(s))


def md(s):
    """notes.json の HTML 断片を GitHub で読める Markdown に変える。"""
    s = str(s)
    s = re.sub(r"<code>(.*?)</code>", lambda m: "`" + m.group(1) + "`", s, flags=re.S)
    # 「。**次の文」のように句読点の直後で閉じる ** は GitHub で太字にならないため、strong はタグのまま残す
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
    scores = json.loads((DIR / "scores.json").read_text())
    trials = {t["trial"]: json.loads((DIR / f"{t['trial']}.json").read_text()) for t in scores}
    by_cand = {}
    for s in scores:
        by_cand.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by_cand]

    def mean(c, key):
        return round(statistics.mean(s[key] for s in by_cand[c]), 1)

    def mean_fact(c, key):
        return statistics.mean(s["facts"][key] for s in by_cand[c])

    ranked = sorted([c for c in cands if c != "baseline"], key=lambda c: -mean(c, "total"))

    # 概要カード
    cards = []
    for c in cands:
        runs = by_cand[c]
        cards.append(f"""
      <article class="card{' top' if ranked and c == ranked[0] else ''}">
        <header><h3>{e(LABEL[c])}</h3><span class="runs">{len(runs)} 回</span></header>
        <p class="score"><strong>{mean(c, 'total')}</strong><small> / 100</small></p>
        <dl>
          <div><dt>受け入れ</dt><dd>{mean(c, 'acceptance')} / 50</dd></div>
          <div><dt>時間・費用</dt><dd>{mean(c, 'efficiency')} / 30</dd></div>
          <div><dt>過剰さ</dt><dd>{mean(c, 'overengineering')} / 20</dd></div>
        </dl>
        <p class="meta">平均 ${mean_fact(c, 'cost_usd'):.2f} ・ {mean_fact(c, 'elapsed_seconds') / 60:.1f} 分</p>
      </article>""")

    # 試行ごとの表
    rows = []
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            f = s["facts"]
            t = trials[s["trial"]]
            checks = " ".join(
                f'<span class="pill {"ok" if t["checks"][k]["pass"] else "ng"}">{k}</span>'
                for k in ("typecheck", "test", "build"))
            rows.append(f"""
        <tr>
          <th scope="row">{e(LABEL[c])} #{s['run']}</th>
          <td class="num">{s['total']}</td>
          <td class="num">{f['e2e_pass']}/{f['e2e_total']}</td>
          <td>{checks}</td>
          <td class="num">{f['code_added']}</td>
          <td class="num">{f['test_added']}</td>
          <td class="num">${f['cost_usd']:.2f}</td>
          <td class="num">{f['elapsed_seconds'] / 60:.1f}</td>
          <td class="num">{f['turns']}</td>
          <td class="num">{f['subagents']}</td>
          <td class="num">{f['denials']}</td>
          <td>{e(', '.join(f['skills_used']) or '—')}</td>
        </tr>""")

    # 配点の内訳（棒）
    breakdown = []
    for c in cands:
        breakdown.append(f"""
        <div class="bd-row">
          <span class="bd-name">{e(LABEL[c])}</span>
          <div class="bd-bars">
            <div><small>受け入れ {mean(c, 'acceptance')}</small>{bar(mean(c, 'acceptance'), 50, 'a')}</div>
            <div><small>時間・費用 {mean(c, 'efficiency')}</small>{bar(mean(c, 'efficiency'), 30, 'b')}</div>
            <div><small>過剰さ {mean(c, 'overengineering')}</small>{bar(mean(c, 'overengineering'), 20, 'c')}</div>
          </div>
        </div>""")

    # 試行ごとの所見
    findings = []
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            note = NOTES["trials"].get(s["trial"], "")
            t = trials[s["trial"]]
            failed = [x for x in t["e2e"] if not x["pass"]]
            fail_html = "".join(f"<li>{e(x['name'])}<br><code>{e(x['detail'][:160])}</code></li>" for x in failed)
            files = "".join(
                f"<li><code>{e(f['path'])}</code> +{f['added']} −{f['deleted']} <span class=\"kind\">{e(f['kind'])}</span></li>"
                for f in t["diff"]["files"])
            findings.append(f"""
      <details>
        <summary><strong>{e(LABEL[c])} #{s['run']}</strong> — {s['total']} 点</summary>
        <p>{e(note)}</p>
        {'<p class="warn">不合格の受け入れテスト</p><ul>' + fail_html + '</ul>' if failed else ''}
        <p class="sub">変更ファイル</p><ul class="files">{files or '<li>なし</li>'}</ul>
        <p class="sub">コミット</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in t['diff']['commits']) or '<li>なし</li>'}</ul>
      </details>""")

    observations = "".join(f"<li>{x}</li>" for x in NOTES["observations"])
    limits = "".join(f"<li>{x}</li>" for x in NOTES["limitations"])
    nexts = "".join(f"<li>{x}</li>" for x in NOTES["next"])

    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W1 結果</title>
<style>
:root {{
  --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df;
  --accent:#2f5bd3; --a:#2f5bd3; --b:#1f8a70; --c:#b7791f; --ok:#1f8a70; --ng:#c0392b; --top:#eef3ff;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
    --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --ok:#4cc39f; --ng:#ff7b6b; --top:#1f2738;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
  --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --ok:#4cc39f; --ng:#ff7b6b; --top:#1f2738;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text);
  font:15px/1.7 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:19px; margin:40px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
.lead {{ color:var(--muted); margin:0 0 20px; }}
.summary {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent);
  border-radius:8px; padding:14px 18px; }}
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
table {{ border-collapse:collapse; width:100%; font-size:13px; min-width:900px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.pill {{ display:inline-block; font-size:11px; padding:0 6px; border-radius:999px; margin-right:2px; }}
.pill.ok {{ color:var(--ok); border:1px solid var(--ok); }} .pill.ng {{ color:var(--ng); border:1px solid var(--ng); }}
.bd-row {{ display:grid; grid-template-columns:180px 1fr; gap:12px; padding:8px 0; border-bottom:1px solid var(--line); }}
.bd-bars {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
.bd-name {{ font-weight:600; font-size:14px; }}
.bar {{ height:8px; background:var(--line); border-radius:4px; overflow:hidden; margin-top:2px; }}
.bar span {{ display:block; height:100%; background:var(--a); }}
.bar.b span {{ background:var(--b); }} .bar.c span {{ background:var(--c); }}
small {{ color:var(--muted); font-size:12px; }}
details {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:10px 14px; margin:8px 0; }}
summary {{ cursor:pointer; }}
.sub {{ color:var(--muted); font-size:12px; margin:10px 0 2px; }}
.warn {{ color:var(--ng); font-size:13px; margin:10px 0 2px; }}
ul {{ padding-left:20px; }} .files {{ font-size:13px; margin:0; }}
.kind {{ color:var(--muted); font-size:11px; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
.cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }}
.box {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 18px; }}
@media (max-width:640px) {{
  .bd-row {{ grid-template-columns:1fr; }} .bd-bars {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<main>
  <h1>開発ワークフロー PoC — W1 小さな変更</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 poc/PLAN.md §5.1</p>

  <section class="summary">
    {''.join(f'<p>{x}</p>' for x in NOTES['summary'])}
  </section>

  <h2>課題</h2>
  <p>{NOTES['task_html']}</p>

  <h2>結果の概要（平均点）</h2>
  <div class="cards">{''.join(cards)}</div>

  <h2>配点ごとの内訳</h2>
  <div class="box">{''.join(breakdown)}</div>

  <h2>試行ごとの結果</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>試行</th><th>点数</th><th>E2E</th><th>チェック</th><th>コード追加行</th><th>テスト追加行</th>
        <th>費用</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th><th>拒否された操作</th><th>使われた Skill</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>所見</h2>
  <div class="box"><ul>{observations}</ul></div>

  <h2>試行の詳細</h2>
  {''.join(findings)}

  <div class="cols">
    <section><h2>採点方法</h2><div class="box">{NOTES['scoring_html']}</div></section>
    <section><h2>この結果の制約</h2><div class="box"><ul>{limits}</ul></div></section>
  </div>

  <h2>次の対応</h2>
  <div class="box"><ul>{nexts}</ul></div>{supplement_report.html_section("W1", scores, DIR)}{two_axis.html_section("W1", DIR)}</main>
</body>
</html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.html'}")

    # 同じ内容の Markdown（GitHub 上でそのまま読める形）
    out = [
        "# 開発ワークフロー PoC — W1 小さな変更", "",
        f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 poc/PLAN.md §5.1", "",
        "> HTML 版: [report.html](report.html)（同じデータから `poc/scripts/report_w1.py` で生成）", "",
    ]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点）", "",
            "| 候補 | 回数 | 合計 / 100 | 受け入れ / 50 | 時間・費用 / 30 | 過剰さ / 20 | 平均費用 | 平均時間（分） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        name = f"**{LABEL[c]}**" if ranked and c == ranked[0] else LABEL[c]
        out.append(f"| {name} | {len(by_cand[c])} | {mean(c, 'total')} | {mean(c, 'acceptance')} | {mean(c, 'efficiency')} | "
                   f"{mean(c, 'overengineering')} | ${mean_fact(c, 'cost_usd'):.2f} | {mean_fact(c, 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## 試行ごとの結果", "",
            "| 試行 | 点数 | E2E | チェック | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            f = s["facts"]
            t = trials[s["trial"]]
            checks = " ".join(f"{k} {'✅' if t['checks'][k]['pass'] else '❌'}" for k in ("typecheck", "test", "build"))
            out.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {f['e2e_pass']}/{f['e2e_total']} | {checks} | {f['code_added']} | "
                       f"{f['test_added']} | ${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} | {f['turns']} | {f['subagents']} | "
                       f"{f['denials']} | {cell(', '.join(f['skills_used']) or '—')} |")
    out += ["", "## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 試行の詳細", ""]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            t = trials[s["trial"]]
            out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["trial"], "")), ""]
            failed = [x for x in t["e2e"] if not x["pass"]]
            if failed:
                out += ["不合格の受け入れテスト:", ""]
                out += [f"- {x['name']}: `{x['detail'][:160].replace(chr(10), ' ')}`" for x in failed]
                out.append("")
            out += ["変更ファイル:", ""]
            out += [f"- `{f['path']}` +{f['added']} −{f['deleted']}（{f['kind']}）" for f in t["diff"]["files"]] or ["- なし"]
            out += ["", "コミット:", ""]
            out += [f"- `{x}`" for x in t["diff"]["commits"]] or ["- なし"]
            out.append("")
    out += ["## 採点方法", "", md(NOTES["scoring_html"]), ""]
    out += ["## この結果の制約", ""] + [f"- {md(x)}" for x in NOTES["limitations"]]
    out += ["", "## 次の対応", ""] + [f"- {md(x)}" for x in NOTES["next"]]
    supp = supplement_report.md_section("W1", scores, DIR, md, cell)
    if supp:
        out += [""] + supp
    out += [""] + two_axis.md_section("W1", DIR)[:-1]  # 2 本立ての点数（PLAN.md §4.4）。既存の節の後ろに足す
    (DIR / "report.md").write_text("\n".join(out) + "\n")
    print(f"wrote {DIR / 'report.md'}")


if __name__ == "__main__":
    main()
