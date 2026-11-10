#!/usr/bin/env python3
"""W16 の品質の点数（100 点）を計算する（配点は docs/poc/answer-key/W16/grading.md）。

使い方:
  python3 scripts/poc/score_w16.py      results/workflow/W16/W16-*.json・judge/・reinject/・blind/scores.json を集計して scores.json を書く
  python3 scripts/poc/score_w16.py --file <grade の JSON> [--judge <JSON>] [--reinject <JSON>] [--design <0〜10>]   試行前の確認用

配点: 原因の特定 20（A 8・B 8・おとり 4）/ 原因に効く修正 30（I1〜I5 各 5、I6a・I6b 各 2.5）/ 後退なし 20（型チェック・単体テスト・ビルド 各 1、
W12 の受け入れ・隠し・堅牢さのうち出荷済みの版で通る項目の維持 10、本番の DB の M1 2・M2 1・M3 3・M4 1）/
再発防止のテスト 10（A 5・B 5）/ ログ・監視 10（L1 4・L2 3・L3 3）/ 設計の筋 10（ブラインドレビュー 2 名の平均（18 点満点）を換算）。
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W16"
KEY = ROOT / "docs" / "poc" / "answer-key" / "W16"
LEVEL = {"full": 1.0, "partial": 0.5, "none": 0.0, None: 0.0}


def regression_items(w):
    base = json.loads((KEY / "baseline-pass.json").read_text())
    reg = w.get("regression", {})
    got = {f"{k}:{x['id']}": x["pass"] for k, xs in reg.items() for x in xs}
    kept = [i for i in base if got.get(i)]
    return len(kept), len(base), sorted(set(base) - set(kept))


def score(w, judge=None, reinject=None, design=None):
    j = (judge or {}).get("final", {})
    cause = 8 * LEVEL[j.get("cause_a")] + 8 * LEVEL[j.get("cause_b")] + (4 if j.get("decoy") == "clean" else 0)
    inc = {x["id"]: x["pass"] for x in w.get("incident", []) + w.get("crash", [])}
    fix = 5 * sum(1 for i in ("I1", "I2", "I3", "I4", "I5") if inc.get(i)) + 2.5 * sum(1 for i in ("I6a", "I6b") if inc.get(i))
    checks = w.get("checks", {})
    n_kept, n_base, lost = regression_items(w)
    p = w.get("prod", {})
    rewritten = w.get("static", {}).get("migrations", {}).get("rewritten")
    regression = sum(1 for k in ("typecheck", "test", "build") if checks.get(k)) + 10 * n_kept / n_base \
        + 2 * bool(p.get("M1")) + 1 * bool(p.get("M2")) + 3 * bool(p.get("M3")) + (1 if rewritten == [] else 0)
    rc = (reinject or {}).get("causes", {})
    tests = 5 * bool(rc.get("A", {}).get("guarded")) + 5 * bool(rc.get("B", {}).get("guarded"))
    lg = w.get("logs", {})
    logs = 4 * bool(lg.get("L1")) + 3 * bool(lg.get("L2")) + 3 * bool(lg.get("L3"))
    parts = {"cause": round(cause, 1), "fix": fix, "regression": round(regression, 1), "tests": tests, "logs": logs,
             "design": None if design is None else round(design, 1)}
    parts["quality"] = round(sum(v for v in parts.values() if v is not None), 1)
    parts["regression_lost"] = lost
    return parts


def main():
    args = sys.argv[1:]
    if args and args[0] == "--file":
        w = json.loads(Path(args[1]).read_text())
        opt = lambda k: json.loads(Path(args[args.index(k) + 1]).read_text()) if k in args else None  # noqa: E731
        design = float(args[args.index("--design") + 1]) if "--design" in args else None
        print(json.dumps(score(w.get("w16", w), opt("--judge"), opt("--reinject"), design), ensure_ascii=False))
        return
    out = {}
    bl = RESULTS / "blind" / "scores.json"
    blind = json.loads(bl.read_text())["by_trial"] if bl.exists() else {}
    for f in sorted(glob.glob(str(RESULTS / "W16-*.json"))):
        trial = Path(f).stem
        r = json.loads(Path(f).read_text())
        load = lambda d: json.loads((RESULTS / d / f"{trial}.json").read_text()) if (RESULTS / d / f"{trial}.json").exists() else None  # noqa: E731
        b = blind.get(trial)
        s = score(r.get("w16", {}), load("judge"), load("reinject"), 10 * b["mean"] / 18 if b else None)
        tr = r.get("transcript", {})
        s.update({"cost_usd": tr.get("cost_usd"), "elapsed_seconds": r.get("elapsed_seconds"), "interventions": r.get("interventions")})
        out[trial] = s
    (RESULTS / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
