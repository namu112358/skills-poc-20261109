#!/usr/bin/env bash
# W21（UI/UX 系ツールの組み合わせの比較）の試行をまとめて流し、終わった試行から採点する（docs/poc/tasks/wf-W21-design.md §4）。
# 使い方: scripts/poc/run_w21_trials.sh [並列数（既定 3）]
#   W21a・W21b は 4 回、W21c は 2 回。奇数回は 課題 × 構成 の順、偶数回は逆の順。採点の axe-core は POC_AXE（既定はスクラッチの grader-deps）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAR="${1:-3}"
export POC_MAX_NUDGES=2
export POC_AXE="${POC_AXE:-/tmp/claude-0/grader-deps/node_modules/axe-core/axe.min.js}"
# W21a・W21b は 4 回、W21c は 2 回（設計書 §4）。回ごとに実行順を逆にする
LIST=()
# W21_CONFIGS で構成を指定できる（W22 は "ui-fd-md ui-a-md ui-all-md"）。W21_TASKS で課題を指定できる（既定 "W21a W21b W21c"）。W21_ROUNDS で回を指定できる（既定 "1 2 3 4"）。5 回目以降は作る課題だけ（依頼者の指示で、戻るまで作り続ける追加の試行）
for r in ${W21_ROUNDS:-1 2 3 4}; do
  ROUND=()
  for t in ${W21_TASKS:-W21a W21b W21c}; do
    [[ "$t" == W21c && "$r" -gt 2 ]] && continue
    for c in ${W21_CONFIGS:-ui-none ui-all ui-a ui-fd ui-pm}; do ROUND+=("$t $c $r"); done
  done
  if (( r % 2 == 0 )); then for ((i=${#ROUND[@]}-1; i>=0; i--)); do LIST+=("${ROUND[$i]}"); done; else LIST+=("${ROUND[@]}"); fi
done
printf '%s\n' "${LIST[@]}" | xargs -P "$PAR" -L 1 bash -c '
  id="$0-$1-$2"
  if [[ -f "'"$ROOT"'/docs/poc/results/workflow/W21/$id.json" ]]; then echo "skip $id"; exit 0; fi
  bash "'"$ROOT"'/scripts/poc/run-trial.sh" "$0" "$1" "$2" > "/tmp/claude-0/w21-$id.log" 2>&1
  python3 "'"$ROOT"'/scripts/poc/grade_w21.py" "$id" --cleanup >> "/tmp/claude-0/w21-$id.log" 2>&1
  echo "finished $id: $(tail -2 /tmp/claude-0/w21-$id.log | head -1)"'
echo ALL-DONE
