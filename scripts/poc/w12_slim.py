#!/usr/bin/env python3
"""W12 の試行の作業用コピーの容量を減らす（採点の後に run_w12_trials.sh が呼ぶ）。

使い方: python3 scripts/poc/w12_slim.py <試行ID>
  - 試行ごとの HOME（プラグインの導入物・キャッシュ。トランスクリプトは raw/ に保存済み）を消す。
  - app/node_modules を、poc-app/node_modules へのハードリンクに置き換える（依存の追加は許可していないので中身は同じ。
    package-lock.json が違うときは置き換えない）。採点し直すときもそのまま使える。
2026-11-10 にディスクの割り当てを使い切り、試行が止まったため追加した（判断の記録）。/tmp/poc-trials の中だけを触る。
"""
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "poc-app"
d = Path("/tmp/poc-trials") / sys.argv[1]
if d.parent != Path("/tmp/poc-trials") or not d.name.startswith("W12-") or not d.exists():
    sys.exit(f"対象外: {d}")
if (d / "home").exists():
    # Claude Code 自身のセッションの記録（サブエージェントの記録を含む）は、念のため raw/<試行ID>/home-transcripts に写してから消す
    proj = d / "home" / ".claude" / "projects"
    if proj.exists():
        dst = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / d.name / "home-transcripts"
        shutil.copytree(proj, dst, dirs_exist_ok=True)
    shutil.rmtree(d / "home")
nm = d / "app" / "node_modules"
if nm.exists() and not nm.is_symlink() and filecmp.cmp(SRC / "package-lock.json", d / "app" / "package-lock.json", shallow=False):
    shutil.rmtree(nm)
    subprocess.run(["cp", "-al", str(SRC / "node_modules"), str(nm)], check=True)
print(f"slimmed {d.name}")
