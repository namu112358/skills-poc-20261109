#!/usr/bin/env python3
"""W9（レビューで不具合を見つける）の指摘と正解の突き合わせ（ブラインド判定。poc/answer-key/W9/grading.md）。

使い方:
  python3 poc/scripts/blind_w9.py prepare <出力先ディレクトリ>
    - 出力先に R01.md〜 を書く。各ファイルはその試行の REVIEW.md（候補名・ツール名は [redacted] に置き換える）。
      費用・時間・候補名は載せない。記号と試行 ID の対応は W9/blind/mapping.json（判定者には渡さない）。
    - 出力先に判定用の資料（key.md: 正解リスト・おとり・突き合わせの基準・具体性、review.patch: レビュー対象の差分）も置く。
    - 出力先はリポジトリの外（スクラッチ領域）にする。
  python3 poc/scripts/blind_w9.py collect
    - W9/blind/reviewer-1.json・reviewer-2.json
      （{"R01": {"findings": [{"summary": "..", "class": "B1".."B10"|"valid"|"wrong"|"out", "specificity": 0-2, "reason": ".."}]}, ...}）
      を集計し、W9/blind/scores.json を書く。再現率・適合率・具体性は判定者ごとに計算した点数の平均。
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W9"
BLIND = RESULTS / "blind"
KEY = ROOT / "poc" / "answer-key" / "W9"
SEED = 20261109
BUGS = [f"B{i}" for i in range(1, 11)]
NAMES = re.compile(
    r"superpowers|feature[-_ ]?dev|gstack|compound(?:[-_ ]?engineering)?|\bce-[a-z-]+|ponytail|"
    r"code-reviewer|requesting-code-review|review army|/review\b", re.I)


def key_sections():
    """grading.md のうち判定者に渡す節（仕込んだ不具合・おとり・突き合わせ・具体性）。"""
    text = (KEY / "grading.md").read_text()
    start = text.index("### 仕込んだ不具合")
    end = text.index("## 配点")
    m_start = text.index("## 指摘と正解の突き合わせ")
    m_end = text.index("## 判定の手順")
    return "# W9 の正解リストと判定の基準\n\n" + text[start:end] + text[m_start:m_end]


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W9-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        t = json.loads((RESULTS / f"{trial}.json").read_text())
        body = t["w9"]["review_md"].strip() or "（REVIEW.md は無い）"
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", f"# {code}\n\n{body}\n"))
    (out / "key.md").write_text(key_sections())
    (out / "review.patch").write_text((KEY / "review.patch").read_text())
    BLIND.mkdir(parents=True, exist_ok=True)
    (BLIND / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} files -> {out}")


def judge_scores(entry):
    """1 名の判定者の 1 試行分の判定から、再現率・適合率・具体性の点数と内訳を返す。"""
    findings = entry.get("findings") or []
    spec = {}
    correct = wrong = 0
    for f in findings:
        cls = str(f.get("class", "")).strip()
        classes = [c.strip() for c in cls.split(",")]
        if any(c in BUGS for c in classes):
            correct += 1
            for c in classes:
                if c in BUGS:
                    spec[c] = max(spec.get(c, 0), max(1, min(2, int(f.get("specificity") or 1))))
        elif cls == "valid":
            correct += 1
        elif cls == "wrong":
            wrong += 1
    found = sorted(spec, key=lambda b: int(b[1:]))
    recall = 40 * len(found) / 10
    precision = 25 * correct / (correct + wrong) if (correct + wrong) else 0.0
    specificity = 20 * sum(spec.values()) / 20
    return {"found": found, "specificity_by_bug": spec, "correct": correct, "wrong": wrong,
            "findings": len(findings), "recall": recall, "precision": round(precision, 2),
            "specificity": specificity}


def collect():
    mapping = json.loads((BLIND / "mapping.json").read_text())
    revs = [json.loads((BLIND / f"reviewer-{i}.json").read_text()) for i in (1, 2)]
    by_trial = {}
    for code, trial in mapping.items():
        js = [judge_scores(r.get(code) or {}) for r in revs]
        dis = []
        for b in BUGS:
            hit = [b in j["found"] for j in js]
            if hit[0] != hit[1]:
                dis.append(f"{b}: 一致の判定が食い違い（判定者 {'1' if hit[0] else '2'} だけが一致とした）")
        p = [j["correct"] / (j["correct"] + j["wrong"]) if (j["correct"] + j["wrong"]) else 0 for j in js]
        if abs(p[0] - p[1]) >= 0.2:
            dis.append(f"適合率が 0.2 以上違う（{p[0]:.2f} と {p[1]:.2f}）")
        by_trial[trial] = {
            "code": code, "judges": js, "disagreements": dis,
            "judges_raw": [(r.get(code) or {}).get("findings") or [] for r in revs],
            "recall": round(sum(j["recall"] for j in js) / 2, 1),
            "precision": round(sum(j["precision"] for j in js) / 2, 1),
            "specificity": round(sum(j["specificity"] for j in js) / 2, 1),
            # 不具合ごとに、2 名のうち何名が一致としたか（0〜2）
            "bug_votes": {b: sum(b in j["found"] for j in js) for b in BUGS},
        }
    (BLIND / "scores.json").write_text(json.dumps({"by_trial": by_trial}, ensure_ascii=False, indent=2) + "\n")
    for trial, v in sorted(by_trial.items()):
        print(f"{trial:30} {v['code']} recall={v['recall']} precision={v['precision']} specificity={v['specificity']} "
              f"votes={''.join(str(n) for n in v['bug_votes'].values())} dis={len(v['disagreements'])}")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    else:
        collect()
