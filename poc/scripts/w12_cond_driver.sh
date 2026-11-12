#!/usr/bin/env bash
# W12 の追加条件の 10 本（5 条件 × 2 回）を、2 本並列で流す。条件は環境変数で渡す（例: POC_STANDARD=generic、
# POC_MODEL=claude-haiku-5-5、POC_W12_BASE=messy）。前半（<回1>）: superpowers → feature-dev → gstack → compound-engineering → baseline、
# 後半（<回2>）は逆順。
# 使い方: poc/scripts/w12_cond_driver.sh <回1> <回2> [<待つプロセス ID> ...]（前の試行が終わるのを待ってから始める）
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
R1="$1"; R2="$2"; shift 2
for p in "$@"; do while kill -0 "$p" 2>/dev/null; do sleep 20; done; done
bash "$ROOT/poc/scripts/run_w12_trials.sh" "superpowers:$R1" "gstack:$R1" "baseline:$R1" &
A=$!
bash "$ROOT/poc/scripts/run_w12_trials.sh" "feature-dev:$R1" "compound-engineering:$R1" &
B=$!
wait $A $B
bash "$ROOT/poc/scripts/run_w12_trials.sh" "baseline:$R2" "gstack:$R2" "superpowers:$R2" &
A=$!
bash "$ROOT/poc/scripts/run_w12_trials.sh" "compound-engineering:$R2" "feature-dev:$R2" &
B=$!
wait $A $B
