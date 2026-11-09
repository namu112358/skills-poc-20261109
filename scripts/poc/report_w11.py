#!/usr/bin/env python3
"""W11（実在する OSS の解決済み課題）の結果を集計し、results/workflow/W11/report.md と report.html を作る。

使い方: python3 scripts/poc/report_w11.py
  results/workflow/W11/W11-*.json（grade_w11.py の出力）を読む。
  判断の記録など、手で書く節は results/workflow/W11/notes.md に置くと、report の末尾に入る。
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W11"
TASKS = json.loads((ROOT / "scripts" / "poc" / "oss" / "tasks.json").read_text())
CANDS = [("superpowers", "Superpowers"), ("feature-dev", "Feature Dev"), ("compound-engineering", "Compound Engineering"),
         ("gstack", "gstack"), ("baseline", "baseline（候補なし）")]
TITLES = {
    "B1": "pytest: 同じ親ディレクトリが引数に複数回出ると、フィクスチャが見つからない",
    "B2": "pytest: assert の中の代入式（:=）が 2 回評価される",
    "B3": "zod: 共通の再帰スキーマを持つ union の非同期検証が不正な入力を通す",
    "F1": "zod: 循環参照を含む入力を検証できるようにする",
    "F2": "packaging: 範囲の包含関係と重なりを 1 回で返す API",
    "F3": "click: テスト実行器 invoke() に Context の設定を渡せるようにする",
}
ORDER = ["B1", "B2", "B3", "F1", "F2", "F3"]

rows = [json.loads(p.read_text()) for p in sorted(DIR.glob("W11-*.json"))]
by = {}
for r in rows:
    by.setdefault((r["task"], r["candidate"]), []).append(r)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def base_of(task, field):
    b = by.get((task, "baseline"))
    return mean([r["facts"][field] for r in b]) if b else None


def ratio(r, field):
    b = base_of(r["task"], field)
    return r["facts"][field] / b if b else None


def eff(r):
    """効率（PLAN.md §4.4 と同じ段階）: 費用 50 + 時間 30 + 介入 20。baseline の実額・時間に対する倍率で付ける"""
    def stage(x):
        if x is None:
            return 1.0
        for lim, v in ((2, 1.0), (3, 0.8), (5, 0.6), (10, 0.3)):
            if x <= lim:
                return v
        return 0.0
    iv = r["facts"]["interventions"]
    return round(50 * stage(ratio(r, "cost_usd")) + 30 * stage(ratio(r, "elapsed_seconds")) + 20 * (1 if iv == 0 else 0.5 if iv == 1 else 0), 1)


def cell(rs):
    if not rs:
        return "—"
    r = rs[0] if len(rs) == 1 else None
    res = sum(1 for x in rs if x["resolved"])
    mark = "✅" if res == len(rs) else ("⚠️" if res else "❌")
    q = mean([x["quality"] for x in rs])
    h = rs[0]["hidden_tests"]
    s = f"{mark} {q:.0f}（新 {h['new_pass']}/{h['new_total']}"
    broken = h["existing_total"] - h["existing_pass"]
    if broken:
        s += f"・既存 −{broken}"
    return s + "）"


def fmt_cost(rs):
    return "—" if not rs else f"${mean([x['facts']['cost_usd'] for x in rs]):.2f}"


def fmt_time(rs):
    return "—" if not rs else f"{mean([x['facts']['elapsed_seconds'] for x in rs]) / 60:.1f} 分"


md = []
md.append("# PoC W11 実在する OSS の解決済み課題 — 結果レポート\n")
md.append("> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w11.py` で生成）\n")
md.append("実在する OSS（pytest・zod・packaging・click）で、2026 年 7〜11 月に本家が解決した課題 6 件（不具合 3・機能 3）を、"
          "解決前の状態から各候補に解かせた。採点は本家の修正で追加されたテスト（隠しテスト）で行った。"
          "設計は [wf-W11-design.md](../../../tasks/wf-W11-design.md)。\n")

# 要点（候補ごと）
md.append("## 候補ごとのまとめ\n")
md.append("| 候補 | 解決（全 6） | 不具合 3 の解決 | 機能 3 の解決 | 品質の平均 | 費用の合計 | 時間の合計 | 効率の平均 |")
md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
summary = []
for c, name in CANDS:
    rs = [r for r in rows if r["candidate"] == c]
    if not rs:
        continue
    res = sum(r["resolved"] for r in rs)
    bug = sum(r["resolved"] for r in rs if r["kind"] == "bug")
    feat = sum(r["resolved"] for r in rs if r["kind"] == "feature")
    nb = sum(1 for r in rs if r["kind"] == "bug"); nf = len(rs) - nb
    q = mean([r["quality"] for r in rs])
    cost = sum(r["facts"]["cost_usd"] for r in rs)
    t = sum(r["facts"]["elapsed_seconds"] for r in rs)
    e = mean([eff(r) for r in rs])
    summary.append((name, res, len(rs), bug, nb, feat, nf, q, cost, t, e))
    md.append(f"| {name} | {res}/{len(rs)} | {bug}/{nb} | {feat}/{nf} | {q:.1f} | ${cost:.2f} | {t / 60:.0f} 分 | {e:.1f} |")
md.append("")
md.append("- 解決 = 本家のテストのうち、修正前に失敗し修正後に通るもの（F2P）がすべて通り、もともと通るもの（P2P）を 1 つも壊していない。")
md.append("- 品質（100 点）= 新しいテストの通過率 × 70 + 既存テストの維持率 × 30。")
md.append("- 効率（100 点）= 費用 50 + 時間 30 + 介入 20。その課題の baseline に対する倍率で段階を付ける（2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、それ超 = 0）。\n")

md.append("## 課題 × 候補の結果\n")
md.append("各セル: 解決（✅ / ❌）と品質、（新しいテストの通過数 / 総数・壊した既存テストの数）。\n")
md.append("| 課題 | " + " | ".join(n for _, n in CANDS) + " |")
md.append("|---|" + "---|" * len(CANDS))
for t in ORDER:
    kind = "不具合" if TASKS[t]["kind"] == "bug" else "機能"
    md.append(f"| **{t}**（{kind}）{TITLES[t]} | " + " | ".join(cell(by.get((t, c), [])) for c, _ in CANDS) + " |")
md.append("")

md.append("## 費用と時間\n")
md.append("| 課題 | " + " | ".join(n for _, n in CANDS) + " |")
md.append("|---|" + "---|" * len(CANDS))
for t in ORDER:
    md.append(f"| {t} | " + " | ".join(f"{fmt_cost(by.get((t, c), []))}・{fmt_time(by.get((t, c), []))}" for c, _ in CANDS) + " |")
md.append("")

md.append("## 変更の規模と、候補が書いたテスト\n")
md.append("ソースの変更行数（追加 + 削除。テスト・文書・候補の管理用ファイルを除く）と、候補が追加したテストの行数。括弧内は本家の修正の行数。\n")
md.append("| 課題（本家） | " + " | ".join(n for _, n in CANDS) + " |")
md.append("|---|" + "---|" * len(CANDS))
for t in ORDER:
    any_r = next((r for r in rows if r["task"] == t), None)
    up = f"{any_r['diff']['upstream_src_added'] + any_r['diff']['upstream_src_removed']}" if any_r else "?"
    cells = []
    for c, _ in CANDS:
        rs = by.get((t, c), [])
        if not rs:
            cells.append("—"); continue
        d = rs[0]["diff"]
        cells.append(f"ソース {d['src_added'] + d['src_removed']}・テスト +{d['test_added']}")
    md.append(f"| {t}（{up}） | " + " | ".join(cells) + " |")
md.append("")

md.append("## 試行の独立性と拒否された操作\n")
md.append("| 試行 | 外部参照などの形跡 | 拒否された操作 | 使った Skill | サブエージェント | 介入 | 費用上限で停止 |")
md.append("|---|---|---:|---|---:|---:|---|")
for r in rows:
    tr = r["transcript"]
    iso = sorted({x["reason"] for x in tr["isolation_suspects"]})
    md.append(f"| {r['trial']} | {'・'.join(iso) or 'なし'} | {len(tr['permission_denials'])} | {', '.join(tr['skills']) or '—'} | "
              f"{tr['subagents']} | {r['facts']['interventions']} | {'あり' if r['facts']['budget_stopped'] else '—'} |")
md.append("")

notes = DIR / "notes.md"
if notes.exists():
    md.append(notes.read_text())
(DIR / "report.md").write_text("\n".join(md) + "\n")

# HTML（同じ内容。表は markdown から素直に変換する）
out, in_table = [], False
for line in md:
    if line.startswith("|"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-:") for c in cells):
            continue
        if not in_table:
            out.append("<div class=tw><table>"); in_table = True
            out.append("<tr>" + "".join(f"<th>{html.escape(c).replace('**', '')}</th>" for c in cells) + "</tr>")
        else:
            out.append("<tr>" + "".join(f"<td>{html.escape(c).replace('**', '')}</td>" for c in cells) + "</tr>")
        continue
    if in_table:
        out.append("</table></div>"); in_table = False
    if line.startswith("# "):
        out.append(f"<h1>{html.escape(line[2:])}</h1>")
    elif line.startswith("## "):
        out.append(f"<h2>{html.escape(line[3:])}</h2>")
    elif line.startswith("### "):
        out.append(f"<h3>{html.escape(line[4:])}</h3>")
    elif line.startswith("- "):
        out.append(f"<p class=li>• {html.escape(line[2:])}</p>")
    elif line.startswith("> "):
        continue
    elif line.strip():
        out.append(f"<p>{html.escape(line)}</p>")
if in_table:
    out.append("</table></div>")
page = """<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>PoC W11 結果</title><style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--head:#f4f4f4}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--mut:#aaa;--line:#333;--head:#222}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px}
.tw{overflow-x:auto}table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}
th,td{border:1px solid var(--line);padding:4px 8px;vertical-align:top}th{background:var(--head);text-align:left}
p.li{margin:2px 0 2px 8px}h2{margin-top:28px;border-bottom:1px solid var(--line)}
</style></head><body>""" + "\n".join(out) + "</body></html>\n"
(DIR / "report.html").write_text(page)
for s in summary:
    print(s)
