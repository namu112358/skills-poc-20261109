#!/usr/bin/env python3
"""W13 の設計のブラインドレビュー（poc/answer-key/W13/grading.md の「設計の筋」）の資料作りと集計。
W12 の blind_w12.py（origin/agent/poc-w12 03b1d05）を写し、最初の版までの差分と変更のステップの差分を分けて渡すようにした。

使い方:
  python3 poc/scripts/blind_w13.py prepare <出力先ディレクトリ>
    - 出力先に R01.md〜 と CONTEXT.md を書く。記号と試行 ID の対応は W13/blind/mapping.json（レビュー担当には渡さない）。
  python3 poc/scripts/blind_w13.py collect
    - W13/blind/reviewer-1.json・reviewer-2.json（{"R01": {"a": 0-3, ..., "f": 0-3, "comment": ".."}, ...}）を集計し、
      W13/blind/scores.json を書く。
"""
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W13"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
BLIND = RESULTS / "blind"
SEED = 20261113
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound(?:[-_ ]?engineering)?|\bce-[a-z-]+|ponytail|claude|baseline", re.I)
ITEMS = ["a", "b", "c", "d", "e", "f"]
TOOL = re.compile(r"^(package-lock\.json|docs/(plans|solutions|superpowers|specs|brainstorms)/|\.compound-engineering/|\.claude/|AGENTS\.md$|\.playwright-mcp/|\.gstack/)")
DOC = re.compile(r"\.(md|mdx|txt)$")


def split(text):
    code, docs = [], []
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", chunk)
        if not m or TOOL.match(m.group(2)):
            continue
        (docs if DOC.search(m.group(2)) else code).append(chunk)
    return "".join(code), "".join(docs)


def base_files(paths):
    patch = ROOT / "poc" / "answer-key" / "W13" / "base.patch"
    d = Path(tempfile.mkdtemp(prefix="w13-ctx-"))
    subprocess.run(f"git -C {ROOT} archive HEAD:poc/app | tar -x -C {d} && git -C {d} init -q && git -C {d} apply {patch}", shell=True, check=True)
    return {p: (d / p).read_text() for p in paths}


def section(title, commits, diff):
    c, d = split(diff)
    return (f"## {title}\n\n### コミットメッセージ\n\n```\n{commits or '（なし）'}\n```\n\n"
            f"### 文書の差分（README・設計メモなど。ツールの管理用ファイルは除く）\n\n```diff\n{d[:20000] or '（なし）'}\n```\n\n"
            f"### コードの差分\n\n```diff\n{c or '（コードの変更なし）'}\n```\n\n")


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W13-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        r = RAW / trial
        read = lambda n: (r / n).read_text() if (r / n).exists() else ""  # noqa: E731
        body = (f"# {code}\n\n"
                + section("1. 最初の依頼から最初の版まで（この版を本番に出した）", read("commits-v1.txt"), read("diff-v1.patch"))
                + section("2. 変更依頼の後の変更（最初の版 → 変更後）", read("commits-change.txt"), read("diff-change.patch")))
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", body))
    files = ["CLAUDE.md", "docs/operations.md", "src/lib/db/migrations.ts", "src/lib/loans.ts"]
    base = base_files(files)
    ctx = ("# 最初の依頼（依頼者からの依頼はこの 1 文だけ。候補は依頼者に質問できた）\n\n" + (ROOT / "poc/tasks/wf-W13.md").read_text()
           + "\n# 変更依頼（最初の版を本番に出した後、同じ会話の続きで送った）\n\n" + (ROOT / "poc/tasks/wf-W13-change.md").read_text())
    for f in files:
        ctx += f"\n\n# 初期状態の {f}\n\n```\n{base[f]}\n```\n"
    (out / "CONTEXT.md").write_text(ctx)
    BLIND.mkdir(parents=True, exist_ok=True)
    (BLIND / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} files -> {out}")


def collect():
    mapping = json.loads((BLIND / "mapping.json").read_text())
    revs = [json.loads((BLIND / f"reviewer-{i}.json").read_text()) for i in (1, 2)]
    by_trial = {}
    for code, trial in mapping.items():
        totals = [sum(int(r[code][k]) for k in ITEMS) for r in revs]
        gaps = [k for k in ITEMS if abs(int(revs[0][code][k]) - int(revs[1][code][k])) >= 2]
        by_trial[trial] = {"code": code, "totals": totals, "mean": sum(totals) / 2,
                           "items": {k: [int(r[code][k]) for r in revs] for k in ITEMS}, "gaps": gaps,
                           "comments": [r[code].get("comment", "") for r in revs]}
    (BLIND / "scores.json").write_text(json.dumps({"by_trial": by_trial}, ensure_ascii=False, indent=2) + "\n")
    for trial, v in sorted(by_trial.items()):
        print(f"{trial:34} {v['code']} totals={v['totals']} mean={v['mean']} gaps={v['gaps']}")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    else:
        collect()
