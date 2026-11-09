#!/usr/bin/env bash
# runkey.sh <app dir> <cjs> [port]  (app must be built)
APP="$1"; KEY="$2"; PORT="${3:-3411}"
K="$(cd "$(dirname "$0")" && pwd)"
cd "$APP"
export POC_FAKE_NOW=2026-11-09T15:30:00.000Z
NODE_OPTIONS="--require $K/fake-clock.cjs" setsid npx next start -p $PORT > "${POC_SERVER_LOG:-/dev/null}" 2>&1 &
SP=$!
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$PORT/login && break; sleep 1; done
NODE_PATH=$(npm root -g) node "$K/$KEY" http://127.0.0.1:$PORT | python3 -c '
import json,sys
r=json.loads(sys.stdin.read().strip().splitlines()[-1])
for t in r: print("PASS" if t["pass"] else "FAIL", t["name"], "" if t["pass"] else t["detail"])
print(sum(t["pass"] for t in r),"/",len(r))'
kill -- -$SP 2>/dev/null; sleep 1
