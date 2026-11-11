#!/usr/bin/env python3
"""W15 の品質の点数（100 点）を、grade_w15.py の結果から計算する（配点は docs/poc/answer-key/W15/grading.md）。

使い方:
  python3 scripts/poc/score_w15.py                       results/workflow/W15/W15-*.json を集計して scores.json を書く
  python3 scripts/poc/score_w15.py --file <JSON> [--design <0〜15>]   1 つの結果（--app の出力）を採点して表示する（試行前の確認用）

設計の筋（15 点）はブラインドレビュー（blind_w15.py collect → results/workflow/W15/blind/scores.json の 2 名の平均。18 点満点を 15 点に換算）。
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W15"
ORDER_POINTS = {"before": 6, "same": 3, "after": 1.5, "none": 0}


def score(w, design=None):
    checks = w.get("checks", {})
    pub, hid, gold = w.get("public", []), w.get("hidden", []), w.get("golden", [])
    business = 4 * sum(1 for x in pub if x["pass"]) + sum(2 / 3 for k in ("typecheck", "test", "build") if checks.get(k)) \
        + 24 / 9 * sum(1 for x in hid if x["pass"])
    golden = 2.5 * sum(1 for x in gold if x["pass"])
    ch = w.get("characterization", {})
    # 分母は、初期状態の古い取込処理から作った変異体の全部（legacy_mutants）。候補が古い処理を書き直して元の行が
    # 残っていない変異体は「検出できなかった」と数える（残った行だけを分母にすると、書き直すほど点が上がるため。試行前の確認で直した）
    total = ch.get("legacy_mutants") or ch.get("mutants")
    c1 = 14 * ch.get("killed", 0) / total if total else 0.0
    characterization = c1 + ORDER_POINTS.get(ch.get("order"), 0)
    mu = w.get("mutation") or {}
    test_strength = 10 * (mu.get("killed", 0) / mu["mutants"]) if mu.get("mutants") else 0.0
    parts = {"business": round(business, 1), "golden": round(golden, 1), "characterization": round(characterization, 1),
             "design": None if design is None else round(design, 1), "test_strength": round(test_strength, 1)}
    parts["quality"] = round(sum(v for v in parts.values() if v is not None), 1)
    return parts


def main():
    args = sys.argv[1:]
    if args and args[0] == "--file":
        w = json.loads(Path(args[1]).read_text())
        design = float(args[args.index("--design") + 1]) if "--design" in args else None
        print(json.dumps(score(w.get("w15", w), design), ensure_ascii=False))
        return
    out = {}
    for f in sorted(glob.glob(str(RESULTS / "W15-*.json"))):
        r = json.loads(Path(f).read_text())
        trial = Path(f).stem
        bl = RESULTS / "blind" / "scores.json"
        b = json.loads(bl.read_text())["by_trial"].get(trial) if bl.exists() else None
        design = 15 * b["mean"] / 18 if b else None
        s = score(r.get("w15", {}), design)
        s.update({"cost_usd": r.get("cost_usd"), "elapsed_seconds": r.get("elapsed_seconds"), "interventions": r.get("interventions")})
        out[trial] = s
    (RESULTS / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
