#!/usr/bin/env bash
# 開発ワークフローの試行を 1 回実行する。
# 使い方: scripts/poc/run-trial.sh <シナリオ> <候補> <回>
#   候補: baseline | superpowers | feature-dev | compound-engineering | gstack
#   （gstack の setup 実行は 2026-11-09 にユーザーの許可を得た。専用 HOME の中だけで実行する）
# 作業用コピー（.poc-work/trials/...）で、専用の HOME を使って Claude Code をヘッドレスで起動する。
# 子セッションの権限は docs/poc/tasks/wf-procedures.md の「権限」のとおり（全許可にはしない）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCENARIO="$1"; CAND="$2"; RUN="$3"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
MODEL="${POC_MODEL:-claude-sonnet-5-5}"
ID="$SCENARIO-$CAND-$RUN"
WORK="$ROOT/.poc-work/trials/$ID"
APP="$WORK/app"
HOME_DIR="$WORK/home"
OUT="$ROOT/docs/poc/results/workflow/raw/$ID"

rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$OUT"

# 1) 評価用アプリのコピー（node_modules を含む）と、常時有効な Skills・MCP
cp -a "$ROOT/poc-app/." "$APP/"
rm -rf "$APP/.next" "$APP"/*.tsbuildinfo
mkdir -p "$APP/.claude"
cp -a "$ROOT/.claude/skills" "$APP/.claude/skills"
rm -f "$APP/.claude/skills/SOURCES.md"
cat > "$APP/.mcp.json" <<'JSON'
{"mcpServers":{
  "playwright":{"type":"stdio","command":"npx","args":["-y","@playwright/mcp@0.0.84"]},
  "next-devtools":{"type":"stdio","command":"npx","args":["-y","next-devtools-mcp@0.4.0"]}}}
JSON
( cd "$APP" && git init -q && git add -A && git -c user.name=poc -c user.email=poc@example.invalid commit -qm baseline )
git -C "$APP" config user.name poc
git -C "$APP" config user.email poc@example.invalid
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"

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

# 4) 手順（docs/poc/tasks/wf-procedures.md）
TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。"
case "$CAND" in
  baseline|superpowers) STEPS=("$TASK") ;;
  feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
  compound-engineering) STEPS=("/ce-plan $TASK" "/ce-work" "/ce-code-review") ;;
  gstack) STEPS=("$TASK" "/review") ;;
esac

START=$(date +%s); SESSION=""; i=0
for step in "${STEPS[@]}"; do
  i=$((i+1))
  RESUME=(); [[ -n "$SESSION" ]] && RESUME=(--resume "$SESSION")
  ( cd "$APP" && HOME="$HOME_DIR" timeout "${POC_STEP_TIMEOUT:-2400}" claude -p "$step" \
      --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
      --mcp-config "$APP/.mcp.json" --strict-mcp-config --add-dir "$PLUG" "${PLUG_EXTRA[@]}" \
      "${PLUGINS[@]}" "${RESUME[@]}" \
      --output-format stream-json --verbose < /dev/null ) > "$OUT/step$i.jsonl" 2> "$OUT/step$i.stderr" \
    || echo "step$i exit=$?" >> "$OUT/errors.log"
  SESSION="$(python3 - "$OUT/step$i.jsonl" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("session_id"):
        print(d["session_id"]); break
PY
)"
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
