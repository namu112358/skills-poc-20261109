#!/usr/bin/env python3
"""W4 のブラインドレビュー用の資料を作る（poc/answer-key/W4/grading.md の「資料の作り方」）。

使い方: python3 poc/scripts/blind_w4.py <出力先ディレクトリ>
  - 出力先に R01.patch〜（コードの資料）と R01.design.md〜（設計の資料）を書く。候補名・コマンド名は伏せる。
  - 記号と試行 ID の対応は poc/results/workflow/W4/review/mapping.json に書く（採点者には渡さない）。
  - 出力先は採点者が読む場所なので、リポジトリの外（スクラッチ領域）にする。
"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W4"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
SEED = 20261109
# コードの資料: CLAUDE.md の更新は影響箇所 16 の判定に使うので残し、ほかの文書・管理用ファイルは除く
CODE_EXCLUDE = [":!package-lock.json", ":!AGENTS.md", ":!docs/", ":!.compound-engineering/", ":!.claude/",
                ":!.gstack/", ":!.superpowers/", ":!*.mdx", ":!README.md", ":!TODOS.md", ":!CHANGELOG.md"]
DESIGN_DOC = re.compile(r"\.(md|mdx|txt)$")
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound[-_ ]?engineering|\bce-[a-z-]+|/autoplan\b|autoplan|"
                   r"office-hours|plan-(ceo|eng|design)-review|code-architect|code-explorer|code-reviewer|ponytail", re.I)
DESIGN_LIMIT = 60000


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def design_material(trial, app, base):
    """候補が書いた文章・サブエージェントの報告・計画書を、記録の順に並べる。"""
    parts = []
    agent_ids = set()
    steps = sorted((RAW / trial).glob("step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p.name).group(1)))
    for step in steps:
        parts.append(f"\n\n## ステップ {re.search(r'step(\d+)', step.name).group(1)}\n")
        for line in step.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("parent_tool_use_id"):  # サブエージェント内部のやり取りは、最後の報告だけを使う
                continue
            msg = d.get("message") or {}
            if d.get("type") == "assistant":
                for c in msg.get("content") or []:
                    if c.get("type") == "text" and c.get("text", "").strip():
                        parts.append("[候補] " + c["text"].strip())
                    if c.get("type") == "tool_use" and c.get("name") in ("Agent", "Task"):
                        agent_ids.add(c.get("id"))
                        desc = (c.get("input") or {}).get("description", "")
                        parts.append(f"[サブエージェントを起動: {desc}]")
            if d.get("type") == "user":
                for c in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                    if c.get("type") == "tool_result" and c.get("tool_use_id") in agent_ids:
                        parts.append("[サブエージェントの報告] " + text_of(c.get("content")).strip())
    names = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", base, "HEAD"], cwd=app,
                           capture_output=True, text=True).stdout.split()
    for path in names:
        if DESIGN_DOC.search(path) and path not in ("CLAUDE.md", "AGENTS.md"):
            body = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=app, capture_output=True, text=True).stdout
            parts.append(f"\n\n## 候補が作った文書（{path}）\n\n{body}")
    text = "\n\n".join(parts)
    if len(text) > DESIGN_LIMIT:
        text = text[:DESIGN_LIMIT] + "\n\n（6 万字で打ち切り）"
    return text


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W4-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        # 作業用コピーの場所は run-trial.sh が raw/<試行>/workdir に記録する（無ければ旧来の .poc-work/trials）
        wd = RAW / trial / "workdir"
        app = (Path(wd.read_text().strip()) if wd.exists() else ROOT / ".poc-work" / "trials" / trial) / "app"
        base = (RAW / trial / "baseline-commit").read_text().strip()
        diff = subprocess.run(["git", "diff", base, "HEAD", "--", ".", *CODE_EXCLUDE], cwd=app,
                              capture_output=True, text=True, check=True).stdout
        (out / f"{code}.patch").write_text(NAMES.sub("[redacted]", diff))
        (out / f"{code}.design.md").write_text(NAMES.sub("[redacted]", design_material(trial, app, base)))
    (RESULTS / "review").mkdir(parents=True, exist_ok=True)
    (RESULTS / "review" / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} trials -> {out}")


if __name__ == "__main__":
    main()
