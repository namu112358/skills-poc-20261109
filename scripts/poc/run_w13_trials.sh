#!/usr/bin/env bash
# W13 の試行を順番に実行し、終わったものから採点する（docs/poc/tasks/wf-W13-design.md）。
# 使い方: scripts/poc/run_w13_trials.sh <候補>:<回> [<候補>:<回> ...]
#   例: scripts/poc/run_w13_trials.sh superpowers:1 gstack:1
# 介入は最大 2 回（変更依頼の前と後でそれぞれ）。費用の上限は渡さない（POC_MAX_TRIAL_USD を使わない。歯止めは POC_STEP_TIMEOUT）。
# 採点（grade_w13.py）はアダプターの下書きを作る。採点者が確かめて <試行ID>-v1.json・-v2.json を確定してから採点し直す。
# 作業用コピーは残す（ブラインドレビューの資料作りの後に grade.py W13 <ID> --cleanup-only で片付ける）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/docs/poc/results/workflow/raw/w13-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec##*:}"
  id="W13-$cand-$run"
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=2 bash "$ROOT/scripts/poc/run-trial.sh" W13 "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
done
