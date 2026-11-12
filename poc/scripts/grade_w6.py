#!/usr/bin/env python3
"""W6（UI 実装からブラウザ検証・PR 作成まで）の試行を採点用に調べ、results/workflow/W6/<試行ID>.json に書き出す。

使い方: python3 poc/scripts/grade_w6.py <試行ID> [--cleanup]
  1. grade.py と同じ集計（型チェック・単体テスト・ビルド・隠しの E2E・差分・トランスクリプト）を行う。
  2. 次の W6 固有の事実を足す（poc/answer-key/W6/grading.md）。
     - evidence: ブラウザの操作（/my-tasks を開いたか、操作したか、幅 480px 以下にしたか）、スクリーンショットの撮影と、
                 作業用コピーにコミットされた画像ファイル。判定に使ったツールの呼び出しの抜粋（操作記録）も残す
     - pr:       コミットされた PR.md の本文、tests/ の追加・変更、push や gh の試み（権限で拒否されたもの）
     - checks_run: 子セッションが実行したチェック（npm test など）のコマンド（PR の説明のブラインドレビューに渡す事実）
  --cleanup: 書き出した後、その試行の作業用コピーを片付ける
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TRIAL = sys.argv[1]
FLAGS = set(sys.argv[2:])
sys.argv = [sys.argv[0], "W6", TRIAL]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

ROOT, APP, RAW, OUT = grade.ROOT, grade.APP, grade.RAW, grade.OUT
IMAGE = re.compile(r"\.(png|jpe?g|webp)$", re.I)
NAV_TOOLS = ("browser_navigate", "browser_tabs", "browser_run_code", "browser_run_code_unsafe")
ACT_TOOLS = ("browser_click", "browser_type", "browser_fill_form", "browser_select_option", "browser_press_key",
             "browser_evaluate", "browser_run_code", "browser_run_code_unsafe")
# Bash で動かすブラウザ（gstack の browse、agent-browser、Playwright を使うスクリプト）
BASH_BROWSER = re.compile(r"browse/dist/browse|\$B\b|\bagent-browser\b|playwright|chromium", re.I)
BASH_NAV = re.compile(r"\b(goto|open|navigate)\b|page\.goto", re.I)
BASH_ACT = re.compile(r"\b(click|fill|type|select|press)\b", re.I)
BASH_SHOT = re.compile(r"\bscreenshot\b", re.I)
BASH_NARROW = re.compile(r"(viewport|set-viewport|resize|setViewportSize|width)[^0-9\n]{0,20}([1-9][0-9]{2})\b", re.I)


def tool_calls():
    """全ステップの tool_use（サブエージェントのものを含む）を (ツール名, 入力) で返す。"""
    calls = []
    for step in sorted(RAW.glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1))):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant":
                continue
            for c in (d.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use":
                    calls.append((step.name, c.get("name") or "", c.get("input") or {}))
    return calls


def evidence(calls):
    nav = act = shot = narrow = False
    record = []
    for step, name, inp in calls:
        text = json.dumps(inp, ensure_ascii=False)
        kind = None
        if name.startswith("mcp__playwright__"):
            short = name.split("__")[-1]
            if short in NAV_TOOLS and "my-tasks" in text:
                nav = True
                kind = "nav"
            # コードを渡すツールは、中身にページ操作（click / fill など）があるときだけ「操作」に数える
            if short in ACT_TOOLS and (not short.startswith("browser_run_code") and short != "browser_evaluate"
                                       or re.search(r"\.(click|fill|type|selectOption|press|check)\(", text)):
                act = True
                kind = kind or "act"
            if short == "browser_take_screenshot" or (short.startswith("browser_run_code") and ".screenshot(" in text):
                shot = True
                kind = "shot"
            if short == "browser_resize" and int(inp.get("width") or 9999) <= 480:
                narrow = True
                kind = "narrow"
            if short in ("browser_run_code", "browser_run_code_unsafe", "browser_evaluate") and re.search(r"setViewportSize\(\{\s*width:\s*([1-4][0-9]{2})\b", text):
                narrow = True
            kind = kind or "browser"
        elif name == "Bash" and BASH_BROWSER.search(inp.get("command", "")):
            cmd = inp.get("command", "")
            if BASH_NAV.search(cmd) and "my-tasks" in cmd:
                nav = True
                kind = "nav"
            if BASH_ACT.search(cmd):
                act = True
                kind = kind or "act"
            if BASH_SHOT.search(cmd):
                shot = True
                kind = "shot"
            m = BASH_NARROW.search(cmd)
            if m and int(m.group(2)) <= 480:
                narrow = True
                kind = "narrow"
            kind = kind or "browser"
        if kind:
            record.append({"step": step, "tool": name, "kind": kind, "input": text[:240]})
    base = (RAW / "baseline-commit").read_text().strip()
    names = subprocess.run(["git", "diff", "--name-only", base, "HEAD"], cwd=APP, capture_output=True, text=True).stdout
    committed_images = [p for p in names.splitlines() if IMAGE.search(p)]
    e1 = (3 if nav else 0) + (2 if nav and act else 0)
    e2 = 5 if committed_images else (3 if shot else 0)
    e3 = 5 if narrow else 0
    return {
        "opened_page": nav, "interacted": act, "screenshot_taken": shot, "narrow_viewport": narrow,
        "committed_images": committed_images[:30], "points": {"E1": e1, "E2": e2, "E3": e3},
        "record": record[:80], "browser_calls": len(record),
    }


def pr_facts(calls, denials):
    base = (RAW / "baseline-commit").read_text().strip()
    body = subprocess.run(["git", "show", "HEAD:PR.md"], cwd=APP, capture_output=True, text=True)
    # 最後の「poc: uncommitted leftovers」で拾ったものは、候補がコミットしたものではない
    leftover = subprocess.run(["git", "log", "--format=%s", "-1", "--", "PR.md"], cwd=APP, capture_output=True, text=True).stdout.strip()
    tests = subprocess.run(["git", "diff", "--name-only", base, "HEAD", "--", "tests/"], cwd=APP, capture_output=True, text=True).stdout.split()
    push = [d for d in denials if re.search(r"git push|\bgh\b", d.get("input", ""))]
    attempts = [json.dumps(i, ensure_ascii=False)[:200] for _, n, i in calls
                if n == "Bash" and re.search(r"git push|\bgh (pr|repo|auth)", i.get("command", ""))]
    return {
        "pr_md": body.stdout if body.returncode == 0 else "",
        "pr_md_committed_by_candidate": body.returncode == 0 and leftover != "poc: uncommitted leftovers",
        "tests_changed": tests,
        "push_or_gh_attempts": attempts[:10],
        "push_or_gh_denied": len(push),
    }


def checks_run(calls):
    cmds = []
    for _, name, inp in calls:
        if name == "Bash":
            c = inp.get("command", "")
            if re.search(r"npm (run )?(test|typecheck|build|dev|start)|npx next|tsc", c):
                cmds.append(c[:160])
    return cmds[:40]


def main():
    grade.main()  # 共通の採点（OUT に書き出す）
    result = json.loads(OUT.read_text())
    calls = tool_calls()
    result["w6"] = {
        "evidence": evidence(calls),
        "pr": pr_facts(calls, result["transcript"]["permission_denials"]),
        "checks_run": checks_run(calls),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    w = result["w6"]
    print(f"{TRIAL}: evidence={w['evidence']['points']} images={len(w['evidence']['committed_images'])} "
          f"PR.md={'yes' if w['pr']['pr_md'] else 'no'} tests_changed={len(w['pr']['tests_changed'])} "
          f"push_attempts={len(w['pr']['push_or_gh_attempts'])}")
    if "--cleanup" in FLAGS:
        grade.cleanup()


if __name__ == "__main__":
    main()
