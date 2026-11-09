#!/usr/bin/env bash
# 必須 Skills を公式リポジトリの指定コミットから .claude/skills/ に同期する。
# 使い方: scripts/sync-skills.sh [ANTHROPIC_SKILLS_REF] [VERCEL_AGENT_SKILLS_REF] [GH_STACK_REF] [GH_CLI_REF]
# 引数を省略した場合は .claude/skills/SOURCES.md に記載の固定コミットを使う。
set -euo pipefail

ANTHROPIC_REF="${1:-2c5958ecac7cee2b583967a2c4981d0f4a75c579}"
VERCEL_REF="${2:-1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62}"
GH_STACK_REF="${3:-bd0a32504f9ae9f795875a9e6bb90ff7408fda08}"
GH_CLI_REF="${4:-736c68f674113337685e3eb1f908602a03b8f99b}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/.claude/skills"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fetch() { # repo ref dir
  git init -q "$3"
  git -C "$3" remote add origin "https://github.com/$1.git"
  git -C "$3" fetch -q --depth 1 origin "$2"
  git -C "$3" checkout -q FETCH_HEAD
}

fetch anthropics/skills "$ANTHROPIC_REF" "$WORK/anthropic"
fetch vercel-labs/agent-skills "$VERCEL_REF" "$WORK/vercel"
fetch github/gh-stack "$GH_STACK_REF" "$WORK/gh-stack"
fetch cli/cli "$GH_CLI_REF" "$WORK/gh-cli"

for s in frontend-design webapp-testing skill-creator; do
  rm -rf "${DEST:?}/$s"
  cp -R "$WORK/anthropic/skills/$s" "$DEST/$s"
done
rm -rf "${DEST:?}/web-design-guidelines"
cp -R "$WORK/vercel/skills/web-design-guidelines" "$DEST/web-design-guidelines"

# GitHub 公式。Skill のディレクトリに LICENSE がないため、リポジトリ直下の LICENSE（MIT）を同梱する。
rm -rf "${DEST:?}/gh-stack"
cp -R "$WORK/gh-stack/skills/gh-stack" "$DEST/gh-stack"
cp "$WORK/gh-stack/LICENSE" "$DEST/gh-stack/LICENSE"
rm -rf "${DEST:?}/gh"
cp -R "$WORK/gh-cli/skills/gh" "$DEST/gh"
cp "$WORK/gh-cli/LICENSE" "$DEST/gh/LICENSE"

echo "synced: anthropics/skills@$ANTHROPIC_REF vercel-labs/agent-skills@$VERCEL_REF github/gh-stack@$GH_STACK_REF cli/cli@$GH_CLI_REF"
echo "SOURCES.md のコミット SHA を更新し、git diff をレビューしてからコミットしてください。"
