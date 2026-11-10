#!/usr/bin/env bash
# W18 の試行前の確認用: 参照の系列・最短の系列（正解データの <名前>-r1.patch〜-r6.patch）を、試行と同じ形の作業用コピーに積む。
# 使い方: scripts/poc/w18_series.sh <名前（reference | shortest）> [<系列の番号。既定 1>]
#   - $POC_TRIAL_ROOT/W18r1-<名前>-<番号>/app に、run-trial.sh の第 1 回と同じ初期状態（poc-app + Skills・MCP の設定 +
#     W18/base.patch + 汎用の開発標準）を作り、各回のパッチを 1 コミットずつ積む（第 4 回の前に agency-api.md の資料をコミットする）。
#   - raw/W18r<回>-<名前>-<番号>/ に workdir・baseline-commit・final-commit を書く（grade_w18.py と、引き継ぎの試行 W18h1・W18h2 がそのまま使える）。
#   試行（候補の作業）は行わない。費用はかからない。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NAME="$1"; RUN="${2:-1}"
KEY="$ROOT/docs/poc/answer-key/W18"
TRIALS="${POC_TRIAL_ROOT:-/tmp/poc-trials}"
WORK="$TRIALS/W18r1-$NAME-$RUN"
APP="$WORK/app"
[[ -e "$WORK" ]] && { echo "すでにある: $WORK（別の番号を指定する）" >&2; exit 1; }
mkdir -p "$APP" "$WORK/home"
cp -a "$ROOT/poc-app/." "$APP/"
mkdir -p "$APP/.claude/skills"
cp -a "$ROOT/.claude/skills/." "$APP/.claude/skills/"
mv "$APP/.claude/skills/SOURCES.md" "$WORK/SOURCES.md.unused" 2>/dev/null || true
cat > "$APP/.mcp.json" <<'JSON'
{"mcpServers":{
  "playwright":{"type":"stdio","command":"npx","args":["-y","@playwright/mcp@0.0.84"]},
  "next-devtools":{"type":"stdio","command":"npx","args":["-y","next-devtools-mcp@0.4.0"]}}}
JSON
git -C "$APP" init -q
git -C "$APP" config user.name poc
git -C "$APP" config user.email poc@example.invalid
git -C "$APP" apply "$KEY/base.patch"
{ echo; sed '1,/^-->$/d' "$ROOT/docs/poc/standards/generic-dev-standard.md"; } >> "$APP/CLAUDE.md"
git -C "$APP" add -A
git -C "$APP" commit -qm baseline
for r in 1 2 3 4 5 6; do
  OUT="$ROOT/docs/poc/results/workflow/raw/W18r$r-$NAME-$RUN"
  mkdir -p "$OUT"
  echo "$WORK" > "$OUT/workdir"
  echo "precheck $NAME-r$r.patch" > "$OUT/precheck"
  if [[ "$r" == 4 ]]; then
    mkdir -p "$APP/docs"
    cp "$KEY/agency-api.md" "$APP/docs/agency-api.md"
    git -C "$APP" add docs/agency-api.md
    git -C "$APP" commit -qm "校正機関の受付システムの API の資料を追加（依頼者）"
  fi
  git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
  git -C "$APP" switch -q -c "poc/wf/$NAME/W18r$r/$RUN"
  git -C "$APP" apply "$KEY/$NAME-r$r.patch"
  git -C "$APP" add -A
  git -C "$APP" commit -qm "$NAME r$r"
  git -C "$APP" rev-parse HEAD > "$OUT/final-commit"
done
echo "done $WORK"
