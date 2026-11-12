#!/usr/bin/env bash
# W7 の試行を 1 段階ずつ実行し、使用量の上限（429 usage_limit_reached）で失敗した段階は、
# リセットの時刻まで待ってから、その段階を 1 つ前の段階の終了時点に戻してやり直す。
# 使い方: poc/scripts/w7_runner.sh <上限USD> <最後の段階> <項目> [<項目> ...]
#   項目: <候補>:<回>            … W7a から最後の段階まで続けて行う
#         <候補>:<回>:<段階>      … その段階から最後の段階まで続けて行う（前の段階は済んでいること）
#         control:<候補>:<回>     … 最後の段階だけの対照（POC_W7_CONTROL=1）
#   例: poc/scripts/w7_runner.sh 7.67 W7e gstack:21:W7e baseline:22 control:baseline:31
# やり直したことは results/workflow/W7/retries.log に記録する（report の「判断の記録」に書く）。
set -u
CAP="$1"; LAST="$2"; shift 2
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export POC_BUDGET_MODE=watch POC_MAX_TRIAL_USD="$CAP" POC_MAX_NUDGES=2 POC_W7_LAST_STAGE="$LAST"
RAW="$ROOT/poc/results/workflow/raw"
LOG="$ROOT/poc/results/workflow/W7/retries.log"

limited() {  # その試行のどこかのステップが使用量の上限で失敗したか。失敗していればリセットの時刻（例: 7:10pm）を出す
  grep -ho '"api_error":"usage_limit_reached","result":"[^"]*"' "$RAW/$1"/step*.jsonl 2>/dev/null | head -1 | grep -o 'resets [0-9:apm]*' | sed 's/resets //'
}

wait_reset() {  # リセットの時刻（UTC）の 2 分後まで待つ
  local t="$1" secs
  secs="$(python3 - "$t" <<'PY'
import datetime, re, sys
m = re.match(r"(\d+)(?::(\d+))?(am|pm)", sys.argv[1])
h, mi = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0), int(m.group(2) or 0)
now = datetime.datetime.now(datetime.timezone.utc)
r = now.replace(hour=h, minute=mi, second=0, microsecond=0)
if r <= now:
    r += datetime.timedelta(days=1)
print(int((r - now).total_seconds()) + 120)
PY
)"
  echo "== $(date -u +%H:%M:%S) usage limit; waiting ${secs}s (reset $t UTC)"
  sleep "$secs"
}

prev_stage() { printf 'W7%b' "\\$(printf '%03o' $(( $(printf '%d' "'${1:2:1}") - 1 )))"; }

restore() {  # 段階 S（W7b 以降）をやり直す前に、作業用コピーを 1 つ前の段階の終了時点に戻す
  local id="$1" s="$2" cand="$3" run="$4" work app
  work="$(cat "$RAW/$id/workdir")"; app="$work/app"
  git -C "$app" checkout -q -f "poc/wf/$cand/$(prev_stage "$s")/$run"
  git -C "$app" clean -q -fd
  git -C "$app" branch -q -D "poc/wf/$cand/$s/$run"
}

run_stage() {  # run_stage <段階> <候補> <回> [control]
  local s="$1" cand="$2" run="$3" ctl="${4:-}" id="$1-$2-$3" t tries=0
  # 途中で失敗した前回の分が残っていれば（その段階の作業ブランチがある）、1 つ前の段階の終了時点に戻してから始める
  if [[ -z "$ctl" && "$s" != W7a && -f "$RAW/$id/workdir" ]] && git -C "$(cat "$RAW/$id/workdir")/app" rev-parse -q --verify "poc/wf/$cand/$s/$run" >/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $id: 前回の途中の分を捨て、$(prev_stage "$s") の終了時点からやり直す" >> "$LOG"
    restore "$id" "$s" "$cand" "$run"
  fi
  while true; do
    echo "== $(date -u +%H:%M:%S) start $id"
    if [[ -n "$ctl" ]]; then POC_W7_CONTROL=1 poc/scripts/run-trial.sh "$s" "$cand" "$run"; else poc/scripts/run-trial.sh "$s" "$cand" "$run"; fi
    t="$(limited "$id")"
    if [[ -z "$t" ]]; then
      python3 poc/scripts/grade_w7.py "$id"
      return 0
    fi
    tries=$((tries + 1))
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $id: 使用量の上限（resets $t UTC）で失敗したため、リセット後にやり直す（$tries 回目）" >> "$LOG"
    [[ "$tries" -ge 3 ]] && { echo "== $id: 3 回失敗したので止める"; exit 1; }
    wait_reset "$t"
    [[ -z "$ctl" && "$s" != W7a ]] && restore "$id" "$s" "$cand" "$run"
  done
}

for item in "$@"; do
  IFS=: read -r a b c <<< "$item"
  if [[ "$a" == control ]]; then
    echo "#### $(date -u +%H:%M:%S) control $b-$c"
    run_stage "$LAST" "$b" "$c" control
    continue
  fi
  echo "#### $(date -u +%H:%M:%S) chain $a-$b from ${c:-W7a}"
  started=""
  for s in W7a W7b W7c W7d W7e W7f W7g W7h; do
    [[ -z "$started" && "$s" != "${c:-W7a}" ]] && continue
    started=1
    run_stage "$s" "$a" "$b"
    [[ "$s" == "$LAST" ]] && break
  done
done
echo "#### $(date -u +%H:%M:%S) ALL DONE"
