#!/usr/bin/env bash
# AI エージェント向けの指示ファイルの雛形と、Skills の検査スクリプトを対象リポジトリに配置する。
# 使い方: scripts/add-agent-templates.sh <対象リポジトリのパス>
# - 置くもの: AGENTS.md、CLAUDE.md、scripts/check-skills.py（正本は templates/agents/）
# - 既存のファイルは上書きしない。ただし AGENTS.md に「共通規約ここから」「共通規約ここまで」の印があれば、その間だけを最新の共通規約に置き換える。
# - 何度実行しても同じ結果になる。Issue・PR のテンプレートと記述ルールは scripts/add-github-templates.sh で配置する。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/templates/agents"

[[ $# -ge 1 ]] || { sed -n '2,6p' "$0"; exit 1; }
DEST="$(cd "$1" && pwd)"
[[ -d "$DEST/.git" ]] || { echo "Git リポジトリではありません: $DEST" >&2; exit 1; }
[[ "$DEST" != "$ROOT" ]] || { echo "このリポジトリ自身には使わない（共通規約の一致は scripts/check-templates.py で確かめる）" >&2; exit 1; }

skipped=()
for f in AGENTS.md CLAUDE.md scripts/check-skills.py; do
  if [[ ! -e "$DEST/$f" ]]; then
    mkdir -p "$(dirname "$DEST/$f")"
    cp "$SRC/$f" "$DEST/$f"
    echo "配置: $f"
    continue
  fi
  cmp -s "$SRC/$f" "$DEST/$f" && continue
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

if (( ${#skipped[@]} )); then
  echo "既存のファイルと内容が違うため、上書きしなかったもの（差分を確認して手で統合してください）:"
  printf '  - %s\n' "${skipped[@]}"
fi
echo "完了。AGENTS.md の「このリポジトリについて」と「このプロジェクトの罠」を、プロジェクトに合わせて書いてください。"
