#!/usr/bin/env bash
# 7 日間の使用量の上限が近いため（ユーザー判断、2026-11-10）、乱れた初期状態は各条件の 1 回目（回 31）の 5 本だけを流す。
# 使い方: poc/scripts/w12_messy_only.sh [<待つプロセス ID> ...]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
for p in "$@"; do while kill -0 "$p" 2>/dev/null; do sleep 20; done; done
export POC_W12_BASE=messy
unset POC_MODEL POC_ANSWER_MODEL POC_STANDARD
bash "$ROOT/poc/scripts/run_w12_trials.sh" superpowers:31 gstack:31 baseline:31 &
A=$!
bash "$ROOT/poc/scripts/run_w12_trials.sh" feature-dev:31 compound-engineering:31 &
B=$!
wait $A $B
echo "$(date -u +%FT%TZ) messy-done" >> "$ROOT/poc/results/workflow/raw/w12-runner.log"
