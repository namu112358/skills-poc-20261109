#!/usr/bin/env bash
# W21（UI/UX 系ツールの組み合わせの比較）の試行をまとめて流し、終わった試行から採点する（docs/poc/tasks/wf-W21-design.md §4）。
# 使い方: scripts/poc/run_w21_trials.sh [並列数（既定 3）]
#   1 回目は 課題 × 構成 の順、2 回目は逆の順。採点の axe-core は POC_AXE（既定はスクラッチの grader-deps）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAR="${1:-3}"
export POC_MAX_NUDGES=2
export POC_AXE="${POC_AXE:-/tmp/claude-0/grader-deps/node_modules/axe-core/axe.min.js}"
LIST=()
for t in W21a W21b W21c; do for c in ui-none ui-all ui-a ui-fd ui-pm; do LIST+=("$t $c 1"); done; done
for ((i=${#LIST[@]}-1; i>=0; i--)); do read -r t c _ <<<"${LIST[$i]}"; LIST+=("$t $c 2"); done
printf '%s\n' "${LIST[@]}" | xargs -P "$PAR" -L 1 bash -c '
  id="$0-$1-$2"
  if [[ -f "'"$ROOT"'/docs/poc/results/workflow/W21/$id.json" ]]; then echo "skip $id"; exit 0; fi
  bash "'"$ROOT"'/scripts/poc/run-trial.sh" "$0" "$1" "$2" > "/tmp/claude-0/w21-$id.log" 2>&1
  python3 "'"$ROOT"'/scripts/poc/grade_w21.py" "$id" --cleanup >> "/tmp/claude-0/w21-$id.log" 2>&1
  echo "finished $id: $(tail -2 /tmp/claude-0/w21-$id.log | head -1)"'
echo ALL-DONE
