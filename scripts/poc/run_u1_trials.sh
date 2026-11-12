#!/usr/bin/env bash
# U1（UI/UX 系ツールの組み合わせの比較）の試行をまとめて流し、終わった試行から採点する（docs/poc/tasks/wf-U1-design.md §4）。
# 使い方: scripts/poc/run_u1_trials.sh [並列数（既定 3）]
#   U1a・U1b は 4 回、U1c は 2 回。奇数回は 課題 × 構成 の順、偶数回は逆の順。採点の axe-core は POC_AXE（既定はスクラッチの grader-deps）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAR="${1:-3}"
export POC_MAX_NUDGES=2
export POC_AXE="${POC_AXE:-/tmp/claude-0/grader-deps/node_modules/axe-core/axe.min.js}"
# U1a・U1b は 4 回、U1c は 2 回（設計書 §4）。回ごとに実行順を逆にする
LIST=()
# U1_CONFIGS で構成を指定できる（U2 は "ui-fd-md ui-a-md ui-all-md"）。U1_TASKS で課題を指定できる（既定 "U1a U1b U1c"）。U1_ROUNDS で回を指定できる（既定 "1 2 3 4"）。5 回目以降は作る課題だけ（依頼者の指示で、戻るまで作り続ける追加の試行）
for r in ${U1_ROUNDS:-1 2 3 4}; do
  ROUND=()
  for t in ${U1_TASKS:-U1a U1b U1c}; do
    [[ "$t" == U1c && "$r" -gt 2 ]] && continue
    for c in ${U1_CONFIGS:-ui-none ui-all ui-a ui-fd ui-pm}; do ROUND+=("$t $c $r"); done
  done
  if (( r % 2 == 0 )); then for ((i=${#ROUND[@]}-1; i>=0; i--)); do LIST+=("${ROUND[$i]}"); done; else LIST+=("${ROUND[@]}"); fi
done
printf '%s\n' "${LIST[@]}" | xargs -P "$PAR" -L 1 bash -c '
  id="$0-$1-$2"
  if [[ -f "'"$ROOT"'/docs/poc/results/workflow/U1/$id.json" ]]; then echo "skip $id"; exit 0; fi
  bash "'"$ROOT"'/scripts/poc/run-trial.sh" "$0" "$1" "$2" > "/tmp/claude-0/w21-$id.log" 2>&1
  python3 "'"$ROOT"'/scripts/poc/grade_u1.py" "$id" --cleanup >> "/tmp/claude-0/w21-$id.log" 2>&1
  echo "finished $id: $(tail -2 /tmp/claude-0/w21-$id.log | head -1)"'
echo ALL-DONE
