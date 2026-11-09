#!/usr/bin/env bash
# W7 の 1 組（W7a → 採点 → W7b → 採点）を実行する。使い方: scripts/poc/w7_chain.sh <候補> <回> <上限USD>
# 対照（W7a を引き継がない W7b、回 11）: POC_W7_CONTROL=1 scripts/poc/w7_chain.sh <候補> 11 <上限USD>（W7b だけを実行）
set -u
CAND="$1"; RUN="$2"; CAP="$3"
cd "$(dirname "$0")/../.."
export POC_BUDGET_MODE=watch POC_MAX_TRIAL_USD="$CAP" POC_MAX_NUDGES=2
if [[ "${POC_W7_CONTROL:-}" == 1 ]]; then
  scripts/poc/run-trial.sh W7b "$CAND" "$RUN"
  python3 scripts/poc/grade_w7.py "W7b-$CAND-$RUN"
  exit 0
fi
echo "== $(date -u +%H:%M:%S) start W7a-$CAND-$RUN cap=$CAP"
scripts/poc/run-trial.sh W7a "$CAND" "$RUN"
python3 scripts/poc/grade_w7.py "W7a-$CAND-$RUN"
echo "== $(date -u +%H:%M:%S) start W7b-$CAND-$RUN"
scripts/poc/run-trial.sh W7b "$CAND" "$RUN"
python3 scripts/poc/grade_w7.py "W7b-$CAND-$RUN"
echo "== $(date -u +%H:%M:%S) end $CAND-$RUN"
