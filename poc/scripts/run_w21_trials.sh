#!/usr/bin/env bash
# W21（見つけにくい問題でのレビューの比較）・W22（同じ題材で、弱いモデル・道具の手順を最後まで）の試行を順番に実行し、終わったものから事実を集める（poc/tasks/wf-W21-design.md）。
# 使い方: poc/scripts/run_w21_trials.sh <設定>:<題材>-<回> [...]（W22 は環境変数 POC_E2_SCENARIO=W22）
#   例: poc/scripts/run_w21_trials.sh ce-review:c1-1 baseline:c2-1
# 介入は最大 1 回（W20 と同じ）。費用の上限は渡さない（歯止めは POC_STEP_TIMEOUT）。
# 結果が既にある試行（results/workflow/W21/<ID>.json）は飛ばす。採点の後に作業用コピーを片付ける（grade_w20.py --cleanup）。
# 並列で動かすときは、このスクリプトを別々の試行の並びで 2 つ起動する（並列 2 本まで）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCN="${POC_E2_SCENARIO:-W21}"
LOG="$ROOT/poc/results/workflow/raw/$(echo "$SCN" | tr A-Z a-z)-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec#*:}"
  id="$SCN-$cand-$run"
  if [[ -f "$ROOT/poc/results/workflow/$SCN/$id.json" ]]; then
    echo "$(date -u +%FT%TZ) skip $id（結果あり）" >> "$LOG"; continue
  fi
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=1 bash "$ROOT/poc/scripts/run-trial.sh" "$SCN" "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
  GRADER=grade_w20.py; [[ "$SCN" == W34 ]] && GRADER=grade_w34.py
  python3 "$ROOT/poc/scripts/$GRADER" "$id" --cleanup >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) graded $id $?" >> "$LOG"
done
