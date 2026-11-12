#!/usr/bin/env bash
# W7 の 1 組（W7a → 採点 → W7b → 採点 → … → 最後の段階 → 採点）を実行する。
# 使い方: poc/scripts/w7_chain.sh <候補> <回> <上限USD> [最後の段階（既定 W7b）]
#   例: poc/scripts/w7_chain.sh superpowers 21 7.67 W7e  → W7a〜W7e を続けて行う（/ce-compound は W7a〜W7d の後）
# 対照（前の段階を引き継がない最後の段階だけ、回 11 など）: POC_W7_CONTROL=1 poc/scripts/w7_chain.sh <候補> <回> <上限USD> [最後の段階]
set -u
CAND="$1"; RUN="$2"; CAP="$3"; LAST="${4:-W7b}"
[[ "$LAST" =~ ^W7[b-z]$ ]] || { echo "最後の段階は W7b〜W7z: $LAST" >&2; exit 1; }
cd "$(dirname "$0")/../.."
export POC_BUDGET_MODE=watch POC_MAX_TRIAL_USD="$CAP" POC_MAX_NUDGES=2 POC_W7_LAST_STAGE="$LAST"
if [[ "${POC_W7_CONTROL:-}" == 1 ]]; then
  poc/scripts/run-trial.sh "$LAST" "$CAND" "$RUN"
  python3 poc/scripts/grade_w7.py "$LAST-$CAND-$RUN"
  exit 0
fi
for s in a b c d e f g h; do
  STAGE="W7$s"
  echo "== $(date -u +%H:%M:%S) start $STAGE-$CAND-$RUN cap=$CAP"
  poc/scripts/run-trial.sh "$STAGE" "$CAND" "$RUN"
  python3 poc/scripts/grade_w7.py "$STAGE-$CAND-$RUN"
  [[ "$STAGE" == "$LAST" ]] && break
done
echo "== $(date -u +%H:%M:%S) end $CAND-$RUN"
