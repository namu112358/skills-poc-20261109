#!/usr/bin/env python3
"""W14 の品質の点数（100 点）を、grade_w14.py の結果から計算する（配点は poc/answer-key/W14/grading.md）。

使い方:
  python3 poc/scripts/score_w14.py                       results/workflow/W14/W14-*.json を集計して scores.json を書く
  python3 poc/scripts/score_w14.py --file <JSON> [--design <0〜15>]   1 つの結果（--app の出力）を採点して表示する（試行前の確認用）

設計の筋（15 点）はブラインドレビュー（blind_w14.py collect → results/workflow/W14/blind/scores.json の 2 名の平均。18 点満点を 15 点に換算）。
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W14"

MIGRATION_WEIGHTS = {"M1": 4, "M2": 3, "M3": 2, "M4": 4, "M5": 4, "M6": 4, "M7": 3, "M8": 3, "M9": 3}


def score(w, design=None):
    checks = w.get("checks", {})
    pub = w.get("public", [])
    hid = w.get("hidden", [])
    business = 0.75 * sum(1 for x in pub if x["pass"]) + sum(2 / 3 for k in ("typecheck", "test", "build") if checks.get(k)) \
        + 2 * sum(1 for x in hid if x["pass"])
    m = w.get("migration", {}).get("checks", {})
    migration = sum(wt for k, wt in MIGRATION_WEIGHTS.items() if m.get(k))
    n = w.get("normalize", {})
    if n.get("available"):
        wr = n.get("wrong_rate", 1)
        normalize = 6 * n.get("export_accuracy", 0) + 3 * n.get("hidden_accuracy", 0) + (3 if wr <= 0.005 else 1.5 if wr <= 0.02 else 0) \
            + 1.5 * n.get("unresolved_kept_ratio", 0) + (1.5 if 14 <= n.get("master_rows", 0) <= 20 else 0)
    else:
        normalize = 0.0
    ops = w.get("ops", {}).get("total", 0)
    mu = w.get("mutation") or {}
    test_strength = 10 * (mu.get("killed", 0) / mu["mutants"]) if mu.get("mutants") else 0.0
    parts = {"business": round(business, 1), "migration": round(migration, 1), "normalize": round(normalize, 1), "ops": round(ops, 1),
             "design": None if design is None else round(design, 1), "test_strength": round(test_strength, 1)}
    parts["quality"] = round(sum(v for v in parts.values() if v is not None), 1)
    return parts


def main():
    args = sys.argv[1:]
    if args and args[0] == "--file":
        w = json.loads(Path(args[1]).read_text())
        design = float(args[args.index("--design") + 1]) if "--design" in args else None
        print(json.dumps(score(w.get("w14", w), design), ensure_ascii=False))
        return
    out = {}
    for f in sorted(glob.glob(str(RESULTS / "W14-*.json"))):
        r = json.loads(Path(f).read_text())
        trial = Path(f).stem
        bl = RESULTS / "blind" / "scores.json"
        b = json.loads(bl.read_text())["by_trial"].get(trial) if bl.exists() else None
        design = 15 * b["mean"] / 18 if b else None  # 6 項目 × 0〜3 点（18 点満点）を 15 点に換算
        w = r.get("w14", {})
        s = score(w, design)
        s.update({"cost_usd": r.get("cost_usd"), "elapsed_seconds": r.get("elapsed_seconds"), "interventions": r.get("interventions")})
        out[trial] = s
    (RESULTS / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
