#!/usr/bin/env bash
# 開発ワークフローの試行を 1 回実行する。
# 使い方: scripts/poc/run-trial.sh <シナリオ> <候補> <回>
#   候補: baseline | superpowers | feature-dev | compound-engineering | gstack
#   （gstack の setup 実行は 2026-11-09 にユーザーの許可を得た。専用 HOME の中だけで実行する）
# 作業用コピー（既定は /tmp/poc-trials/<ID>。POC_TRIAL_ROOT で変更可）で、専用の HOME を使って Claude Code をヘッドレスで起動する。
# 作業用コピーをリポジトリの外に置くのは、正解データ（docs/poc/answer-key/）や他の試行の結果へ相対パスで辿れないようにするため。
# 置き場所は raw/<ID>/workdir に記録し、grade.py はそこを読む（記録がなければ旧来の .poc-work/trials/<ID>）。
# 子セッションの権限は docs/poc/tasks/wf-procedures.md の「権限」のとおり（全許可にはしない）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCENARIO="$1"; CAND="$2"; RUN="$3"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
MODEL="${POC_MODEL:-claude-sonnet-5-5}"
ID="$SCENARIO-$CAND-$RUN"
TRIALS="${POC_TRIAL_ROOT:-/tmp/poc-trials}"
WORK="$TRIALS/$ID"
APP="$WORK/app"
HOME_DIR="$WORK/home"
OUT="$ROOT/docs/poc/results/workflow/raw/$ID"

rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$OUT"
echo "$WORK" > "$OUT/workdir"

# 1) 評価用アプリのコピー（node_modules を含む）と、常時有効な Skills・MCP
# POC_APP_SRC: コピー元の評価用アプリ（既定は $ROOT/poc-app）。W1 を当時の poc-app（ログイン・SQLite の追加前）で
# 再試行するときなどに、その版を取り出したディレクトリを指定する。使ったコピー元は raw/<ID>/app-src に記録する。
APP_SRC="${POC_APP_SRC:-$ROOT/poc-app}"
[[ -n "${POC_APP_SRC:-}" ]] && echo "$APP_SRC" > "$OUT/app-src"
cp -a "$APP_SRC/." "$APP/"
rm -rf "$APP/.next" "$APP"/*.tsbuildinfo
mkdir -p "$APP/.claude"
cp -a "$ROOT/.claude/skills" "$APP/.claude/skills"
rm -f "$APP/.claude/skills/SOURCES.md"
cat > "$APP/.mcp.json" <<'JSON'
{"mcpServers":{
  "playwright":{"type":"stdio","command":"npx","args":["-y","@playwright/mcp@0.0.84"]},
  "next-devtools":{"type":"stdio","command":"npx","args":["-y","next-devtools-mcp@0.4.0"]}}}
JSON
# W5（バグ修正）: 仕込みバグのパッチ（正解データ）を作業用コピーにだけ当ててから baseline コミットを作る。
# バグは baseline の一部になるので、候補からは差分として見えない。パッチファイル自体は作業用コピーに置かない。
# W5 以外は既定で当てない（POC_INJECT_PATCH で明示したときだけ当てる）。
INJECT="${POC_INJECT_PATCH:-}"
[[ -z "$INJECT" && "$SCENARIO" == W5 ]] && INJECT="$ROOT/docs/poc/answer-key/W5/bugs.patch"
( cd "$APP" && git init -q )
if [[ -n "$INJECT" ]]; then
  git -C "$APP" apply "$INJECT"
  sha256sum "$INJECT" | sed "s#$ROOT/##" > "$OUT/injected-patch"
fi
( cd "$APP" && git add -A && git -c user.name=poc -c user.email=poc@example.invalid commit -qm baseline )
git -C "$APP" config user.name poc
git -C "$APP" config user.email poc@example.invalid
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
# 試行は作業ブランチの上で始める（W2 以降。W1 で gstack の /review が master 直コミットのため差分なしで止まったため）
#（W1 は master のまま。W1 の手順を同じ条件で再実行できるようにするため）
[[ "$SCENARIO" != W1 ]] && git -C "$APP" switch -q -c "poc/wf/$CAND/$SCENARIO/$RUN"

# 2) 必須プラグイン + 候補プラグイン（すべて固定コミット。scripts/poc/fetch-plugins.sh で取得）
#    Skill が自分の参照ファイル（references/*.md など）を読めるよう、試行ごとの作業領域にコピーして
#    --add-dir で読み取りを許可する（コピーなので、書き換えられても他の試行には影響しない）。
PLUG="$WORK/plugins"; mkdir -p "$PLUG"
PLUG_EXTRA=()
CPO="$CACHE/claude-plugins-official/plugins"
copy_plugin() { cp -a "$1" "$PLUG/$2"; rm -rf "$PLUG/$2/.git"; PLUGINS+=(--plugin-dir "$PLUG/$2"); }
PLUGINS=()
copy_plugin "$CPO/security-guidance" security-guidance
copy_plugin "$CPO/typescript-lsp" typescript-lsp
copy_plugin "$CACHE/impeccable/plugin" impeccable
copy_plugin "$CACHE/ui-ux-pro-max" ui-ux-pro-max
case "$CAND" in
  baseline) ;;
  superpowers) copy_plugin "$CACHE/superpowers" superpowers ;;
  feature-dev) copy_plugin "$CPO/feature-dev" feature-dev ;;
  compound-engineering) copy_plugin "$CACHE/compound-engineering" compound-engineering ;;
  gstack)
    # gstack は marketplace 配布ではないため、試行ごとの専用 HOME の ~/.claude/skills/gstack に固定コミットを置き、
    # setup を実行する（チーム用の自動更新フックなし・plan-tune フックなし）。
    # ブラウザ（Chrome for Testing）は環境のネットワーク制限で取得できないため --no-browser。
    GSTACK="$HOME_DIR/.claude/skills/gstack"
    mkdir -p "$HOME_DIR/.claude/skills"
    cp -a "$CACHE/gstack" "$GSTACK"
    ( cd "$GSTACK" && HOME="$HOME_DIR" ./setup --host claude --no-team --no-plan-tune-hooks --no-browser --quiet ) > "$OUT/gstack-setup.log" 2>&1
    # 外部送信を止める（更新確認、Codex への外部レビュー）。テレメトリーは初期値 off のまま
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" set update_check false >> "$OUT/gstack-setup.log" 2>&1
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" set codex_reviews disabled >> "$OUT/gstack-setup.log" 2>&1
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" get telemetry >> "$OUT/gstack-setup.log" 2>&1
    PLUG_EXTRA=(--add-dir "$GSTACK")
    ;;
  *) echo "unknown candidate: $CAND" >&2; exit 1 ;;
esac

# 3) 権限（全許可にはしない）
ALLOWED=(
  "Bash(npm run typecheck)" "Bash(npm test)" "Bash(npm run test)" "Bash(npm run build)"
  "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git branch:*)" "Bash(git rev-parse:*)"
  "Bash(git switch:*)" "Bash(git checkout:*)" "Bash(git -C:*)" "Bash(git check-ignore:*)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(find:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
  "Bash(cd:*)" "Bash(mkdir:*)" "Bash(sleep:*)" "Bash(curl -s:*)" "Bash(npx next:*)"
  # 候補プラグイン自身のスクリプト（試行ごとのコピー）
  "Bash(python3 $PLUG/:*)" "Bash(bash $PLUG/:*)" "Bash(node $PLUG/:*)"
)
if [[ "$CAND" == gstack ]]; then
  # gstack 自身のコマンド（~/.claude/skills/gstack/bin/*）
  ALLOWED+=("Bash($GSTACK/bin/:*)" "Bash(~/.claude/skills/gstack/bin/:*)" "Bash(bun $GSTACK/:*)")
fi
# W6 以降（UI 実装からブラウザ検証まで）: 開発サーバーの起動とブラウザ操作を許可する（2026-11-09 追加）。
# W1〜W5 は比較の条件を揃えるため従来の許可リストのまま。サーバーは試行後に reap_servers が止める。
SCN_NUM="${SCENARIO#W}"; SCN_NUM="${SCN_NUM%%[a-z]*}"
CHILD_ENV=()
if [[ "$SCN_NUM" -ge 6 ]]; then
  ALLOWED+=(
    "Bash(npm run dev)" "Bash(npm run dev:*)" "Bash(npm run start)" "Bash(npm run start:*)"
    "Bash(timeout * npm run dev*)" "Bash(timeout * npm run start*)" "Bash(timeout * npx next *)"
    # npm start（npm run start の別名）と、ポートを環境変数で渡す形（PORT=3100 npm run start など）。
    # 2026-11-09 の最初の試行でこの形が漏れていて、2 試行がサーバーを起動できなかったため追加した
    "Bash(npm start)" "Bash(npm start:*)" "Bash(PORT=* npm start*)" "Bash(PORT=* npm run start*)"
    "Bash(PORT=* npm run dev*)" "Bash(PORT=* npx next *)"
    # ブラウザ: Playwright MCP（全候補共通。事前インストール済みの Chromium を使う）と Next.js DevTools MCP
    "mcp__playwright" "mcp__next-devtools"
  )
  if [[ "$CAND" == gstack ]]; then
    # gstack のブラウザ（browse）。Chrome for Testing は取得できないので、事前インストール済みの Chromium を使わせる
    ALLOWED+=("Bash($GSTACK/browse/dist/:*)" "Bash(~/.claude/skills/gstack/browse/dist/:*)")
  fi
  CHILD_ENV=(GSTACK_CHROMIUM_PATH=/opt/pw-browsers/chromium)
  # 子セッションが起動したサーバー・ブラウザが試行後に残らないよう、終了時にも止める（reap_servers は下で定義）
  trap 'declare -F reap_servers >/dev/null && reap_servers end' EXIT
fi

# 4) 手順（docs/poc/tasks/wf-procedures.md）
if [[ "$SCENARIO" == W3 ]]; then
  # W3 は質問に定型回答シートで答える（docs/poc/tasks/wf-answers.md の「W3」）。末尾の定型文もそれに合わせる。
  TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

この作業は無人で実行しています。質問には、依頼者の代わりに定型の回答シートから答えます（シートに無いことは「お任せします」と答えます）。"
else
  # 末尾の定型文（2026-11-09 変更）。旧文言では Feature Dev が「無人のため」と調査・設計・レビューの工程を省いたため、
  # W4 以降は工程を省かないよう明記した新文言にする。W1・W2 は再現性のため旧文言が既定。
  # POC_TASK_SUFFIX=old|new で明示的に切り替えられる（W1・W2 の新文言での再試行など）。
  SUFFIX_MODE="${POC_TASK_SUFFIX:-}"
  if [[ -z "$SUFFIX_MODE" ]]; then
    case "$SCENARIO" in W1|W2) SUFFIX_MODE=old ;; *) SUFFIX_MODE=new ;; esac
  fi
  case "$SUFFIX_MODE" in
    old) SUFFIX="この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。" ;;
    new) SUFFIX="この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことの判断はお任せしますが、ツールの手順にある工程（調査・設計・レビューなど）は省かずに進めてください。作業が終わったら、変更内容を git にコミットしてください。" ;;
    *) echo "POC_TASK_SUFFIX は old か new: $SUFFIX_MODE" >&2; exit 1 ;;
  esac
  echo "$SUFFIX_MODE" > "$OUT/task-suffix"
  TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

$SUFFIX"
fi
EXTRA=()
if [[ "$SCENARIO" == W3 ]]; then
  # 質問はメッセージ本文で受け、回答役（answer_w3.py）が次のステップで返す。質問ツールは無人では答えられないので外す。
  EXTRA=(--disallowedTools AskUserQuestion)
  case "$CAND" in
    baseline|superpowers) STEPS=("$TASK") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
    compound-engineering) STEPS=("/ce-brainstorm $TASK") ;;
    gstack) STEPS=("/office-hours $TASK" "/plan-ceo-review") ;;
  esac
else
  case "$CAND" in
    baseline|superpowers) STEPS=("$TASK") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
    compound-engineering) STEPS=("/ce-plan $TASK" "/ce-work" "/ce-code-review") ;;
    gstack) STEPS=("$TASK" "/review") ;;
  esac
fi
# W4 の gstack は /autoplan → 実装 → /review（PLAN.md §5.1。ほかのシナリオの手順は変えない）
if [[ "$SCENARIO" == W4 && "$CAND" == gstack ]]; then
  STEPS=("/autoplan $TASK" "計画に沿って実装し、変更を git にコミットしてください。" "/review")
fi
if [[ "$SCENARIO" == W6 ]]; then
  # W6 の手順（docs/poc/tasks/wf-procedures.md）。PR はリモートが無いので PR.md に書かせる（課題文に明記）。
  PR_STEP="PR を作成してください（課題文の「確認と PR」のとおり、PR のタイトルと本文を PR.md に書いてコミットします）。"
  case "$CAND" in
    baseline) STEPS=("$TASK") ;;
    superpowers) STEPS=("$TASK" "/superpowers:finishing-a-development-branch") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK" "$PR_STEP") ;;
    compound-engineering) STEPS=("/ce-work $TASK" "/ce-test-browser" "/ce-commit-push-pr") ;;
    gstack) STEPS=("$TASK" "/qa" "/ship") ;;
  esac
fi
if [[ "$SCENARIO" == W5 ]]; then
  # W5 の手順（docs/poc/tasks/wf-procedures.md）。gstack は /qa、Compound Engineering は /ce-debug に課題を渡す。
  case "$CAND" in
    baseline|superpowers|feature-dev) STEPS=("$TASK") ;;
    compound-engineering) STEPS=("/ce-debug $TASK") ;;
    gstack) STEPS=("/qa $TASK") ;;
  esac
fi

# 1 試行の費用の上限（米ドル。空なら上限なし）。
MAX_USD="${POC_MAX_TRIAL_USD:-}"
# 上限の守り方（POC_BUDGET_MODE）:
#   flag（W1〜W5 の既定）: 各ステップに、それまでの累計を引いた残りを --max-budget-usd で渡す。
#     この値は子セッションのモデルに「USD budget: $0/$0.9; $0.9 remaining」のように見えるため、
#     予算を意識して工程を減らすことがある（W1 の Feature Dev 再試行で確認）。
#   watch（W6 以降の既定）: --max-budget-usd を渡さず、run-trial.sh が途中のトークン使用量から費用を見積もり、
#     上限に達したら子セッションを止める。見積もりの単価は POC_RATE_*（米ドル / 100 万トークン）で変えられる。
#     正式な費用は従来どおり result の total_cost_usd。止めたときは budget-stopped に見積額を記録する。
# 既定はシナリオで決める（W1〜W5 は再現のため flag、W6 以降は watch）。POC_BUDGET_MODE で上書きできる。
BUDGET_MODE="${POC_BUDGET_MODE:-}"
if [[ -z "$BUDGET_MODE" ]]; then
  case "$SCENARIO" in W1|W2|W3|W4|W5) BUDGET_MODE=flag ;; *) BUDGET_MODE=watch ;; esac
fi
echo "$BUDGET_MODE" > "$OUT/budget-mode"
case "$BUDGET_MODE" in flag|watch) ;; *) echo "POC_BUDGET_MODE は flag か watch: $BUDGET_MODE" >&2; exit 1 ;; esac
# 介入（定型の「お任せします」で続けさせる）の上限回数。0 なら介入しない（W1 の手順）。
MAX_NUDGES="${POC_MAX_NUDGES:-0}"
NUDGE="お任せします。確認は不要なので、課題を最後まで実装し、変更を git にコミットしてください。"
# W3: 回答のやり取りの上限（試行全体の回数）と、締め切り・完了の定型文
MAX_QA="${POC_MAX_QA_ROUNDS:-10}"
QA_CLOSE="質問はここまでで締め切ります。残りはお任せします。ここまでの回答をもとに要件を REQUIREMENTS.md にまとめ、git にコミットしてください。"
[[ "$SCENARIO" == W3 ]] && NUDGE="お任せします。確認は不要なので、要件を REQUIREMENTS.md にまとめ、git にコミットしてください。"
[[ "$SCENARIO" == W5 ]] && NUDGE="お任せします。確認は不要なので、報告された不具合を最後まで直し、変更を git にコミットしてください。"
[[ "$SCENARIO" == W6 ]] && NUDGE="お任せします。確認は不要なので、課題を最後まで実装し、PR.md を含めて変更を git にコミットしてください。"

session_cost() {  # これまでの全ステップの最後の result の total_cost_usd（--resume では累計）
  python3 -c '
import json, sys, glob, re
cost = 0.0
for f in sorted(glob.glob(sys.argv[1] + "/step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p).group(1))):
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result" and d.get("total_cost_usd") is not None:
            cost = d["total_cost_usd"]
print(cost)' "$OUT"
}
over_budget() {
  [[ -s "$OUT/budget-stopped" ]] && return 0
  [[ -n "$MAX_USD" ]] && python3 -c "import sys; sys.exit(0 if $(session_cost) >= $MAX_USD * 0.98 else 1)"
}
step_estimate() {  # watch 用: 実行中のステップの費用の見積もり（それまでの result の累計 + このステップのトークン × 単価）
  python3 -c '
import json, os, sys
rate = {k: float(os.environ.get("POC_RATE_" + k.upper(), d)) / 1e6 for k, d in
        {"in": 1.87, "out": 9.96, "cache_read": 0.187, "cache_5m": 2.34, "cache_1h": 3.74}.items()}
# 途中のメッセージの usage.output_tokens は書き始め時点の値なので、出力は本文の文字数 / 3 との大きい方で見積もる
msgs = {}
for line in open(sys.argv[2]):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    m = d.get("message") or {}
    if d.get("type") != "assistant" or not m.get("usage"):
        continue
    e = msgs.setdefault(m.get("id"), {"usage": m["usage"], "chars": 0})
    e["chars"] += len(json.dumps(m.get("content") or [], ensure_ascii=False))
est = 0.0
for e in msgs.values():
    u = e["usage"]; cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0)
    w5m = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - w1h)
    out = max(u.get("output_tokens", 0), e["chars"] / 3)
    est += (u.get("input_tokens", 0) * rate["in"] + out * rate["out"]
            + u.get("cache_read_input_tokens", 0) * rate["cache_read"] + w5m * rate["cache_5m"] + w1h * rate["cache_1h"])
print(round(float(sys.argv[1]) + est, 4))' "$1" "$2"
}
first_session_id() {
  python3 -c '
import json, sys
for line in open(sys.argv[1]):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("session_id"):
        print(d["session_id"]); break' "$1"
}
reap_servers() {  # 作業用コピーを cwd にして動く next のプロセス（子セッションが起動したサーバー）を止める
  local p pid cwd cmd
  for p in /proc/[0-9]*; do
    pid="${p#/proc/}"
    cwd="$(readlink "$p/cwd" 2>/dev/null)" || continue
    [[ "$cwd" == "$APP"* ]] || continue
    cmd="$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)" || continue
    case "$cmd" in claude*|timeout*|*run-trial.sh*|*playwright-mcp*|*next-devtools-mcp*) continue ;; esac
    # next（開発サーバー）に加え、W6 以降の gstack の browse デーモンと、そのブラウザ（chrome）も止める
    if [[ "$cmd" == *next* || "$cmd" == *browse/dist/* || "$cmd" == *chrom* ]]; then
      kill "$pid" 2>/dev/null && echo "step$1 killed leftover: ${cmd:0:120}" >> "$OUT/errors.log"
    fi
  done
}
run_step() {  # run_step <番号> <プロンプト>
  local n="$1" prompt="$2" RESUME=() BUDGET=()
  [[ -n "$SESSION" ]] && RESUME=(--resume "$SESSION")
  local before; before="$(session_cost)"
  if [[ -n "$MAX_USD" && "$BUDGET_MODE" == flag ]]; then
    BUDGET=(--max-budget-usd "$(python3 -c "print(max(0.01, round($MAX_USD - $(session_cost), 2)))")")
  fi
  ( cd "$APP" && env HOME="$HOME_DIR" "${CHILD_ENV[@]}" timeout "${POC_STEP_TIMEOUT:-2400}" claude -p "$prompt" \
      --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
      --mcp-config "$APP/.mcp.json" --strict-mcp-config --add-dir "$PLUG" "${PLUG_EXTRA[@]}" \
      "${PLUGINS[@]}" "${RESUME[@]}" "${BUDGET[@]}" \
      "${EXTRA[@]}" --output-format stream-json --verbose < /dev/null ) > "$OUT/step$n.jsonl" 2> "$OUT/step$n.stderr" &
  local pid=$! waited=0
  # 子セッションがバックグラウンドで起動した開発サーバー（npx next dev など）が残ると、結果を出した後も
  # claude -p が終了待ちになる。結果が出てから 30 秒たっても終わらなければ、作業用コピーで動く next のプロセスを止める。
  while kill -0 "$pid" 2>/dev/null; do
    sleep 5
    if [[ -n "$MAX_USD" && "$BUDGET_MODE" == watch ]] && ! grep -q '"type":"result"' "$OUT/step$n.jsonl" 2>/dev/null; then
      local est; est="$(step_estimate "$before" "$OUT/step$n.jsonl")"
      if python3 -c "import sys; sys.exit(0 if $est >= $MAX_USD else 1)"; then
        echo "step$n est=\$$est limit=\$$MAX_USD" > "$OUT/budget-stopped"
        echo "step$n stopped: estimated \$$est reached budget \$$MAX_USD" >> "$OUT/errors.log"
        pkill -TERM -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null
        break
      fi
    fi
    if grep -q '"type":"result"' "$OUT/step$n.jsonl" 2>/dev/null; then
      waited=$((waited + 5))
      if [[ "$waited" -ge 30 ]]; then reap_servers "$n"; waited=-60; fi
    fi
  done
  wait "$pid" || echo "step$n exit=$?" >> "$OUT/errors.log"
  [[ -z "$SESSION" ]] && SESSION="$(first_session_id "$OUT/step$n.jsonl")"
  return 0
}

qa_loop() {  # W3: 直前のステップの最後のメッセージに質問があれば、回答役の回答で続ける（上限 MAX_QA 回）
  [[ "$SCENARIO" == W3 ]] || return 0
  local reply
  while :; do
    if [[ "$QA" -ge "$MAX_QA" ]]; then
      # 上限に達した後も質問が続くときは、締め切りの定型文を 1 回だけ送る（qa-closed.log に記録）
      if [[ ! -s "$OUT/qa-closed.log" ]] && ! over_budget; then
        reply="$(POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w3.py" "$OUT" "$i" "$((QA+1))")"
        mv "$OUT/qa-$((QA+1)).json" "$OUT/qa-unanswered.json"
        if [[ -n "$reply" ]]; then
          i=$((i+1)); echo "step$i" > "$OUT/qa-closed.log"; run_step "$i" "$QA_CLOSE"
        fi
      fi
      return 0
    fi
    over_budget && { echo "qa skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; return 0; }
    QA=$((QA+1))
    reply="$(POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w3.py" "$OUT" "$i" "$QA")"
    [[ -z "$reply" ]] && return 0
    i=$((i+1)); run_step "$i" "$reply"
  done
}

START=$(date +%s); SESSION=""; i=0; QA=0
for step in "${STEPS[@]}"; do
  i=$((i+1))
  if over_budget; then echo "step$i skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
  run_step "$i" "$step"
  qa_loop
done

# 介入: 手順を終えてもコミットが無い、または未コミットの変更が残る（確認待ちで止まった）ときは、
# 定型の「お任せします」で続けさせ、その回数を interventions.log に記録する（PLAN.md §5.1 実行手順 3）。
: > "$OUT/interventions.log"
for _ in $(seq 1 "$MAX_NUDGES"); do
  commits="$(git -C "$APP" rev-list --count "$(cat "$OUT/baseline-commit")"..HEAD)"
  # AGENTS.md は next dev が自動で書き出すファイルなので、未コミットの変更に数えない
  # W6 以降の Playwright MCP が自動で書き出すページの記録（.playwright-mcp/）も数えない（W5 までは出ない）
  dirty="$(git -C "$APP" status --porcelain -- . ':!AGENTS.md' ':!.playwright-mcp' | head -1)"
  # W3 は要件文書（REQUIREMENTS.md）がコミットされていることも完了の条件にする
  if [[ "$SCENARIO" == W3 ]] && ! git -C "$APP" cat-file -e HEAD:REQUIREMENTS.md 2>/dev/null; then commits=0; fi
  # W6 は PR の本文（PR.md）がコミットされていることも完了の条件にする
  if [[ "$SCENARIO" == W6 ]] && ! git -C "$APP" cat-file -e HEAD:PR.md 2>/dev/null; then commits=0; fi
  [[ "$commits" -gt 0 && -z "$dirty" ]] && break
  if over_budget; then echo "nudge skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
  i=$((i+1))
  echo "step$i commits=$commits dirty=${dirty:+yes}" >> "$OUT/interventions.log"
  run_step "$i" "$NUDGE"
  qa_loop
done
echo $(( $(date +%s) - START )) > "$OUT/elapsed-seconds"

# 5) 成果物の保存（コミット済み・未コミットの両方を含む差分）
( cd "$APP" && git add -A && git commit -qm "poc: uncommitted leftovers" ) || true
git -C "$APP" diff "$(cat "$OUT/baseline-commit")" HEAD -- . ':!package-lock.json' > "$OUT/diff.patch"
git -C "$APP" log --oneline "$(cat "$OUT/baseline-commit")"..HEAD > "$OUT/commits.txt"
if [[ "$CAND" == gstack ]]; then
  # 外部送信の記録（G2 の確認用）
  HOME="$HOME_DIR" "$GSTACK/bin/gstack-egress" list > "$OUT/gstack-egress.txt" 2>&1 || true
fi
echo "done $ID ($(cat "$OUT/elapsed-seconds")s)"
