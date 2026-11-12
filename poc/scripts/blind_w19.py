#!/usr/bin/env python3
"""W19 の設計のブラインドレビュー（poc/answer-key/W19/grading.md の「設計の筋」）の資料作りと集計（blind_w15.py を写した）。

使い方:
  python3 poc/scripts/blind_w19.py prepare <出力先ディレクトリ>
    - 出力先に R01.md〜 を書く。各ファイルは、その試行のコミットメッセージ・文書（.md）の差分（仮定の明示を見るため）と、
      コードの差分（package-lock.json と、候補のツールが作る管理用の文書 docs/plans/ などを除く）。候補名・ツール名は [redacted]。
    - 共通の資料（課題文・初期状態のアプリの CLAUDE.md・docs/operations.md・src/lib/instruments.ts・src/lib/db/migrations.ts・src/lib/db/index.ts）を CONTEXT.md に書く。
    - 記号と試行 ID の対応は W19/blind/mapping.json（レビュー担当には渡さない）。記号の順番は乱数（種 20261110）で決める。
  python3 poc/scripts/blind_w19.py collect
    - W19/blind/reviewer-1.json・reviewer-2.json（{"R01": {"a": 0-3, ..., "f": 0-3, "comment": ".."}, ...}）を集計し、
      W19/blind/scores.json（試行ごとの 2 名の合計の平均（18 点満点）と、2 点以上ずれた項目）を書く。
"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "poc" / "results" / "workflow" / "W19"
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
BLIND = RESULTS / "blind"
SEED = 20261119
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


def base_file(path):
    patch = ROOT / "poc" / "answer-key" / "W19" / "base.patch"
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="w19-ctx-"))
    subprocess.run(f"git -C {ROOT} archive HEAD:poc/app | tar -x -C {d} && git -C {d} init -q && git -C {d} apply {patch}", shell=True, check=True)
    return {p: (d / p).read_text() for p in path}


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    trials = sorted(p.stem for p in RESULTS.glob("W19-*.json"))
    codes = [f"R{i:02d}" for i in range(1, len(trials) + 1)]
    random.Random(SEED).shuffle(trials)
    mapping = dict(zip(codes, trials))
    for code, trial in mapping.items():
        c, d = split((RAW / trial / "diff.patch").read_text())
        commits = (RAW / trial / "commits.txt").read_text() if (RAW / trial / "commits.txt").exists() else ""
        body = (f"# {code}\n\n## コミットメッセージ（1 行目）\n\n```\n{commits}```\n\n"
                f"## 文書の差分（README・設計メモなど。ツールの管理用ファイルは除く）\n\n```diff\n{d[:30000] or '（なし）'}\n```\n\n"
                f"## コードの差分\n\n```diff\n{c or '（コードの変更なし）'}\n```\n")
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", body))
    files = ["CLAUDE.md", "docs/operations.md", "src/lib/instruments.ts", "src/lib/db/migrations.ts", "src/lib/db/index.ts"]
    base = base_file(files)
    ctx = "# 課題文（依頼者からの依頼はこの 1 文だけ。候補は依頼者に質問できた）\n\n" + (ROOT / "poc/tasks/wf-W19.md").read_text()
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
