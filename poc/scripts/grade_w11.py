#!/usr/bin/env python3
"""W11（実在する OSS の解決済み課題）の試行を採点し、results/workflow/W11/<試行ID>.json に書き出す。

使い方: python3 poc/scripts/grade_w11.py <試行ID> [--cleanup]
  例:   python3 poc/scripts/grade_w11.py W11-B1-baseline-1

採点（poc/tasks/wf-W11-design.md）:
  - 隠しテスト（本家の修正で変更されたテストファイル）を、作業後のコードに上書きして実行する。
    候補が同じテストファイルを書き換えていても、本家の版で上書きする（SWE-bench と同じ）。
  - 解決 = F2P がすべて通り、P2P が 1 つも壊れていない。
  - 品質（100 点）= 新しいテスト（F2P のうち、修正前のテストファイルに無かったもの）の通過率 × 70
                    + 既存テスト（P2P と、新しい API の import などに巻き込まれて修正前に失敗した既存テスト）の維持率 × 30。
  - 候補の書いたテスト（隠しテスト以外の場所を含む）の追加行数、ソースの変更行数（本家の修正との比）も記録する。
作業用コピーは採点の後に元に戻す（隠しテストは残さない）。--cleanup で作業用コピーを消す。
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "oss"))
import oss  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TRIAL = sys.argv[1]
m = re.fullmatch(r"W11-([BF]\d+)-([a-z-]+)-(\d+)", TRIAL)
if not m:
    raise SystemExit(f"bad trial id: {TRIAL}")
TID, CAND, RUN = m.group(1), m.group(2), int(m.group(3))
RAW = ROOT / "poc" / "results" / "workflow" / "raw" / TRIAL
WORK = Path((RAW / "workdir").read_text().strip())
APP = WORK / "app"
KEY = json.loads((ROOT / "poc" / "answer-key" / "W11" / f"{TID}.json").read_text())
T = oss.task(TID)
OUT = ROOT / "poc" / "results" / "workflow" / "W11" / f"{TRIAL}.json"
TRIAL_ID = re.compile(r"\bW\d+[a-z]?(?:-[BF]\d+)?-(?:baseline|superpowers|feature-dev|compound-engineering|gstack)-\d+\b")


def isolation_reasons(text):
    """自分の試行の外や、本家の修正を参照した形跡（検出であって防止ではない）"""
    t = text.replace(str(WORK), "<own>")
    reasons = []
    if str(ROOT) in t:
        reasons.append("リポジトリ本体の絶対パス")
    if "/poc-trials/" in t or "/poc-oss/" in t:
        reasons.append("他の試行・準備領域")
    others = sorted({x for x in TRIAL_ID.findall(t) if x != TRIAL})
    if others:
        reasons.append("他の試行 ID: " + ", ".join(others[:5]))
    if "answer-key" in t or "poc" in t:
        reasons.append("正解データ・PoC 文書")
    if re.search(r"github\.com|githubusercontent|api\.github|pypi\.org|registry\.npmjs|unpkg|jsdelivr", t):
        reasons.append("外部サイト（本家・パッケージ配布元）")
    if re.search(r"(pip|uv|npm|pnpm|yarn)\s+(install|add|download)|pip\s+download", t):
        reasons.append("依存のインストール・取得")
    if re.search(r"node_modules/(\.pnpm/)?zod@|site-packages/(_pytest|click|packaging)/", t):
        reasons.append("公開版のパッケージのソース")
    return reasons


def transcript():
    tools, skills, denials, isolation = {}, set(), [], []
    subagents, last, turns = 0, None, 0
    for step in sorted(RAW.glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1))):
        step_last = None
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result":
                step_last = d
                for den in d.get("permission_denials") or []:
                    item = {"tool": den.get("tool_name"), "input": json.dumps(den.get("tool_input"), ensure_ascii=False)[:200]}
                    if item not in denials:
                        denials.append(item)
            if d.get("type") == "assistant":
                for c in (d.get("message") or {}).get("content") or []:
                    if c.get("type") != "tool_use":
                        continue
                    name = c.get("name")
                    tools[name] = tools.get(name, 0) + 1
                    inp = c.get("input") or {}
                    if name == "Skill":
                        skills.add(inp.get("skill", "?"))
                    if name in ("Agent", "Task"):
                        subagents += 1
                    for r in isolation_reasons(json.dumps(inp, ensure_ascii=False)):
                        isolation.append({"tool": name, "reason": r, "input": json.dumps(inp, ensure_ascii=False)[:200]})
        if step_last:
            last = step_last
            turns += step_last.get("num_turns") or 0
    return {
        "cost_usd": round((last or {}).get("total_cost_usd") or 0.0, 4),
        "turns": turns, "tools": tools, "skills": sorted(skills), "subagents": subagents,
        "permission_denials": denials, "isolation_suspects": isolation,
        "final_text": ((last or {}).get("result") or "")[-1500:],
    }


def diff_stats():
    patch = (RAW / "diff.patch").read_text(errors="replace") if (RAW / "diff.patch").exists() else ""
    files, cur = {}, None
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            cur = line.split(" b/", 1)[1]
            files[cur] = [0, 0]
        elif cur and line.startswith("+") and not line.startswith("+++"):
            files[cur][0] += 1
        elif cur and line.startswith("-") and not line.startswith("---"):
            files[cur][1] += 1
    tool = re.compile(r"^(docs/(plans|solutions|superpowers|specs|brainstorms)/|\.compound-engineering/|\.claude/|\.gstack/|TODOS?\.md$)")
    src = {f: v for f, v in files.items() if not oss.TEST_RE.search(f) and not tool.search(f)
           and not re.search(r"(^|/)(changelog|CHANGES|docs?)(/|\.)|\.(md|rst|txt)$", f, re.I)}
    tests = {f: v for f, v in files.items() if oss.TEST_RE.search(f)}
    other = sorted(f for f in files if f not in src and f not in tests)
    return {
        "src_added": sum(v[0] for v in src.values()), "src_removed": sum(v[1] for v in src.values()),
        "src_files": sorted(src), "test_added": sum(v[0] for v in tests.values()), "test_files": sorted(tests),
        "other_files": other,
    }


def hidden():
    repo = oss.clone(T)
    files = oss.hidden_tests(repo, T)
    git = ["git", "-C", str(APP)]
    oss.apply_files(APP, files)
    try:
        res, log, sec = oss.run_tests(T, APP, WORK / "venv", KEY["run_files"])
    finally:
        # 隠しテストを作業用コピーから取り除き、作業後の状態に戻す
        subprocess.run(git + ["checkout", "-q", "HEAD", "--", "."], capture_output=True)
        subprocess.run(git + ["clean", "-qfd", "--", *KEY["test_files"]], capture_output=True)
    f2p_ok = [k for k in KEY["f2p"] if res.get(k) == "pass"]
    new_ok = [k for k in KEY["f2p_new"] if res.get(k) == "pass"]
    existing = KEY["p2p"] + KEY["f2p_old"]
    existing_ok = [k for k in existing if res.get(k) == "pass"]
    p2p_ok = [k for k in KEY["p2p"] if res.get(k) == "pass"]
    return {
        "f2p_total": len(KEY["f2p"]), "f2p_pass": len(f2p_ok),
        "new_total": len(KEY["f2p_new"]), "new_pass": len(new_ok),
        "existing_total": len(existing), "existing_pass": len(existing_ok),
        "p2p_total": len(KEY["p2p"]), "p2p_pass": len(p2p_ok),
        "f2p_failed": [k for k in KEY["f2p"] if res.get(k) != "pass"][:40],
        "p2p_broken": [k for k in KEY["p2p"] if res.get(k) != "pass"][:40],
        "seconds": sec, "log_tail": log[-1500:] if len(f2p_ok) < len(KEY["f2p"]) else "",
    }


def read(name, default=""):
    p = RAW / name
    return p.read_text().strip() if p.exists() else default


h = hidden()
tr = transcript()
dstat = diff_stats()
new_rate = h["new_pass"] / h["new_total"] if h["new_total"] else 0.0
existing_rate = h["existing_pass"] / h["existing_total"] if h["existing_total"] else 1.0
resolved = h["f2p_pass"] == h["f2p_total"] and h["p2p_pass"] == h["p2p_total"]
up = KEY["upstream_diff"]
result = {
    "scenario": "W11", "task": TID, "kind": T["kind"], "repo": T["repo"], "trial": TRIAL, "candidate": CAND, "run": RUN,
    "resolved": resolved,
    "quality": round(70 * new_rate + 30 * existing_rate, 1),
    "hidden_tests": h,
    "diff": dict(dstat, upstream_src_added=up["added"], upstream_src_removed=up["removed"]),
    "facts": {
        "cost_usd": tr["cost_usd"], "elapsed_seconds": int(read("elapsed-seconds", "0") or 0),
        "interventions": len([x for x in read("interventions.log").splitlines() if x.strip()]),
        "budget_stopped": read("budget-stopped"), "errors": read("errors.log")[-1000:],
        "commits": len(read("commits.txt").splitlines()),
    },
    "transcript": {k: v for k, v in tr.items()},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
print(f"{TRIAL}: resolved={resolved} quality={result['quality']} F2P {h['f2p_pass']}/{h['f2p_total']} "
      f"P2P {h['p2p_pass']}/{h['p2p_total']} cost=${tr['cost_usd']} time={result['facts']['elapsed_seconds']}s "
      f"isolation={len(tr['isolation_suspects'])}")
if "--cleanup" in sys.argv[2:]:
    shutil.rmtree(WORK, ignore_errors=True)
