#!/usr/bin/env bash
# セキュリティ監査のツールを 1 回、ヘッドレスで実行し、費用・時間・エージェント数・指摘を記録する（PLAN §5.2）。
# 使い方: scripts/poc/run-security-trial.sh <ツール> <題材> <深さ> <回>
#   ツール: cloudflare（security-audit Skill） | claude-security（Claude Security プラグイン）
#           | security-review（Claude Code 組み込みの /security-review。題材 diff だけ。深さは default）
#   題材:   clean（poc-app のまま） | vulns（answer-key/SEC/vulns.patch を当てる） | diff（diff.patch を作業ブランチのコミットにする）
#           | diff2（diff2.patch。見つけにくい脆弱性の差分。SEC-2 で追加）
#           | diff3（diff3.patch。既存のコードと合わせて初めて脆弱性になる差分。SEC-3 で追加）
#           | infra（infra.patch。CI・コンテナ・LLM の機能に脆弱性を仕込んだ版。SEC-6 で追加。全体の監査用）
#   深さ:   cloudflare は quick | standard | deep、claude-security は low | medium | high（どちらも各ツールの言葉）
#   例: POC_MODEL=claude-opus-5-5 scripts/poc/run-security-trial.sh cloudflare vulns standard 1
# 作業用コピー（既定は /tmp/poc-trials/<ID>。POC_TRIAL_ROOT で変更可）に、poc-app のソースだけを写す
#（node_modules・.next は写さない。定期実行で clone した直後と同じく、ソースと lockfile だけを監査させるため）。
# パッチ（正解データ）は作業用コピーにだけ当て、パッチのファイル自体は置かない。題材の脆弱性は初期状態の一部になる。
# 作業用コピーに置くのは監査のツールだけ。ほかの Skills・プラグイン・MCP は入れない（監査の費用だけを測るため）。
# 子セッションには対象のコードの実行（npm など）を許可しない。この環境では Skill が求める OS の隔離を用意できないため。
# 既定のモデルは Opus 5.5。Sonnet 5.5 では、Cloudflare の探索役のエージェントが安全機構（general_harms）に
# すべて止められ、監査が終わらなかったため（2026-11-11。docs/poc/results/security/README.md）。
# POC_SBX=1: 対象のコードを隔離して動かすコマンド（scripts/poc/sbx.sh）を sbx として渡す（SEC-6。Cloudflare の確認のため）。
#   試行 ID の末尾に -sbx が付く。
# POC_PRIOR=<試行 ID>: Cloudflare に、その試行の監査の記録（run-1）を前回の記録として渡し、今回は run-2 に出力させる（SEC-6）。
#   同じ題材の試行を指定する。試行 ID の末尾に -prior が付く。
# 子セッションからは /home/user の下（このリポジトリと採点用の正解）を Read・Grep・Glob で読めないようにする。
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
case "$TARGET" in clean|vulns|diff|diff2|diff3|infra) ;; *) echo "題材は clean・vulns・diff・diff2・diff3・infra のいずれか: $TARGET" >&2; exit 1 ;; esac
[[ "$TOOL" == security-review && "$TARGET" != diff* ]] && { echo "security-review は題材 diff だけ" >&2; exit 1; }
MODEL="${POC_MODEL:-claude-opus-5-5}"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
KEY="$ROOT/docs/poc/answer-key/SEC"
ID="SEC-$TOOL-$TARGET-$LEVEL-$RUN${POC_SBX:+-sbx}${POC_PRIOR:+-prior}"
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
if [[ "$TARGET" == vulns || "$TARGET" == infra ]]; then
  git -C "$APP" apply "$KEY/$TARGET.patch"
  sha256sum "$KEY/$TARGET.patch" | sed "s#$ROOT/##" > "$OUT/injected-patch"
fi
( cd "$APP" && git add -A && git commit -qm "タスク管理アプリ" )
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
if [[ "$TARGET" == diff* ]]; then
  case "$TARGET" in
    diff) BRANCH=feature/comments; MSG="タスクにコメントを書けるようにする" ;;
    diff2) BRANCH=feature/share-links; MSG="タスクを共有リンクで社外の人に見せられるようにする" ;;
    diff3) BRANCH=feature/assignee-ux; MSG="担当者の検索・付け替えと、ログインまわりの使い勝手を良くする" ;;
  esac
  git -C "$APP" switch -q -c "$BRANCH"
  git -C "$APP" apply "$KEY/$TARGET.patch"
  sha256sum "$KEY/$TARGET.patch" | sed "s#$ROOT/##" > "$OUT/injected-patch"
  ( cd "$APP" && git add -A && git commit -qm "$MSG" )
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
  "Bash(cd:*)" "Bash(mkdir:*)" "Bash(echo:*)"
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
  RUN_DIR=run-1; PRIOR_LINE="- 前回の監査の記録はありません"
  if [[ -n "${POC_PRIOR:-}" ]]; then
    PRIOR_OUT="$ROOT/docs/poc/results/security/raw/$POC_PRIOR/audit-out/run-1"
    [[ -f "$PRIOR_OUT/findings.json" ]] || { echo "前回の記録が無い: $PRIOR_OUT" >&2; exit 1; }
    cp -R "$PRIOR_OUT" "$AUDIT_OUT/run-1"
    rm -rf "$AUDIT_OUT/run-1/agents"
    echo "$POC_PRIOR" > "$OUT/prior"
    RUN_DIR=run-2; PRIOR_LINE="- 前回の監査の記録: $AUDIT_OUT/run-1（同じソースに対する 1 回前の監査。Skill の手順どおりに読み込んでください）"
  fi
  if [[ "$TARGET" == diff* ]]; then
    SCOPE="- 範囲（scoped run）: 2 つのコミットの差分（$BASE..HEAD。ブランチ $BRANCH の変更）
- 差分を調べるために git diff $BASE..HEAD と git show HEAD を使ってかまいません"
    ALLOWED+=("Bash(git diff $BASE..HEAD:*)" "Bash(git diff $BASE HEAD:*)" "Bash(git show HEAD:*)" "Bash(git show --stat HEAD)")
  else
    SCOPE="- 範囲: コードベース全体"
  fi
  TASK="このリポジトリ（作業ディレクトリ）のセキュリティ監査（full audit）を、security-audit Skill の手順どおりに行ってください。

- profile: $LEVEL
$SCOPE
- 出力先（output directory）: $AUDIT_OUT/$RUN_DIR （対象リポジトリの外。作ってから使ってください）
- 予算（budget）: 指定しません
$PRIOR_LINE

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
  if [[ "$TARGET" == diff* ]]; then
    JOB="scan my branch's changes (the branch $BRANCH, base $BASE) at $LEVEL"
  else
    JOB="scan the whole codebase at $LEVEL"
  fi
  TASK="/claude-security:claude-security $JOB

I accept the scan's time and token cost; do not ask me to confirm. This session is unattended, so nobody can answer questions: where the recipe would ask, take its \"I don't know\" default. Do not modify the source code under review."
  # 利用状況の送信と、push 後のスキャンの勧めを止める（README の Telemetry）
  CHILD_ENV+=(DISABLE_TELEMETRY=1 CLAUDE_SECURITY_SCAN_TIP=off)
fi
# 権限の制約を伝える（SEC-6 から）。dontAsk では、つないだコマンドの一部でも許可リストに無いと全体が断られ、
# SEC-6 の 1 回目は検証用のスクリプトの実行まで断られて、監査が未完了で終わったため
TASK="$TASK

権限の都合で、Bash は 1 回に 1 つのコマンドだけを実行してください（; && || | やループでつながない。ファイルの探索と読み取りは Glob・Grep・Read を使う）。"
if [[ "${POC_SBX:-}" == 1 ]]; then
  # 隔離して動かすコマンド。root の持ち物として作業用コピーの外に置き、子セッションの PATH に入れる
  mkdir -p "$WORK/bin" "$AUDIT_OUT/${RUN_DIR:-run-1}/agents"
  install -m 0755 "$ROOT/scripts/poc/sbx.sh" "$WORK/bin/sbx"
  chmod -R a+rX "$APP"
  CHILD_ENV+=(SBX_ROOT="$AUDIT_OUT/${RUN_DIR:-run-1}/agents" SBX_TARGET="$APP" PATH="$WORK/bin:$PATH")
  ALLOWED+=("Bash(sbx:*)" "Bash($WORK/bin/sbx:*)")
  echo 1 > "$OUT/sbx"
  TASK="$TASK

この環境には、対象のコードを隔離して動かすコマンド sbx があります（使い方: sbx <作業用ディレクトリ> <コマンド> [引数...]）。
- 作業用ディレクトリは $AUDIT_OUT/${RUN_DIR:-run-1}/agents/<エージェント ID>/scratch のように、$AUDIT_OUT/${RUN_DIR:-run-1}/agents の下の新しいパスを指定します。書き込めるのはそこだけです。
- 中では、ネットワーク（ループバック以外）が切れ、権限のない利用者で動き、対象のリポジトリは読み取り専用になり、環境変数は PATH・HOME・TMPDIR だけになります。
- CPU 60 秒・仮想メモリ 16 GiB・プロセス 64・ファイル 64 MiB・実時間 120 秒の上限があります。
- 依存パッケージは入っていません（node_modules はありません）。Node.js の標準の機能（node:test、node:sqlite など）は使えます。"
fi
printf '%s\n' "$TASK" > "$OUT/prompt.txt"

# 権限のモードは dontAsk（許可リストに無いものは確認せず断る）。acceptEdits は作業ディレクトリの中の編集をすべて許すので、
# Write・Edit の許可を絞っても効かず、package.json などを書き換えてから許可したコマンドで動かせてしまうため（2026-11-11 に変更）
START=$(date +%s)
( cd "$APP" && env HOME="$HOME_DIR" "${CHILD_ENV[@]}" timeout "${POC_STEP_TIMEOUT:-7200}" claude -p "$TASK" \
    --model "$MODEL" --permission-mode dontAsk --allowedTools "${ALLOWED[@]}" \
    --disallowedTools AskUserQuestion "Read(//home/user/**)" "Grep(//home/user/**)" "Glob(//home/user/**)" --strict-mcp-config --add-dir "$AUDIT_OUT" "${PLUGINS[@]}" \
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
