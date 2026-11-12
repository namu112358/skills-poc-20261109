#!/usr/bin/env python3
"""開発ワークフローの試行を採点し、results/workflow/<シナリオ>/<試行ID>.json に書き出す。

使い方: python3 poc/scripts/grade.py <シナリオ> <試行ID> [--cleanup | --cleanup-only]
  例:   python3 poc/scripts/grade.py W1 W1-superpowers-1
  --cleanup:      採点して結果を書いた後、その試行の作業用コピーを片付ける
  --cleanup-only: 採点せずに作業用コピーだけを片付ける（ブラインドレビューなどが済んだ後に使う）
  どちらも付けなければ作業用コピーは残す（従来どおり）。
  --supplement:   結果を results/workflow/<シナリオ>/supplement/<試行ID>.json に書く（元の試行と混ぜない補足の再試行用）
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO, TRIAL = sys.argv[1], sys.argv[2]
FLAGS = set(sys.argv[3:])
RAW = ROOT / "poc" / "results" / "workflow" / "raw" / TRIAL
LEGACY_WORK = ROOT / ".poc-work" / "trials" / TRIAL
# run-trial.sh が作業用コピーの場所を workdir に記録する（記録がない古い試行は .poc-work/trials/<ID>）
WORK = Path((RAW / "workdir").read_text().strip()) if (RAW / "workdir").exists() else LEGACY_WORK
APP = WORK / "app"
# W7b は W7a の作業用コピーと HOME を引き継ぐ（run-trial.sh が continued-from に W7a の試行 ID を記録する）。
# W7a の作業用コピー・試行 ID への参照は自分の試行の一部として扱い、他の試行への参照とは分けて数える。
CONTINUED_FROM = (RAW / "continued-from").read_text().strip() if (RAW / "continued-from").exists() else ""
# 引き継ぎの連鎖（W7c → W7b → W7a など）の試行 ID と、実際に使った作業用コピーの名前は、他の試行に数えない
SAME_CHAIN = {TRIAL, WORK.name}
_prev = CONTINUED_FROM
while _prev and _prev not in SAME_CHAIN:
    SAME_CHAIN.add(_prev)
    _cf = ROOT / "poc" / "results" / "workflow" / "raw" / _prev / "continued-from"
    _prev = _cf.read_text().strip() if _cf.exists() else ""
TRIAL_ID = re.compile(r"\bW\d+[a-z]?-(?:baseline(?:-conventions)?|superpowers|feature-dev|compound-engineering|gstack)-\d+\b")
OUT = ROOT / "poc" / "results" / "workflow" / SCENARIO / ("supplement" if "--supplement" in FLAGS else "") / f"{TRIAL}.json"

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


def isolation_reasons(text):
    """ツール入力（切り詰める前の全文）から、自分の試行の外を参照している形跡を返す。

    検出であって防止ではない（Bash の cat/ls/find/grep などはパスを制限できない）。
    """
    own = [str(WORK), str(WORK.resolve()) if WORK.exists() else str(WORK)]
    t = text
    for o in own:
        t = t.replace(o, "<own>")
    reasons = []
    if str(ROOT) in t:
        reasons.append("リポジトリ本体の絶対パス")
    for root in ("/poc-trials/", ".poc-work/trials/"):
        if root in t:
            reasons.append("他の試行の作業用コピー")
            break
    others = sorted({m for m in TRIAL_ID.findall(t) if m not in SAME_CHAIN})
    if others:
        reasons.append("他の試行 ID: " + ", ".join(others[:5]))
    if re.search(r"(?:\.\./){2,}", t):
        reasons.append("../ で作業用コピーの外に出る相対パス")
    if "answer-key" in t:
        reasons.append("answer-key")
    if "poc" in t:
        reasons.append("poc/")
    if re.search(r"(?<![\w.-])results/", t):
        reasons.append("results/")
    return reasons


def transcript_stats():
    cost = 0.0
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    turns = 0
    denials = []
    tools = {}
    skills = set()
    subagents = 0
    subagent_types = {}
    final_text = []
    # 注意: --resume で続けたステップの result に入る total_cost_usd / modelUsage は、セッションの累計になっている。
    # そのため費用・トークンは全 result の最後（累計）を使い、ターン数はステップごとの最後の result を足す。
    last_result = None
    questions = 0
    active_ms = 0
    answer_key_access = []
    isolation = []
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
                            kind = (c.get("input") or {}).get("subagent_type") or "general-purpose"
                            subagent_types[kind] = subagent_types.get(kind, 0) + 1
                        if name == "AskUserQuestion":
                            questions += 1
                        full = json.dumps(c.get("input"), ensure_ascii=False)
                        # 正解データ（poc/answer-key/）を覗いていないか
                        if "answer-key" in full:
                            answer_key_access.append(f"{name}: {full[:200]}")
                        # 試行間の独立性: 自分の作業用コピーの外を参照していないか（切り詰める前の全文で判定）
                        reasons = isolation_reasons(full)
                        if reasons:
                            isolation.append({"step": step.name, "tool": name, "reasons": reasons, "input": full[:300]})
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
        # サブエージェントの種類ごとの回数（2026-11-09 追加。これより前に採点した試行の JSON には無い）
        "subagent_types": subagent_types,
        "questions": questions,
        # 子セッションが実際に動いていた時間（ステップごとの result の duration_ms の合計。終了待ちで固まった時間を含まない）
        "active_seconds": round(active_ms / 1000),
        "answer_key_access": answer_key_access,
        # 自分の試行の外（リポジトリ本体・他の試行・poc/・results/・answer-key）を参照した形跡。空なら形跡なし
        "isolation_suspects": isolation,
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
    # 隠しの E2E が無い W（W9 のレビューなど）は E2E を実行しない（W1〜W8 は従来どおり）
    if checks["build"]["pass"] and key_path("acceptance.cjs").exists():
        e2e = run_key("acceptance.cjs")
        # 認可プローブ（W4 以降。正解データに authz.cjs があるシナリオだけ、別に起動したサーバーで実行する）
        if key_path("authz.cjs").exists():
            authz = run_key("authz.cjs")
    return checks, e2e, authz


def key_path(name):
    """正解データの検査スクリプトの場所。W7a・W7b などは answer-key/W7/<名前>-<シナリオ>.cjs（例: acceptance-W7a.cjs）、
    それ以外は answer-key/<シナリオ>/<名前>。"""
    if SCENARIO.startswith("W7"):
        stem, ext = name.rsplit(".", 1)
        return ROOT / "poc" / "answer-key" / "W7" / f"{stem}-{SCENARIO}.{ext}"
    return ROOT / "poc" / "answer-key" / SCENARIO / name


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
        key = key_path(name)
        # run() は出力の末尾 3000 字だけを返すため、不合格が多いと結果の JSON が途中で切れる。ここでは標準出力を丸ごと読む
        p = subprocess.run(f"node {key} http://127.0.0.1:{port}", cwd=APP, shell=True, capture_output=True, text=True,
                           timeout=600, env=env)
        log = p.stdout + p.stderr
        try:
            results = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            results = [{"name": f"{name} の実行", "pass": False, "detail": log[-500:]}]
    finally:
        os.killpg(server.pid, 15)
        time.sleep(2)
    return results


def cleanup():
    """作業用コピーを片付ける。片付けてよい場所（試行の置き場所の直下にある、この試行の ID のディレクトリ）だけを消す。"""
    if CONTINUED_FROM:
        print(f"{TRIAL}: 作業用コピーは {CONTINUED_FROM} のもの。片付けは grade.py W7a {CONTINUED_FROM} --cleanup-only で行う")
        return
    if WORK.name != TRIAL or not WORK.exists():
        print(f"{TRIAL}: 作業用コピーなし（{WORK}）")
        return
    if (RAW / "diff.patch").exists() is False:
        sys.exit(f"{TRIAL}: raw/{TRIAL}/diff.patch が無いため片付けない（成果が保存されていない）")
    shutil.rmtree(WORK)
    print(f"{TRIAL}: 作業用コピーを片付けた（{WORK}）")


def main():
    if "--cleanup-only" in FLAGS:
        cleanup()
        return
    checks, e2e, authz = acceptance()
    result = {
        "scenario": SCENARIO,
        "trial": TRIAL,
        "candidate": TRIAL.split("-", 1)[1].rsplit("-", 1)[0],
        "run": int(TRIAL.rsplit("-", 1)[1]),
        "elapsed_seconds": int((RAW / "elapsed-seconds").read_text()),
        "errors": (RAW / "errors.log").read_text() if (RAW / "errors.log").exists() else "",
        # run-trial.sh が「お任せします」で続けさせた回数（POC_MAX_NUDGES。W1 は 0 固定）
        # run-trial.sh の watch モードで費用の見積もりが上限に達して止めたとき（無ければ空）。止めたステップの費用は result に含まれない
        "budget_stopped": (RAW / "budget-stopped").read_text().strip() if (RAW / "budget-stopped").exists() else "",
        "interventions": len((RAW / "interventions.log").read_text().splitlines()) if (RAW / "interventions.log").exists() else 0,
        # W7: 落とし穴を避けられなかったときに送ったレビューの定型の指摘の回数（W7 以外は 0）と、引き継いだ W7a の試行 ID
        "feedback_rounds": len((RAW / "feedback.log").read_text().splitlines()) if (RAW / "feedback.log").exists() else 0,
        "continued_from": CONTINUED_FROM,
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
          f"build={checks['build']['pass']} cost=${result['transcript']['cost_usd']} time={result['elapsed_seconds']}s "
          f"isolation_suspects={len(result['transcript']['isolation_suspects'])}")
    if "--cleanup" in FLAGS:
        cleanup()


if __name__ == "__main__":
    main()
