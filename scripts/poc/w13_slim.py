#!/usr/bin/env python3
"""W13 の採点済みの試行の作業用コピーの容量を減らす（W12 の w12_slim.py（origin/agent/poc-w12 028acdb・3796bfd）を写したもの）。

使い方: python3 scripts/poc/w13_slim.py <試行ID>
  - 試行ごとの HOME（プラグインの導入物・キャッシュ）を、Claude Code のセッションの記録を raw/<試行ID>/home-transcripts に写してから消す。
  - app/node_modules がハードリンクでなければ、poc-app/node_modules へのハードリンクに置き換える（package-lock.json が同じときだけ）。
採点の直後に片付けてよい（2026-11-10 コーディネーター）。/tmp/poc-trials/W13-* の中だけを触る。採点し直すときもそのまま使える。
"""
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "poc-app"
d = Path("/tmp/poc-trials") / sys.argv[1]
if d.parent != Path("/tmp/poc-trials") or not d.name.startswith("W13-") or not d.exists():
    sys.exit(f"対象外: {d}")
if (d / "home").exists():
    proj = d / "home" / ".claude" / "projects"
    if proj.exists():
        dst = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / d.name / "home-transcripts"
        shutil.copytree(proj, dst, dirs_exist_ok=True)
    shutil.rmtree(d / "home")
nm = d / "app" / "node_modules"
if nm.exists() and not nm.is_symlink() and (nm / "next" / "package.json").stat().st_nlink < 2 \
        and filecmp.cmp(SRC / "package-lock.json", d / "app" / "package-lock.json", shallow=False):
    shutil.rmtree(nm)
    subprocess.run(["cp", "-al", str(SRC / "node_modules"), str(nm)], check=True)
print(f"slimmed {d.name}")
