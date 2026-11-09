#!/usr/bin/env python3
"""W7（続けて行う作業での学習効果）の試行を採点用に調べ、results/workflow/W7/<試行ID>.json に書き出す。

使い方: python3 scripts/poc/grade_w7.py <試行ID>   （例: W7a-superpowers-1、W7b-superpowers-1）
  W7a は W7b を始める前に採点する（W7b は W7a の作業用コピーをそのまま使い、HEAD が進むため）。
  1. grade.py と同じ集計（型チェック・単体テスト・ビルド・隠しの E2E・差分・トランスクリプト）を行う。
  2. 次の W7 固有の事実を足す（docs/poc/answer-key/W7/grading.md）。
     - pitfalls:  run-trial.sh が試行中に判定した落とし穴の結果（pitfalls-<回>.json。1 回目が指摘を受ける前）
     - memory:    W7a の終了時点で、作業用コピーと専用 HOME に残っている「記憶」になりうるもの（W7a のみ）
     - memory_reads: 子セッションが記憶になりうるものを読んだ形跡（W7b のみ）
作業用コピーの片付けは、W7b の採点が済んでから python3 scripts/poc/grade.py W7a <W7a の試行 ID> --cleanup-only で行う。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TRIAL = sys.argv[1]
SCENARIO = TRIAL.split("-", 1)[0]
assert SCENARIO in ("W7a", "W7b"), TRIAL
# grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む。結果はどちらも results/workflow/W7/ に置く
sys.argv = [sys.argv[0], "W7", TRIAL]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

grade.SCENARIO = SCENARIO  # 受け入れテストの選択（answer-key/W7/acceptance-<W7a|W7b>.cjs）
ROOT, APP, RAW, OUT, WORK = grade.ROOT, grade.APP, grade.RAW, grade.OUT, grade.WORK

# 記憶になりうるもの: 候補が残す学習メモ・計画、エージェントが書いた指示ファイル
MEMORY_IN_APP = re.compile(r"^(docs/|CLAUDE\.md$|AGENTS\.md$|\.claude/(?!skills/)|\.compound-engineering/|.*\.md$)")
MEMORY_READ = re.compile(r"docs/solutions|docs/plans|learnings|CLAUDE\.md|AGENTS\.md|memory|\.gstack|ce-learnings|compound")


def pitfalls():
    rounds = []
    for f in sorted(RAW.glob("pitfalls-*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        d = json.loads(f.read_text())
        rounds.append({
            "round": int(re.search(r"(\d+)", f.stem).group(1)),
            "build": d.get("build"),
            "error": d.get("error", ""),
            "P1": bool((d.get("P1") or {}).get("pass")),
            "P2": bool((d.get("P2") or {}).get("pass")),
            "P1_reasons": (d.get("P1") or {}).get("reasons", []),
            "P2_failed": [c for c in (d.get("P2") or {}).get("cases", []) if not c.get("pass")],
        })
    return rounds


def memory():
    base = (RAW / "baseline-commit").read_text().strip()
    names = subprocess.run(["git", "diff", "--name-only", base, "HEAD"], cwd=APP, capture_output=True, text=True).stdout.split()
    in_app = [n for n in names if MEMORY_IN_APP.match(n)]
    home = WORK / "home"
    in_home = []
    for sub in [".gstack", ".claude/CLAUDE.md", ".claude/projects", ".claude/memory", ".compound-engineering"]:
        p = home / sub
        if p.is_file():
            in_home.append(str(p.relative_to(home)))
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                rel = str(f.relative_to(home))
                # セッションの記録（再開用の .jsonl）は新しいセッションに読み込まれないので除く
                if f.is_file() and not rel.endswith(".jsonl") and "/analytics/" not in rel:
                    in_home.append(rel)
    return {"in_app": in_app, "in_home": in_home[:200]}


def memory_reads():
    hits = []
    for step in sorted(RAW.glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1))):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant":
                continue
            for c in (d.get("message") or {}).get("content") or []:
                if c.get("type") != "tool_use":
                    continue
                full = json.dumps(c.get("input"), ensure_ascii=False)
                m = MEMORY_READ.search(full)
                if m and c.get("name") in ("Read", "Grep", "Glob", "Bash", "Skill", "Agent", "Task"):
                    hits.append({"step": step.name, "tool": c.get("name"), "match": m.group(0), "input": full[:200]})
    return hits


def main():
    grade.main()
    result = json.loads(OUT.read_text())
    result["scenario"] = SCENARIO
    w7 = {"pitfalls": pitfalls(),
          "check_seconds": int((RAW / "check-seconds").read_text()) if (RAW / "check-seconds").exists() else 0,
          "auto_memory_disabled": (RAW / "auto-memory-disabled").exists()}
    if SCENARIO == "W7a":
        w7["memory"] = memory()
    else:
        w7["memory_reads"] = memory_reads()[:50]
    if (RAW / "injected-patch").exists():
        w7["injected_patch"] = (RAW / "injected-patch").read_text().strip()
    result["w7"] = w7
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    first = w7["pitfalls"][0] if w7["pitfalls"] else {}
    print(f"{TRIAL}: pitfalls(before feedback) P1={first.get('P1')} P2={first.get('P2')} rounds={len(w7['pitfalls'])} "
          f"feedback={result['feedback_rounds']}")


if __name__ == "__main__":
    main()
