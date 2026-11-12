#!/usr/bin/env bash
# W8 の参考判定（正式な点数には使わない）: タグの要素（data-testid="tag"）の中に「外す」ボタンを置いた実装について、
# ボタンの文字を除いたタグの名前で隠しの E2E を判定し直す。
# 課題文は「各タグは data-testid="tag" の要素とし、タグの名前を表示する」「各タグに『外す』ボタンを置く」で、
# ボタンを tag 要素の中に置く読み方も許されるため（2026-11-09 コーディネーター判断。report の判断の記録を参照）。
# acceptance.cjs 自体は書き換えず、タグの名前を読む 1 行だけを置き換えた写しを作業ディレクトリに作って使う。
# 使い方: poc/scripts/w8_alt_tagtext.sh <試行ID> <ポート>
#   試行の差分（raw/<試行ID>/diff.patch）を poc-app の写しに当て、ビルドして判定する。結果は W8/alt-tagtext/<試行ID>.json。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ID="$1"; PORT="$2"
RAW="$ROOT/poc/results/workflow/raw/$ID"
OUTD="$ROOT/poc/results/workflow/W8/alt-tagtext"
WORK="/tmp/poc-alt/$ID-$(date +%s)"
mkdir -p "$WORK" "$OUTD"
cp -a "$ROOT/poc/app/." "$WORK/app/"
git -C "$WORK/app" init -q
git -C "$WORK/app" apply --exclude='.playwright-mcp/*' "$RAW/diff.patch" || { echo "patch failed"; exit 1; }
python3 - "$ROOT/poc/answer-key/W8/acceptance.cjs" "$WORK/acceptance-alt.cjs" <<'EOF'
import sys
s = open(sys.argv[1]).read()
old = """return (await p.locator('[data-testid="tag"]').allInnerTexts()).map((s) => s.trim());"""
new = """return await p.locator('[data-testid="tag"]').evaluateAll((els) => els.map((e) => { const c = e.cloneNode(true); c.querySelectorAll('button').forEach((b) => b.remove()); return c.textContent.trim(); }));"""
assert s.count(old) == 1, "置き換え対象の行が見つからない"
open(sys.argv[2], "w").write(s.replace(old, new))
EOF
cd "$WORK/app"
npm run build > "$WORK/build.log" 2>&1 || { echo BUILD FAIL; tail -n 20 "$WORK/build.log"; exit 1; }
# 判定ごとに DB の状態を揃えるため、ビルド後の写しをもう 1 つ作る（2 回目の判定はこちらで行う）
cp -a "$WORK/app" "$WORK/app2"
setsid npx next start -p "$PORT" > "$WORK/start.log" 2>&1 &
SP=$!
for i in $(seq 1 60); do curl -s -o /dev/null "http://127.0.0.1:$PORT/login" && break; sleep 1; done
# 確認用に、元の acceptance.cjs でも判定する（正式な結果と同じになるはず）。参考判定は別の写し（app2）で起動し直して行う
NODE_PATH=$(npm root -g) node "$ROOT/poc/answer-key/W8/acceptance.cjs" "http://127.0.0.1:$PORT" | tail -n 1 > "$WORK/result-orig.json"
kill -- -$SP 2>/dev/null; sleep 2
cd "$WORK/app2"
setsid npx next start -p "$PORT" > "$WORK/start2.log" 2>&1 &
SP=$!
for i in $(seq 1 60); do curl -s -o /dev/null "http://127.0.0.1:$PORT/login" && break; sleep 1; done
NODE_PATH=$(npm root -g) node "$WORK/acceptance-alt.cjs" "http://127.0.0.1:$PORT" | tail -n 1 > "$WORK/result.json"
kill -- -$SP 2>/dev/null
python3 - "$WORK/result.json" "$OUTD/$ID.json" "$ID" "$WORK/result-orig.json" <<'EOF'
import json, sys
r = json.loads(open(sys.argv[1]).read())
o = json.loads(open(sys.argv[4]).read())
out = {"trial": sys.argv[3], "method": "tag 要素の文字から子孫の button を除いて判定（poc/scripts/w8_alt_tagtext.sh）。正式な点数には使わない参考値",
       "pass": sum(x["pass"] for x in r), "total": len(r), "failed": [x["name"] for x in r if not x["pass"]],
       "original_rerun": {"pass": sum(x["pass"] for x in o), "total": len(o)}}
open(sys.argv[2], "w").write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(out["trial"], "alt", out["pass"], "/", out["total"], out["failed"], "orig-rerun", out["original_rerun"])
EOF
