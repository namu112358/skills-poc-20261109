#!/usr/bin/env bash
# W8 の受け入れテストを、任意の poc-app のコピーで試す（参照実装・不具合を入れた版の確認用。試行前の確認に使った）。
# 使い方: docs/poc/answer-key/W8/verify.sh <アプリのディレクトリ> <ポート>
set -u
APPD="$1"; PORT="$2"
cd "$APPD"
npm run build > /tmp/claude-0/build-$PORT.log 2>&1 || { echo BUILD FAIL; tail -n 20 /tmp/claude-0/build-$PORT.log; exit 1; }
setsid npx next start -p "$PORT" > /tmp/claude-0/start-$PORT.log 2>&1 &
SP=$!
for i in $(seq 1 60); do curl -s -o /dev/null "http://127.0.0.1:$PORT/login" && break; sleep 1; done
NODE_PATH=$(npm root -g) node /home/user/skills-poc-20261109/docs/poc/answer-key/W8/acceptance.cjs "http://127.0.0.1:$PORT" | python3 -c '
import json,sys
r=json.loads(sys.stdin.read().strip().splitlines()[-1])
for x in r: print("PASS" if x["pass"] else "FAIL", x["name"], "" if x["pass"] else x["detail"])
print(sum(x["pass"] for x in r),"/",len(r))'
kill -- -$SP 2>/dev/null
