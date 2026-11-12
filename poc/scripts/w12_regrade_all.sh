#!/usr/bin/env bash
# W12 の全試行を、最終版の採点スクリプト・正解データで採点し直す（版を混在させないため）。ミューテーションは前回の結果を使う。
# 使い方: poc/scripts/w12_regrade_all.sh <試行ID> ...
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$ROOT/poc/results/workflow/raw/w12-regrade.log"
for id in "$@"; do
  python3 "$ROOT/poc/scripts/grade_w12.py" "$id" --keep-mutation 2>&1 | tail -1 >> "$LOG"
done
echo "$(date -u +%FT%TZ) regrade-done $*" >> "$LOG"
