#!/usr/bin/env bash
# W11 の試行をまとめて実行し、終わったものから採点する（並列数は POC_PARALLEL、既定 3）。
# 使い方: scripts/poc/oss/run_all.sh <試行ID>...   例: W11-B1-baseline-1
# 試行 ID ごとに run-trial.sh → grade_w11.py の順で行い、結果を 1 行ずつ出す。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export POC_MAX_NUDGES="${POC_MAX_NUDGES:-2}" POC_MAX_TRIAL_USD="${POC_MAX_TRIAL_USD:-10}"
one() {
  local id="$1" re='^(W11-[BF][0-9]+)-(.+)-([0-9]+)$'
  [[ "$id" =~ $re ]] || { echo "bad id $id"; return; }
  bash "$ROOT/scripts/poc/run-trial.sh" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" > /dev/null 2>&1 || echo "$id run-trial exit=$?"
  python3 "$ROOT/scripts/poc/grade_w11.py" "$id" 2>&1 | tail -1
}
export -f one; export ROOT
printf '%s\n' "$@" | xargs -P "${POC_PARALLEL:-3}" -I{} bash -c 'one {}'
