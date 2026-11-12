#!/usr/bin/env python3
"""W34 の集計表（レビューで見つけた数と、直した後の質）。poc/tasks/wf-W34-design.md。
使い方: python3 poc/scripts/report_w34.py > poc/results/workflow/W34/tables.md
入力: results/workflow/W34/W34-*.json（grade_w34.py）と judge/scores.json（POC_E2_SCENARIO=W34 judge_w20.py collect）。
"""
import json, glob
from collections import defaultdict
from pathlib import Path
RES = Path(__file__).resolve().parents[2] / "poc/results/workflow/W34"
CFG = ["baseline", "cr-high", "review-pr", "review-pr-full", "principles", "ce-review", "ce-full"]
LABEL = {"baseline": "道具なし", "cr-high": "内蔵 /code-review high", "review-pr": "/review-pr", "review-pr-full": "/review-pr（専門エージェントを明示）",
         "principles": "design-principles-review", "ce-review": "ce-code-review", "ce-full": "ce-code-review depth:full"}
scores = json.loads((RES / "judge/scores.json").read_text())["by_trial"]
rows = defaultdict(list)
for f in sorted(glob.glob(str(RES / "W34-*-[12].json"))):
    r = json.loads(Path(f).read_text()); s = scores.get(r["trial"], {})
    rows[(r["case"], r["config"])].append((r, s))
def fmt(vals): return "・".join(vals)
out = []
for case, title, extra in [
    ("f1", "f1 作りすぎ・重複・不具合", "不具合を直した（隠し 5/5）／登録の仕組みを消した"),
    ("f2", "f2 ファイル分割で消えた振る舞い", "隠しテスト（4 項目）"),
    ("f3", "f3 弱いテスト", "変異を落とせた数／対象 ・ 隠しテスト（5 項目）"),
    ("f4", "f4 時間がたつと落ちるテスト", "時間がたった状態で落ちる数（5 中。P3 を除くと 4 中）・ 変異（6 中）・ 隠しテスト（4 項目）")]:
    out.append(f"## {title}\n\n| 設定 | レビューで見つけた正解 | 直した後: {extra} | 差分（足した行・消した行。PR は " + {"f1":"150・12","f2":"218・217","f3":"89・0","f4":"89・0"}[case] + "） | 1 回の費用 |")
    out.append("|---|---|---|---|---|")
    for c in CFG:
        items = rows.get((case, c), [])
        if not items: continue
        found = [f"{len(s.get('matched', []))}/{len(s.get('bugs', [])) or '?'}" for _, s in items]
        post = []
        for r, _ in items:
            e = r["eval"]; h = f"{e['hidden']['passed']}/{e['hidden']['total']}"
            if case == "f1":
                post.append(("直した" if e['hidden']['passed'] == e['hidden']['total'] else "残した") + "／" + ("残した" if e['design']['registry_remains'] else "消した"))
            elif case == "f2":
                post.append(h)
            elif case == "f3":
                m = e.get("mutation", {}); post.append(f"{m.get('killed')}/{m.get('applicable')} ・ {h}")
            else:
                m = e.get("mutation", {}); p = e["perturb"]; noP3 = sum(1 for x in p["perturbations"] if x["status"] == "fail" and x["id"] != "P3")
                post.append(f"{p['fragile']}（{noP3}） ・ {m.get('killed')}/{m.get('applicable')} ・ {h}")
        diff = [f"{r['fixed']['diff_added']}・{r['fixed']['diff_deleted']}" for r, _ in items]
        cost = sum(r["transcript"]["cost_usd"] for r, _ in items) / len(items)
        out.append(f"| {LABEL[c]} | {fmt(found)} | {fmt(post)} | {fmt(diff)} | ${cost:.2f} |")
    out.append("")
print("\n".join(out))
