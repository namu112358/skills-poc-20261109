#!/usr/bin/env bash
# 開発ワークフローの試行を 1 回実行する。
# 使い方: scripts/poc/run-trial.sh <シナリオ> <候補> <回>
#   候補: baseline | superpowers | feature-dev | compound-engineering
#   （gstack は外部の setup スクリプトを実行する必要があるため、別途承認を得てから追加する）
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
  *) echo "unknown candidate: $CAND" >&2; exit 1 ;;
esac

# 3) 権限（全許可にはしない）
ALLOWED=(
  "Bash(npm run typecheck)" "Bash(npm test)" "Bash(npm run test)" "Bash(npm run build)"
  "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git branch:*)" "Bash(git rev-parse:*)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(find:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
)

# 4) 手順（docs/poc/tasks/wf-procedures.md）
TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。"
case "$CAND" in
  baseline|superpowers) STEPS=("$TASK") ;;
  feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
  compound-engineering) STEPS=("/ce-plan $TASK" "/ce-work" "/ce-code-review") ;;
esac

START=$(date +%s); SESSION=""; i=0
for step in "${STEPS[@]}"; do
  i=$((i+1))
  RESUME=(); [[ -n "$SESSION" ]] && RESUME=(--resume "$SESSION")
  ( cd "$APP" && HOME="$HOME_DIR" timeout "${POC_STEP_TIMEOUT:-2400}" claude -p "$step" \
      --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
      --mcp-config "$APP/.mcp.json" --strict-mcp-config --add-dir "$PLUG" \
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
echo "done $ID ($(cat "$OUT/elapsed-seconds")s)"
