#!/usr/bin/env python3
"""W18 の結果の表と、回を追った推移のグラフ（report.md に入れる表と、report.html に入れる SVG）を作る。

使い方:
  python3 scripts/poc/report_w18.py tables          → results/workflow/W18/tables.md（report.md に貼る表）
  python3 scripts/poc/report_w18.py charts <out.html> → 推移のグラフ（SVG）の HTML 断片
  前に score_w18.py --all を実行して results/workflow/W18/scores.json を作っておく。
条件（候補）ごとに 2 系列の平均を示す。参照の系列・最短の系列（試行前の確認）は別の行に参考として示す。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W18"
CONDS = ["superpowers", "feature-dev", "gstack", "compound-engineering", "baseline"]
LABELS = {"superpowers": "Superpowers", "feature-dev": "Feature Dev", "gstack": "gstack", "compound-engineering": "Compound Engineering",
          "baseline": "baseline", "reference": "参照の系列（確認用）", "shortest": "最短の系列（確認用）"}
COLORS = {"superpowers": "#2a6fdb", "feature-dev": "#d9822b", "gstack": "#2f9e44", "compound-engineering": "#9c36b5",
          "baseline": "#495057", "reference": "#adb5bd", "shortest": "#e03131"}
METRICS = [
    ("all", "全機能の隠しテストの通過率", lambda r: r.get("all")),
    ("cx_mean", "関数の複雑さ（平均）", lambda r: (r.get("metrics") or {}).get("cx_mean")),
    ("cx_over10", "複雑さが 10 を超える関数の数", lambda r: (r.get("metrics") or {}).get("cx_over10")),
    ("dup_pct", "重複の割合（%）", lambda r: (r.get("metrics") or {}).get("dup_pct")),
    ("max_file_lines", "最も大きいファイルの行数", lambda r: (r.get("metrics") or {}).get("max_file_lines")),
    ("lint_warnings", "lint の警告の数", lambda r: (r.get("metrics") or {}).get("lint_warnings")),
    ("test_cases", "テストケースの数", lambda r: (r.get("metrics") or {}).get("test_cases")),
    ("mutation", "ミューテーションの検出率", lambda r: r.get("mutation")),
    ("cost_usd", "その回の費用（$）", lambda r: r.get("cost_usd")),
]


def load():
    return json.loads((RESULTS / "scores.json").read_text())


def groups(scores):
    out = {}
    for sid, s in scores.items():
        cond = sid.rsplit("-", 1)[0]
        out.setdefault(cond, []).append(s)
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def series_metric(ss, fn):
    return [mean([fn(s["rounds"][k]) for s in ss]) for k in range(6)]


def fmt(v, d=2):
    return "—" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def tables():
    g = groups(load())
    order = [c for c in CONDS if c in g] + [c for c in ("reference", "shortest") if c in g]
    lines = ["| 条件 | 系列 | 品質 | 各回の受け入れ 25 | 最終の全機能 20 | 後退の少なさ 10 | 引き継ぎ 25 | 設計 10 | テストの強さ 10 | 開発の費用 | 開発の時間 | 保守の費用 | 保守の時間 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in order:
        ss = g[c]
        p = lambda k: mean([s["points"][k] for s in ss])  # noqa: E731
        lines.append(f"| {LABELS.get(c, c)} | {len(ss)} | {fmt(p('total'), 1)} | {fmt(p('accept'), 1)} | {fmt(p('final_all'), 1)} | "
                     f"{fmt(p('no_regression'), 1)} | {fmt(p('handover'), 1)} | {fmt(p('design'), 1)} | {fmt(p('test_strength'), 1)} | "
                     f"${fmt(mean([s['dev_cost_usd'] for s in ss]))} | {fmt(mean([s['dev_seconds'] / 60 for s in ss]), 0)} 分 | "
                     f"${fmt(mean([s['maint_cost_usd'] for s in ss]))} | {fmt(mean([s['maint_seconds'] / 60 for s in ss]), 0)} 分 |")
    out = ["## 系列の点数（2 系列の平均）", "", *lines, ""]
    for key, title, fn in METRICS:
        out += [f"### {title}（回ごと）", "", "| 条件 | " + " | ".join(f"第 {k} 回" for k in range(1, 7)) + " |", "|---|" + "---:|" * 6]
        for c in order:
            vals = series_metric(g[c], fn)
            out.append(f"| {LABELS.get(c, c)} | " + " | ".join(fmt(v) for v in vals) + " |")
        out.append("")
    out += ["## 引き継ぎ（固定のエージェント）", "", "| 条件 | h1 の通過率 | h1 の後退なし | h2 の通過率 | h2 の後退なし | h1 の費用 | h2 の費用 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for c in order:
        ss = g[c]
        hv = lambda h, k: mean([s["handover"][h].get(k) for s in ss])  # noqa: E731
        out.append(f"| {LABELS.get(c, c)} | {fmt(hv('h1', 'task'))} | {fmt(hv('h1', 'kept'))} | {fmt(hv('h2', 'task'))} | {fmt(hv('h2', 'kept'))} | "
                   f"${fmt(hv('h1', 'cost_usd'))} | ${fmt(hv('h2', 'cost_usd'))} |")
    (RESULTS / "tables.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


def svg_chart(title, data, w=520, h=260):
    """data: {cond: [v1..v6]}。折れ線のグラフ（SVG）"""
    vals = [v for vs in data.values() for v in vs if v is not None]
    if not vals:
        return ""
    lo, hi = min(0, min(vals)), max(vals) or 1
    pad_l, pad_r, pad_t, pad_b = 48, 120, 28, 30
    x = lambda i: pad_l + i * (w - pad_l - pad_r) / 5  # noqa: E731
    y = lambda v: pad_t + (h - pad_t - pad_b) * (1 - (v - lo) / ((hi - lo) or 1))  # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{title}" class="chart">',
             f'<text x="{pad_l}" y="16" class="t">{title}</text>']
    for i in range(6):
        parts.append(f'<text x="{x(i):.1f}" y="{h - 10}" class="ax" text-anchor="middle">{i + 1}</text>')
    for frac in (0, 0.5, 1):
        v = lo + (hi - lo) * frac
        parts.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                     f'<text x="{pad_l - 6}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{v:.2g}</text>')
    for n, (c, vs) in enumerate(data.items()):
        pts = [(x(i), y(v)) for i, v in enumerate(vs) if v is not None]
        if not pts:
            continue
        dash = ' stroke-dasharray="4 3"' if c in ("reference", "shortest") else ""
        parts.append(f'<polyline fill="none" stroke="{COLORS.get(c, "#000")}" stroke-width="2"{dash} points="'
                     + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        parts.append(f'<text x="{w - pad_r + 8}" y="{pad_t + 14 * n + 8}" class="lg" fill="{COLORS.get(c, "#000")}">{LABELS.get(c, c)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def charts(out):
    g = groups(load())
    order = [c for c in CONDS if c in g] + [c for c in ("reference", "shortest") if c in g]
    html = []
    for key, title, fn in METRICS:
        html.append(svg_chart(title, {c: series_metric(g[c], fn) for c in order}))
    Path(out).write_text("\n".join(html) + "\n")
    print(f"{len(html)} charts -> {out}")


if __name__ == "__main__":
    if sys.argv[1] == "tables":
        tables()
    else:
        charts(sys.argv[2])
