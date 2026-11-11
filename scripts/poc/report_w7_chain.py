#!/usr/bin/env python3
"""W7 の 5 段階（W7a〜W7e）の結果から、W7/report-5stages.html と同じ内容の W7/report-5stages.md を作る。

データ: W7/scores-5stages.json（score_w7_chain.py）、W7/notes-5stages.json（採点者の所見・判断の記録）。
"""
import html
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_w7 import LABEL, ORDER, cell, md  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W7"
NOTES = json.loads((DIR / "notes-5stages.json").read_text())
DATA = json.loads((DIR / "scores-5stages.json").read_text())
STAGES = DATA["stages"]
STAGE_NAME = {"W7a": "完了報告", "W7b": "作業記録", "W7c": "日別一覧", "W7d": "予定", "W7e": "CSV 出力"}


def e(s):
    return html.escape(str(s))


def yn(v):
    return "✅" if v else "❌"


def main():
    chains = sorted(DATA["chains"], key=lambda c: (ORDER.index(c["candidate"]), c["run"]))
    by_cand = {}
    for c in chains:
        by_cand.setdefault(c["candidate"], []).append(c)
    cands = [c for c in ORDER if c in by_cand]
    controls = {x["candidate"]: x for x in DATA["controls"]}

    def mean(c, key):
        return round(statistics.mean(x[key] for x in by_cand[c]), 1)

    def stage_mean(c, s, key):
        vals = [st[key] for x in by_cand[c] for st in x["stages"] if st["stage"] == s]
        return statistics.mean(vals) if vals else None

    def avoided(c, s):
        n = sum(int(st["pitfalls_first"][p]) for x in by_cand[c] for st in x["stages"] if st["stage"] == s for p in ("P1", "P2"))
        return f"{n}/{2 * len(by_cand[c])}"

    # 表 1: 候補ごとの品質・効率
    t1 = [("候補", "組", "品質（W7b〜W7e 平均）", "効率（同）", "費用の合計（5 段階・平均）", "時間の合計（分・平均）", "指摘前に外した落とし穴（5 段階・合計）", "繰り返し（合計）")]
    for c in cands:
        xs = by_cand[c]
        t1.append((LABEL[c], str(len(xs)), f"{mean(c, 'quality')}", f"{mean(c, 'efficiency')}",
                   f"${statistics.mean(x['cost_total'] for x in xs):.2f}", f"{statistics.mean(x['elapsed_total'] for x in xs) / 60:.1f}",
                   str(sum(x["missed_first_total"] for x in xs)), str(sum(x["repeated_total"] for x in xs))))
    # 表 2: 学習曲線（指摘前に避けた落とし穴の数、段階ごと）
    t2 = [("候補",) + tuple(f"{s} {STAGE_NAME[s]}" for s in STAGES)]
    for c in cands:
        t2.append((LABEL[c],) + tuple(avoided(c, s) for s in STAGES))
    # 表 3: 費用の推移
    t3 = [("候補",) + tuple(STAGES)]
    for c in cands:
        t3.append((LABEL[c],) + tuple(f"${stage_mean(c, s, 'cost_usd'):.2f}" for s in STAGES))
    t3b = [("候補",) + tuple(STAGES)]
    for c in cands:
        t3b.append((LABEL[c],) + tuple(f"{stage_mean(c, s, 'elapsed_seconds') / 60:.1f}" for s in STAGES))
    # 表 4: 組ごとの段階の詳細
    t4 = [("組", "段階", "指摘前", "最終", "受入", "品質", "効率", "費用", "時間（分）", "ターン", "介入", "繰り返し", "前の段階の知見を読んだ形跡")]
    for x in chains:
        for st in x["stages"]:
            used = sorted({m["file"] for m in st["memory_used"]})
            t4.append((f"{LABEL[x['candidate']]} #{x['run']}", st["stage"],
                       " ".join(f"{p}{yn(st['pitfalls_first'][p])}" for p in ("P1", "P2")),
                       " ".join(f"{p}{yn(st['pitfalls_final'][p])}" for p in ("P1", "P2")),
                       f"{st['e2e_pass']}/{st['e2e_total']}", f"{st['quality']}", f"{st['efficiency']}",
                       f"${st['cost_usd']:.2f}" + ("（上限で停止）" if st["budget_stopped"] else ""),
                       f"{st['elapsed_seconds'] / 60:.1f}", str(st["turns"]), str(st["interventions"]),
                       ", ".join(st["repeated"]) or "—", ", ".join(used) or "—"))
    # 表 5: W7e の対照
    t5 = [("候補", "対照: 指摘前", "続けて: 指摘前に避けた数", "対照: 受入", "費用 対照 / 続けて", "時間（分）対照 / 続けて", "品質 対照 / 続けて", "効率 対照 / 続けて")]
    for c in cands:
        x = controls.get(c)
        if not x:
            continue
        t5.append((LABEL[c], " ".join(f"{p}{yn(x['pitfalls_first'][p])}" for p in ("P1", "P2")), avoided(c, "W7e"),
                   f"{x['e2e_pass']}/{x['e2e_total']}", f"${x['cost_usd']:.2f} / ${stage_mean(c, 'W7e', 'cost_usd'):.2f}",
                   f"{x['elapsed_seconds'] / 60:.1f} / {stage_mean(c, 'W7e', 'elapsed_seconds') / 60:.1f}",
                   f"{x['quality']} / {stage_mean(c, 'W7e', 'quality'):.1f}", f"{x['efficiency']} / {stage_mean(c, 'W7e', 'efficiency'):.1f}"))

    tables = [("候補ごとの品質と効率（主表示）", NOTES.get("table_notes", {}).get("t1", ""), t1),
              ("指摘の前に避けた落とし穴の数（段階ごと。学習曲線）", "P1・P2 の 2 件 × 組の数のうち、レビューの指摘を受ける前に避けた数。", t2),
              ("費用の推移（段階ごと、組の平均）", "", t3), ("所要時間の推移（分、段階ごと、組の平均）", "", t3b),
              ("W7e の対照（前の段階を引き継がない W7e）との比較", "対照は W7e だけを、初期状態 + 参照実装 W7a〜W7d の新しい作業用コピーと新しい HOME で行ったもの（各 1 回）。「続けて」は 5 段階を続けて行った W7e（2 組）。", t5),
              ("組・段階ごとの結果", "「指摘前」は手順を終えた時点（レビューの指摘を受ける前）、「最終」は指摘のやり取りの後。「繰り返し」は、それより前の段階で指摘を受けた落とし穴を、この段階でも指摘の前に避けられなかったもの。", t4)]

    def lis(key):
        return "".join(f"<li>{x}</li>" for x in NOTES[key])

    def html_table(rows):
        head = "".join(f"<th>{e(h)}</th>" for h in rows[0])
        body = "".join("<tr>" + "".join(f"<td>{e(v)}</td>" for v in r) + "</tr>" for r in rows[1:])
        return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    sections = "".join(f"<h2>{e(t)}</h2>{f'<p class=lead>{e(n)}</p>' if n else ''}{html_table(r)}" for t, n, r in tables)
    doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PoC W7 5 段階の結果</title>
<style>
:root {{ --bg:#f7f7f5; --surface:#ffffff; --text:#1d1d1f; --muted:#5f6368; --line:#e3e3df; --accent:#2f5bd3; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033; --accent:#7c9cff; }}
}}
:root[data-theme="dark"] {{ --bg:#121314; --surface:#1c1d1f; --text:#ececec; --muted:#a0a4a8; --line:#2e3033; --accent:#7c9cff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.7 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:19px; margin:40px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
.lead {{ color:var(--muted); margin:0 0 12px; }}
.summary {{ background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:8px; padding:14px 18px; }}
.summary p {{ margin:4px 0; }}
.table-wrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
thead th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; overflow-wrap:anywhere; }}
.box {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 18px; }}
ul {{ padding-left:20px; }}
</style>
</head>
<body>
<main>
  <h1>開発ワークフロー PoC — W7 続けて行う作業での学習効果（5 段階）</h1>
  <p class="lead">実施日 {e(NOTES['date'])} ・ モデル {e(NOTES['model'])} ・ Claude Code {e(NOTES['claude_code'])} ・ 2 段階の結果は <a href="report.html">report.html</a></p>
  <section class="summary">{''.join(f'<p>{x}</p>' for x in NOTES['summary'])}</section>
  <h2>課題</h2>
  <div class="box">{NOTES['task_html']}</div>
  {sections}
  <h2>所見</h2>
  <div class="box"><ul>{lis('observations')}</ul></div>
  <h2>採点方法</h2>
  <div class="box">{NOTES['scoring_html']}</div>
  <h2>この結果の制約</h2>
  <div class="box"><ul>{lis('limitations')}</ul></div>
  <h2>判断の記録</h2>
  <div class="box"><ul>{lis('decisions')}</ul></div>
  <h2>試行間の独立性の確認結果</h2>
  <div class="box"><p>{NOTES['isolation']}</p></div>
  <h2>結論と次の対応</h2>
  <div class="box"><ul>{lis('next')}</ul></div>
</main>
</body>
</html>
"""
    (DIR / "report-5stages.html").write_text(doc)
    print(f"wrote {DIR / 'report-5stages.html'}")

    def md_table(rows):
        out = ["| " + " | ".join(cell(h) for h in rows[0]) + " |", "|" + "---|" * len(rows[0])]
        out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows[1:]]
        return out

    out = ["# 開発ワークフロー PoC — W7 続けて行う作業での学習効果（5 段階）", "",
           f"実施日 {NOTES['date']} ・ モデル {NOTES['model']} ・ Claude Code {NOTES['claude_code']} ・ 2 段階の結果は [report.md](report.md)", "",
           "> HTML 版: [report-5stages.html](report-5stages.html)（同じデータから `scripts/poc/report_w7_chain.py` で生成）", ""]
    out += [md(x) + "\n" for x in NOTES["summary"]]
    out += ["## 課題", "", md(NOTES["task_html"]), ""]
    for t, n, r in tables:
        out += [f"## {t}", ""] + ([n, ""] if n else []) + md_table(r) + [""]
    out += ["## 所見", ""] + [f"- {md(x)}" for x in NOTES["observations"]]
    out += ["", "## 採点方法", "", md(NOTES["scoring_html"]), ""]
    out += ["## この結果の制約", ""] + [f"- {md(x)}" for x in NOTES["limitations"]]
    out += ["", "## 判断の記録", ""] + [f"- {md(x)}" for x in NOTES["decisions"]]
    out += ["", "## 試行間の独立性の確認結果", "", md(NOTES["isolation"]), ""]
    out += ["## 結論と次の対応", ""] + [f"- {md(x)}" for x in NOTES["next"]]
    (DIR / "report-5stages.md").write_text("\n".join(out) + "\n")
    print(f"wrote {DIR / 'report-5stages.md'}")


if __name__ == "__main__":
    main()
