#!/usr/bin/env python3
"""W2 の結果から HTML レポート（docs/poc/results/workflow/W2/report.html）を作る。"""
import html
import re
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W2"
ITEM_LABEL = {"conventions": "規約", "design": "設計", "security": "認可・入力", "tests": "テスト", "scope": "過不足"}
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
    """notes.json の HTML 断片を GitHub で読める Markdown に変える（report_w1.py と同じ）。"""
    s = str(s)
    s = re.sub(r"<code>(.*?)</code>", lambda m: "`" + m.group(1) + "`", s, flags=re.S)
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
          <div><dt>受け入れ</dt><dd>{mean(c, 'acceptance')} / 40</dd></div>
          <div><dt>介入</dt><dd>{mean(c, 'intervention')} / 20</dd></div>
          <div><dt>設計・テスト</dt><dd>{mean(c, 'quality')} / 25</dd></div>
          <div><dt>費用</dt><dd>{mean(c, 'cost')} / 15</dd></div>
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
          <td class="num">{f['interventions']} / {f['questions']}</td>
          <td class="num">{s['quality']}</td>
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
            <div><small>受け入れ {mean(c, 'acceptance')} / 40</small>{bar(mean(c, 'acceptance'), 40, 'a')}</div>
            <div><small>介入 {mean(c, 'intervention')} / 20</small>{bar(mean(c, 'intervention'), 20, 'b')}</div>
            <div><small>設計・テスト {mean(c, 'quality')} / 25</small>{bar(mean(c, 'quality'), 25, 'c')}</div>
            <div><small>費用 {mean(c, 'cost')} / 15</small>{bar(mean(c, 'cost'), 15, 'd')}</div>
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
        <p class="sub">ブラインドレビュー（{' ・ '.join(f'{ITEM_LABEL[k]} {v}' for k, v in s['quality_detail'].items()) or '未実施'}）</p>
        <ul class="files">{''.join(f'<li>{e(x)}</li>' for x in s['quality_comments'])}</ul>
        {'<p class="warn">不合格の受け入れテスト</p><ul>' + fail_html + '</ul>' if failed else ''}
        <p class="sub">変更ファイル</p><ul class="files">{files or '<li>なし</li>'}</ul>
        <p class="sub">コミット</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in t['diff']['commits']) or '<li>なし</li>'}</ul>
      </details>""")

    review_rows = "".join(
        f"<tr><th scope=\"row\">{e(LABEL[c])}</th>"
        + "".join(f"<td class=\"num\">{round(statistics.mean(s['quality_detail'][k] for s in by_cand[c]), 1) if all(s['quality_detail'] for s in by_cand[c]) else '—'}</td>" for k in ITEM_LABEL)
        + "</tr>" for c in cands)
    gap_html = ("<p class=\"sub\">採点者 2 名の差が 3 点以上だった項目: "
                + "、".join(f"{e(g['trial'])} の{ITEM_LABEL[g['item']]}（{'・'.join(map(str, g['scores']))}）" for g in gaps)
                + "</p>") if gaps else "<p class=\"sub\">採点者 2 名の差が 3 点以上の項目はありませんでした。</p>"
    observations = "".join(f"<li>{x}</li>" for x in NOTES["observations"])
    limits = "".join(f"<li>{x}</li>" for x in NOTES["limitations"])
    decisions = "".join(f"<li>{x}</li>" for x in NOTES["decisions"])
    nexts = "".join(f"<li>{x}</li>" for x in NOTES["next"])

    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W2 結果</title>
<style>
:root {{
  --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df;
  --accent:#2f5bd3; --a:#2f5bd3; --b:#1f8a70; --c:#b7791f; --d:#8e44ad; --ok:#1f8a70; --ng:#c0392b; --top:#eef3ff;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
    --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --ok:#4cc39f; --ng:#ff7b6b; --top:#1f2738;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
  --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --ok:#4cc39f; --ng:#ff7b6b; --top:#1f2738;
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
.bd-bars {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
.bd-name {{ font-weight:600; font-size:14px; }}
.bar {{ height:8px; background:var(--line); border-radius:4px; overflow:hidden; margin-top:2px; }}
.bar span {{ display:block; height:100%; background:var(--a); }}
.bar.b span {{ background:var(--b); }} .bar.c span {{ background:var(--c); }} .bar.d span {{ background:var(--d); }}
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
  <h1>開発ワークフロー PoC — W2 仕様が明確な機能追加</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 docs/poc/PLAN.md §5.1</p>

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
        <th>試行</th><th>点数</th><th>E2E</th><th>チェック</th><th>介入 / 質問</th><th>設計・テスト</th><th>コード追加行</th><th>テスト追加行</th>
        <th>費用</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th><th>拒否された操作</th><th>使われた Skill</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>ブラインドレビューの項目別平均（0〜5）</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>候補</th>{''.join(f'<th>{v}</th>' for v in ITEM_LABEL.values())}</tr></thead>
      <tbody>{review_rows}</tbody>
    </table>
  </div>
  {gap_html}

  <h2>所見</h2>
  <div class="box"><ul>{observations}</ul></div>

  <h2>試行の詳細</h2>
  {''.join(findings)}

  <div class="cols">
    <section><h2>採点方法</h2><div class="box">{NOTES['scoring_html']}</div></section>
    <section><h2>この結果の制約</h2><div class="box"><ul>{limits}</ul></div></section>
  </div>

  <h2>判断の記録</h2>
  <div class="box"><ul>{decisions}</ul></div>

  <h2>次の対応</h2>
  <div class="box"><ul>{nexts}</ul></div>
</main>
</body>
</html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.html'}")

    # 同じ内容の Markdown（GitHub 上でそのまま読める形）
    out = [
        "# 開発ワークフロー PoC — W2 仕様が明確な機能追加", "",
        f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 docs/poc/PLAN.md §5.1", "",
        "> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w2.py` で生成）", "",
    ]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点）", "",
            "| 候補 | 回数 | 合計 / 100 | 受け入れ / 40 | 介入 / 20 | 設計・テスト / 25 | 費用 / 15 | 平均費用 | 平均時間（分） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        name = f"**{LABEL[c]}**" if ranked and c == ranked[0] else LABEL[c]
        out.append(f"| {name} | {len(by_cand[c])} | {mean(c, 'total')} | {mean(c, 'acceptance')} | {mean(c, 'intervention')} | "
                   f"{mean(c, 'quality')} | {mean(c, 'cost')} | ${mean_fact(c, 'cost_usd'):.2f} | {mean_fact(c, 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## 試行ごとの結果", "",
            "| 試行 | 点数 | E2E | チェック | 介入 / 質問 | 設計・テスト | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            f = s["facts"]
            t = trials[s["trial"]]
            checks = " ".join(f"{k} {'✅' if t['checks'][k]['pass'] else '❌'}" for k in ("typecheck", "test", "build"))
            out.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {f['e2e_pass']}/{f['e2e_total']} | {checks} | "
                       f"{f['interventions']} / {f['questions']} | {s['quality']} | {f['code_added']} | {f['test_added']} | "
                       f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} | {f['turns']} | {f['subagents']} | "
                       f"{f['denials']} | {cell(', '.join(f['skills_used']) or '—')} |")
    out += ["", "## ブラインドレビューの項目別平均（0〜5）", "",
            "| 候補 | " + " | ".join(ITEM_LABEL.values()) + " |", "|---|" + "---:|" * len(ITEM_LABEL)]
    for c in cands:
        vals = [str(round(statistics.mean(s["quality_detail"][k] for s in by_cand[c]), 1)) if all(s["quality_detail"] for s in by_cand[c]) else "—"
                for k in ITEM_LABEL]
        out.append(f"| {LABEL[c]} | " + " | ".join(vals) + " |")
    out += ["", re.sub(r"<[^>]+>", "", gap_html), ""]
    out += ["## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 試行の詳細", ""]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            t = trials[s["trial"]]
            out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["trial"], "")), ""]
            detail = " ・ ".join(f"{ITEM_LABEL[k]} {v}" for k, v in s["quality_detail"].items()) or "未実施"
            out += [f"ブラインドレビュー（{detail}）:", ""] + [f"- {cell(x)}" for x in s["quality_comments"]] + [""]
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
    out += ["", "## 判断の記録", ""] + [
        "- " + "\n".join(l if i == 0 or l.startswith("  ") else "  " + l
                         for i, l in enumerate(re.sub(r"\n+- ", "\n  - ", md(x)).replace("\n\n", "\n").split("\n")))
        for x in NOTES["decisions"]]
    out += ["", "## 次の対応", ""] + [f"- {md(x)}" for x in NOTES["next"]]
    (DIR / "report.md").write_text("\n".join(out) + "\n")
    print(f"wrote {DIR / 'report.md'}")


if __name__ == "__main__":
    main()
