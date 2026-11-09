#!/usr/bin/env bash
# GitHub リポジトリに標準設定を反映する（docs/github-setup/README.md の §3 に対応）。
#
# 使い方:
#   scripts/github-setup/apply-repo-settings.sh <owner>/<repo> --profile <solo|solo-minimal|team> \
#     [--secret-protection] [--code-security] [--apply]
#
#   --profile solo          個人開発（AI 専用 ID あり。承認 1 件を必須にする）
#   --profile solo-minimal  個人開発（AI が本人の最小権限トークンで動く。承認 0、Auto merge 無効）
#   --profile team          チーム開発（承認 1 件＋Code Owner レビュー、最新状態でのテスト）
#   --secret-protection     Private で Secret Protection を購入済みの場合に Secret Scanning を有効化
#   --code-security         Private で Code Security を購入済みの場合に CodeQL Default Setup を有効化
#   --apply                 実際に反映する（省略時は実行内容を表示するだけ）
#
# 実行には、対象リポジトリの Admin 権限を持つ人間の gh 認証が必要。
# セキュリティ上重要な設定変更のため、--apply の前に管理者の承認を得ること。
set -euo pipefail

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

REPO=""; PROFILE=""; APPLY=0; SECRET_PROTECTION=0; CODE_SECURITY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --secret-protection) SECRET_PROTECTION=1; shift ;;
    --code-security) CODE_SECURITY=1; shift ;;
    -h|--help) usage ;;
    */*) REPO="$1"; shift ;;
    *) echo "不明な引数: $1" >&2; usage ;;
  esac
done
[[ -n "$REPO" && -n "$PROFILE" ]] || usage
case "$PROFILE" in solo|solo-minimal|team) ;; *) echo "--profile は solo / solo-minimal / team のいずれか" >&2; exit 1 ;; esac

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RULESET_DIR="$ROOT/docs/github-setup/templates/rulesets"
command -v gh >/dev/null || { echo "gh が見つかりません" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq が見つかりません" >&2; exit 1; }

# 読み取りのみ（ドライランでも実行する）
VISIBILITY="$(gh api "repos/$REPO" --jq .visibility 2>/dev/null || echo unknown)"
echo "対象: $REPO（visibility: $VISIBILITY、profile: $PROFILE、$([[ $APPLY == 1 ]] && echo 反映 || echo ドライラン)）"
[[ "$VISIBILITY" == "unknown" ]] && echo "警告: リポジトリ情報を取得できません。Private として扱います。" >&2

# 実行または表示する。第 1 引数は説明、以降は gh api の引数。stdin に JSON を渡す場合は "-" を最後の --input に指定する。
run() {
  local desc="$1"; shift
  if [[ $APPLY == 1 ]]; then
    echo "==> $desc"
    if ! gh api "$@" >/dev/null; then
      echo "    失敗: $desc（Web UI で設定するか、プランとライセンスを確認してください）" >&2
      FAILED=$((FAILED + 1))
    fi
  else
    echo "[dry-run] $desc"
    echo "          gh api $*"
  fi
}
FAILED=0

# --- A. General -------------------------------------------------------------
AUTO_MERGE=true; [[ "$PROFILE" == "solo-minimal" ]] && AUTO_MERGE=false
run "General: マージ方式（Squash のみ）・ブランチ自動削除・Auto merge=$AUTO_MERGE・Wiki/Projects 無効" \
  -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true -F allow_update_branch=true -F allow_auto_merge=$AUTO_MERGE \
  -F has_wiki=false -F has_projects=false -F has_issues=true

# --- C. Advanced Security ---------------------------------------------------
run "Dependency graph / Dependabot alerts を有効化" -X PUT "repos/$REPO/vulnerability-alerts"
run "Dependabot security updates を有効化" -X PUT "repos/$REPO/automated-security-fixes"

if [[ "$VISIBILITY" == "public" || $SECRET_PROTECTION == 1 ]]; then
  run "Secret scanning / Push protection を有効化" -X PATCH "repos/$REPO" --input - <<'JSON'
{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}
JSON
else
  echo "[skip] Secret scanning: Private で Secret Protection がないため（CI の Gitleaks で代替）"
fi

if [[ "$VISIBILITY" == "public" || $CODE_SECURITY == 1 ]]; then
  run "CodeQL Default setup を有効化" -X PATCH "repos/$REPO/code-scanning/default-setup" -f state=configured
else
  echo "[skip] CodeQL: Private で Code Security がないため"
fi

if [[ "$VISIBILITY" == "public" ]]; then
  run "Private vulnerability reporting を有効化" -X PUT "repos/$REPO/private-vulnerability-reporting"
fi

# --- D. Actions -------------------------------------------------------------
run "Actions: 許可する Action を限定し、SHA 固定を必須化" -X PUT "repos/$REPO/actions/permissions" --input - <<'JSON'
{"enabled":true,"allowed_actions":"selected","sha_pinning_required":true}
JSON
run "Actions: GitHub 製の Action のみ許可（必要な Action は patterns_allowed に追加）" \
  -X PUT "repos/$REPO/actions/permissions/selected-actions" --input - <<'JSON'
{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":[]}
JSON
run "Actions: GITHUB_TOKEN を読み取りのみ、PR の作成・承認を禁止" \
  -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false

# --- B. Rulesets ------------------------------------------------------------
apply_ruleset() {
  local file="$1" name id
  name="$(jq -r .name "$file")"
  id="$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2>/dev/null || true)"
  if [[ -n "$id" ]]; then
    run "Ruleset を更新: $name（$(basename "$file")）" -X PUT "repos/$REPO/rulesets/$id" --input "$file"
  else
    run "Ruleset を作成: $name（$(basename "$file")）" -X POST "repos/$REPO/rulesets" --input "$file"
  fi
}
apply_ruleset "$RULESET_DIR/main-$PROFILE.json"
apply_ruleset "$RULESET_DIR/tags-release.json"

echo
if [[ $APPLY == 1 ]]; then
  echo "完了（失敗: $FAILED 件）。"
else
  echo "ドライランです。内容を確認し、承認を得てから --apply を付けて実行してください。"
fi
cat <<'NOTE'
Web UI で確認すること:
  - Ruleset の Required status checks: CI を一度実行し、ジョブ名と発行元（GitHub Actions）を確認する
  - Settings → Collaborators: AI 専用 ID が Write であること（Admin / Maintain にしない）
  - Settings → Advanced Security: Alerts へのアクセス権限
  - Settings → Environments: staging / production（docs/github-setup/README.md §3.E）
NOTE
[[ $FAILED == 0 ]]
