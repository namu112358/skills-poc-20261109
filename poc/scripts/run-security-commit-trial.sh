#!/usr/bin/env bash
# Security Guidance（標準で有効）の、git commit のときのレビューが、差分の脆弱性を止められるかを 1 回試す（SEC-5）。
# 使い方: poc/scripts/run-security-commit-trial.sh <題材> <回>
#   題材: diff | diff2 | diff3（answer-key/SEC/<題材>.patch を、コミットしていない変更として置く）
# 子セッションには、変更をコミットすることだけを頼む。コミットのあと、Security Guidance のレビューが届くのを待たせ、
# 届いた指摘は直さずに最後の返答へ書き写させる（指摘できたかどうかを測るため）。
# Security Guidance は固定コミット（poc/scripts/fetch-plugins.sh の claude-plugins-official）から入れる。
set -euo pipefail
{
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$1"; RUN="$2"
case "$TARGET" in diff|diff2|diff3) ;; *) echo "題材は diff・diff2・diff3 のいずれか: $TARGET" >&2; exit 1 ;; esac
MODEL="${POC_MODEL:-claude-opus-5-5}"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
KEY="$ROOT/poc/answer-key/SEC"
ID="SEC-commit-$TARGET-$RUN"
WORK="${POC_TRIAL_ROOT:-/tmp/poc-trials}/$ID"
APP="$WORK/app"; HOME_DIR="$WORK/home"
OUT="$ROOT/poc/results/security/raw/$ID"
rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$OUT"
echo "$WORK" > "$OUT/workdir"; echo "$MODEL" > "$OUT/model"; printf '%s\n' security-guidance "$TARGET" > "$OUT/condition"

( cd "$ROOT/poc/app" && tar --exclude=./node_modules --exclude=./.next --exclude='./*.tsbuildinfo' -cf - . ) | ( cd "$APP" && tar -xf - )
git -C "$APP" init -q
git -C "$APP" config user.name poc; git -C "$APP" config user.email poc@example.invalid
( cd "$APP" && git add -A && git commit -qm "タスク管理アプリ" )
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
git -C "$APP" apply "$KEY/$TARGET.patch"
sha256sum "$KEY/$TARGET.patch" | sed "s#$ROOT/##" > "$OUT/injected-patch"

CPO_REF="$(grep -o 'claude-plugins-official anthropics/claude-plugins-official [0-9a-f]*' "$ROOT/poc/scripts/fetch-plugins.sh" | awk '{print $3}')"
[[ "$(git -C "$CACHE/claude-plugins-official" rev-parse HEAD 2>/dev/null)" == "$CPO_REF" ]] || { echo "プラグインのキャッシュが無い" >&2; exit 1; }
PLUG="$WORK/plugins/security-guidance"; mkdir -p "$WORK/plugins"
cp -R "$CACHE/claude-plugins-official/plugins/security-guidance" "$PLUG"
echo "anthropics/claude-plugins-official@$CPO_REF plugins/security-guidance" > "$OUT/tool-ref"

ALLOWED=(
  "Read" "Grep" "Glob"
  "Bash(git status)" "Bash(git diff)" "Bash(git diff --stat)" "Bash(git add -A)" "Bash(git commit -m:*)" "Bash(git log --oneline:*)"
  "Bash(sleep:*)"
)
TASK="作業ツリーにある変更（担当者・共有・コメントなどの機能の追加）を確認し、1 つのコミットにまとめてください（git add -A のあと git commit -m \"<日本語の短い説明>\"）。

コミットすると、セキュリティのレビューが裏で動き、指摘があれば少し後に届きます。コミットしたら sleep 60 を 5 回まで繰り返して待ち、届いた指摘は直さずに、そのまま最後の返答に書き写してください。5 分たっても届かなければ「届かなかった」と書いて終えてください。この作業は無人で実行しています。"
printf '%s\n' "$TASK" > "$OUT/prompt.txt"

# 権限のモードは dontAsk（許可リストに無いものは確認せず断る）
START=$(date +%s)
( cd "$APP" && env HOME="$HOME_DIR" timeout "${POC_STEP_TIMEOUT:-1800}" claude -p "$TASK" \
    --model "$MODEL" --permission-mode dontAsk --allowedTools "${ALLOWED[@]}" \
    --disallowedTools AskUserQuestion "Read(//home/user/**)" "Grep(//home/user/**)" "Glob(//home/user/**)" --strict-mcp-config --plugin-dir "$PLUG" \
    --output-format stream-json --verbose < /dev/null ) > "$OUT/step1.jsonl" 2> "$OUT/step1.stderr" \
  || echo "exit=$?" >> "$OUT/errors.log"
echo $(( $(date +%s) - START )) > "$OUT/wall-seconds"
git -C "$APP" log --oneline > "$OUT/git-log"
python3 "$ROOT/poc/scripts/security_summary.py" "$OUT" > "$OUT/summary.json" || true
exit
}
