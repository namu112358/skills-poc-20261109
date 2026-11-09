#!/usr/bin/env python3
"""開発ワークフローの試行を採点し、results/workflow/<シナリオ>/<試行ID>.json に書き出す。

使い方: python3 scripts/poc/grade.py <シナリオ> <試行ID>
  例:   python3 scripts/poc/grade.py W1 W1-superpowers-1
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO, TRIAL = sys.argv[1], sys.argv[2]
APP = ROOT / ".poc-work" / "trials" / TRIAL / "app"
RAW = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / TRIAL
OUT = ROOT / "docs" / "poc" / "results" / "workflow" / SCENARIO / f"{TRIAL}.json"

# 候補が作る管理用ファイル（コード量の集計から除く。過剰さの判定では別に数える）
TOOL_ARTIFACT = re.compile(r"^(docs/(plans|solutions|superpowers|specs)/|\.compound-engineering/|\.claude/)")
DOC_FILE = re.compile(r"\.(md|mdx|txt)$")


def run(cmd, timeout=600, env=None):
    p = subprocess.run(cmd, cwd=APP, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, (p.stdout + p.stderr)[-3000:]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def transcript_stats():
    cost = 0.0
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    turns = 0
    denials = []
    tools = {}
    skills = set()
    subagents = 0
    final_text = []
    for step in sorted(RAW.glob("step*.jsonl")):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result":
                cost += d.get("total_cost_usd") or 0
                u = d.get("usage") or {}
                tokens["input"] += u.get("input_tokens", 0)
                tokens["output"] += u.get("output_tokens", 0)
                tokens["cache_read"] += u.get("cache_read_input_tokens", 0)
                tokens["cache_creation"] += u.get("cache_creation_input_tokens", 0)
                turns += d.get("num_turns") or 0
                for den in d.get("permission_denials") or []:
                    denials.append({"tool": den.get("tool_name"), "input": json.dumps(den.get("tool_input"), ensure_ascii=False)[:200]})
                if d.get("result"):
                    final_text.append(d["result"][-1500:])
            if d.get("type") == "assistant":
                for c in (d.get("message") or {}).get("content") or []:
                    if c.get("type") == "tool_use":
                        name = c.get("name")
                        tools[name] = tools.get(name, 0) + 1
                        if name == "Skill":
                            skills.add((c.get("input") or {}).get("skill", "?"))
                        if name in ("Agent", "Task"):
                            subagents += 1
    return {
        "cost_usd": round(cost, 4),
        "tokens": tokens,
        "turns": turns,
        "permission_denials": denials,
        "tool_calls": tools,
        "skills_used": sorted(skills),
        "subagents": subagents,
        "final_message": final_text[-1] if final_text else "",
    }


def diff_stats():
    base = (RAW / "baseline-commit").read_text().strip()
    out = subprocess.run(["git", "diff", "--numstat", base, "HEAD", "--", ".", ":!package-lock.json"],
                         cwd=APP, capture_output=True, text=True).stdout
    files = []
    for line in out.strip().splitlines():
        add, delete, path = line.split("\t")
        add = int(add) if add != "-" else 0
        delete = int(delete) if delete != "-" else 0
        if path.startswith("tests/"):
            kind = "test"
        elif TOOL_ARTIFACT.match(path):
            kind = "tool-artifact"
        elif DOC_FILE.search(path):
            kind = "doc"
        else:
            kind = "code"
        files.append({"path": path, "added": add, "deleted": delete, "kind": kind})
    names = subprocess.run(["git", "diff", "--name-status", base, "HEAD"], cwd=APP, capture_output=True, text=True).stdout
    new_files = [l.split("\t")[-1] for l in names.splitlines() if l.startswith("A")]
    pkg_changed = subprocess.run(["git", "diff", "--quiet", base, "HEAD", "--", "package.json"], cwd=APP).returncode != 0
    commits = (RAW / "commits.txt").read_text().strip().splitlines() if (RAW / "commits.txt").exists() else []
    return {"files": files, "new_files": new_files, "package_json_changed": pkg_changed, "commits": commits}


def acceptance():
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = run(cmd)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    e2e = []
    if checks["build"]["pass"]:
        port = free_port()
        server = subprocess.Popen(f"npx next start -p {port}", cwd=APP, shell=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            for _ in range(60):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=1).close()
                    break
                except OSError:
                    time.sleep(1)
            env = dict(os.environ, NODE_PATH=subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip())
            key = ROOT / "docs" / "poc" / "answer-key" / SCENARIO / "acceptance.cjs"
            code, log = run(f"node {key} http://127.0.0.1:{port}", timeout=180, env=env)
            try:
                e2e = json.loads(log.strip().splitlines()[-1])
            except (ValueError, IndexError):
                e2e = [{"name": "E2E 実行", "pass": False, "detail": log[-500:]}]
        finally:
            os.killpg(server.pid, 15)
    return checks, e2e


def main():
    checks, e2e = acceptance()
    result = {
        "scenario": SCENARIO,
        "trial": TRIAL,
        "candidate": TRIAL.split("-", 1)[1].rsplit("-", 1)[0],
        "run": int(TRIAL.rsplit("-", 1)[1]),
        "elapsed_seconds": int((RAW / "elapsed-seconds").read_text()),
        "errors": (RAW / "errors.log").read_text() if (RAW / "errors.log").exists() else "",
        "checks": checks,
        "e2e": e2e,
        "diff": diff_stats(),
        "transcript": transcript_stats(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    passed = sum(1 for t in e2e if t["pass"])
    print(f"{TRIAL}: e2e {passed}/{len(e2e)} typecheck={checks['typecheck']['pass']} test={checks['test']['pass']} "
          f"build={checks['build']['pass']} cost=${result['transcript']['cost_usd']} time={result['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
