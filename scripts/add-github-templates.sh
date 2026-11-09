#!/usr/bin/env bash
# 標準の Issue Forms・PR テンプレート・Issue/PR 記述ルールを対象リポジトリに配置する。
# 使い方: scripts/add-github-templates.sh <対象リポジトリのパス> [--with-check]
#   --with-check : PR 本文の必須見出しを検証する GitHub Actions（pr-body-check.yml）も配置する
# - 既存ファイルは上書きしない（スキップして一覧を表示する）。差分は手で確認・統合すること。
# - CLAUDE.md / AGENTS.md があれば、記述ルール（docs/github-writing.md）への参照を 1 行追記する。
# - 何度実行しても同じ結果になる。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/templates/github"

[[ $# -ge 1 ]] || { sed -n '2,7p' "$0"; exit 1; }
DEST="$(cd "$1" && pwd)"
WITH_CHECK=false
[[ "${2:-}" == "--with-check" ]] && WITH_CHECK=true
[[ -d "$DEST/.git" ]] || { echo "Git リポジトリではありません: $DEST" >&2; exit 1; }

files=(
  .github/ISSUE_TEMPLATE/feature.yml
  .github/ISSUE_TEMPLATE/bug.yml
  .github/ISSUE_TEMPLATE/tech-debt.yml
  .github/ISSUE_TEMPLATE/config.yml
  .github/pull_request_template.md
  docs/github-writing.md
)
$WITH_CHECK && files+=(.github/workflows/pr-body-check.yml)

skipped=()
for f in "${files[@]}"; do
  if [[ -e "$DEST/$f" ]]; then
    cmp -s "$SRC/$f" "$DEST/$f" || skipped+=("$f")
    continue
  fi
  mkdir -p "$(dirname "$DEST/$f")"
  cp "$SRC/$f" "$DEST/$f"
  echo "配置: $f"
done

# 大文字・別の場所の PR テンプレートや Markdown の Issue テンプレートがあると、意図しない方が使われることがある
for f in PULL_REQUEST_TEMPLATE.md pull_request_template.md docs/pull_request_template.md .github/PULL_REQUEST_TEMPLATE.md; do
  [[ -e "$DEST/$f" ]] && echo "注意: 既存の PR テンプレート $f があります。どちらを使うか決めて片方を削除してください"
done
shopt -s nullglob
md_templates=("$DEST"/.github/ISSUE_TEMPLATE/*.md)
(( ${#md_templates[@]} )) && echo "注意: 既存の Markdown 形式の Issue テンプレートがあります: ${md_templates[*]#"$DEST/"}"

# エージェント向け設定から記述ルールを参照させる（Claude Code は @ で取り込み、他ツールはリンクとして読む）
ref_line='Issue・PR を作成するときは [docs/github-writing.md](docs/github-writing.md) の記述ルールに従う。'
for agent_file in CLAUDE.md AGENTS.md; do
  target="$DEST/$agent_file"
  [[ -e "$target" ]] || continue
  if grep -qF 'docs/github-writing.md' "$target"; then
    continue
  fi
  line="- $ref_line"
  [[ "$agent_file" == CLAUDE.md ]] && line="- Issue・PR を作成するときは @docs/github-writing.md の記述ルールに従う。"
  printf '\n%s\n' "$line" >>"$target"
  echo "追記: $agent_file に記述ルールへの参照"
done
[[ -e "$DEST/CLAUDE.md" || -e "$DEST/AGENTS.md" ]] || echo "注意: CLAUDE.md / AGENTS.md がありません。作成したら docs/github-writing.md への参照を追加してください"

if (( ${#skipped[@]} )); then
  echo "スキップ（既存ファイルと内容が異なるため上書きしていません）:"
  printf '  %s\n' "${skipped[@]}"
fi

cat <<'EOS'
次の手順:
  1. tech-debt ラベルを作成する（未作成だとテンプレートのラベルが付かない）
       gh label create tech-debt --color BFD4F2 --description "技術的負債・リファクタリング" -R <owner>/<repo>
  2. 既定ブランチにマージすると Issue / PR 画面に反映される
EOS
