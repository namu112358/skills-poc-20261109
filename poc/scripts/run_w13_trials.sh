#!/usr/bin/env bash
# W13 の試行を順番に実行し、終わったものから採点する（poc/tasks/wf-W13-design.md）。
# 使い方: poc/scripts/run_w13_trials.sh <候補>:<回> [<候補>:<回> ...]
#   例: poc/scripts/run_w13_trials.sh superpowers:1 gstack:1
# 介入は最大 2 回（変更依頼の前と後でそれぞれ）。費用の上限は渡さない（POC_MAX_TRIAL_USD を使わない。歯止めは POC_STEP_TIMEOUT）。
# 試行のあと grade_w13.py で採点する（アダプターの下書きを作って使う。採点者が確かめて <試行ID>-v1.json・-v2.json を確定したら採点し直す）。
# 採点の後に w13_slim.py で HOME（記録は raw/ に写す）と node_modules の容量を減らす。app は採点し直しのために残す。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/poc/results/workflow/raw/w13-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec##*:}"
  id="W13-$cand-$run"
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=2 bash "$ROOT/poc/scripts/run-trial.sh" W13 "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
  # 採点（アダプターは確定したものが無ければ下書きを使う。採点者が確かめて確定したら採点し直す）→ 作業用コピーの容量を減らす
  python3 "$ROOT/poc/scripts/grade_w13.py" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) graded $id $?" >> "$LOG"
  python3 "$ROOT/poc/scripts/w13_slim.py" "$id" >> "$LOG" 2>&1
done
