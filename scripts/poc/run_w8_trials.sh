#!/usr/bin/env bash
# W8 の試行を 1 本ずつ順番に実行し、採点（grade_w8.py）と作業用コピーの片付けまで行う。
# 使い方: scripts/poc/run_w8_trials.sh <候補>:<回> [<候補>:<回> ...]
#   例:   scripts/poc/run_w8_trials.sh compound-engineering:1 compound-engineering:2 gstack:2
# 条件: 介入なし（POC_MAX_NUDGES=0）、新文言・watch 方式（W8 の既定）。上限は下の cap()（規模係数 3.15 × W1 の候補平均 × 5、最大 $10）。
# /tmp/claude-0/STOP があれば、次の試行に入る前に止まる。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cap() { case "$1" in baseline) echo 5;; superpowers) echo 2.67;; feature-dev) echo 2.70;; gstack) echo 7.21;; compound-engineering) echo 10;; esac; }
cd "$ROOT"
for t in "$@"; do
  c=${t%%:*}; r=${t##*:}
  [[ -f /tmp/claude-0/STOP ]] && { echo "stopped before $c-$r"; break; }
  POC_MAX_NUDGES=0 POC_MAX_TRIAL_USD="$(cap "$c")" scripts/poc/run-trial.sh W8 "$c" "$r"
  R="docs/poc/results/workflow/raw/W8-$c-$r"
  echo "suffix=$(cat "$R/task-suffix") budget=$(cat "$R/budget-mode") stopped=$(cat "$R/budget-stopped" 2>/dev/null)"
  python3 scripts/poc/grade_w8.py "W8-$c-$r"
  python3 scripts/poc/grade.py W8 "W8-$c-$r" --cleanup-only
done
echo ALLDONE
