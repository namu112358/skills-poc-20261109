#!/usr/bin/env bash
# Cloudflare Security Audit（security-audit Skill）の全体監査を 1 回、ヘッドレスで実行し、費用・時間・エージェント数を記録する。
# 使い方: scripts/poc/run-security-trial.sh <profile> <回>
#   profile: quick | standard | deep（Skill の深さ）
# 目的: 定期実行の頻度と費用の上限を決めるための測定（docs/tool-candidates/security-audit-schedule.md の「進め方」の 1）。
# 作業用コピー（既定は /tmp/poc-trials/SEC-<profile>-<回>。POC_TRIAL_ROOT で変更可）に、poc-app のソースだけを写す
#（node_modules・.next は写さない。定期実行で clone した直後と同じく、ソースと lockfile だけを監査させるため）。
# 作業用コピーに置く Skill は security-audit だけ。ほかの Skills・プラグイン・MCP は入れない（監査の費用だけを測るため）。
# 監査の出力先は、Skill の決まり（対象の外）どおり $WORK/out に置く。
# 子セッションには対象のコードの実行（npm など）を許可しない。この環境では Skill が求める OS の隔離を用意できないため。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROFILE="$1"; RUN="$2"
case "$PROFILE" in quick|standard|deep) ;; *) echo "profile は quick・standard・deep のいずれか: $PROFILE" >&2; exit 1 ;; esac
MODEL="${POC_MODEL:-claude-sonnet-5-5}"
CF_REF="$(grep -o 'CF_REF="[^"]*' "$ROOT/scripts/poc-profile.sh" | cut -d'"' -f2)"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}/security-audit-skill"
ID="SEC-$PROFILE-$RUN"
WORK="${POC_TRIAL_ROOT:-/tmp/poc-trials}/$ID"
APP="$WORK/app"; HOME_DIR="$WORK/home"; AUDIT_OUT="$WORK/out"
OUT="$ROOT/docs/poc/results/security/raw/$ID"

rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$AUDIT_OUT" "$OUT"
echo "$WORK" > "$OUT/workdir"; echo "$MODEL" > "$OUT/model"; echo "$CF_REF" > "$OUT/skill-ref"

# 1) Skill の固定コミットを取得（キャッシュがあれば使う）
if [[ "$(git -C "$CACHE" rev-parse HEAD 2>/dev/null)" != "$CF_REF" ]]; then
  rm -rf "$CACHE"; git init -q "$CACHE"
  git -C "$CACHE" remote add origin https://github.com/cloudflare/security-audit-skill.git
  git -C "$CACHE" fetch -q --depth 1 origin "$CF_REF"
  git -C "$CACHE" checkout -q FETCH_HEAD
fi

# 2) 監査対象（poc-app のソース）と Skill
( cd "$ROOT/poc-app" && tar --exclude=./node_modules --exclude=./.next --exclude='./*.tsbuildinfo' -cf - . ) | ( cd "$APP" && tar -xf - )
mkdir -p "$APP/.claude/skills"
cp -R "$CACHE/skills/security-audit" "$APP/.claude/skills/security-audit"
SKILL="$APP/.claude/skills/security-audit"
( cd "$APP" && git init -q && git add -A && git -c user.name=poc -c user.email=poc@example.invalid commit -qm baseline )
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"

# 3) 権限（全許可にはしない。対象のコードの実行と依存の取得は許可しない）
ALLOWED=(
  "Read" "Grep" "Glob" "Task" "Agent" "Write(/$AUDIT_OUT/**)" "Edit(/$AUDIT_OUT/**)"
  "Bash(node $SKILL/validate-findings.cjs:*)" "Bash(node $SKILL/validate-coverage-ledger.cjs:*)"
  "Bash(node .claude/skills/security-audit/validate-findings.cjs:*)" "Bash(node .claude/skills/security-audit/validate-coverage-ledger.cjs:*)"
  "Bash(git status:*)" "Bash(git log:*)" "Bash(git rev-parse:*)" "Bash(git diff:*)" "Bash(git show:*)"
  "Bash(git ls-files:*)" "Bash(git remote:*)" "Bash(git -C:*)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(find:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
  "Bash(cd:*)" "Bash(mkdir:*)" "Bash(mkdir -p $AUDIT_OUT/:*)"
)

TASK="このリポジトリ（作業ディレクトリ）のコードベース全体のセキュリティ監査（full audit）を、security-audit Skill の手順どおりに行ってください。

- profile: $PROFILE
- 出力先（output directory）: $AUDIT_OUT/run-1 （対象リポジトリの外。作ってから使ってください）
- 予算（budget）: 指定しません
- 前回の監査の記録はありません

この作業は無人で実行しています。確認の質問には答えられないので、上に書いていないことの判断はお任せしますが、Skill の手順にある工程は省かずに、6 つの段階を最後まで進めてください。対象のソースは変更しないでください。"
printf '%s\n' "$TASK" > "$OUT/prompt.txt"

START=$(date +%s)
( cd "$APP" && env HOME="$HOME_DIR" timeout "${POC_STEP_TIMEOUT:-7200}" claude -p "$TASK" \
    --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
    --disallowedTools AskUserQuestion --strict-mcp-config --add-dir "$AUDIT_OUT" \
    --output-format stream-json --verbose < /dev/null ) > "$OUT/step1.jsonl" 2> "$OUT/step1.stderr" \
  || echo "exit=$?" >> "$OUT/errors.log"
echo $(( $(date +%s) - START )) > "$OUT/wall-seconds"

# 4) 監査の出力を記録に写し、集計する
cp -R "$AUDIT_OUT" "$OUT/audit-out"
python3 "$ROOT/scripts/poc/security_summary.py" "$OUT" > "$OUT/summary.json"
cat "$OUT/summary.json"
