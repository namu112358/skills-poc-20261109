#!/usr/bin/env python3
"""W19 の品質の点数（100 点）を、grade_w19.py の結果から計算する（配点は docs/poc/answer-key/W19/grading.md）。

使い方:
  python3 scripts/poc/score_w19.py                       results/workflow/W19/W19-*.json を集計して scores.json を書く
  python3 scripts/poc/score_w19.py --file <JSON> [--design <0〜15>]   1 つの結果（--app の出力）を採点して表示する（試行前の確認用）

設計の筋（15 点）はブラインドレビュー（blind_w19.py collect → results/workflow/W19/blind/scores.json の 2 名の平均。18 点満点を 15 点に換算）。
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W19"
STRUCTURE = {"S1": 6, "S2": 6, "S3": 5, "S4": 4, "S5": 4}
MIGRATION = {"M1": 3, "M2": 2, "M3": 2, "M4": 3, "M5": 3, "M6": 2, "M7": 2, "M8": 3}
SCOPE = {"R1": 3, "R2": 2}


def pts(d, table):
    c = (d or {}).get("checks", {})
    return sum(v for k, v in table.items() if c.get(k))


def migration_points(m):
    """旧データの点検者を移していない（寄せられた割合が 5 割未満）なら、壊していないこと（M1・M4）だけを数える。
    何も移さなければ、データを失わない・2 回目の起動・戻しは自然に通るため（試行前の確認で直した）。"""
    ratio = ((m or {}).get("detail") or {}).get("linked_ratio") or 0
    table = MIGRATION if ratio >= 0.5 else {k: MIGRATION[k] for k in ("M1", "M4")}
    return pts(m, table)


def score(w, design=None):
    checks = w.get("checks", {})
    ok = lambda k: checks[k] if isinstance(checks.get(k), bool) else bool((checks.get(k) or {}).get("pass"))  # noqa: E731
    business = 1.5 * sum(1 for x in w.get("public", []) if x["pass"]) + sum(0.5 for k in ("typecheck", "test", "build") if ok(k)) \
        + 1.9 * sum(1 for x in w.get("hidden", []) if x["pass"])
    mu = w.get("mutation") or {}
    test_strength = 10 * (mu.get("killed", 0) / mu["mutants"]) if mu.get("mutants") else 0.0
    parts = {"business": round(business, 1), "structure": pts(w.get("structure"), STRUCTURE),
             "migration": migration_points(w.get("migration")), "scope": pts(w.get("scope"), SCOPE),
             "design": None if design is None else round(design, 1), "test_strength": round(test_strength, 1)}
    parts["quality"] = round(sum(v for v in parts.values() if v is not None), 1)
    return parts


def main():
    args = sys.argv[1:]
    if args and args[0] == "--file":
        w = json.loads(Path(args[1]).read_text())
        design = float(args[args.index("--design") + 1]) if "--design" in args else None
        print(json.dumps(score(w.get("w19", w), design), ensure_ascii=False))
        return
    out = {}
    bl = RESULTS / "blind" / "scores.json"
    blind = json.loads(bl.read_text())["by_trial"] if bl.exists() else {}
    for f in sorted(glob.glob(str(RESULTS / "W19-*.json"))):
        r = json.loads(Path(f).read_text())
        trial = Path(f).stem
        b = blind.get(trial)
        s = score(r.get("w19", {}), 15 * b["mean"] / 18 if b else None)
        s.update({"cost_usd": r.get("cost_usd"), "elapsed_seconds": r.get("elapsed_seconds"), "interventions": r.get("interventions")})
        out[trial] = s
    (RESULTS / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
