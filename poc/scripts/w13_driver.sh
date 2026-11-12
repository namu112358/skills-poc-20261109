#!/usr/bin/env bash
# W13 の 10 本（5 条件 × 2 回）を 2 本並列で流す（poc/tasks/wf-W13-design.md §5）。
# 前半（1）: superpowers → feature-dev → gstack → compound-engineering → baseline の順に 2 列へ配り、後半（2）は逆順。
# 使い方: poc/scripts/w13_driver.sh [first|second|all]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
R="$ROOT/poc/scripts/run_w13_trials.sh"
LOG="$ROOT/poc/results/workflow/raw/w13-runner.log"
if [[ "${1:-all}" != second ]]; then
  bash "$R" superpowers:1 gstack:1 baseline:1 & A=$!
  bash "$R" feature-dev:1 compound-engineering:1 & B=$!
  wait $A $B
  echo "$(date -u +%FT%TZ) first-half-done" >> "$LOG"
fi
if [[ "${1:-all}" != first ]]; then
  bash "$R" baseline:2 gstack:2 superpowers:2 & A=$!
  bash "$R" compound-engineering:2 feature-dev:2 & B=$!
  wait $A $B
  echo "$(date -u +%FT%TZ) second-half-done" >> "$LOG"
fi
