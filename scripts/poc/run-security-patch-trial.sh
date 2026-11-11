#!/usr/bin/env bash
# Claude Security の修正提案（Suggest patches）を 1 回、ヘッドレスで実行する（PLAN §5.2 の 4。SEC-4）。
# 使い方: scripts/poc/run-security-patch-trial.sh <もとの試行 ID> <指摘の ID（例: F1,F2,F9）> <回>
#   もとの試行: run-security-trial.sh claude-security … で、作業用コピーに CLAUDE-SECURITY-*/ の報告が残っているもの
# もとの作業用コピー（app と、その報告）を写してから実行する。もとの記録は変えない。
# 子セッションには、run-security-trial.sh の Claude Security と同じ許可に加えて、プロジェクトのテストと型チェックの実行を許す。
# 修正の検証役がテストを動かす手順のため。題材は自分で作った poc-app なので、対象のコードを動かしてよいと判断した
#（CLAUDE.md の例外: 子セッションの許可リストの変更。docs/poc/results/security/README.md の SEC-4 に記録）。
set -euo pipefail
{
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_ID="$1"; IDS="$2"; RUN="$3"
[[ "$IDS" =~ ^F[0-9]{1,9}(,F[0-9]{1,9})*$ ]] || { echo "指摘の ID は F1,F2 の形: $IDS" >&2; exit 1; }
SRC_WORK="$(cat "$ROOT/docs/poc/results/security/raw/$SRC_ID/workdir")"
MODEL="${POC_MODEL:-claude-opus-5-5}"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
ID="SEC-patch-$SRC_ID-$RUN"
WORK="${POC_TRIAL_ROOT:-/tmp/poc-trials}/$ID"
APP="$WORK/app"; HOME_DIR="$WORK/home"
OUT="$ROOT/docs/poc/results/security/raw/$ID"
rm -rf "$WORK" "$OUT"; mkdir -p "$WORK" "$HOME_DIR" "$OUT"
cp -a "$SRC_WORK/app" "$APP"
echo "$WORK" > "$OUT/workdir"; echo "$MODEL" > "$OUT/model"; echo "$SRC_ID $IDS" > "$OUT/condition"
REPORT="$(cd "$APP" && ls -d CLAUDE-SECURITY-*/ | tail -1)"; REPORT="${REPORT%/}"
echo "$REPORT" > "$OUT/report"
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"

CPO_REF="$(grep -o 'claude-plugins-official anthropics/claude-plugins-official [0-9a-f]*' "$ROOT/scripts/poc/fetch-plugins.sh" | awk '{print $3}')"
[[ "$(git -C "$CACHE/claude-plugins-official" rev-parse HEAD 2>/dev/null)" == "$CPO_REF" ]] || { echo "プラグインのキャッシュが無い（run-security-trial.sh claude-security を先に回す）" >&2; exit 1; }
PLUG="$WORK/plugins/claude-security"; mkdir -p "$WORK/plugins"
cp -R "$CACHE/claude-plugins-official/plugins/claude-security" "$PLUG"
echo "anthropics/claude-plugins-official@$CPO_REF plugins/claude-security" > "$OUT/tool-ref"

ALLOWED=(
  "Read" "Grep" "Glob" "Task" "Agent" "Workflow"
  "Write(/$APP/CLAUDE-SECURITY-*/**)" "Edit(/$APP/CLAUDE-SECURITY-*/**)"
  "Bash(git status)" "Bash(git rev-parse HEAD)" "Bash(git log --oneline:*)" "Bash(git ls-files)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)" "Bash(cd:*)" "Bash(mkdir:*)"
  "Bash(python3 $PLUG/scripts/render_report.py:*)" "Bash(python3 $PLUG/scripts/save_result.py:*)"
  "Bash(python3 $PLUG/scripts/write_scan_meta.py:*)" "Bash(python3 $PLUG/scripts/patch_artifacts.py:*)"
  "Bash(bash $PLUG/scripts/keep-waiting.sh:*)" "Bash(date:*)" "Bash(sleep:*)"
  # プロジェクトのテストと型チェック（修正の検証役が動かす）。引数は付けられない形だけを許す。
  # 修正提案は、結果の置き場の中の作業用コピーでコードを書き換え、そこでテストを動かす作りなので、そのコピーの中の
  # コード（package.json を含む）は子セッションが書き換えられる。自分で作った題材にだけ使う（他人のリポジトリには使わない）
  "Bash(npm test)" "Bash(npm run typecheck)"
)
TASK="/claude-security:claude-security suggest patches for $IDS from the newest report ($REPORT)

This session is unattended, so nobody can answer questions: where the recipe would ask, take its \"I don't know\" default. Do not apply the patches to the checkout."
printf '%s\n' "$TASK" > "$OUT/prompt.txt"

# 権限のモードは dontAsk（許可リストに無いものは確認せず断る）。acceptEdits は作業ディレクトリの中の編集をすべて許すので、
# Write・Edit の許可を絞っても効かず、package.json などを書き換えてから許可したコマンドで動かせてしまうため（2026-11-11 に変更）
START=$(date +%s)
( cd "$APP" && env HOME="$HOME_DIR" DISABLE_TELEMETRY=1 CLAUDE_SECURITY_SCAN_TIP=off timeout "${POC_STEP_TIMEOUT:-5400}" claude -p "$TASK" \
    --model "$MODEL" --permission-mode dontAsk --allowedTools "${ALLOWED[@]}" \
    --disallowedTools AskUserQuestion --strict-mcp-config --plugin-dir "$PLUG" --add-dir "$PLUG" \
    --output-format stream-json --verbose < /dev/null ) > "$OUT/step1.jsonl" 2> "$OUT/step1.stderr" \
  || echo "exit=$?" >> "$OUT/errors.log"
echo $(( $(date +%s) - START )) > "$OUT/wall-seconds"

mkdir -p "$OUT/patches"
find "$APP/$REPORT" -path '*/patches/*' -type f \( -name '*.patch' -o -name '*.md' \) -exec cp {} "$OUT/patches/" \; 2>/dev/null || true
git -C "$APP" status --porcelain -- . ':!CLAUDE-SECURITY-*' > "$OUT/source-changes"
python3 "$ROOT/scripts/poc/security_summary.py" "$OUT" > "$OUT/summary.json" || true
ls "$OUT/patches"
exit
}
