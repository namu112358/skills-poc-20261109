#!/usr/bin/env python3
"""W4 の結果から HTML レポート（docs/poc/results/workflow/W4/report.html）と同じ内容の report.md を作る（report_w2.py を W4 の配点に合わせたもの）。"""
import html
import re
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import two_axis  # noqa: E402  2 本立ての点数（PLAN.md §4.4）を主表示にする

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W4"
IMPACT_LABEL = {
    "1": "マイグレーション", "2": "既存データの移行", "3": "初期データ", "4": "型と読み出し", "5": "一覧の閲覧範囲",
    "6": "1 件の閲覧範囲", "7": "作成時の所属・作成者", "8": "担当者の規則", "9": "所属変更の権限", "10": "チームの処理",
    "11": "チームの API", "12": "一覧画面", "13": "詳細画面", "14": "チーム画面・ヘッダー", "15": "既存テストの更新",
    "16": "新しいテストと文書",
}
ITEM_LABEL = {"A": "認可: 一貫性", "B": "認可: 入力と境界", "D1": "設計: 比較の有無", "D2": "設計: 選択肢", "D3": "設計: トレードオフ",
              "D4": "設計: 決定と実装"}
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


def budget_compare(by_cand):
    """1 回目（打ち切り額が見える flag）と 2 回目（見えない watch）の比較の行。"""
    rows = []
    for c, runs in by_cand.items():
        r = {s["budget_mode"]: s for s in runs}
        if "flag" in r and "watch" in r:
            f, w = r["flag"], r["watch"]
            rows.append({
                "candidate": c,
                "cost": (f["facts"]["cost_usd"], w["facts"]["cost_usd"]),
                "minutes": (f["facts"]["elapsed_seconds"] / 60, w["facts"]["elapsed_seconds"] / 60),
                "turns": (f["facts"]["turns"], w["facts"]["turns"]),
                "subagents": (f["facts"]["subagents"], w["facts"]["subagents"]),
                "total": (f["total"], w["total"]),
                "mentions": (len(f["facts"]["budget_mentions"]), len(w["facts"]["budget_mentions"])),
            })
    return rows


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
          <div><dt>影響箇所</dt><dd>{mean(c, 'impact')} / 30</dd></div>
          <div><dt>受け入れ</dt><dd>{mean(c, 'acceptance')} / 30</dd></div>
          <div><dt>認可</dt><dd>{mean(c, 'authz')} / 20</dd></div>
          <div><dt>設計案の比較</dt><dd>{mean(c, 'design')} / 20</dd></div>
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
          <td class="num">{f['authz_pass']}/{f['authz_total']}</td>
          <td class="num">{s['impact']}</td>
          <td class="num">{s['design']}</td>
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

    # 配点の内訳（棒）
    breakdown = []
    for c in cands:
        breakdown.append(f"""
        <div class="bd-row">
          <span class="bd-name">{e(LABEL[c])}</span>
          <div class="bd-bars">
            <div><small>影響箇所 {mean(c, 'impact')} / 30</small>{bar(mean(c, 'impact'), 30, 'a')}</div>
            <div><small>受け入れ {mean(c, 'acceptance')} / 30</small>{bar(mean(c, 'acceptance'), 30, 'b')}</div>
            <div><small>認可 {mean(c, 'authz')} / 20</small>{bar(mean(c, 'authz'), 20, 'c')}</div>
            <div><small>設計案の比較 {mean(c, 'design')} / 20</small>{bar(mean(c, 'design'), 20, 'd')}</div>
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
        <p class="sub">コードのレビュー（影響箇所 {s['impact']} / 30、{' ・ '.join(f'{ITEM_LABEL[k]} {v}' for k, v in s['authz_detail'].items() if k in ITEM_LABEL) or '未実施'}）</p>
        <ul class="files">{''.join(f'<li>{e(x)}</li>' for x in s['code_comments'])}</ul>
        <p class="sub">設計のレビュー（{' ・ '.join(f'{ITEM_LABEL[k]} {v}' for k, v in s['design_detail'].items()) or '未実施'}）</p>
        <ul class="files">{''.join(f'<li>{e(x)}</li>' for x in s['design_comments'])}</ul>
        {'<p class="warn">不合格の認可プローブ</p><ul>' + ''.join(f'<li>{e(x)}</li>' for x in s['facts']['authz_failed']) + '</ul>' if s['facts']['authz_failed'] else ''}
        {'<p class="warn">不合格の受け入れテスト</p><ul>' + fail_html + '</ul>' if failed else ''}
        <p class="sub">変更ファイル</p><ul class="files">{files or '<li>なし</li>'}</ul>
        <p class="sub">コミット</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in t['diff']['commits']) or '<li>なし</li>'}</ul>
      </details>""")

    def item_mean(c, k):
        src = "design_detail" if k.startswith("D") else "authz_detail"
        vals = [s[src].get(k) for s in by_cand[c]]
        return round(statistics.mean(vals), 1) if all(v is not None for v in vals) else "—"

    def impact_mean(c, k):
        vals = [s["impact_detail"].get(k) for s in by_cand[c]]
        return round(statistics.mean(vals), 2) if all(v is not None for v in vals) else "—"

    review_rows = "".join(
        f"<tr><th scope=\"row\">{e(LABEL[c])}</th>"
        + "".join(f"<td class=\"num\">{item_mean(c, k)}</td>" for k in ITEM_LABEL)
        + "</tr>" for c in cands)
    impact_rows = "".join(
        f"<tr><th scope=\"row\">{e(k)}. {e(v)}</th>"
        + "".join(f"<td class=\"num\">{impact_mean(c, k)}</td>" for c in cands)
        + "</tr>" for k, v in IMPACT_LABEL.items())
    def gap_label(item):
        kind, k = item.split(":")
        return f"影響箇所 {k}（{IMPACT_LABEL[k]}）" if kind == "impact" else ITEM_LABEL[k]

    gap_html = ("<p class=\"sub\">採点者 2 名の差が大きかった項目（影響箇所は 1、ほかは 3 点以上）: "
                + "、".join(f"{e(g['trial'])} の{e(gap_label(g['item']))}（{'・'.join(map(str, g['scores']))}）" for g in gaps)
                + "</p>") if gaps else "<p class=\"sub\">採点者 2 名の差が大きい項目（影響箇所は 1、ほかは 3 点以上）はありませんでした。</p>"
    observations = "".join(f"<li>{x}</li>" for x in NOTES["observations"])
    limits = "".join(f"<li>{x}</li>" for x in NOTES["limitations"])
    decisions = "".join(f"<li>{x}</li>" for x in NOTES["decisions"])
    nexts = "".join(f"<li>{x}</li>" for x in NOTES["next"])

    bc = budget_compare(by_cand)
    bc_rows = "".join(
        f"<tr><th scope=\"row\">{e(LABEL[r['candidate']])}</th><td>${r['cost'][0]:.2f} → ${r['cost'][1]:.2f}</td>"
        f"<td>{r['minutes'][0]:.1f} → {r['minutes'][1]:.1f}</td><td>{r['turns'][0]} → {r['turns'][1]}</td>"
        f"<td>{r['subagents'][0]} → {r['subagents'][1]}</td><td>{r['total'][0]} → {r['total'][1]}</td>"
        f"<td>{r['mentions'][0]} → {r['mentions'][1]}</td></tr>" for r in bc)
    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W4 結果</title>
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
  <h1>開発ワークフロー PoC — W4 既存コードを横断する大きな変更</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 docs/poc/PLAN.md §5.1</p>

  <section class="summary">
    {''.join(f'<p>{x}</p>' for x in NOTES['summary'])}
  </section>

  {two_axis.html_section("W4")}

  <h2>1 回目（打ち切り額が見える）と 2 回目（見えない）の比較</h2>
  <p class="sub">{e(NOTES.get("budget_compare_note", ""))}</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>候補</th><th>費用（1 回目 → 2 回目）</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th><th>点数</th><th>打ち切り額・予算への言及</th></tr></thead>
      <tbody>{bc_rows}</tbody>
    </table>
  </div>
  <p>{e(NOTES.get("isolation", ""))}</p>

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
        <th>試行</th><th>点数</th><th>E2E</th><th>チェック</th><th>認可プローブ</th><th>影響箇所</th><th>設計案</th><th>介入 / 質問</th><th>コード追加行</th><th>テスト追加行</th>
        <th>費用</th><th>時間（分）</th><th>ターン</th><th>サブエージェント</th><th>拒否された操作</th><th>使われた Skill</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>影響箇所ごとの対応（0〜1、採点者 2 名・2 回の平均）</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>影響箇所</th>{''.join(f'<th>{e(LABEL[c])}</th>' for c in cands)}</tr></thead>
      <tbody>{impact_rows}</tbody>
    </table>
  </div>

  <h2>認可・設計のレビューの項目別平均（0〜5）</h2>
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
        "# 開発ワークフロー PoC — W4 既存コードを横断する大きな変更", "",
        f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 docs/poc/PLAN.md §5.1", "",
        "> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w4.py` で生成）", "",
    ]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += two_axis.md_section("W4")
    out += ["## 1 回目（打ち切り額が見える）と 2 回目（見えない）の比較", "", md(NOTES.get("budget_compare_note", "")), "",
            "| 候補 | 費用（1 回目 → 2 回目） | 時間（分） | ターン | サブエージェント | 点数 | 打ち切り額・予算への言及 |",
            "|---|---|---|---|---|---|---|"]
    for r in bc:
        out.append(f"| {LABEL[r['candidate']]} | ${r['cost'][0]:.2f} → ${r['cost'][1]:.2f} | {r['minutes'][0]:.1f} → {r['minutes'][1]:.1f} | "
                   f"{r['turns'][0]} → {r['turns'][1]} | {r['subagents'][0]} → {r['subagents'][1]} | {r['total'][0]} → {r['total'][1]} | "
                   f"{r['mentions'][0]} → {r['mentions'][1]} |")
    out += ["", md(NOTES.get("isolation", "")), ""]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点）", "",
            "| 候補 | 回数 | 合計 / 100 | 影響箇所 / 30 | 受け入れ / 30 | 認可 / 20 | 設計案の比較 / 20 | 平均費用 | 平均時間（分） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        name = f"**{LABEL[c]}**" if ranked and c == ranked[0] else LABEL[c]
        out.append(f"| {name} | {len(by_cand[c])} | {mean(c, 'total')} | {mean(c, 'impact')} | {mean(c, 'acceptance')} | "
                   f"{mean(c, 'authz')} | {mean(c, 'design')} | ${mean_fact(c, 'cost_usd'):.2f} | {mean_fact(c, 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## 試行ごとの結果", "",
            "| 試行 | 点数 | E2E | チェック | 認可プローブ | 影響箇所 | 設計案 | 介入 / 質問 | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            f = s["facts"]
            t = trials[s["trial"]]
            checks = " ".join(f"{k} {'✅' if t['checks'][k]['pass'] else '❌'}" for k in ("typecheck", "test", "build"))
            out.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {f['e2e_pass']}/{f['e2e_total']} | {checks} | "
                       f"{f['authz_pass']}/{f['authz_total']} | {s['impact']} | {s['design']} | "
                       f"{f['interventions']} / {f['questions']} | {f['code_added']} | {f['test_added']} | "
                       f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} | {f['turns']} | {f['subagents']} | "
                       f"{f['denials']} | {cell(', '.join(f['skills_used']) or '—')} |")
    out += ["", "## 影響箇所ごとの対応（0〜1、採点者 2 名・2 回の平均）", "",
            "| 影響箇所 | " + " | ".join(LABEL[c] for c in cands) + " |", "|---|" + "---:|" * len(cands)]
    for k, v in IMPACT_LABEL.items():
        out.append(f"| {k}. {v} | " + " | ".join(str(impact_mean(c, k)) for c in cands) + " |")
    out += ["", "## 認可・設計のレビューの項目別平均（0〜5）", "",
            "| 候補 | " + " | ".join(ITEM_LABEL.values()) + " |", "|---|" + "---:|" * len(ITEM_LABEL)]
    for c in cands:
        out.append(f"| {LABEL[c]} | " + " | ".join(str(item_mean(c, k)) for k in ITEM_LABEL) + " |")
    out += ["", re.sub(r"<[^>]+>", "", gap_html), ""]
    out += ["## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 試行の詳細", ""]
    for c in cands:
        for s in sorted(by_cand[c], key=lambda s: s["run"]):
            t = trials[s["trial"]]
            out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["trial"], "")), ""]
            detail = " ・ ".join(f"{ITEM_LABEL[k]} {v}" for k, v in s["authz_detail"].items() if k in ITEM_LABEL) or "未実施"
            out += [f"コードのレビュー（影響箇所 {s['impact']} / 30、{detail}）:", ""] + [f"- {cell(x)}" for x in s["code_comments"]] + [""]
            detail = " ・ ".join(f"{ITEM_LABEL[k]} {v}" for k, v in s["design_detail"].items()) or "未実施"
            out += [f"設計のレビュー（{detail}）:", ""] + [f"- {cell(x)}" for x in s["design_comments"]] + [""]
            if s["facts"]["authz_failed"]:
                out += ["不合格の認可プローブ:", ""] + [f"- {x}" for x in s["facts"]["authz_failed"]] + [""]
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
