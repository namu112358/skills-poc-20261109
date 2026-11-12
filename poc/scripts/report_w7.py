#!/usr/bin/env python3
"""W7 の結果から、HTML レポート（W7/report.html）と同じ内容の Markdown（W7/report.md）を作る。

データ: W7/scores.json（score_w7.py）、W7/<試行ID>.json（grade_w7.py）、W7/notes.json（採点者の所見・判断の記録）。
"""
import html
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import two_axis  # noqa: E402  2 本立ての点数（品質・効率。PLAN.md §4.4）の共通部品

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W7"
NOTES = json.loads((DIR / "notes.json").read_text())
LABEL = {
    "baseline": "baseline（候補なし）",
    "superpowers": "Superpowers",
    "feature-dev": "Feature Dev",
    "compound-engineering": "Compound Engineering",
    "gstack": "gstack",
}
ORDER = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]
PARTS = [("pitfalls", "落とし穴（W7b）", 50, "a"), ("time", "所要時間の比", 15, "b"), ("interventions", "介入回数の比", 15, "c"),
         ("acceptance", "受け入れテスト（W7b）", 20, "d")]
PIT = {"P1": "P1 日時（UTC 保存・JST 表示）", "P2": "P2 独自のエラー型"}


def e(s):
    return html.escape(str(s))


def md(s):
    """notes.json の HTML 断片を GitHub で読める Markdown に変える。"""
    s = str(s)
    s = re.sub(r"<code>(.*?)</code>", lambda m: "`" + m.group(1) + "`", s, flags=re.S)
    s = re.sub(r"<strong>(.*?)</strong>", lambda m: "**" + m.group(1) + "**", s, flags=re.S)
    s = re.sub(r'<a href="([^"]*?)\.html">(.*?)</a>', lambda m: f"[{m.group(2)}]({m.group(1)}.md)", s, flags=re.S)
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


def home_mem(mem):
    """専用 HOME に残ったもの。Claude Code のセッションの記録（.claude/projects/ の memory/ 以外）は新しいセッションに読み込まれないので除く
    （grade_w7.py が除くようになる前に採点した試行の分も、ここで同じように除く）。"""
    return [x for x in mem.get("in_home", []) if not (x.startswith(".claude/projects/") and "/memory/" not in x)]


def yn(v):
    return "✅" if v else "❌"


def main():
    scores = json.loads((DIR / "scores.json").read_text())["scores"]
    by_cand = {}
    for s in scores:
        by_cand.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by_cand]

    def mean(c, key):
        return round(statistics.mean(s[key] for s in by_cand[c]), 1)

    def mean_half(c, half, key):
        return statistics.mean(s[half][key] for s in by_cand[c])

    def avoided(c, half, which="pitfalls_first"):
        return sum(int(s[half][which][p]) for s in by_cand[c] for p in ("P1", "P2"))

    ranked = sorted([c for c in cands if c != "baseline"], key=lambda c: -mean(c, "total"))
    best = max((mean(c, "total") for c in ranked), default=None)
    tops = {c for c in ranked if mean(c, "total") == best}
    rows_sorted = [(c, s) for c in cands for s in sorted(by_cand[c], key=lambda s: s["run"])]
    controls = sorted(json.loads((DIR / "scores.json").read_text()).get("controls", []),
                      key=lambda x: ORDER.index(x["candidate"]) if x["candidate"] in ORDER else 99)

    def learn_rows():
        """組ごとの学習の記録: (a) 前段の知見を読んだか、(b) 同じ間違いを繰り返したか。"""
        out = []
        for c, s in rows_sorted:
            used = sorted({m["file"] for m in s.get("memory_used", [])})
            out.append((f"{LABEL[c]} #{s['run']}", ", ".join(s.get("learned", [])) or "なし",
                        ", ".join(s.get("repeated", [])) or ("なし" if s.get("learned") else "—"), used))
        return out

    def control_rows():
        """対照（W7a を引き継がない W7b）と、同じ候補の続けて行った W7b（平均）の比較。"""
        out = []
        for x in controls:
            c, b = x["candidate"], x["b"]
            pair = by_cand.get(c, [])
            n = len(pair)
            pav = sum(int(s["b"]["pitfalls_first"][p]) for s in pair for p in ("P1", "P2"))
            out.append({
                "name": LABEL.get(c, c),
                "ctl_pit": " ".join(f"{p}{yn(b['pitfalls_first'][p])}" for p in ("P1", "P2")),
                "pair_pit": f"{pav} / {2 * n}" if n else "—",
                "ctl_acc": f"{b['e2e_pass']}/{b['e2e_total']}",
                "ctl_cost": b["cost_usd"], "pair_cost": statistics.mean(s["b"]["cost_usd"] for s in pair) if n else None,
                "ctl_time": b["elapsed_seconds"], "pair_time": statistics.mean(s["b"]["elapsed_seconds"] for s in pair) if n else None,
                "ctl_turns": b["turns"], "pair_turns": statistics.mean(s["b"]["turns"] for s in pair) if n else None,
                "ctl_q": x["quality"], "ctl_eff": x["efficiency"],
                "pair_q": statistics.mean(s["quality"] for s in pair) if n else None,
                "pair_eff": statistics.mean(s["efficiency"] for s in pair) if n else None,
                "stopped": b.get("budget_stopped") or "",
            })
        return out

    def f2(v, fmt):
        return "—" if v is None else fmt.format(v)

    # ---------- HTML ----------
    cards = []
    for c in cands:
        n = len(by_cand[c])
        parts = "".join(f"<div><dt>{lab}</dt><dd>{mean(c, k)} / {mx}</dd></div>" for k, lab, mx, _ in PARTS)
        cards.append(f"""
      <article class="card{' top' if c in tops else ''}">
        <header><h3>{e(LABEL[c])}</h3><span class="runs">{n} 組</span></header>
        <p class="score"><strong>{mean(c, 'total')}</strong><small> / 100</small></p>
        <dl>{parts}</dl>
        <p class="meta">指摘前に避けた落とし穴 W7a {avoided(c, 'a')} / {2 * n} → W7b {avoided(c, 'b')} / {2 * n}<br>
        平均 W7a ${mean_half(c, 'a', 'cost_usd'):.2f}・{mean_half(c, 'a', 'elapsed_seconds') / 60:.1f} 分 → W7b ${mean_half(c, 'b', 'cost_usd'):.2f}・{mean_half(c, 'b', 'elapsed_seconds') / 60:.1f} 分</p>
      </article>""")
    breakdown = []
    for c in cands:
        bars = "".join(f"<div><small>{lab} {mean(c, k)} / {mx}</small>{bar(mean(c, k), mx, cls)}</div>" for k, lab, mx, cls in PARTS)
        breakdown.append(f'<div class="bd-row"><span class="bd-name">{e(LABEL[c])}</span><div class="bd-bars">{bars}</div></div>')

    def pill(ok, text):
        return f'<span class="pill {"ok" if ok else "ng"}">{e(text)}</span>'

    def pits(h, which):
        return " ".join(pill(h[which][p], p) for p in ("P1", "P2"))

    rows = []
    for c, s in rows_sorted:
        a, b = s["a"], s["b"]
        rows.append(f"""
        <tr>
          <th scope="row">{e(LABEL[c])} #{s['run']}</th>
          <td class="num">{s['total']}</td>
          <td>{pits(a, 'pitfalls_first')}</td><td>{pits(a, 'pitfalls_final')}</td>
          <td>{pits(b, 'pitfalls_first')}</td><td>{pits(b, 'pitfalls_final')}</td>
          <td class="num">{a['e2e_pass']}/{a['e2e_total']}</td><td class="num">{b['e2e_pass']}/{b['e2e_total']}</td>
          <td class="num">{a['elapsed_seconds'] / 60:.1f} → {b['elapsed_seconds'] / 60:.1f}（{s['time_ratio']}）</td>
          <td class="num">{s['interventions_a']} → {s['interventions_b']}</td>
          <td class="num">${a['cost_usd']:.2f} → ${b['cost_usd']:.2f}</td>
          <td class="num">{a['turns']} → {b['turns']}</td>
          <td>{e(', '.join(sorted(set(a['skills_used']) | set(b['skills_used']))) or '—')}</td>
        </tr>""")

    pit_rows = "".join(
        f"<tr><th scope=\"row\">{e(LABEL[c])}</th>"
        + "".join(f"<td class=\"num\">{sum(1 for s in by_cand[c] if s[h]['pitfalls_first'][p])} / {len(by_cand[c])}</td>"
                  for h in ("a", "b") for p in ("P1", "P2"))
        + "</tr>" for c in cands)

    details = []
    for c, s in rows_sorted:
        mem = s["memory"]
        reads = s["memory_reads"]
        note = NOTES["trials"].get(s["pair"], "")
        fa = "".join(f"<li>W7a: {e(x)}</li>" for x in s["a"]["e2e_failed"]) + "".join(f"<li>W7b: {e(x)}</li>" for x in s["b"]["e2e_failed"])
        details.append(f"""
      <details>
        <summary><strong>{e(LABEL[c])} #{s['run']}</strong> — {s['total']} 点</summary>
        <p>{note}</p>
        {'<p class="warn">不合格の受け入れテスト</p><ul>' + fa + '</ul>' if fa else ''}
        <p class="sub">W7a から W7b に残ったもの（作業用コピー）</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in mem.get('in_app', [])) or '<li>なし</li>'}</ul>
        <p class="sub">W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）</p><ul class="files">{''.join(f'<li><code>{e(x)}</code></li>' for x in home_mem(mem)[:30]) or '<li>なし</li>'}</ul>
        <p class="sub">W7b で記憶になりうるものを読んだ形跡（最初の 10 件）</p><ul class="files">{''.join(f'<li>{e(x["tool"])}: <code>{e(x["input"][:160])}</code></li>' for x in reads[:10]) or '<li>なし</li>'}</ul>
      </details>""")

    def lis(key):
        return "".join(f"<li>{x}</li>" for x in NOTES[key])

    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W7 結果</title>
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
  <h1>開発ワークフロー PoC — W7 続けて行う作業での学習効果</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 計画書 poc/PLAN.md §5.1</p>

  <section class="summary">{''.join(f'<p>{x}</p>' for x in NOTES['summary'])}</section>

  {two_axis.html_section("W7")}

  <h2>課題</h2>
  <div class="box">{NOTES['task_html']}</div>

  <h2>結果の概要（平均点。W7a → W7b の 1 組ごとに採点）</h2>
  <div class="cards">{''.join(cards)}</div>

  <h2>配点ごとの内訳</h2>
  <div class="box">{''.join(breakdown)}</div>

  <h2>落とし穴を指摘の前に避けられた組の数</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th rowspan="2">候補</th><th colspan="2">W7a（初めて出会う）</th><th colspan="2">W7b（採点対象）</th></tr>
        <tr><th>{e(PIT['P1'])}</th><th>{e(PIT['P2'])}</th><th>{e(PIT['P1'])}</th><th>{e(PIT['P2'])}</th></tr>
      </thead>
      <tbody>{pit_rows}</tbody>
    </table>
  </div>

  <h2>組ごとの結果</h2>
  <div class="table-wrap">
    <table class="wide">
      <thead><tr>
        <th>組</th><th>点数</th><th>W7a 指摘前</th><th>W7a 最終</th><th>W7b 指摘前</th><th>W7b 最終</th>
        <th>受入 W7a</th><th>受入 W7b</th><th>時間（分）W7a → W7b（比）</th><th>介入 W7a → W7b</th><th>費用 W7a → W7b</th><th>ターン</th><th>使われた Skill</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>

  <h2>前の段階の知見を読んだか・同じ間違いを繰り返したか</h2>
  <p class="lead">「W7a で指摘を受けた」は W7a で指摘の前に避けられなかった落とし穴（学ぶ機会があったもの）。「W7b で繰り返した」はそのうち W7b でも指摘の前に避けられなかったもの。</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>組</th><th>W7a で指摘を受けた</th><th>W7b で繰り返した</th><th>W7b で読んだ前の段階の知見（W7a が残したファイル）</th></tr></thead>
      <tbody>{''.join(f"<tr><th scope='row'>{e(n)}</th><td>{e(l)}</td><td>{e(r)}</td><td>{'<br>'.join(f'<code>{e(u)}</code>' for u in used) or 'なし'}</td></tr>" for n, l, r, used in learn_rows())}</tbody>
    </table>
  </div>

  <h2>対照（W7a を引き継がない W7b）との比較</h2>
  <p class="lead">対照は、同じ候補で W7b だけを、新しい作業用コピー（初期状態 + W7a の参照実装）と新しい HOME で行ったもの（各候補 1 回）。候補の記憶も、候補自身が書いた W7a のコードも無い。右側は続けて行った W7b（2 組の平均）。</p>
  <div class="table-wrap">
    <table class="wide">
      <thead><tr><th>候補</th><th>対照: 指摘前</th><th>続けて: 指摘前に避けた数</th><th>対照: 受入</th><th>費用 対照 / 続けて</th><th>時間（分）対照 / 続けて</th><th>ターン 対照 / 続けて</th><th>品質 対照 / 続けて</th><th>効率 対照 / 続けて</th></tr></thead>
      <tbody>{''.join(f"<tr><th scope='row'>{e(r['name'])}</th><td>{e(r['ctl_pit'])}</td><td class='num'>{r['pair_pit']}</td><td class='num'>{r['ctl_acc']}</td><td class='num'>${r['ctl_cost']:.2f} / {f2(r['pair_cost'], '${:.2f}')}</td><td class='num'>{r['ctl_time'] / 60:.1f} / {f2(r['pair_time'] and r['pair_time'] / 60, '{:.1f}')}</td><td class='num'>{r['ctl_turns']} / {f2(r['pair_turns'], '{:.1f}')}</td><td class='num'>{r['ctl_q']} / {f2(r['pair_q'], '{:.1f}')}</td><td class='num'>{r['ctl_eff']} / {f2(r['pair_eff'], '{:.1f}')}</td></tr>" for r in control_rows())}</tbody>
    </table>
  </div>

  <h2>所見</h2>
  <div class="box"><ul>{lis('observations')}</ul></div>

  <h2>各候補が W7a → W7b に残したもの</h2>
  <div class="box"><ul>{lis('memory')}</ul></div>

  <h2>組の詳細</h2>
  {''.join(details)}

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
        "# 開発ワークフロー PoC — W7 続けて行う作業での学習効果", "",
        f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 計画書 poc/PLAN.md §5.1", "",
        "> HTML 版: [report.html](report.html)（同じデータから `poc/scripts/report_w7.py` で生成）", "",
    ]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += two_axis.md_section("W7") + [""]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    out += ["## 結果の概要（平均点。W7a → W7b の 1 組ごとに採点）", "",
            "| 候補 | 組 | 合計 / 100 | 落とし穴（W7b）/ 50 | 所要時間の比 / 15 | 介入回数の比 / 15 | 受け入れテスト（W7b）/ 20 | 指摘前に避けた落とし穴 W7a → W7b | 平均費用 W7a → W7b | 平均時間（分）W7a → W7b |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cands:
        n = len(by_cand[c])
        name = f"**{LABEL[c]}**" if c in tops else LABEL[c]
        out.append(f"| {name} | {n} | {mean(c, 'total')} | {mean(c, 'pitfalls')} | {mean(c, 'time')} | {mean(c, 'interventions')} | "
                   f"{mean(c, 'acceptance')} | {avoided(c, 'a')} / {2 * n} → {avoided(c, 'b')} / {2 * n} | "
                   f"${mean_half(c, 'a', 'cost_usd'):.2f} → ${mean_half(c, 'b', 'cost_usd'):.2f} | "
                   f"{mean_half(c, 'a', 'elapsed_seconds') / 60:.1f} → {mean_half(c, 'b', 'elapsed_seconds') / 60:.1f} |")
    out += ["", "## 落とし穴を指摘の前に避けられた組の数", "",
            f"| 候補 | W7a {PIT['P1']} | W7a {PIT['P2']} | W7b {PIT['P1']} | W7b {PIT['P2']} |", "|---|---:|---:|---:|---:|"]
    for c in cands:
        n = len(by_cand[c])
        out.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by_cand[c] if s[h]['pitfalls_first'][p])} / {n}"
                                                   for h in ("a", "b") for p in ("P1", "P2")) + " |")
    out += ["", "## 組ごとの結果", "",
            "落とし穴: 「指摘前」は手順を終えた時点（レビューの指摘を受ける前）、「最終」は指摘のやり取りの後。", "",
            "| 組 | 点数 | W7a 指摘前 | W7a 最終 | W7b 指摘前 | W7b 最終 | 受入 W7a | 受入 W7b | 時間（分）W7a → W7b（比） | 介入 W7a → W7b | 費用 W7a → W7b | ターン | 使われた Skill |",
            "|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|"]

    def pm(h, which):
        return " ".join(f"{p}{yn(h[which][p])}" for p in ("P1", "P2"))

    for c, s in rows_sorted:
        a, b = s["a"], s["b"]
        out.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {pm(a, 'pitfalls_first')} | {pm(a, 'pitfalls_final')} | "
                   f"{pm(b, 'pitfalls_first')} | {pm(b, 'pitfalls_final')} | {a['e2e_pass']}/{a['e2e_total']} | {b['e2e_pass']}/{b['e2e_total']} | "
                   f"{a['elapsed_seconds'] / 60:.1f} → {b['elapsed_seconds'] / 60:.1f}（{s['time_ratio']}） | {s['interventions_a']} → {s['interventions_b']} | "
                   f"${a['cost_usd']:.2f} → ${b['cost_usd']:.2f} | {a['turns']} → {b['turns']} | "
                   f"{cell(', '.join(sorted(set(a['skills_used']) | set(b['skills_used']))) or '—')} |")
    out += ["", "## 前の段階の知見を読んだか・同じ間違いを繰り返したか", "",
            "「W7a で指摘を受けた」は W7a で指摘の前に避けられなかった落とし穴（学ぶ機会があったもの）。「W7b で繰り返した」はそのうち W7b でも指摘の前に避けられなかったもの。", "",
            "| 組 | W7a で指摘を受けた | W7b で繰り返した | W7b で読んだ前の段階の知見（W7a が残したファイル） |", "|---|---|---|---|"]
    for n, l, r, used in learn_rows():
        out.append(f"| {n} | {l} | {r} | {'<br>'.join(f'`{u}`' for u in used) or 'なし'} |")
    out += ["", "## 対照（W7a を引き継がない W7b）との比較", "",
            "対照は、同じ候補で W7b だけを、新しい作業用コピー（初期状態 + W7a の参照実装）と新しい HOME で行ったもの（各候補 1 回）。候補の記憶も、候補自身が書いた W7a のコードも無い。「続けて」は続けて行った W7b（2 組の平均）。", "",
            "| 候補 | 対照: 指摘前 | 続けて: 指摘前に避けた数 | 対照: 受入 | 費用 対照 / 続けて | 時間（分）対照 / 続けて | ターン 対照 / 続けて | 品質 対照 / 続けて | 効率 対照 / 続けて |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in control_rows():
        out.append(f"| {r['name']} | {r['ctl_pit']} | {r['pair_pit']} | {r['ctl_acc']} | ${r['ctl_cost']:.2f} / {f2(r['pair_cost'], '${:.2f}')} | "
                   f"{r['ctl_time'] / 60:.1f} / {f2(r['pair_time'] and r['pair_time'] / 60, '{:.1f}')} | {r['ctl_turns']} / {f2(r['pair_turns'], '{:.1f}')} | "
                   f"{r['ctl_q']} / {f2(r['pair_q'], '{:.1f}')} | {r['ctl_eff']} / {f2(r['pair_eff'], '{:.1f}')} |")
    out += ["", "## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 各候補が W7a → W7b に残したもの", ""] + [f"- {md(x)}" for x in NOTES["memory"]]
    out += ["", "## 組の詳細", ""]
    for c, s in rows_sorted:
        mem = s["memory"]
        out += [f"### {LABEL[c]} #{s['run']} — {s['total']} 点", "", md(NOTES["trials"].get(s["pair"], "")), ""]
        failed = [f"W7a: {x}" for x in s["a"]["e2e_failed"]] + [f"W7b: {x}" for x in s["b"]["e2e_failed"]]
        if failed:
            out += ["不合格の受け入れテスト:", ""] + [f"- {x}" for x in failed] + [""]
        out += ["W7a から W7b に残ったもの（作業用コピー）:", ""] + ([f"- `{x}`" for x in mem.get("in_app", [])] or ["- なし"])
        out += ["", "W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:", ""] + ([f"- `{x}`" for x in home_mem(mem)[:30]] or ["- なし"])
        out += ["", "W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:", ""]
        out += [f"- {x['tool']}: `{cell(x['input'][:160]).replace('`', '')}`" for x in s["memory_reads"][:10]] or ["- なし"]
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
