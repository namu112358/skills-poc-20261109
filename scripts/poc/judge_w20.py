#!/usr/bin/env python3
"""W20・W21 の判定（指摘と正解の突き合わせ）の資料作りと集計。docs/poc/tasks/wf-W20-design.md の「判定」。
W21 は環境変数 POC_E2_SCENARIO=W21 で使う（既定は W20。docs/poc/tasks/wf-W21-design.md）。

使い方:
  python3 scripts/poc/judge_w20.py prepare <出力先>
    - results/workflow/W20/W20-*.json（繰り返し 0 の動作確認は除く）を、記号 J01〜 の資料にする。各資料は、題材の正解の一覧
      （answer-key/W20/cases/<題材>/truth.md）と REVIEW.md。設定の名前は伏せる。記号の順番は乱数（種 20261120）。
    - 2 回判定する資料（全体の約 25%。各設定から同じ数）を選び、twice.json に書く。
    - 記号と試行 ID の対応は results/workflow/W20/judge/mapping.json（判定役には渡さない）。
  python3 scripts/poc/judge_w20.py collect
    - judge/J01.json〜（判定役の出力）と、2 回目の judge/J01-b.json を集計し、judge/scores.json を書く。
      判定役の出力の形: {"findings": [{"n": 1, "summary": "..", "severity": "高|中|低|なし", "match": "B1|D2|none",
                                        "kind": "real|wrong|nit|unsure"}]}
      match が正解の ID のとき kind は見ない。none のとき kind は、real = 正解外だが本当らしい問題、wrong = 事実と違う・直すと害、
      nit = 好み・細かい点、unsure = 判断できない（担当が読んで決め、judge/manual.json に {"J01": {"3": "real"}} の形で上書きする）。
"""
import glob
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = os.environ.get("POC_E2_SCENARIO", "W20")
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / SCENARIO
# W22 は W21 の題材と正解を使う
CASES = ROOT / "docs" / "poc" / "answer-key" / ({"W22": "W21", "W25": "W21", "W26": "W24"}.get(SCENARIO, SCENARIO)) / "cases"
JUDGE = RESULTS / "judge"
SEED = {"W20": 20261120, "W21": 20261121, "W22": 20261122, "W23": 20261123, "W24": 20261124, "W25": 20261125}.get(SCENARIO, 20261126)
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|pr-review-toolkit|review-pr|code-review|compound|gstack|claude|"
                   r"design-principles-review|\bce-[a-z-]+|silent-failure-hunter|pr-test-analyzer|type-design-analyzer|"
                   r"comment-analyzer|code-simplifier", re.I)
ID_RE = r"[BGDPI]\d+"

INSTRUCTIONS = """# 判定の依頼

あなたはコードレビューの採点者です。下の「レビューの指摘」（REVIEW.md）を、指摘 1 件ずつに分け（見出し・箇条書きの 1 項目を 1 件。
1 項目に別々の問題が 2 つ以上書かれていれば分ける）、それぞれを「正解の一覧」と突き合わせてください。

- match: 正解の ID（B1・G1・P1・I1・D2 など）か none。正解に一致するのは、場所（ファイルと関数）と仕組みの核心の両方を述べているときだけ。
  場所だけ合っていて別の問題を述べているもの、一般論（「入力検証を強化すべき」だけ）は none。
  D で始まる ID（おとり）は、そこを「問題がある」と指摘したときに付ける（「問題ない」と書いただけなら付けない）。
- kind（match が none のときだけ）: real = 正解の一覧に無いが、コードの本当の問題らしい / wrong = 事実と違う、または直すと害がある /
  nit = 好み・書き方・細かい点 / unsure = 判断できない。
- severity: 指摘に付いている重要度（高・中・低。無ければ なし）。

出力は JSON だけを、指定のファイルに書いてください:
{"findings": [{"n": 1, "summary": "指摘の要約（1 文）", "severity": "高", "match": "B1", "kind": ""}, ...]}
"""


def trials():
    out = []
    for f in sorted(glob.glob(str(RESULTS / f"{SCENARIO}-*.json"))):
        r = json.loads(Path(f).read_text())
        if r.get("rep", 0) >= 1:
            out.append(r)
    return out


def prepare(dest):
    dest.mkdir(parents=True, exist_ok=True)
    rs = trials()
    rnd = random.Random(SEED)
    rnd.shuffle(rs)
    mapping = {}
    for i, r in enumerate(rs, 1):
        code = f"J{i:02d}"
        mapping[code] = r["trial"]
        truth = (CASES / r["case"] / "truth.md").read_text()
        body = (f"{INSTRUCTIONS}\n---\n\n# 正解の一覧（題材 {r['case']}）\n\n{truth}\n\n---\n\n# レビューの指摘（REVIEW.md）\n\n"
                f"{r['review_md'] or '（REVIEW.md が無い。指摘 0 件）'}\n")
        (dest / f"{code}.md").write_text(NAMES.sub("[redacted]", body))
    by_cfg = {}
    for code, t in mapping.items():
        by_cfg.setdefault(re.sub(r"-[cd]\d+-\d+$", "", t), []).append(code)
    per = max(1, round(len(mapping) * 0.25 / max(1, len(by_cfg))))
    twice = sorted(c for codes in by_cfg.values() for c in rnd.sample(codes, min(per, len(codes))))
    JUDGE.mkdir(parents=True, exist_ok=True)
    (JUDGE / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    (JUDGE / "twice.json").write_text(json.dumps(twice) + "\n")
    print(f"{len(mapping)} 件 -> {dest}（2 回判定: {len(twice)} 件 {twice}）")


def truth_ids(case):
    text = (CASES / case / "truth.md").read_text()
    ids = sorted(set(re.findall(r"^\| (" + ID_RE + r") \|", text, re.M)), key=lambda s: (s[0], int(s[1:])))
    return [i for i in ids if not i.startswith("D")], [i for i in ids if i.startswith("D")]


def score_one(j, bugs, decoys, manual):
    fs = j.get("findings", [])
    for f in fs:
        k = manual.get(str(f.get("n")))
        if k:
            f["kind"] = k
    matched = sorted({f["match"] for f in fs if f.get("match") in bugs})
    decoy_hits = sorted({f["match"] for f in fs if f.get("match") in decoys})
    none = [f for f in fs if f.get("match") not in bugs and f.get("match") not in decoys]
    kinds = {k: sum(1 for f in none if f.get("kind") == k) for k in ("real", "wrong", "nit", "unsure")}
    high_noise = sum(1 for f in none if f.get("kind") in ("wrong", "nit") and f.get("severity") == "高")
    return {"findings": len(fs), "matched": matched, "recall": round(len(matched) / len(bugs), 3) if bugs else None,
            "decoy_hits": decoy_hits, "off_truth": kinds, "false": kinds["wrong"] + len(decoy_hits), "high_noise": high_noise}


def collect():
    mapping = json.loads((JUDGE / "mapping.json").read_text())
    manual_all = json.loads((JUDGE / "manual.json").read_text()) if (JUDGE / "manual.json").exists() else {}
    by_id = {r["trial"]: r for r in trials()}
    out, agree = {}, []
    for code, trial in mapping.items():
        r = by_id[trial]
        bugs, decoys = truth_ids(r["case"])
        j = json.loads((JUDGE / f"{code}.json").read_text())
        s = score_one(j, bugs, decoys, manual_all.get(code, {}))
        s.update({"code": code, "config": r["config"], "case": r["case"], "rep": r["rep"],
                  "cost_usd": r["transcript"].get("cost_usd"), "bugs": bugs})
        b = JUDGE / f"{code}-b.json"
        if b.exists():
            s2 = score_one(json.loads(b.read_text()), bugs, decoys, manual_all.get(code, {}))
            same = s2["matched"] == s["matched"] and s2["decoy_hits"] == s["decoy_hits"]
            agree.append({"code": code, "same": same, "a": s["matched"], "b": s2["matched"]})
        out[trial] = s
    rate = round(sum(a["same"] for a in agree) / len(agree), 3) if agree else None
    (JUDGE / "scores.json").write_text(json.dumps({"by_trial": out, "agreement": {"rate": rate, "pairs": agree}},
                                                  ensure_ascii=False, indent=1) + "\n")
    print(f"判定の一致率（正解の一致・おとり）: {rate}（{len(agree)} 組）")
    for t, s in sorted(out.items()):
        print(f"{t:28} recall={s['recall']} matched={s['matched']} false={s['false']} off={s['off_truth']} ${s['cost_usd']}")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    else:
        collect()
