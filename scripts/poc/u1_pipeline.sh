#!/usr/bin/env bash
# U1 を無人で最後まで流す（依頼者の指示: 不在の間も続ける）。
# 1) 実行中の run_u1_trials.sh が終わるのを待つ → 2) U1a〜c の残り（中断した試行を含む）→ 3) U1d〜f を 4 回ずつ。
# 何度実行しても、採点済みの試行（results/workflow/U1/<ID>.json がある）は飛ばす。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG=/tmp/claude-0/w21-pipeline.log
while pgrep -f "run_u1_trials.sh" > /dev/null; do sleep 30; done
echo "stage a-c $(date -u +%H:%M)" >> "$LOG"
bash "$ROOT/scripts/poc/run_u1_trials.sh" 3 >> /tmp/claude-0/w21-batch.log 2>&1
echo "stage d-f $(date -u +%H:%M)" >> "$LOG"
U1_TASKS="U1d U1e U1f" bash "$ROOT/scripts/poc/run_u1_trials.sh" 3 >> /tmp/claude-0/w21-batch.log 2>&1
echo "stage U2 $(date -u +%H:%M)" >> "$LOG"
U1_TASKS="U1d U1e U1f" U1_CONFIGS="ui-fd-md ui-a-md ui-all-md" U1_ROUNDS="1 2 3" bash "$ROOT/scripts/poc/run_u1_trials.sh" 3 >> /tmp/claude-0/w21-batch.log 2>&1
echo "PIPELINE-DONE $(date -u +%H:%M)" >> "$LOG"
