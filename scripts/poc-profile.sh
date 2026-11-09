#!/usr/bin/env bash
# PoC 用プロファイルを切り替える（.claude/settings.local.json を上書き）。
# 使い方: scripts/poc-profile.sh <profile>   例: scripts/poc-profile.sh wf-superpowers
#         scripts/poc-profile.sh list | current
# 切り替え後は Claude Code を再起動するか /reload-plugins を実行すること。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILES="$ROOT/docs/poc/profiles"
LOCAL="$ROOT/.claude/settings.local.json"
MARK="$ROOT/.claude/poc-profile"
CF_DIR="$ROOT/.claude/skills/security-audit"
CF_REF="c1c8a8c1471069fb0e188eeaff69b8e8db6564a8" # cloudflare/security-audit-skill

case "${1:-}" in
  list) ls "$PROFILES" | sed 's/\.json$//'; exit 0 ;;
  current) cat "$MARK" 2>/dev/null || echo "(none)"; exit 0 ;;
  "") echo "usage: $0 <profile|list|current>" >&2; exit 1 ;;
esac

SRC="$PROFILES/$1.json"
[[ -f "$SRC" ]] || { echo "unknown profile: $1" >&2; exit 1; }

if [[ -f "$LOCAL" && ! -f "$MARK" ]]; then
  cp "$LOCAL" "$LOCAL.bak"
  echo "既存の settings.local.json を settings.local.json.bak に退避しました"
fi
cp "$SRC" "$LOCAL"
echo "$1" > "$MARK"

# Cloudflare Security Audit は marketplace が無いため、プロファイル適用時のみ
# 固定コミットからプロジェクト Skill として配置する（.gitignore 済み）。
rm -rf "$CF_DIR"
if [[ "$1" == "sec-cloudflare" ]]; then
  WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
  git init -q "$WORK/cf"
  git -C "$WORK/cf" remote add origin https://github.com/cloudflare/security-audit-skill.git
  git -C "$WORK/cf" fetch -q --depth 1 origin "$CF_REF"
  git -C "$WORK/cf" checkout -q FETCH_HEAD
  cp -R "$WORK/cf/skills/security-audit" "$CF_DIR"
  echo "security-audit skill を配置: $CF_DIR (@$CF_REF)"
fi

if [[ "$1" == wf-gstack* ]]; then
  echo "注意: gstack は marketplace 配布ではありません。docs/poc/PLAN.md §3.4 の専用環境で、固定コミットから手作業で入れてください。"
fi
echo "PoC profile: $1 を適用しました。Claude Code を再起動するか /reload-plugins を実行してください。"
