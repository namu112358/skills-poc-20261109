#!/usr/bin/env python3
"""W6 の結果から、HTML レポート（W6/report.html）と同じ内容の Markdown（W6/report.md）を作る。

データ: W6/scores.json（score_w6.py）、W6/<試行ID>.json（grade_w6.py）、W6/blind/scores.json（blind_w6.py）、
W6/notes.json（採点者の所見・判断の記録）。
"""
import html
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W6"
NOTES = json.loads((DIR / "notes.json").read_text())
LABEL = {
    "baseline": "baseline（候補なし）",
    "superpowers": "Superpowers",
    "feature-dev": "Feature Dev",
    "compound-engineering": "Compound Engineering",
    "gstack": "gstack",
}
ORDER = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]
PARTS = [("ui", "UI チェックリスト", 40, "a"), ("evidence", "検証の証跡", 15, "b"), ("pr", "PR の完成度", 30, "c"),
         ("cost", "費用", 15, "d")]
ITEMS = [f"U{i}" for i in range(1, 9)]
ITEM_LABEL = {"U1": "表示・並び順", "U2": "空状態", "U3": "追加・二重送信", "U4": "入力エラー", "U5": "通信エラー",
              "U6": "ステータス変更", "U7": "レスポンシブ", "U8": "導線・ラベル"}


def e(s):
    return html.escape(str(s))


def md(s):
    """notes.json の HTML 断片を GitHub で読める Markdown に変える。"""
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
    scores = json.loads((DIR / "scores.json").read_text())["scores"]
    trials = {s["trial"]: json.loads((DIR / f"{s['trial']}.json").read_text()) for s in scores}
    by_cand = {}
    for s in scores:
        by_cand.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by_cand]

    def mean(c, key):
        return round(statistics.mean(s[key] for s in by_cand[c]), 1)

    def mean_fact(c, key):
        return statistics.mean(s["facts"][key] for s in by_cand[c])

    def items_ok(c):
        return sum(1 for s in by_cand[c] for u in ITEMS if s["items"][u])

    ranked = sorted([c for c in cands if c != "baseline"], key=lambda c: -mean(c, "total"))
    best = max((mean(c, "total") for c in ranked), default=None)
    tops = {c for c in ranked if mean(c, "total") == best}
    trial_rows = [(c, s) for c in cands for s in sorted(by_cand[c], key=lambda s: s["run"])]

    def pill(cls, text):
        return f'<span class="pill {cls}">{e(text)}</span>'

    # ---------- HTML ----------
    cards = []
    for c in cands:
        runs = by_cand[c]
        parts = "".join(f"<div><dt>{lab}</dt><dd>{mean(c, k)} / {mx}</dd></div>" for k, lab, mx, _ in PARTS)
        cards.append(f"""
      <article class="card{' top' if c in tops else ''}">
        <header><h3>{e(LABEL[c])}</h3><span class="runs">{len(runs)} 回</span></header>
        <p class="score"><strong>{mean(c, 'total')}</strong><small> / 100</small></p>
        <dl>{parts}</dl>
        <p class="meta">不具合なしの項目 {items_ok(c)} / {8 * len(runs)}<br>
        平均 ${mean_fact(c, 'cost_usd'):.2f} ・ {mean_fact(c, 'elapsed_seconds') / 60:.1f} 分</p>
      </article>""")

    breakdown = []
    for c in cands:
        bars = "".join(f"<div><small>{lab} {mean(c, k)} / {mx}</small>{bar(mean(c, k), mx, cls)}</div>" for k, lab, mx, cls in PARTS)
        breakdown.append(f'<div class="bd-row"><span class="bd-name">{e(LABEL[c])}</span><div class="bd-bars">{bars}</div></div>')

    item_rows = "".join(
        f"<tr><th scope=\"row\">{e(LABEL[c])}</th>"
        + "".join(f"<td class=\"num\">{sum(1 for s in by_cand[c] if s['items'][u])} / {len(by_cand[c])}</td>" for u in ITEMS)
        + "</tr>" for c in cands)

    rows = []
    for c, s in trial_rows:
        f = s["facts"]
        items = " ".join(pill("ok" if s["items"][u] else "ng", u) for u in ITEMS)
        ev = " ".join(pill("ok" if v == 5 else ("warn" if v else "ng"), f"{k} {v}") for k, v in s["evidence_points"].items())
        checks = " ".join(pill("ok" if f["checks"][k] else "ng", k) for k in ("typecheck", "test", "build"))
        pr = s["pr_parts"]
        rows.append(f"""
        <tr>
          <th scope="row">{e(LABEL[c])} #{s['run']}</th>
          <td class="num">{s['total']}</td>
          <td>{items}</td>
          <td>{ev}</td>
          <td class="num">{pr['description']} / {pr['tests']} / {pr['ci']}</td>
          <td>{checks}</td>
          <td class="num">{f['interventions']} / {f['questions']}</td>
          <td class="num">{f['code_added']}</td>
          <td class="num">{f['test_added']}</td>
          <td class="num">${f['cost_usd']:.2f}</td>
          <td class="num">{f['elapsed_seconds'] / 60:.1f}</td>
          <td class="num">{f['turns']}</td>
          <td class="num">{f['subagents']}</td>
          <td class="num">{f['denials']}</td>
          <td>{e(', '.join(f['skills_used']) or '—')}</td>
        </tr>""")

    findings = []
    for c, s in trial_rows:
        t = trials[s["trial"]]
        f = s["facts"]
        note = NOTES["trials"].get(s["trial"], "")
        failed = [x for x in t["e2e"] if not x["pass"]]
        fail_html = "".join(f"<li>{e(x['name'])}<br><code>{e(x['detail'][:160])}</code></li>" for x in failed)
        files = "".join(
            f"<li><code>{e(x['path'])}</code> +{x['added']} −{x['deleted']} <span class=\"kind\">{e(x['kind'])}</span></li>"
            for x in t["diff"]["files"])
        rev = s["pr_parts"]["review"]
        rev_html = (f"<p class=\"sub\">PR の説明のブラインドレビュー（{rev['code']}）: 採点者 1 = {rev['totals'][0]}、採点者 2 = {rev['totals'][1]}（各 12 点満点）</p>"
                    f"<ul class=\"files\">{''.join(f'<li>{e(x)}</li>' for x in rev['comments'] if x)}</ul>") if rev else ""
        findings.append(f"""
      <details>
        <summary><strong>{e(LABEL[c])} #{s['run']}</strong> — {s['total']} 点</summary>
        <p>{note}</p>
        {'<p class="warn">不合格の隠しの E2E</p><ul>' + fail_html + '</ul>' if failed else ''}
        {rev_html}
        <p class="sub">変更ファイル</p><ul class="files">{files or '<li>なし</li>'}</ul>
        <p class="sub">コミット</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in t['diff']['commits']) or '<li>なし</li>'}</ul>
      </details>""")

    def lis(key):
        return "".join(f"<li>{x}</li>" for x in NOTES[key])

    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W6 結果</title>
<style>
:root {{
  --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df;
  --accent:#2f5bd3; --a:#2f5bd3; --b:#1f8a70; --c:#b7791f; --d:#8e44ad; --ok:#1f8a70; --ng:#c0392b; --warn:#b7791f; --top:#eef3ff;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
    --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --ok:#4cc39f; --ng:#ff7b6b; --warn:#e0a84a; --top:#1f2738;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033;
  --accent:#7c9cff; --a:#7c9cff; --b:#4cc39f; --c:#e0a84a; --d:#c39bd3; --ok:#4cc39f; --ng:#ff7b6b; --warn:#e0a84a; --top:#1f2738;
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
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
table.wide {{ min-width:1000px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.pill {{ display:inline-block; font-size:11px; padding:0 6px; border-radius:999px; margin-right:2px; white-space:nowrap; }}
.pill.ok {{ color:var(--ok); border:1px solid var(--ok); }} .pill.ng {{ color:var(--ng); border:1px solid var(--ng); }}
.pill.warn {{ color:var(--warn); border:1px solid var(--warn); }}
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
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; overflow-wrap:anywhere; }}
.box {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 18px; }}
@media (max-width:640px) {{
  .bd-row {{ grid-template-columns:1fr; }} .bd-bars {{ grid-template-columns:1fr 1fr; }}
}}
</style>
</head>
<body>
<main>
  <h1>開発ワークフロー PoC — W6 UI 実装からブラウザ検証・PR 作成まで</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 docs/poc/PLAN.md §5.1</p>

  <section class="summary">{''.join(f'<p>{x}</p>' for x in NOTES['summary'])}</section>

  <h2>課題</h2>
  <div class="box">{NOTES['task_html']}</div>

  <h2>結果の概要（平均点）</h2>
  <div class="cards">{''.join(cards)}</div>

  <h2>配点ごとの内訳</h2>
  <div class="box">{''.join(breakdown)}</div>

  <h2>UI チェックリストの項目ごとの結果</h2>
  <p class="lead">その項目に不具合が残っていなかった試行の数（候補ごとの試行数のうち）。</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>候補</th>{''.join(f'<th>{u} {e(ITEM_LABEL[u])}</th>' for u in ITEMS)}</tr></thead>
      <tbody>{item_rows}</tbody>
    </table>
  </div>

  <h2>試行ごとの結果</h2>
  <div class="table-wrap">
    <table class="wide">
      <thead><tr>
        <th>試行</th><th>点数</th><th>UI チェックリスト</th><th>証跡</th><th>PR（説明 / テスト / CI）</th><th>チェック</th>
        <th>介入 / 質問</th><th>コード追加行</th><th>テスト追加行</th><th>費用</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th>
        <th>拒否された操作</th><th>使われた Skill</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>所見</h2>
  <div class="box"><ul>{lis('observations')}</ul></div>

  <h2>試行の詳細</h2>
  {''.join(findings)}

  <h2>採点方法</h2>
  <div class="box">{NOTES['scoring_html']}</div>

  <h2>この結果の制約</h2>
  <div class="box"><ul>{lis('limitations')}</ul></div>

  <h2>判断の記録</h2>
  <div class="box"><ul>{lis('decisions')}</ul></div>

  <h2>試行間の独立性の確認結果</h2>
  <div class="box"><p>{NOTES['isolation']}</p></div>

  <h2>次の対応</h2>
  <div class="box"><ul>{lis('next')}</ul></div>
</main>
</body>
</html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.html'}")

    # ---------- Markdown（GitHub 上でそのまま読める形。HTML と同じデータ） ----------
    out = [
        "# 開発ワークフロー PoC — W6 UI 実装からブラウザ検証・PR 作成まで", "",
        f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 docs/poc/PLAN.md §5.1", "",
        "> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w6.py` で生成）", "",
    ]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点）", "",
            "| 候補 | 回数 | 合計 / 100 | UI チェックリスト / 40 | 証跡 / 15 | PR / 30 | 費用 / 15 | 不具合なしの項目 | 平均費用 | 平均時間（分） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        name = f"**{LABEL[c]}**" if c in tops else LABEL[c]
        n = len(by_cand[c])
        out.append(f"| {name} | {n} | {mean(c, 'total')} | {mean(c, 'ui')} | {mean(c, 'evidence')} | {mean(c, 'pr')} | {mean(c, 'cost')} | "
                   f"{items_ok(c)} / {8 * n} | ${mean_fact(c, 'cost_usd'):.2f} | {mean_fact(c, 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## UI チェックリストの項目ごとの結果", "",
            "その項目に不具合が残っていなかった試行の数（候補ごとの試行数のうち）。", "",
            "| 候補 | " + " | ".join(f"{u} {ITEM_LABEL[u]}" for u in ITEMS) + " |",
            "|---|" + "---:|" * len(ITEMS)]
    for c in cands:
        n = len(by_cand[c])
        out.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by_cand[c] if s['items'][u])} / {n}" for u in ITEMS) + " |")
    out += ["", "## 試行ごとの結果", "",
            "UI チェックリスト: ✅ = 不具合なし、❌ = 不具合が残った項目。証跡: E1 ブラウザ操作 / E2 スクリーンショット / E3 スマートフォン幅（各 5 点）。"
            "PR: 説明（12）/ テスト（8）/ CI（10）。", "",
            "| 試行 | 点数 | UI チェックリスト | 証跡 | PR（説明 / テスト / CI） | チェック | 介入 / 質問 | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |",
            "|---|---:|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c, s in trial_rows:
        f = s["facts"]
        checks = " ".join(f"{k} {'✅' if f['checks'][k] else '❌'}" for k in ("typecheck", "test", "build"))
        items = " ".join(f"{u}{'✅' if s['items'][u] else '❌'}" for u in ITEMS)
        ev = " ".join(f"{k} {v}" for k, v in s["evidence_points"].items())
        pr = s["pr_parts"]
        out.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {items} | {ev} | {pr['description']} / {pr['tests']} / {pr['ci']} | {checks} | "
                   f"{f['interventions']} / {f['questions']} | {f['code_added']} | {f['test_added']} | ${f['cost_usd']:.2f} | "
                   f"{f['elapsed_seconds'] / 60:.1f} | {f['turns']} | {f['subagents']} | {f['denials']} | {cell(', '.join(f['skills_used']) or '—')} |")
    out += ["", "## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 試行の詳細", ""]
    for c, s in trial_rows:
        t = trials[s["trial"]]
        out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["trial"], "")), ""]
        failed = [x for x in t["e2e"] if not x["pass"]]
        if failed:
            out += ["不合格の隠しの E2E:", ""] + [f"- {x['name']}: `{x['detail'][:160].replace(chr(10), ' ')}`" for x in failed] + [""]
        rev = s["pr_parts"]["review"]
        if rev:
            out += [f"PR の説明のブラインドレビュー（{rev['code']}）: 採点者 1 = {rev['totals'][0]}、採点者 2 = {rev['totals'][1]}（各 12 点満点）", ""]
            out += [f"- {cell(x)}" for x in rev["comments"] if x] + [""]
        out += ["変更ファイル:", ""]
        out += [f"- `{x['path']}` +{x['added']} −{x['deleted']}（{x['kind']}）" for x in t["diff"]["files"]] or ["- なし"]
        out += ["", "コミット:", ""]
        out += [f"- `{x}`" for x in t["diff"]["commits"]] or ["- なし"]
        out.append("")
    out += ["## 採点方法", "", md(NOTES["scoring_html"]), ""]
    out += ["## この結果の制約", ""] + [f"- {md(x)}" for x in NOTES["limitations"]]
    out += ["", "## 判断の記録", ""] + [
        "- " + "\n".join(l if i == 0 or l.startswith("  ") else "  " + l
                         for i, l in enumerate(re.sub(r"\n+- ", "\n  - ", md(x)).replace("\n\n", "\n").split("\n")))
        for x in NOTES["decisions"]]
    out += ["", "## 試行間の独立性の確認結果", "", md(NOTES["isolation"]), ""]
    out += ["## 次の対応", ""] + [f"- {md(x)}" for x in NOTES["next"]]
    (DIR / "report.md").write_text("\n".join(out) + "\n")
    print(f"wrote {DIR / 'report.md'}")


if __name__ == "__main__":
    main()
