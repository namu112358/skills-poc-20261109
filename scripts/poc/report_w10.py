#!/usr/bin/env python3
"""W10 の結果から、Markdown のレポート（W10/report.md）と、同じ内容の HTML（W10/report.html）を作る。

データ: W10/scores.json（score_w10.py）、W10/<試行ID>.json（grade_w10.py）、W10/blind/scores.json（blind_w10.py）、
W10/notes.json（採点者の所見・判断の記録。Markdown の文字列のリスト）。
HTML は Markdown を変換して作る（内容を 2 か所で書かないため）。
"""
import html
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import two_axis  # noqa: E402
from score_w10 import HIDDEN_LABELS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W10"
LABEL = two_axis.LABEL
ORDER = two_axis.ORDER
PARTS = [("acceptance", "公開の受け入れ", 25), ("hidden", "隠しテスト", 40), ("test_strength", "テストの強さ", 20),
         ("review", "ブラインドレビュー", 15)]


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def build_md():
    notes = json.loads((DIR / "notes.json").read_text())
    scores = json.loads((DIR / "scores.json").read_text())["scores"]
    by = {}
    for s in scores:
        by.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by]

    def mean(c, k):
        return round(statistics.mean(s[k] for s in by[c]), 1)

    def mfact(c, k):
        return statistics.mean(s["facts"][k] for s in by[c])

    L = ["# W10 仕様に書かれていない落とし穴がある機能追加 — 結果レポート", ""]
    L += [f"- {x}" for x in notes["summary"]] + [""]
    L += two_axis.md_section("W10")

    L += ["## 総合点（品質の内訳。費用・時間は上の効率で見る）", ""]
    L += ["| 候補 | 回数 | 総合 / 100 | " + " | ".join(f"{lab} / {mx}" for _, lab, mx in PARTS)
          + " | 隠しテストの通過 | 平均費用 | 平均時間 |",
          "|---|---|---|" + "---|" * len(PARTS) + "---|---|---|"]
    for c in cands:
        hp = sum(s["facts"]["hidden_pass"] for s in by[c])
        L.append(f"| {LABEL[c]} | {len(by[c])} | {mean(c, 'total')} | " + " | ".join(str(mean(c, k)) for k, _, _ in PARTS)
                 + f" | {hp} / {12 * len(by[c])} | ${mfact(c, 'cost_usd'):.2f} | {mfact(c, 'elapsed_seconds') / 60:.1f} 分 |")
    L.append("")

    L += ["## 隠しテストの項目ごとの結果（通過した試行の数）", ""]
    ids = list(HIDDEN_LABELS)
    L += ["| 候補 | " + " | ".join(f"{i} {HIDDEN_LABELS[i]}" for i in ids) + " |", "|---|" + "---|" * len(ids)]
    for c in cands:
        L.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by[c] if s['hidden_items'][i])} / {len(by[c])}" for i in ids) + " |")
    allc = len(scores)
    L.append("| 全試行 | " + " | ".join(f"{sum(1 for s in scores if s['hidden_items'][i])} / {allc}" for i in ids) + " |")
    L += ["", "項目の定義は [grading.md](../../../answer-key/W10/grading.md) の「隠しテスト」。", ""]

    L += ["## 試行ごとの内訳", ""]
    L += ["| 試行 | 総合 | 公開 E2E | 型・単体・ビルド | 隠し | 検出 / 壊した数 | レビュー（2 名） | 費用 | 時間 | 介入 | 上限で停止 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        for s in sorted(by[c], key=lambda s: s["run"]):
            f = s["facts"]
            ck = "".join("○" if f["checks"][k] else "×" for k in ("typecheck", "test", "build"))
            hid = "".join("○" if v else "×" for v in s["hidden_items"].values())
            rv = s.get("review_detail") or {}
            L.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {f['e2e_pass']} / {f['e2e_total']} | {ck} | "
                     f"{f['hidden_pass']} / 12（{hid}） | {f['killed']} / {f['mutants']} | {rv.get('totals', '—')} | "
                     f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} 分 | {f['interventions']} | "
                     f"{'あり' if f['budget_stopped'] else 'なし'} |")
    L += ["", "隠しの ○× は H01〜H12 の順。型・単体・ビルドの ○× は採点者が作業用コピーで再実行した結果。", ""]

    L += ["## 所見", ""] + [f"- {x}" for x in notes["findings"]] + [""]
    if notes.get("review_notes"):
        L += ["## ブラインドレビュー", ""] + [f"- {x}" for x in notes["review_notes"]] + [""]
    L += ["## 試行の条件", ""] + [f"- {x}" for x in notes["conditions"]] + [""]
    L += ["## 判断の記録", ""] + [f"- {x}" for x in notes["decisions"]] + [""]
    L += ["## データの場所", ""] + [f"- {x}" for x in notes["data"]] + [""]
    return L


# ---------- Markdown → HTML（このレポートで使う書式だけ） ----------
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def table(rows):
    cells = [[c.strip() for c in re.split(r"(?<!\\)\|", r.strip().strip("|"))] for r in rows]
    head, body = cells[0], cells[2:]
    th = "".join(f"<th>{inline(h)}</th>" for h in head)
    trs = "".join("<tr>" + "".join((f'<th scope="row">{inline(c)}</th>' if i == 0 else f"<td>{inline(c)}</td>")
                                   for i, c in enumerate(r)) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def to_html(lines):
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(table(lines[i:j]))
            i = j
            continue
        if ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        m = re.match(r"(#{1,3}) (.*)", ln)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)


CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5d6670;--line:#d9dde3;--head:#f0f2f5;--accent:#2f5d8a;--code:#eef1f4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181c;--fg:#e6e8eb;--muted:#a3abb5;--line:#343a42;--head:#1f242a;--accent:#8db7e0;--code:#232930}}
:root[data-theme="dark"]{--bg:#15181c;--fg:#e6e8eb;--muted:#a3abb5;--line:#343a42;--head:#1f242a;--accent:#8db7e0;--code:#232930}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;line-height:1.4;margin:0 0 16px}
h2{font-size:1.15rem;margin:36px 0 10px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:1rem;margin:22px 0 8px}
a{color:var(--accent)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.88em;word-break:break-all}
ul{padding-left:1.3em}li{margin:4px 0}
.table-wrap{overflow-x:auto;margin:10px 0;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:.86rem;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top;white-space:nowrap}
thead th{background:var(--head);font-weight:600}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
"""


def main():
    L = build_md()
    (DIR / "report.md").write_text("\n".join(L).rstrip() + "\n")
    body = to_html(L)
    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>W10 結果レポート</title><style>{CSS}</style></head>
<body><main>
{body}
</main></body></html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.md'} and report.html")


if __name__ == "__main__":
    main()
