#!/usr/bin/env python3
"""W21（UI/UX 系ツールの組み合わせの比較）の試行の事実を集め、results/workflow/W21/<試行ID>.json に書き出す。
docs/poc/tasks/wf-W21-design.md の「採点」。

使い方: python3 scripts/poc/grade_w21.py <試行ID> [--cleanup]
  - 試行 ID は W21<a〜f>-<構成>-<回>（d・e・f は依頼者の指示で足した題材: SaaS の LP・ダッシュボード・登録フォーム）（例 W21a-ui-all-1）。構成は ui-none・ui-all・ui-a・ui-fd・ui-pm。
  - W21a・W21b・W21d〜f: 型チェック・単体テスト・ビルド、依存の追加の有無、本番ビルドを起動して隠しの検査・axe-core・スクリーンショット
    （scripts/poc/w21_browser.cjs。POC_AXE に axe.min.js のパス）。スクリーンショットは results/workflow/W21/shots/ に置く。
  - W21c: REVIEW.md の本文を保存する（正解との突き合わせは judge_w21.py の判定役）。
  - 観察: 呼ばれた Skill、Impeccable のフックの出力、設計の文書、使った書体。
  --cleanup: 書き出した後、その試行の作業用コピーを片付ける（grade.py の cleanup）
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TRIAL = sys.argv[1]
FLAGS = set(sys.argv[2:])
m = re.fullmatch(r"(W21[a-f])-(ui-(?:none|all|a|fd|pm)(?:-md(?:-wdg|-imp)?)?)-(\d+)", TRIAL)
if not m:
    sys.exit(f"W21 の試行 ID ではない: {TRIAL}")
TASK, CONFIG, REP = m.group(1), m.group(2), int(m.group(3))
sys.argv = [sys.argv[0], "W21", TRIAL]  # grade.py は読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

APP, RAW, OUT, ROOT = grade.APP, grade.RAW, grade.OUT, grade.ROOT
SHOTS = OUT.parent / "shots"
# Impeccable が「使い古された書体」として指摘する一覧（pbakaus/impeccable の crates/foundation/src/constants.rs。固定コミット b7d1a80）
OVERUSED_FONTS = ["inter", "roboto", "open sans", "lato", "montserrat", "arial", "helvetica", "fraunces", "instrument sans",
                  "instrument serif", "geist", "geist sans", "geist mono", "mona sans", "plus jakarta sans", "space grotesk", "recoleta"]


def git(*args):
    return subprocess.run(["git", *args], cwd=APP, capture_output=True, text=True)


def observations(base):
    """点数にしない観察: フックの出力、設計の文書、書体。"""
    hooks = {}
    hook_samples = []
    for step in sorted(RAW.glob("step*.jsonl")):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "system" and d.get("subtype") == "hook_response":
                name = d.get("hook_name", "?")
                text = (d.get("output") or d.get("stdout") or "").strip()
                if "[impeccable" in text:
                    # Impeccable のフック: 走った回数と、指摘があった回数（「問題なし」の定型文以外）
                    hooks["impeccable"] = hooks.get("impeccable", 0) + 1
                    if "No deterministic design-quality issues found" not in text:
                        hooks["impeccable_findings"] = hooks.get("impeccable_findings", 0) + 1
                        if len(hook_samples) < 8:
                            hook_samples.append({"hook": name, "output": text[:600]})
                    continue
                if text and "sdk_bootstrap" not in text and "metrics" not in text and text != '{"async": true, "asyncTimeout": 180000}':
                    hooks[name] = hooks.get(name, 0) + 1
                    if len(hook_samples) < 8:
                        hook_samples.append({"hook": name, "output": text[:400]})
    files = git("diff", "--name-only", base, "HEAD").stdout.split()
    design_docs = [f for f in files if re.search(r"(^|/)(DESIGN|PRODUCT)\.md$|design-system/|MASTER\.md$|\.impeccable", f, re.I)]
    diff = git("diff", base, "HEAD", "--", "src", "*.css").stdout
    fonts = set()
    for line in diff.splitlines():
        if not line.startswith("+"):
            continue
        for fm in re.finditer(r"font-?family\s*[:=]\s*([^;}\n]+)", line, re.I):
            fonts.add(fm.group(1).strip().strip("'\",").lower()[:120])
        for fm in re.finditer(r"from\s+[\"']next/font/(?:google|local)[\"']|import\s*\{\s*([A-Za-z_, ]+)\}\s*from\s*[\"']next/font/google", line):
            if fm.group(1):
                fonts.add("next/font/google: " + fm.group(1).strip().lower())
    overused = sorted({f for f in OVERUSED_FONTS for s in fonts if re.search(r"\b" + re.escape(f) + r"\b", s.replace("_", " "))})
    return {"hook_outputs": hooks, "hook_samples": hook_samples, "design_docs": design_docs,
            "fonts": sorted(fonts), "overused_fonts": overused, "files_changed": files}


def build_checks(base):
    checks = {}
    for name, cmd in (("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")):
        code, tail = grade.run(cmd, timeout=900)
        checks[name] = {"pass": code == 0, "tail": tail[-600:]}
    old = json.loads(git("show", f"{base}:package.json").stdout)
    new = json.loads((APP / "package.json").read_text())
    deps_same = all(old.get(k, {}) == new.get(k, {}) for k in ("dependencies", "devDependencies"))
    return checks, deps_same


def browser(kind, app=None, prefix=None):
    app = app or APP
    prefix = prefix or TRIAL
    port = grade.free_port()
    env = dict(os.environ, PORT=str(port))
    env.pop("DATABASE_PATH", None)
    srv = subprocess.Popen(["npx", "next", "start", "-p", str(port)], cwd=app, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        base_url = f"http://localhost:{port}"  # ログイン後の移動先が localhost になるため、Cookie の送り先を合わせる
        for _ in range(60):
            try:
                subprocess.run(["curl", "-s", "-o", "/dev/null", base_url + "/login"], check=True, timeout=5)
                break
            except Exception:
                time.sleep(1)
        SHOTS.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["node", str(ROOT / "scripts/poc/w21_browser.cjs"), kind, base_url, str(SHOTS / prefix)],
                           capture_output=True, text=True, timeout=300)
        try:
            return json.loads(p.stdout)
        except ValueError:
            return {"errors": [p.stderr[-800:]], "checks": {}, "axe": {}}
    finally:
        os.killpg(srv.pid, 15)


def pre_polish(kind):
    """W23: 仕上げの前のコミット（raw/<ID>/pre-polish-commit）を別の作業ツリーでビルドし、検査とスクリーンショット（<ID>-pre）を取る。"""
    pre = (RAW / "pre-polish-commit").read_text().strip()
    tree = APP.parent / "pre"
    subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=APP, capture_output=True)
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(tree), pre], cwd=APP, check=True, capture_output=True)
    subprocess.run(["cp", "-al", str(APP / "node_modules"), str(tree / "node_modules")], check=True)
    b = subprocess.run("npm run build", cwd=tree, shell=True, capture_output=True, text=True, timeout=900)
    res = {"commit": pre, "build": b.returncode == 0}
    res["browser"] = browser(kind, tree, TRIAL + "-pre") if b.returncode == 0 else {"errors": ["build failed"], "checks": {}, "axe": {}}
    subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=APP, capture_output=True)
    # 仕上げの前までの費用（その時点までの最後の result の累計）
    n = int((RAW / "pre-polish-step").read_text().strip())
    cost = 0.0
    for k in range(1, n + 1):
        f = RAW / f"step{k}.jsonl"
        if not f.exists():
            continue
        for line in f.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result" and d.get("total_cost_usd") is not None:
                cost = d["total_cost_usd"]
    res["cost_before_polish"] = round(cost, 4)
    return res


def score_build(checks, deps_same, b):
    func_items = b.get("checks", {})
    keys = {
        "W21a": ["landing_shown", "link_to_login", "login_works", "logged_in_redirect", "no_overflow_375"],
        "W21b": ["all_tasks_linked", "assignee_and_due", "filter_control", "filter_done", "no_overflow_375"],
        "W21d": ["page_shown", "pricing", "faq", "cta_to_login", "no_overflow_375"],
        "W21e": ["requires_login", "page_shown", "status_counts", "assignees", "header_link", "no_overflow_375"],
        "W21f": ["requires_login", "link_from_list", "error_on_empty", "create_works", "no_overflow_375"],
    }[TASK]
    func = 20 * sum(bool(func_items.get(k)) for k in keys) / len(keys)
    cmds = 5 * sum(checks[k]["pass"] for k in checks) / 3
    deps = 5 if deps_same else 0
    rules = {}
    for vs in (b.get("axe") or {}).values():
        for v in vs:
            rules[v["id"]] = v["impact"]
    serious = sorted(k for k, v in rules.items() if v in ("serious", "critical"))
    moderate = sorted(k for k, v in rules.items() if v == "moderate")
    a11y = max(0, 20 - 4 * len(serious) - len(moderate)) if b.get("axe") else 0
    return {"functional": round(func, 2), "functional_items": {k: bool(func_items.get(k)) for k in keys},
            "commands": round(cmds, 2), "deps": deps, "a11y": a11y, "axe_serious": serious, "axe_moderate": moderate,
            "subtotal_50": round(func + cmds + deps + a11y, 2)}


def main():
    stats = grade.transcript_stats()
    # 作り直した作業用コピーで採点し直すとき（regrade_w21.py）は、作り直した初期状態のコミットを使う
    base = os.environ.get("POC_REGRADE_BASE") or (RAW / "baseline-commit").read_text().strip()
    result = {"trial": TRIAL, "scenario": "W21", "task": TASK, "config": CONFIG, "rep": REP, "transcript": stats,
              "elapsed_seconds": int((RAW / "elapsed-seconds").read_text()) if (RAW / "elapsed-seconds").exists() else None,
              "interventions": len((RAW / "interventions.log").read_text().splitlines()) if (RAW / "interventions.log").exists() else 0}
    if TASK == "W21c":
        body = git("show", "HEAD:REVIEW.md")
        result["review_md"] = body.stdout if body.returncode == 0 else ""
        (RAW / "diff.patch").write_text(git("diff", base, "HEAD", "--", "REVIEW.md").stdout)
        result["observations"] = observations(base)
        msg = f"REVIEW.md={len(result['review_md'])} chars"
    else:
        checks, deps_same = build_checks(base)
        b = browser(TASK[-1]) if checks["build"]["pass"] else {"errors": ["build failed"], "checks": {}, "axe": {}}
        result.update({"checks": checks, "deps_same": deps_same, "browser": b, "score": score_build(checks, deps_same, b),
                       "observations": observations(base)})
        if (RAW / "pre-polish-commit").exists():
            pre = pre_polish(TASK[-1])
            pre["score"] = score_build({"build": {"pass": pre["build"]}, "typecheck": {"pass": True}, "test": {"pass": True}}, True, pre["browser"])
            result["pre_polish"] = pre
            msg_pre = f" pre={pre['score']['subtotal_50']}"
        else:
            msg_pre = ""
        msg = f"subtotal={result['score']['subtotal_50']}/50 axe={result['score']['axe_serious']}{msg_pre}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{TRIAL}: {msg} cost=${stats.get('cost_usd', 0):.2f} skills={stats.get('skills_used')}")
    if "--cleanup" in FLAGS:
        grade.cleanup()


if __name__ == "__main__":
    main()
