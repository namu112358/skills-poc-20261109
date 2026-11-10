#!/usr/bin/env bash
# W14・W15 の試行を順番に実行し、終わったものから採点する（docs/poc/tasks/wf-W14-design.md・wf-W15-design.md）。
# 使い方: scripts/poc/run_w14_trials.sh <シナリオ> <候補>:<回> [<候補>:<回> ...]
#   例: scripts/poc/run_w14_trials.sh W14 superpowers:1 gstack:1
# 介入は最大 2 回（W2 以降と同じ）。費用の上限は渡さない（POC_MAX_TRIAL_USD を使わない。歯止めは POC_STEP_TIMEOUT）。
# 試行の記録は docs/poc/results/workflow/raw/<W>-<候補>-<回>/、採点の結果は results/workflow/<W>/<W>-<候補>-<回>.json。
# 作業用コピーは採点の後も残す（ブラインドレビューの資料作りの後に grade.py <W> <ID> --cleanup-only で片付ける）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCN="$1"; shift
LOG="$ROOT/docs/poc/results/workflow/raw/$(echo "$SCN" | tr 'A-Z' 'a-z')-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
GRADER="$ROOT/scripts/poc/grade_$(echo "$SCN" | tr 'A-Z' 'a-z').py"
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec##*:}"
  id="$SCN-$cand-$run"
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=2 bash "$ROOT/scripts/poc/run-trial.sh" "$SCN" "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
  python3 "$GRADER" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) graded $id $?" >> "$LOG"
done
