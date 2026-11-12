#!/usr/bin/env python3
"""二択のページ（pairs_u1.py）の回答を集計する。

使い方: python3 scripts/poc/pairs_summary_u1.py <回答の JSON があるディレクトリ> > docs/poc/results/workflow/U1/human-pairs.md
  - 回答は ArtifactData の list で out_dir に保存したもの（votes/<id>.json。中身は {task, left, right, choice, at}）。
  - 構成ごとの勝率（勝ち 1・同じくらい 0.5・負け 0）、Bradley–Terry の強さ、デザインの Skill が呼ばれたかどうかでの勝率、
    同じ組での AI の判定との一致、左右の偏りを書く。
"""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "docs" / "poc" / "results" / "workflow" / "U1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_u1 import LABEL, TASKS  # noqa: E402

DESIGN = ("frontend-design", "impeccable", "ui-ux-pro-max", "web-design-guidelines")


def load_votes(d):
    out = []
    for f in sorted(Path(d).rglob("*.json")):
        v = json.loads(f.read_text())
        v = v.get("data", v)
        if {"task", "left", "right", "choice"} <= v.keys():
            # 二択のページの保存先には、改名前の ID（W21a-… など）で残っている。U1 の ID に読み替える
            for k in ("task", "left", "right"):
                v[k] = re.sub(r"^W21", "U1", v[k])
            out.append(v)
    return out


def trial(t):
    return json.loads((R / f"{t}.json").read_text())


def config(t):
    return trial(t)["config"]


def invoked(t):
    return any(any(k in s for k in DESIGN) for s in trial(t)["transcript"]["skills_used"])


def ai_scores():
    v = {}
    for f in R.glob("judge/visual-*.json"):
        for t, x in json.loads(f.read_text())["per_trial"].items():
            v[t] = x["mean_total"]
    return v


def outcomes(votes, key):
    """key(trial) ごとの [勝ち点, 回数]。"""
    s = defaultdict(lambda: [0.0, 0])
    for v in votes:
        l, r = key(v["left"]), key(v["right"])
        if l == r:
            continue
        lw = 1.0 if v["choice"] == "left" else 0.5 if v["choice"] == "same" else 0.0
        s[l][0] += lw; s[l][1] += 1
        s[r][0] += 1 - lw; s[r][1] += 1
    return s


def bradley_terry(votes, key, iters=200):
    """同じくらいは半分ずつの勝ちとして数える。強さは平均 1 に正規化し、log を 0 中心で返す。"""
    wins = defaultdict(float)
    games = defaultdict(float)
    items = set()
    for v in votes:
        a, b = key(v["left"]), key(v["right"])
        if a == b:
            continue
        items |= {a, b}
        w = 1.0 if v["choice"] == "left" else 0.5 if v["choice"] == "same" else 0.0
        wins[a] += w; wins[b] += 1 - w
        games[(a, b)] += 1; games[(b, a)] += 1
    p = {i: 1.0 for i in items}
    for _ in range(iters):
        new = {}
        for i in items:
            den = sum(games[(i, j)] / (p[i] + p[j]) for j in items if j != i and games[(i, j)])
            new[i] = (wins[i] + 0.1) / den if den else p[i]
        m = sum(new.values()) / len(new)
        p = {i: x / m for i, x in new.items()}
    return {i: math.log(x) for i, x in p.items()}


def table(title, s, bt=None):
    rows = sorted(s.items(), key=lambda kv: -kv[1][0] / kv[1][1])
    print(f"### {title}\n")
    print("| 構成 | 勝率 | 比べた回数 |" + (" Bradley–Terry（log、0 が平均） |" if bt else ""))
    print("|---|---:|---:|" + ("---:|" if bt else ""))
    for k, (w, n) in rows:
        print(f"| {LABEL.get(k, k)} | {w / n * 100:.0f}% | {n} |" + (f" {bt.get(k, 0):+.2f} |" if bt else ""))
    print()


def main(d):
    votes = load_votes(d)
    print(f"# 依頼者の二択の回答の集計（{len(votes)} 件）\n")
    print("勝率は、勝ち 1・同じくらい 0.5・負け 0 として、その構成の画面が出た比較の平均。各試行の画面は幅 1280px のページ全体。\n")
    table("全題材", outcomes(votes, config), bradley_terry(votes, config))
    for task, name in TASKS.items():
        vs = [v for v in votes if v["task"] == task]
        if vs:
            table(f"{task} {name}（{len(vs)} 件）", outcomes(vs, config))
    # デザインの Skill が呼ばれたかどうか（ツールなしを除いた試行どうし）
    vs = [v for v in votes if "ui-none" not in (config(v["left"]), config(v["right"]))]
    s = outcomes(vs, lambda t: "呼ばれた" if invoked(t) else "呼ばれなかった")
    print("### デザインの Skill が呼ばれた試行と呼ばれなかった試行（ツールなしの構成は除く）\n")
    print("| | 勝率 | 比べた回数 |\n|---|---:|---:|")
    for k, (w, n) in s.items():
        print(f"| {k} | {w / n * 100:.0f}% | {n} |")
    print()
    # AI の判定との一致（同じ組で、AI の点が高い方を依頼者も選んだか）
    ai = ai_scores()
    agree = disagree = tie_ai = same_h = 0
    for v in votes:
        a, b = ai.get(v["left"]), ai.get(v["right"])
        if a is None or b is None:
            continue
        if v["choice"] == "same":
            same_h += 1; continue
        if a == b:
            tie_ai += 1; continue
        ai_left = a > b
        if ai_left == (v["choice"] == "left"):
            agree += 1
        else:
            disagree += 1
    n = agree + disagree
    print("### AI の判定との一致\n")
    print(f"依頼者がどちらかを選んだ組のうち、AI の点が高い方と同じだったのは {agree} / {n} 件"
          f"（{agree / n * 100:.0f}%。偶然なら 50%）。AI の点が同じだった組 {tie_ai} 件、依頼者が「同じくらい」を選んだ組 {same_h} 件は除く。\n" if n else "比べられる組がまだ無い。\n")
    # 左右の偏り
    c = defaultdict(int)
    for v in votes:
        c[v["choice"]] += 1
    print("### 左右の偏り\n")
    print(f"左 {c['left']} 件・右 {c['right']} 件・同じくらい {c['same']} 件（左右はランダムに入れ替えて出している）。")


if __name__ == "__main__":
    main(sys.argv[1])
