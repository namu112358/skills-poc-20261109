#!/usr/bin/env bash
# W16 の試行を順番に実行し、終わったものから採点する（docs/poc/tasks/wf-W16-design.md）。
# 使い方: scripts/poc/run_w16_trials.sh <候補>:<回> [<候補>:<回> ...]
# 介入は最大 2 回。費用の上限は渡さない（POC_MAX_TRIAL_USD を使わない。歯止めは POC_STEP_TIMEOUT）。
# 試行 → grade_w16.py（動かす採点）→ reinject_w16.py（再発防止のテスト）→ judge_w16.py（原因の特定）→ w16_slim.py（HOME と node_modules の片付け）。
# 作業用コピー（app）は残す（ブラインドレビューの資料作りの後に grade.py W16 <ID> --cleanup-only で片付ける）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/docs/poc/results/workflow/raw/w16-runner.log"
mkdir -p "$(dirname "$LOG")"
unset POC_MAX_TRIAL_USD
for spec in "$@"; do
  cand="${spec%%:*}"; run="${spec##*:}"
  id="W16-$cand-$run"
  echo "$(date -u +%FT%TZ) start $id" >> "$LOG"
  POC_MAX_NUDGES=2 bash "$ROOT/scripts/poc/run-trial.sh" W16 "$cand" "$run" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) trial-exit $id $?" >> "$LOG"
  python3 "$ROOT/scripts/poc/grade_w16.py" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) graded $id $?" >> "$LOG"
  python3 "$ROOT/scripts/poc/reinject_w16.py" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) reinjected $id $?" >> "$LOG"
  python3 "$ROOT/scripts/poc/judge_w16.py" "$id" >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) judged $id $?" >> "$LOG"
  python3 "$ROOT/scripts/poc/w16_slim.py" "$id" >> "$LOG" 2>&1
done
