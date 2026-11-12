#!/usr/bin/env bash
# W12 の試行を順番に実行し、終わったものから採点する（poc/tasks/wf-W12-design.md）。
# 使い方: poc/scripts/run_w12_trials.sh <候補>:<回> [<候補>:<回> ...]
#   例: poc/scripts/run_w12_trials.sh superpowers:1 gstack:1
# 介入は最大 2 回（W2 以降と同じ）。費用の上限は渡さない（POC_MAX_TRIAL_USD を使わない。歯止めは POC_STEP_TIMEOUT）。
# 試行の記録は poc/results/workflow/raw/W12-<候補>-<回>/、採点の結果は results/workflow/W12/W12-<候補>-<回>.json。
# 作業用コピーは採点の後も残す（ブラインドレビューの資料作りの後に grade.py W12 <ID> --cleanup-only で片付ける）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/poc/results/workflow/raw/w12-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec##*:}"
  id="W12-$cand-$run"
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=2 bash "$ROOT/poc/scripts/run-trial.sh" W12 "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
  python3 "$ROOT/poc/scripts/grade_w12.py" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) graded $id $?" >> "$LOG"
  python3 "$ROOT/poc/scripts/w12_slim.py" "$id" >> "$LOG" 2>&1
done
