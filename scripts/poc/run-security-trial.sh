#!/usr/bin/env bash
# セキュリティ監査のツールを 1 回、ヘッドレスで実行し、費用・時間・エージェント数・指摘を記録する（PLAN §5.2）。
# 使い方: scripts/poc/run-security-trial.sh <ツール> <題材> <深さ> <回>
#   ツール: cloudflare（security-audit Skill） | claude-security（Claude Security プラグイン）
#           | security-review（Claude Code 組み込みの /security-review。題材 diff だけ。深さは default）
#   題材:   clean（poc-app のまま） | vulns（answer-key/SEC/vulns.patch を当てる） | diff（diff.patch を作業ブランチのコミットにする）
#   深さ:   cloudflare は quick | standard | deep、claude-security は low | medium | high（どちらも各ツールの言葉）
#   例: POC_MODEL=claude-opus-5-5 scripts/poc/run-security-trial.sh cloudflare vulns standard 1
# 作業用コピー（既定は /tmp/poc-trials/<ID>。POC_TRIAL_ROOT で変更可）に、poc-app のソースだけを写す
#（node_modules・.next は写さない。定期実行で clone した直後と同じく、ソースと lockfile だけを監査させるため）。
# パッチ（正解データ）は作業用コピーにだけ当て、パッチのファイル自体は置かない。題材の脆弱性は初期状態の一部になる。
# 作業用コピーに置くのは監査のツールだけ。ほかの Skills・プラグイン・MCP は入れない（監査の費用だけを測るため）。
# 子セッションには対象のコードの実行（npm など）を許可しない。この環境では Skill が求める OS の隔離を用意できないため。
# 既定のモデルは Opus 5.5。Sonnet 5.5 では、Cloudflare の探索役のエージェントが安全機構（general_harms）に
# すべて止められ、監査が終わらなかったため（2026-11-11。docs/poc/results/security/README.md）。
# 記録: docs/poc/results/security/raw/<ID>/（git には入れない）。集計は summary.json。
set -euo pipefail
# 全体を { } で包み、実行の前にすべて読み込ませる（実行中にこのファイルを書き換えても、動いている試行が壊れないように）
{
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL="$1"; TARGET="$2"; LEVEL="$3"; RUN="$4"
case "$TOOL:$LEVEL" in
  cloudflare:quick|cloudflare:standard|cloudflare:deep|claude-security:low|claude-security:medium|claude-security:high|security-review:default) ;;
  *) echo "ツールと深さの組み合わせが正しくない: $TOOL $LEVEL" >&2; exit 1 ;;
esac
case "$TARGET" in clean|vulns|diff) ;; *) echo "題材は clean・vulns・diff のいずれか: $TARGET" >&2; exit 1 ;; esac
[[ "$TOOL" == security-review && "$TARGET" != diff ]] && { echo "security-review は題材 diff だけ" >&2; exit 1; }
MODEL="${POC_MODEL:-claude-opus-5-5}"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
KEY="$ROOT/docs/poc/answer-key/SEC"
ID="SEC-$TOOL-$TARGET-$LEVEL-$RUN"
WORK="${POC_TRIAL_ROOT:-/tmp/poc-trials}/$ID"
APP="$WORK/app"; HOME_DIR="$WORK/home"; AUDIT_OUT="$WORK/out"
OUT="$ROOT/docs/poc/results/security/raw/$ID"
CHILD_ENV=(POC_SECURITY_TRIAL=1)
PLUGINS=()

rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$AUDIT_OUT" "$OUT"
echo "$WORK" > "$OUT/workdir"; echo "$MODEL" > "$OUT/model"
printf '%s\n' "$TOOL" "$TARGET" "$LEVEL" > "$OUT/condition"

fetch() {  # fetch <キャッシュ名> <リポジトリ> <コミット>
  local dir="$CACHE/$1"
  if [[ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" != "$3" ]]; then
    rm -rf "$dir"; git init -q "$dir"
    git -C "$dir" remote add origin "https://github.com/$2.git"
    git -C "$dir" fetch -q --depth 1 origin "$3"
    git -C "$dir" checkout -q FETCH_HEAD
  fi
}

# 1) 監査対象（poc-app のソース）と題材
( cd "$ROOT/poc-app" && tar --exclude=./node_modules --exclude=./.next --exclude='./*.tsbuildinfo' -cf - . ) | ( cd "$APP" && tar -xf - )
git -C "$APP" init -q
git -C "$APP" config user.name poc; git -C "$APP" config user.email poc@example.invalid
if [[ "$TARGET" == vulns ]]; then
  git -C "$APP" apply "$KEY/vulns.patch"
  sha256sum "$KEY/vulns.patch" | sed "s#$ROOT/##" > "$OUT/injected-patch"
fi
( cd "$APP" && git add -A && git commit -qm "タスク管理アプリ" )
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
if [[ "$TARGET" == diff ]]; then
  git -C "$APP" switch -q -c feature/comments
  git -C "$APP" apply "$KEY/diff.patch"
  sha256sum "$KEY/diff.patch" | sed "s#$ROOT/##" > "$OUT/injected-patch"
  ( cd "$APP" && git add -A && git commit -qm "タスクにコメントを書けるようにする" )
fi
git -C "$APP" rev-parse HEAD > "$OUT/head-commit"
# git の設定とフックは読み取り専用にする（設定やフックを仕込んで、許可した git の読み取りから任意のコマンドを起動できないように）。
# root で動く環境では効かないので、書き込みの許可に .git を含めないことが実際の守り
chmod a-w "$APP/.git/config"; chmod -R a-w "$APP/.git/hooks"

# 2) ツールと権限（全許可にはしない。対象のコードの実行と依存の取得は許可しない）
# find（-exec）や git -C（-c で設定を上書きして任意のコマンドを起動できる）は許可しない。ファイルの探索は Glob・Grep で足りる
ALLOWED=(
  "Read" "Grep" "Glob" "Task" "Agent" "Write(/$AUDIT_OUT/**)" "Edit(/$AUDIT_OUT/**)"
  "Bash(git status)" "Bash(git rev-parse HEAD)" "Bash(git log --oneline:*)" "Bash(git ls-files)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
  "Bash(cd:*)" "Bash(mkdir:*)"
)
BASE="$(cat "$OUT/baseline-commit")"
if [[ "$TOOL" == cloudflare ]]; then
  CF_REF="$(grep -o 'CF_REF="[^"]*' "$ROOT/scripts/poc-profile.sh" | cut -d'"' -f2)"
  fetch security-audit-skill cloudflare/security-audit-skill "$CF_REF"
  echo "cloudflare/security-audit-skill@$CF_REF" > "$OUT/tool-ref"
  mkdir -p "$APP/.claude/skills"
  cp -R "$CACHE/security-audit-skill/skills/security-audit" "$APP/.claude/skills/security-audit"
  SKILL="$APP/.claude/skills/security-audit"
  ALLOWED+=(
    "Bash(node $SKILL/validate-findings.cjs:*)" "Bash(node $SKILL/validate-coverage-ledger.cjs:*)"
    "Bash(node .claude/skills/security-audit/validate-findings.cjs:*)" "Bash(node .claude/skills/security-audit/validate-coverage-ledger.cjs:*)"
  )
  if [[ "$TARGET" == diff ]]; then
    SCOPE="- 範囲（scoped run）: 2 つのコミットの差分（$BASE..HEAD。ブランチ feature/comments の変更）
- 差分を調べるために git diff $BASE..HEAD と git show HEAD を使ってかまいません"
    ALLOWED+=("Bash(git diff $BASE..HEAD:*)" "Bash(git diff $BASE HEAD:*)" "Bash(git show HEAD:*)" "Bash(git show --stat HEAD)")
  else
    SCOPE="- 範囲: コードベース全体"
  fi
  TASK="このリポジトリ（作業ディレクトリ）のセキュリティ監査（full audit）を、security-audit Skill の手順どおりに行ってください。

- profile: $LEVEL
$SCOPE
- 出力先（output directory）: $AUDIT_OUT/run-1 （対象リポジトリの外。作ってから使ってください）
- 予算（budget）: 指定しません
- 前回の監査の記録はありません

この作業は無人で実行しています。確認の質問には答えられないので、上に書いていないことの判断はお任せしますが、Skill の手順にある工程は省かずに、6 つの段階を最後まで進めてください。対象のソースは変更しないでください。"
elif [[ "$TOOL" == security-review ]]; then
  # /security-review は origin/HEAD との差分をレビューする。リモートは無いので、origin/main を機能追加の前のコミットに向ける
  git -C "$APP" update-ref refs/remotes/origin/main "$BASE"
  git -C "$APP" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
  echo "claude-code-builtin:/security-review" > "$OUT/tool-ref"
  # /security-review 自身が持つ許可と同じ形。書き込みは出力先だけで、インタープリタの実行も許さないので、これで任意のコードは動かせない
  ALLOWED+=("Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)" "Bash(git status:*)" "Bash(git merge-base:*)")
  TASK="/security-review"
else
  CPO_REF="$(grep -o 'claude-plugins-official anthropics/claude-plugins-official [0-9a-f]*' "$ROOT/scripts/poc/fetch-plugins.sh" | awk '{print $3}')"
  fetch claude-plugins-official anthropics/claude-plugins-official "$CPO_REF"
  echo "anthropics/claude-plugins-official@$CPO_REF plugins/claude-security" > "$OUT/tool-ref"
  PLUG="$WORK/plugins/claude-security"; mkdir -p "$WORK/plugins"
  cp -R "$CACHE/claude-plugins-official/plugins/claude-security" "$PLUG"
  # プラグインのコピーは読み取り専用にする（書き換えたスクリプトを python3 で動かせないように）。
  # ただし root で動く環境では効かない。実際の守りは、書き込みの許可を結果の置き場に絞ることと、実行できるスクリプトを名前で決めること
  chmod -R a-w "$PLUG"
  PLUGINS=(--plugin-dir "$PLUG" --add-dir "$PLUG")
  # 結果はリポジトリの中（CLAUDE-SECURITY-<時刻>/）に書く作りなので、そこへの書き込みだけを許す。対象のソースは変えないよう依頼し、
  # 終了後に変わっていないかを source-changes に記録する。git の読み取りは、Skill の allowed-tools にあるものから、決まった形だけを許す
  ALLOWED+=(
    "Write(/$APP/CLAUDE-SECURITY-*/**)" "Edit(/$APP/CLAUDE-SECURITY-*/**)" "Workflow" "Workflow(claude-security:scan)"
    "Bash(python3 $PLUG/scripts/render_report.py:*)" "Bash(python3 $PLUG/scripts/save_result.py:*)"
    "Bash(python3 $PLUG/scripts/write_scan_meta.py:*)" "Bash(python3 $PLUG/scripts/patch_artifacts.py:*)"
    "Bash(bash $PLUG/scripts/keep-waiting.sh:*)" "Bash(date:*)" "Bash(sleep:*)"
    "Bash(git rev-list:*)" "Bash(git diff --stat:*)" "Bash(git diff --name-only:*)" "Bash(git merge-base:*)" "Bash(git branch --show-current)"
    "Bash(GIT_TERMINAL_PROMPT=0 git rev-list:*)" "Bash(GIT_TERMINAL_PROMPT=0 git rev-parse:*)" "Bash(GIT_TERMINAL_PROMPT=0 git status:*)"
  )
  if [[ "$TARGET" == diff ]]; then
    JOB="scan my branch's changes (the branch feature/comments, base $BASE) at $LEVEL"
  else
    JOB="scan the whole codebase at $LEVEL"
  fi
  TASK="/claude-security:claude-security $JOB

I accept the scan's time and token cost; do not ask me to confirm. This session is unattended, so nobody can answer questions: where the recipe would ask, take its \"I don't know\" default. Do not modify the source code under review."
  # 利用状況の送信と、push 後のスキャンの勧めを止める（README の Telemetry）
  CHILD_ENV+=(DISABLE_TELEMETRY=1 CLAUDE_SECURITY_SCAN_TIP=off)
fi
printf '%s\n' "$TASK" > "$OUT/prompt.txt"

START=$(date +%s)
( cd "$APP" && env HOME="$HOME_DIR" "${CHILD_ENV[@]}" timeout "${POC_STEP_TIMEOUT:-7200}" claude -p "$TASK" \
    --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
    --disallowedTools AskUserQuestion --strict-mcp-config --add-dir "$AUDIT_OUT" "${PLUGINS[@]}" \
    --output-format stream-json --verbose < /dev/null ) > "$OUT/step1.jsonl" 2> "$OUT/step1.stderr" \
  || echo "exit=$?" >> "$OUT/errors.log"
echo $(( $(date +%s) - START )) > "$OUT/wall-seconds"

# 3) 監査の出力を記録に写し、集計する（Claude Security はリポジトリの中の CLAUDE-SECURITY-*/）
cp -R "$AUDIT_OUT" "$OUT/audit-out"
for d in "$APP"/CLAUDE-SECURITY-*/; do [[ -d "$d" ]] && cp -R "$d" "$OUT/audit-out/"; done
git -C "$APP" status --porcelain -- . ':!CLAUDE-SECURITY-*' ':!.claude/skills/security-audit' > "$OUT/source-changes"
python3 "$ROOT/scripts/poc/security_summary.py" "$OUT" > "$OUT/summary.json"
cat "$OUT/summary.json"
exit
}
