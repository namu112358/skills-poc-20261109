#!/usr/bin/env bash
# 2026-11-10 05:10 UTC の使用量の上限のリセット後に、止まった試行を順番どおりにやり直す（判断の記録）。
# 標準ありの残り 4 本（後半の逆順の続き）→ Haiku の 10 本 → 乱れた初期状態の 10 本。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
( export POC_STANDARD=generic
  bash "$ROOT/poc/scripts/run_w12_trials.sh" gstack:12 superpowers:12 &
  bash "$ROOT/poc/scripts/run_w12_trials.sh" compound-engineering:12 feature-dev:12 &
  wait )
echo "$(date -u +%FT%TZ) std-done" >> "$ROOT/poc/results/workflow/raw/w12-runner.log"
POC_MODEL=claude-haiku-5-5 POC_ANSWER_MODEL=claude-sonnet-5-5 bash "$ROOT/poc/scripts/w12_cond_driver.sh" 21 22
echo "$(date -u +%FT%TZ) haiku-done" >> "$ROOT/poc/results/workflow/raw/w12-runner.log"
POC_W12_BASE=messy bash "$ROOT/poc/scripts/w12_cond_driver.sh" 31 32
echo "$(date -u +%FT%TZ) messy-done" >> "$ROOT/poc/results/workflow/raw/w12-runner.log"
