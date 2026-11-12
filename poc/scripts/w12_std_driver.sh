#!/usr/bin/env bash
# W12 の追加条件（汎用の開発標準。POC_STANDARD=generic、回の番号 11・12）の 10 本を、2 本並列で流す。
# 前半（11）: superpowers → feature-dev → gstack → compound-engineering → baseline、後半（12）は逆順。
# 使い方: poc/scripts/w12_std_driver.sh [<待つプロセス ID> ...]（今の試行が終わるのを待ってから始める）
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
for p in "$@"; do while kill -0 "$p" 2>/dev/null; do sleep 20; done; done
export POC_STANDARD=generic
bash "$ROOT/poc/scripts/run_w12_trials.sh" superpowers:11 gstack:11 baseline:11 &
A=$!
bash "$ROOT/poc/scripts/run_w12_trials.sh" feature-dev:11 compound-engineering:11 &
B=$!
wait $A $B
bash "$ROOT/poc/scripts/run_w12_trials.sh" baseline:12 gstack:12 superpowers:12 &
A=$!
bash "$ROOT/poc/scripts/run_w12_trials.sh" compound-engineering:12 feature-dev:12 &
B=$!
wait $A $B
