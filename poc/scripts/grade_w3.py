#!/usr/bin/env python3
"""W3（曖昧な要望から要件を固める）の試行の事実を集め、results/workflow/W3/<試行ID>.json に書き出す。

使い方: python3 poc/scripts/grade_w3.py <試行ID>
  - 費用・ターン数などは grade.py と同じ集計（transcript_stats / diff_stats）を使う。
  - 質問のやり取り（answer_w3.py の qa-*.json）から質問数・重複数を数える。
  - 採点する文書（poc/answer-key/W3/grading.md）を取り出し、results/workflow/W3/docs/<試行ID>.md に保存する。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TRIAL = sys.argv[1]
sys.argv = [sys.argv[0], "W3", TRIAL]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade  # noqa: E402

ROOT, APP, RAW = grade.ROOT, grade.APP, grade.RAW
DIR = ROOT / "poc" / "results" / "workflow" / "W3"
HOME = APP.parent / "home"
# 候補が自分の流儀で作る要件・設計の文書（REQUIREMENTS.md が無いときの代わり）
NATIVE = ["docs/superpowers/specs/", "docs/brainstorms/", "docs/specs/", "docs/plans/"]
CODE = re.compile(r"^(src/|tests/|package\.json$|next\.config|tsconfig)")


def git(*args):
    return subprocess.run(["git", *args], cwd=APP, capture_output=True, text=True).stdout


def qa_stats():
    rounds, items = [], []
    answered = set()
    duplicates = []
    for p in sorted((p for p in RAW.glob("qa-*.json") if re.fullmatch(r"qa-\d+\.json", p.name)),
                    key=lambda p: int(re.search(r"\d+", p.name).group())):
        q = json.loads(p.read_text())
        if not q.get("has_questions"):
            continue
        new_ids = set()
        for it in q["items"]:
            ids = set(it.get("sheet_ids") or [])
            if it["kind"] in ("context", "requirement") and ids and ids <= answered:
                duplicates.append({"round": q["round"], "question": it["question"], "sheet_ids": sorted(ids)})
            new_ids |= ids
            items.append(dict(it, round=q["round"]))
        answered |= new_ids
        rounds.append({"round": q["round"], "questions": len(q["items"]), "cost_usd": q.get("cost_usd", 0)})
    answerer_cost = sum(json.loads(p.read_text()).get("cost_usd", 0) for p in RAW.glob("qa-*.json"))
    return {
        "rounds": len(rounds),
        "questions": len(items),
        "by_kind": {k: sum(1 for i in items if i["kind"] == k) for k in ("requirement", "context", "confirmation")},
        "duplicates": duplicates,
        "elicited_ids": sorted(answered, key=lambda x: (x[0], int(x[1:]))),
        "closed_by_limit": (RAW / "qa-closed.log").exists(),
        "answerer_cost_usd": round(answerer_cost, 4),
        "items": items,
        "per_round": rounds,
    }


def pick_doc():
    """採点する文書（出どころ, 本文）。"""
    text = git("show", "HEAD:REQUIREMENTS.md")
    if text.strip():
        return "REQUIREMENTS.md", text
    for prefix in NATIVE:
        names = [n for n in git("ls-tree", "-r", "--name-only", "HEAD", "--", prefix).split() if n.endswith(".md")]
        if names:
            name = sorted(names)[-1]
            return name, git("show", f"HEAD:{name}")
    designs = sorted((HOME / ".gstack").glob("projects/**/*.md"), key=lambda p: p.stat().st_mtime) if HOME.exists() else []
    if designs:
        return f"~/{designs[-1].relative_to(HOME)}", designs[-1].read_text()
    final = ""
    for step in sorted(RAW.glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1))):
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result" and d.get("result"):
                final = d["result"]
    return "最後のメッセージ", final


def main():
    tr = grade.transcript_stats()
    diff = grade.diff_stats()
    source, text = pick_doc()
    (DIR / "docs").mkdir(parents=True, exist_ok=True)
    (DIR / "docs" / f"{TRIAL}.md").write_text(text)
    gstack_docs = []
    if HOME.exists():
        gstack_docs = [str(p.relative_to(HOME)) for p in sorted((HOME / ".gstack").glob("projects/**/*.md"))]
    result = {
        "scenario": "W3",
        "trial": TRIAL,
        "candidate": TRIAL.split("-", 1)[1].rsplit("-", 1)[0],
        "run": int(TRIAL.rsplit("-", 1)[1]),
        "elapsed_seconds": int((RAW / "elapsed-seconds").read_text()),
        "errors": (RAW / "errors.log").read_text() if (RAW / "errors.log").exists() else "",
        "interventions": len((RAW / "interventions.log").read_text().splitlines()) if (RAW / "interventions.log").exists() else 0,
        "doc_source": source,
        "doc_lines": len(text.splitlines()),
        "requirements_committed": source == "REQUIREMENTS.md",
        "code_changed": [f["path"] for f in diff["files"] if CODE.match(f["path"])],
        "gstack_docs": gstack_docs,
        "qa": qa_stats(),
        "diff": diff,
        "transcript": tr,
    }
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{TRIAL}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    q = result["qa"]
    print(f"{TRIAL}: doc={source}({result['doc_lines']} 行) rounds={q['rounds']} questions={q['questions']} "
          f"dup={len(q['duplicates'])} elicited={','.join(q['elicited_ids'])} code_changed={len(result['code_changed'])} "
          f"cost=${tr['cost_usd']} time={result['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
