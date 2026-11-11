#!/usr/bin/env bash
# AI エージェント向けの標準構成（指示ファイル・設定・Skills・検査）を対象リポジトリに配置する。
# 使い方: scripts/add-agent-templates.sh <対象リポジトリのパス> [--with-check] [--no-skills]
#   --with-check : Skills の検査を CI で回す GitHub Actions（.github/workflows/skills-check.yml）も配置する
#   --no-skills  : 標準の Skills（.claude/skills/）を配置しない
# - 置くもの: AGENTS.md、CLAUDE.md、.claude/settings.json、.mcp.json、scripts/check-skills.py、
#   このリポジトリで作った Skill（.claude/skills/ の下。正本は templates/agents/）と、
#   標準の Skills（scripts/sync-skills.sh で固定コミットから取得し、指紋 scripts/skills.lock.json も作る）
# - 既存のファイルは上書きしない。ただし AGENTS.md に「共通規約ここから」「共通規約ここまで」の印があれば、その間だけを最新の共通規約に置き換える。
# - 何度実行しても同じ結果になる。採用技術ごとの追加は scripts/add-stack.sh --dest <対象> <stack>...、
#   Issue・PR のテンプレートと記述ルールは scripts/add-github-templates.sh で配置する。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/templates/agents"

[[ $# -ge 1 ]] || { sed -n '2,10p' "$0"; exit 1; }
DEST="$(cd "$1" && pwd)"
shift
WITH_CHECK=false
WITH_SKILLS=true
for opt in "$@"; do
  case "$opt" in
    --with-check) WITH_CHECK=true ;;
    --no-skills) WITH_SKILLS=false ;;
    *) echo "不明な指定: $opt" >&2; exit 1 ;;
  esac
done
[[ -d "$DEST/.git" ]] || { echo "Git リポジトリではありません: $DEST" >&2; exit 1; }
[[ "$DEST" != "$ROOT" ]] || { echo "このリポジトリ自身には使わない（共通規約の一致は scripts/check-templates.py で確かめる）" >&2; exit 1; }

skipped=()
files=(AGENTS.md CLAUDE.md .claude/settings.json .mcp.json scripts/check-skills.py)
$WITH_CHECK && files+=(.github/workflows/skills-check.yml)
for f in "${files[@]}"; do
  if [[ ! -e "$DEST/$f" ]]; then
    mkdir -p "$(dirname "$DEST/$f")"
    cp "$SRC/$f" "$DEST/$f"
    echo "配置: $f"
    continue
  fi
  cmp -s "$SRC/$f" "$DEST/$f" && continue
  # 設定ファイルは、雛形の中身をすべて含んでいれば（add-stack.sh などで足しただけなら）そのままにする
  if [[ "$f" == *.json ]] && python3 - "$SRC/$f" "$DEST/$f" <<'PY'
import json, sys
def contains(t, l):
    if isinstance(t, dict):
        return isinstance(l, dict) and all(k in l and contains(v, l[k]) for k, v in t.items())
    if isinstance(t, list):
        return isinstance(l, list) and all(x in l for x in t)
    return t == l
sys.exit(0 if contains(json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))) else 1)
PY
  then
    continue
  fi
  if [[ "$f" == AGENTS.md ]]; then
    result="$(python3 - "$SRC/AGENTS.md" "$DEST/AGENTS.md" <<'PY'
import re, sys, pathlib
pat = re.compile(r"<!-- 共通規約ここから.*?<!-- 共通規約ここまで -->", re.S)
src = pat.search(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")).group(0)
dest = pathlib.Path(sys.argv[2])
text = dest.read_text(encoding="utf-8")
m = pat.search(text)
if not m:
    print("nomarker")
elif m.group(0) == src:
    print("same")
else:
    dest.write_text(text[:m.start()] + src + text[m.end():], encoding="utf-8")
    print("updated")
PY
)"
    case "$result" in
      updated) echo "更新: AGENTS.md の共通規約" ;;
      same) ;;
      *) skipped+=("AGENTS.md（共通規約の印がない。templates/agents/AGENTS.md の印の間を手で取り込む）") ;;
    esac
    continue
  fi
  skipped+=("$f")
done

# このリポジトリで作った Skill（templates/agents/.claude/skills/）を配る。既存の内容と違えば上書きしない
for own in "$SRC"/.claude/skills/*/; do
  [[ -d "$own" ]] || continue
  name="$(basename "$own")"
  if [[ ! -e "$DEST/.claude/skills/$name" ]]; then
    mkdir -p "$DEST/.claude/skills"
    cp -R "$own" "$DEST/.claude/skills/$name"
    echo "配置: .claude/skills/$name"
  elif ! diff -rq "$own" "$DEST/.claude/skills/$name" >/dev/null; then
    skipped+=(".claude/skills/$name")
  fi
done

# 標準の Skills を固定コミットから取得する（既にあれば同じ内容で上書きされる。手での編集は check-skills.py が検出する）
if $WITH_SKILLS; then
  "$ROOT/scripts/sync-skills.sh" --dest "$DEST" >/dev/null
  echo "配置: 標準の Skills（.claude/skills/）と指紋（scripts/skills.lock.json）"
fi

if (( ${#skipped[@]} )); then
  echo "既存のファイルと内容が違うため、上書きしなかったもの（差分を確認して手で統合してください）:"
  printf '  - %s\n' "${skipped[@]}"
fi
echo "完了。次を行ってください。"
echo "  1. AGENTS.md の「このリポジトリについて」と「このプロジェクトの罠」を、プロジェクトに合わせて書く"
echo "  2. 採用技術に応じて scripts/add-stack.sh --dest \"$DEST\" <stack>... を実行する"
echo "  3. 対象リポジトリで python3 scripts/check-skills.py を実行し、エラーが 0 件であることを確かめる"
