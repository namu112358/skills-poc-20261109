#!/usr/bin/env python3
"""W21・W22 の結果の表を作る（report.md に貼る数字の出どころ）。

使い方: python3 scripts/poc/report_w21.py > docs/poc/results/workflow/W21/tables.md
  - results/workflow/W21/<試行ID>.json（繰り返し 0 の動作確認は除く）と judge/ の AI 判定・レビュー判定から、課題 × 構成の表を書く。
  - 人の順位付け（順位付けのページの db）は、依頼者が付けた後に別に集計する。
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "docs" / "poc" / "results" / "workflow" / "W21"
LABEL = {"ui-none": "ツールなし", "ui-all": "4 つすべて", "ui-a": "Impeccable（整理案 A）", "ui-fd": "Frontend Design",
         "ui-pm": "UI/UX Pro Max", "ui-fd-md": "Frontend Design + 指示", "ui-a-md": "Impeccable + 指示", "ui-all-md": "4 つすべて + 役割の指示"}
TASKS = {"W21a": "紹介ページ", "W21b": "タスク一覧の改善", "W21c": "UI レビュー", "W21d": "SaaS の LP", "W21e": "ダッシュボード", "W21f": "登録フォーム"}
DESIGN_SKILLS = ("frontend-design", "web-design-guidelines", "impeccable", "ui-ux-pro-max")


def load():
    rows = defaultdict(list)
    for f in sorted(R.glob("W21*-ui-*.json")):
        d = json.loads(f.read_text())
        if d["rep"] == 0:
            continue
        rows[(d["task"], d["config"])].append(d)
    return rows


def visual():
    v = {}
    for f in R.glob("judge/visual-*.json"):
        for t, x in json.loads(f.read_text())["per_trial"].items():
            v[t] = x["mean_total"]
    return v


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def main():
    rows, vis = load(), visual()
    review = {}
    if (R / "scores.json").exists():
        review = {t: s for t, s in json.loads((R / "scores.json").read_text()).items() if s["task"] == "W21c"}
    for task, name in TASKS.items():
        cfgs = [c for c in LABEL if (task, c) in rows]
        if not cfgs:
            continue
        print(f"### {task} {name}\n")
        if task == "W21c":
            print("| 構成 | 回数 | 品質 / 100 | 見つけた問題 / 9 | おとり・誤りへの指摘 | 費用（平均） | Skill が呼ばれた回数 |")
            print("|---|---:|---:|---:|---:|---:|---|")
        else:
            print("| 構成 | 回数 | AI の見た目の判定 / 20 | 機械の検査 / 50 | 費用（平均） | 時間（平均・分） | デザインの Skill が呼ばれた回数 | 呼ばれた Skill |")
            print("|---|---:|---:|---:|---:|---:|---|---|")
        for c in cfgs:
            ds = rows[(task, c)]
            used = [[s for s in d["transcript"]["skills_used"] if s.split(":")[0] in DESIGN_SKILLS or s.split(":")[-1] in DESIGN_SKILLS] for d in ds]
            names = sorted({s for u in used for s in u})
            cost = mean([d["transcript"]["cost_usd"] for d in ds])
            if task == "W21c":
                sc = [review.get(d["trial"]) for d in ds]
                sc = [s for s in sc if s]
                print(f"| {LABEL[c]} | {len(ds)} | {fmt(mean([s['quality'] for s in sc]))} | {fmt(mean([len(s['found']) for s in sc]))} | "
                      f"{fmt(mean([len(s['decoys']) + s['wrong'] for s in sc]))} | ${cost:.2f} | {sum(bool(u) for u in used)} / {len(ds)} |")
            else:
                print(f"| {LABEL[c]} | {len(ds)} | {fmt(mean([vis.get(d['trial']) for d in ds]))} | {fmt(mean([d['score']['subtotal_50'] for d in ds]))} | "
                      f"${cost:.2f} | {fmt(mean([(d['elapsed_seconds'] or 0) / 60 for d in ds]))} | {sum(bool(u) for u in used)} / {len(ds)} | {', '.join(names) or 'なし'} |")
        print()
    # Skill が呼ばれたかどうかでの AI 判定の差
    print("### デザインの Skill が呼ばれたかどうかと AI の見た目の判定\n")
    print("| 課題 | 呼ばれた試行（数・平均） | 呼ばれなかった試行（数・平均） |")
    print("|---|---|---|")
    for task in TASKS:
        inv, no = [], []
        for (t, c), ds in rows.items():
            if t != task or c == "ui-none":
                continue
            for d in ds:
                if d["trial"] not in vis:
                    continue
                u = [s for s in d["transcript"]["skills_used"] if any(k in s for k in DESIGN_SKILLS)]
                (inv if u else no).append(vis[d["trial"]])
        if inv or no:
            print(f"| {task} {TASKS[task]} | {len(inv)} 件・{fmt(mean(inv))} | {len(no)} 件・{fmt(mean(no))} |")
    print("\n（ツールなしの構成は除く。AI の判定は 5 項目 × 0〜4 点、順番を変えた 2 回の平均）")


if __name__ == "__main__":
    main()
