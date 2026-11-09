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
    # 注意: --resume で続けたステップの result に入る total_cost_usd / modelUsage は、セッションの累計になっている。
    # そのため費用・トークンは全 result の最後（累計）を使い、ターン数はステップごとの最後の result を足す。
    last_result = None
    questions = 0
    active_ms = 0
    answer_key_access = []
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
                    if c.get("type") == "tool_use":
                        name = c.get("name")
                        tools[name] = tools.get(name, 0) + 1
                        if name == "Skill":
                            skills.add((c.get("input") or {}).get("skill", "?"))
                        if name in ("Agent", "Task"):
                            subagents += 1
                        if name == "AskUserQuestion":
                            questions += 1
                        # 正解データ（docs/poc/answer-key/）を覗いていないか
                        if "answer-key" in json.dumps(c.get("input"), ensure_ascii=False):
                            answer_key_access.append(f"{name}: {json.dumps(c.get('input'), ensure_ascii=False)[:200]}")
        if step_last:
            turns += step_last.get("num_turns") or 0
            active_ms += step_last.get("duration_ms") or 0
            if step_last.get("result"):
                final_text.append(step_last["result"][-1500:])
            last_result = step_last
    if last_result:
        cost = last_result.get("total_cost_usd") or 0
        for m in (last_result.get("modelUsage") or {}).values():
            tokens["input"] += m.get("inputTokens", 0)
            tokens["output"] += m.get("outputTokens", 0)
            tokens["cache_read"] += m.get("cacheReadInputTokens", 0)
            tokens["cache_creation"] += m.get("cacheCreationInputTokens", 0)
    return {
        "cost_usd": round(cost, 4),
        "tokens": tokens,
        "turns": turns,
        "permission_denials": denials,
        "tool_calls": tools,
        "skills_used": sorted(skills),
        "subagents": subagents,
        "questions": questions,
        # 子セッションが実際に動いていた時間（ステップごとの result の duration_ms の合計。終了待ちで固まった時間を含まない）
        "active_seconds": round(active_ms / 1000),
        "answer_key_access": answer_key_access,
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
    e2e, authz = [], []
    if checks["build"]["pass"]:
        e2e = run_key("acceptance.cjs")
        # 認可プローブ（W4 以降。正解データに authz.cjs があるシナリオだけ、別に起動したサーバーで実行する）
        if (ROOT / "docs" / "poc" / "answer-key" / SCENARIO / "authz.cjs").exists():
            authz = run_key("authz.cjs")
    return checks, e2e, authz


def run_key(name):
    """正解データの検査スクリプト（acceptance.cjs など）を、起動したばかりのサーバーに対して実行する。"""
    results = []
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
        key = ROOT / "docs" / "poc" / "answer-key" / SCENARIO / name
        code, log = run(f"node {key} http://127.0.0.1:{port}", timeout=600, env=env)
        try:
            results = json.loads(log.strip().splitlines()[-1])
        except (ValueError, IndexError):
            results = [{"name": f"{name} の実行", "pass": False, "detail": log[-500:]}]
    finally:
        os.killpg(server.pid, 15)
        time.sleep(2)
    return results


def main():
    checks, e2e, authz = acceptance()
    result = {
        "scenario": SCENARIO,
        "trial": TRIAL,
        "candidate": TRIAL.split("-", 1)[1].rsplit("-", 1)[0],
        "run": int(TRIAL.rsplit("-", 1)[1]),
        "elapsed_seconds": int((RAW / "elapsed-seconds").read_text()),
        "errors": (RAW / "errors.log").read_text() if (RAW / "errors.log").exists() else "",
        # run-trial.sh が「お任せします」で続けさせた回数（POC_MAX_NUDGES。W1 は 0 固定）
        "interventions": len((RAW / "interventions.log").read_text().splitlines()) if (RAW / "interventions.log").exists() else 0,
        "checks": checks,
        "e2e": e2e,
        **({"authz": authz} if authz else {}),
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
