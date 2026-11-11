#!/usr/bin/env python3
"""片付け済みの W21 の試行を、保存した差分から作り直して採点し直す（採点の誤りを直したとき用）。

使い方: python3 scripts/poc/regrade_w21.py <試行ID> ...
  - poc-app の初期状態（node_modules はハードリンク）に raw/<試行ID>/diff.patch を当てた作業用コピーを、raw/<試行ID>/workdir の
    場所に作り、grade_w21.py で採点し直して片付ける。初期状態のコミットは作り直すので、POC_REGRADE_BASE で grade_w21.py に渡す。
  - 画像の差分（スクリーンショットなど）は当てられない形で保存されているので除く（採点には使わない）。
  - W21 の構成は poc-app に何も当てずに始めるので、初期状態はそのまま作れる（W22 の *-md は CLAUDE.md への追記も足す）。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs" / "poc" / "results" / "workflow" / "raw"


def sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, shell=True, check=True, capture_output=True, text=True)


def regrade(trial):
    raw = RAW / trial
    work = Path((raw / "workdir").read_text().strip())
    app = work / "app"
    if work.exists():
        shutil.rmtree(work)
    app.mkdir(parents=True)
    sh(f"cd {ROOT}/poc-app && tar --exclude=./node_modules --exclude=./.next -cf - . | (cd {app} && tar -xf -)", ROOT)
    sh(f"cp -al {ROOT}/poc-app/node_modules {app}/node_modules", ROOT)
    cand = trial.split("-", 1)[1].rsplit("-", 1)[0]
    if cand.endswith("-md"):
        with open(app / "CLAUDE.md", "a") as f:
            f.write((ROOT / "docs" / "poc" / "tasks" / f"wf-W22-{cand}.md").read_text())
    sh("git init -q && git add -A && git -c user.name=poc -c user.email=poc@example.invalid commit -qm baseline", app)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=app, capture_output=True, text=True).stdout.strip()
    sh(f"git apply --whitespace=nowarn --exclude='*.png' --exclude='*.jpg' --exclude='*.jpeg' --exclude='*.webp' --exclude='*.gif' {raw / 'diff.patch'} && git add -A && "
       "git -c user.name=poc -c user.email=poc@example.invalid commit -qm regrade", app)
    env = dict(os.environ, POC_REGRADE_BASE=base)
    p = subprocess.run([sys.executable, str(ROOT / "scripts/poc/grade_w21.py"), trial, "--cleanup"], env=env, capture_output=True, text=True)
    print(p.stdout.strip() or p.stderr[-800:])


if __name__ == "__main__":
    for t in sys.argv[1:]:
        regrade(t)
