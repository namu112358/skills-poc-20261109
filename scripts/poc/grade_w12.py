#!/usr/bin/env python3
"""W12（短い要件から、運用まで考えて作る）の試行を採点用に調べ、results/workflow/W12/<試行ID>.json に書き出す。

使い方:
  python3 scripts/poc/grade_w12.py <試行ID> [--cleanup]
    1. grade.py と同じ集計（型チェック・単体テスト・ビルド・差分・トランスクリプト）
    2. W12 固有の事実（docs/poc/answer-key/W12/grading.md）を w12 に足す
       - adapter:   候補の実装の重要度の項目名・値・ジョブの API（adapt.cjs。採点者の補正は W12/adapters/<試行ID>.json）
       - public / hidden / robust: 受け入れテスト・隠しテスト・外部呼び出しの堅牢さ（それぞれ新しい DB・偽の通知サービスで起動）
       - migration: 旧スキーマ + データ入りの DB（old-db.sql）で起動し、データが消えない・新しい列が埋まる・2 回起動しても壊れないか
       - ops:       構造化ログ（logger.ts）・秘密情報をログに出さない・設定を環境変数で読む
       - static:    既存のマイグレーションの書き換え・アプリの中の定期実行など（コードから）
       - mutation:  候補が src/lib/ に足した行をわざと壊した版を、候補の npm test が検出した割合（grade_w10.py と同じ方法）
  python3 scripts/poc/grade_w12.py --app <アプリのディレクトリ> --base <コミット> [--out <JSON>]
    試行前の検証用（参照実装・最短の実装・半分の実装）。同じ判定をして JSON を標準出力（または --out）に書く。
"""
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W12"
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W12"
JOBS_TOKEN = "jobs-tkn-7c1e93SECRETa52f"
NOTIFY_TOKEN = "ntf-tkn-4b8d20SECRET9e6c"
BASE_KEYS = ["managementNo", "name", "model", "location", "managerId", "intervalMonths", "lastCalibratedOn", "status", "note"]
# next start が出す起動時の行（構造化ログの判定から除く）
NEXT_LINES = re.compile(r"^\s*(▲ Next\.js|- Local:|- Network:|✓ Starting|✓ Ready|✓ Running|Starting\.\.\.|$|> |⚠ |\(node:\d+\) ExperimentalWarning|\(Use `node --trace)")
BASE_EVENTS = {"auth.login_failed", "job.unauthorized", "calibration.failed", "loan.overdue"}


def sh(cmd, cwd, timeout=900, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout + p.stderr


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, seconds=90):
    for _ in range(seconds):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(1)
    return False


NODE_PATH = None


def node_path():
    global NODE_PATH
    if NODE_PATH is None:
        NODE_PATH = subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip()
    return NODE_PATH


# ---- コードから分かること ----

def git(app, *args):
    return subprocess.run(["git", *args], cwd=app, capture_output=True, text=True).stdout


def added_code_lines(app, base):
    """src/ のテスト以外のファイルに足された行 [(ファイル, 行)]。"""
    out, cur = [], None
    for line in git(app, "diff", "-U0", base, "HEAD", "--", "src").splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and not line.startswith("+++") and cur and ".test." not in cur:
            out.append((cur, line[1:]))
    return out


def migrations_of(app):
    """src/lib/db/migrations.ts の MIGRATIONS を node で読み込んで返す。読めなければ None。"""
    script = ("import('./src/lib/db/migrations.ts').then(m => console.log(JSON.stringify("
              "(m.MIGRATIONS || []).map(x => ({version: x.version, name: x.name, sql: x.sql})))))")
    code, out = sh(f"node --experimental-strip-types --no-warnings -e \"{script}\"", app, timeout=60)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def norm_sql(s):
    return re.sub(r"\s+", " ", s).strip()


def static_checks(app, base):
    lines = added_code_lines(app, base)
    code = "\n".join(l for _, l in lines)
    files = sorted({f for f, _ in lines})
    base_dir = Path(tempfile.mkdtemp(prefix="w12-base-"))
    subprocess.run(f"git -C {app} archive {base} src | tar -x -C {base_dir}", shell=True, check=True)
    before, after = migrations_of(base_dir), migrations_of(app)
    shutil.rmtree(base_dir, ignore_errors=True)
    mig = {"readable": after is not None, "base_versions": [m["version"] for m in before or []]}
    if after is not None and before is not None:
        old = {m["version"]: norm_sql(m["sql"]) for m in before}
        new = {m["version"]: norm_sql(m["sql"]) for m in after}
        mig["rewritten"] = [v for v in old if new.get(v) != old[v]]
        mig["added"] = [m["version"] for m in after if m["version"] not in old]
        mig["appended_in_order"] = bool(mig["added"]) and min(mig["added"]) > max(old) and [m["version"] for m in after] == sorted(m["version"] for m in after)
    sched = [l.strip()[:160] for f, l in lines if re.search(r"setInterval\s*\(|node-cron|cron\.schedule|\bschedule\s*\(", l)]
    sched += [f for f in files if re.search(r"(^|/)instrumentation\.(ts|js)$", f)]
    # process.env.X・env.X・env["X"]（env を引数で受け取る書き方を含む）と、文書の変数名がそのまま書かれているもの
    env_names = sorted({m for m in re.findall(r"\benv(?:\.|\[\s*[\"'])([A-Z][A-Z0-9_]+)", code)}
                       | {n for n in ("NOTIFY_API_URL", "NOTIFY_API_TOKEN", "JOBS_TOKEN") if n in code})
    return {
        "migrations": mig,
        "inProcessScheduler": sched,
        "console_lines": [l.strip()[:160] for f, l in lines if re.search(r"\bconsole\.(log|info|warn|error|debug)\s*\(", l)],
        "logger_used": bool(re.search(r"\blogger\.(info|warn|error|debug)\s*\(", code)),
        "env_names": env_names,
        "hardcoded_urls": [l.strip()[:160] for f, l in lines if re.search(r"https?://(?!localhost|127\.0\.0\.1)[^\s\"'`]*", l) and "example" not in l],
        "new_deps": git(app, "diff", base, "HEAD", "--", "package.json").count("\n+  ") > 0,
        "changed_src_files": files,
    }


def new_routes(app, base):
    names = git(app, "diff", "--name-only", "--diff-filter=A", base, "HEAD", "--", "src/app").split()
    out = []
    for n in names:
        m = re.match(r"src/app(/.*)/route\.(ts|js)$", n)
        if not m:
            continue
        src = (Path(app) / n).read_text()
        methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b", src)
        methods += re.findall(r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\b", src)
        out.append({"path": m.group(1), "methods": sorted(set(methods))})
    return out


# ---- サーバーと偽の通知サービス ----

class Env:
    """偽の通知サービス 1 つと、候補のアプリのサーバー 1 つ（偽の時計・DB ファイル・ログの記録つき）。"""

    def __init__(self, app, work, name, db_path=None, aliases=None, now="2026-11-10T00:00:00.000Z"):
        self.app, self.work, self.name = Path(app), Path(work), name
        self.work.mkdir(parents=True, exist_ok=True)
        self.clock = self.work / f"{name}.now"
        self.clock.write_text(now + "\n")
        self.db = Path(db_path) if db_path else self.work / f"{name}.db"
        self.log = self.work / f"{name}.server.log"
        self.aliases = aliases or {}
        self.server = self.notify = None

    def start_notify(self):
        self.notify_port = free_port()
        self.notify = subprocess.Popen(["node", str(KEY / "fake-notify.cjs"), str(self.notify_port), NOTIFY_TOKEN],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        wait_port(self.notify_port, 20)

    def start_server(self):
        self.port = free_port()
        env = dict(os.environ)
        env.update({
            "DATABASE_PATH": str(self.db), "JOBS_TOKEN": JOBS_TOKEN,
            "NOTIFY_API_URL": f"http://127.0.0.1:{self.notify_port}", "NOTIFY_API_TOKEN": NOTIFY_TOKEN,
            "POC_FAKE_NOW_FILE": str(self.clock), "NODE_ENV": "production",
            "NODE_OPTIONS": (env.get("NODE_OPTIONS", "") + f" --require {KEY / 'fake-clock.cjs'}").strip(),
        })
        for k, v in self.aliases.items():
            env[k] = {"notify_url": env["NOTIFY_API_URL"], "notify_token": NOTIFY_TOKEN, "jobs_token": JOBS_TOKEN}[v]
        self.logf = open(self.log, "a")
        self.server = subprocess.Popen(f"npx next start -p {self.port}", cwd=self.app, shell=True, env=env,
                                       stdout=self.logf, stderr=self.logf, start_new_session=True)
        return wait_port(self.port, 90)

    def stop_server(self):
        if self.server:
            try:
                os.killpg(self.server.pid, 15)
            except ProcessLookupError:
                pass
            self.server.wait(timeout=30)
            self.server = None
            self.logf.close()
            time.sleep(1)

    def stop(self):
        self.stop_server()
        if self.notify:
            os.killpg(self.notify.pid, 15)
            self.notify = None

    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def run_cjs(self, name, adapter, extra=None, timeout=1800):
        env = dict(os.environ, NODE_PATH=node_path(), W12_ADAPTER=json.dumps(adapter), W12_NOTIFY=f"http://127.0.0.1:{self.notify_port}",
                   W12_JOBS_TOKEN=JOBS_TOKEN, POC_FAKE_NOW_FILE=str(self.clock), **(extra or {}))
        p = subprocess.run(["node", str(KEY / name), self.base()], cwd=self.app, capture_output=True, text=True,
                           timeout=timeout, env=env)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return [{"id": "X", "name": f"{name} の実行", "pass": False, "detail": (p.stdout + p.stderr)[-800:]}]

    def notify_state(self):
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{self.notify_port}/__state", timeout=10) as r:
            return json.loads(r.read())


def aliases_for(static):
    """候補が文書と違う名前の環境変数で通知サービスの URL・トークン、ジョブのトークンを読むとき、同じ値を渡す（運用の判定で減点）。"""
    out = {}
    for n in static["env_names"]:
        if n in ("NOTIFY_API_URL", "NOTIFY_API_TOKEN", "JOBS_TOKEN", "DATABASE_PATH", "NODE_ENV", "LOG_LEVEL"):
            continue
        if "NOTIF" in n and re.search(r"URL|ENDPOINT|HOST|BASE", n):
            out[n] = "notify_url"
        elif "NOTIF" in n and re.search(r"TOKEN|KEY|SECRET", n):
            out[n] = "notify_token"
        elif re.search(r"CRON|JOB", n) and re.search(r"TOKEN|SECRET|KEY", n):
            out[n] = "jobs_token"
    return out


def suite(app, work, name, script, adapter, aliases, extra=None):
    e = Env(app, work, name, aliases=aliases)
    e.start_notify()
    try:
        if not e.start_server():
            return [{"id": "X", "name": "サーバーの起動", "pass": False, "detail": e.log.read_text()[-500:]}], e.log.read_text(), {}
        res = e.run_cjs(script, adapter, extra)
        state = e.notify_state()
    finally:
        e.stop()
    return res, e.log.read_text(), state


def discover_adapter(app, work, routes, aliases, override):
    e = Env(app, work, "adapt", aliases=aliases)
    e.start_notify()
    try:
        if not e.start_server():
            return {"error": "サーバーが起動しない", "needs_review": True}
        env = dict(os.environ, NODE_PATH=node_path(), W12_ROUTES=json.dumps(routes), W12_JOBS_TOKEN=JOBS_TOKEN)
        p = subprocess.run(["node", str(KEY / "adapt.cjs"), e.base()], cwd=app, capture_output=True, text=True, timeout=900, env=env)
        try:
            adapter = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            adapter = {"error": (p.stdout + p.stderr)[-500:], "needs_review": True}
    finally:
        e.stop()
    if override:
        adapter = {**adapter, **override, "overridden": sorted(override)}
    return adapter


# ---- マイグレーション ----

def restore_old_db(path):
    con = sqlite3.connect(path)
    con.executescript((KEY / "old-db.sql").read_text())
    con.commit()
    con.close()


def snapshot(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    out = {"user_version": con.execute("PRAGMA user_version").fetchone()[0]}
    for t in ("departments", "users", "instruments", "loans", "calibration_records", "sessions"):
        try:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
            out[t] = {"columns": cols, "rows": [dict(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY rowid")]}
        except sqlite3.DatabaseError:
            out[t] = None
    con.close()
    return out


def migration_checks(app, work, adapter, aliases, static):
    import urllib.request
    work = Path(work)
    db = work / "old.db"
    restore_old_db(db)
    before = snapshot(db)
    res = {"static": static["migrations"], "steps": []}
    e = Env(app, work, "migration", db_path=db, aliases=aliases)
    e.start_notify()

    def api(method, path, body=None, cookie=None):
        req = urllib.request.Request(e.base() + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"content-type": "application/json", **({"cookie": cookie} if cookie else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null"), r.headers
        except urllib.error.HTTPError as ex:
            return ex.code, None, ex.headers

    def login():
        st, _, h = api("POST", "/api/login", {"userId": "sato", "password": "password"})
        c = h.get("set-cookie", "") if h else ""
        return st, c.split(";")[0]

    old_instr = {r["management_no"]: r for r in before["instruments"]["rows"]}
    target = "MI-0003"
    try:
        # 1 回目の起動（マイグレーションの適用）
        started = e.start_server()
        st, cookie = login() if started else (0, "")
        res["first_start"] = {"started": started, "login": st}
        listed = {}
        if st == 200:
            s, body, _ = api("GET", "/api/instruments", cookie=cookie)
            listed = {i["managementNo"]: i for i in (body or {}).get("instruments", [])}
        key = adapter.get("key")
        res["api_instruments"] = len(listed)
        mism = []
        for no, row in old_instr.items():
            i = listed.get(no)
            if not i:
                mism.append(f"{no}: 一覧に無い")
                continue
            for k, col in [("name", "name"), ("model", "model"), ("location", "location"), ("managerId", "manager_id"),
                           ("intervalMonths", "interval_months"), ("lastCalibratedOn", "last_calibrated_on"), ("status", "status"), ("note", "note")]:
                if i.get(k) != row[col]:
                    mism.append(f"{no}.{k}: {i.get(k)!r} != {row[col]!r}")
        res["api_mismatch"] = mism[:20]
        levels = adapter.get("levels") or []
        res["default_values"] = sorted({json.dumps(i.get(key)) for i in listed.values()}) if key else []
        # 既存の計測器の重要度を最も高い値に変える（あとで、別の列に詰め込んでいないか・再起動しても残るかを見る）
        set_status = None
        if key and levels and target in listed:
            set_status, _, _ = api("PATCH", f"/api/instruments/{listed[target]['id']}", {key: levels[0]}, cookie)
        res["set_status"] = set_status
        e.stop_server()
        mid = snapshot(db)
        # 2 回目の起動（マイグレーションを 2 回走らせても壊れないか、値が DB に残っているか）
        started2 = e.start_server()
        st2, cookie2 = login() if started2 else (0, "")
        after_val = None
        count2 = 0
        if st2 == 200:
            s, body, _ = api("GET", "/api/instruments", cookie=cookie2)
            l2 = {i["managementNo"]: i for i in (body or {}).get("instruments", [])}
            count2 = len(l2)
            after_val = l2.get(target, {}).get(key) if key else None
        res["second_start"] = {"started": started2, "login": st2, "instruments": count2, "value_after_restart": after_val}
        e.stop_server()
    finally:
        e.stop()
    after = snapshot(db)
    log = e.log.read_text()
    # DB の中身の比較
    def rows(snap, t):
        return (snap.get(t) or {}).get("rows") or []
    kept = {}
    for t in ("departments", "users", "instruments", "loans", "calibration_records"):
        b = rows(before, t)
        a = rows(after, t)
        cols = (before.get(t) or {}).get("columns") or []
        a_by = {r.get("id"): r for r in a}
        changed = [r["id"] for r in b if r.get("id") not in a_by or any(a_by[r["id"]].get(c) != r.get(c) for c in cols)]
        if t == "instruments":
            # 重要度を変えた MI-0003 は、既存の列が変わっていなければよい
            changed = [x for x in changed]
        kept[t] = {"before": len(b), "after": len(a), "changed_ids": changed[:10]}
    res["db"] = {"user_version": [before["user_version"], mid["user_version"], after["user_version"]],
                 "instruments_columns": (after.get("instruments") or {}).get("columns"), "kept": kept}
    res["errors_in_log"] = [l[:200] for l in log.splitlines() if re.search(r"Error|SQLITE|no such column|duplicate column", l)][:10]
    # 判定（grading.md の M1〜M6）
    m = static["migrations"]
    target_id = old_instr[target]["id"]
    tgt_changed = target_id in kept["instruments"]["changed_ids"]
    others_changed = [i for i in kept["instruments"]["changed_ids"] if i != target_id]
    data_kept = all(v["before"] == v["after"] and not v["changed_ids"] for k, v in kept.items() if k != "instruments") \
        and kept["instruments"]["before"] == kept["instruments"]["after"] and not others_changed
    mid_level = levels[1] if len(levels) >= 3 else None
    res["checks"] = {
        "M1": bool(m.get("appended_in_order")) and after["user_version"] > before["user_version"],
        "M2": m.get("readable", False) and not m.get("rewritten") and m.get("base_versions") == [1, 2, 3, 4] and before["user_version"] == 4,
        "M3": bool(res["first_start"]["started"] and res["first_start"]["login"] == 200 and not mism and data_kept),
        "M4": bool(key and len(res["default_values"]) == 1 and json.loads(res["default_values"][0]) is not None
                   and json.loads(res["default_values"][0]) in levels and (mid_level is None or json.loads(res["default_values"][0]) == mid_level)),
        "M5": bool(key and levels and res["set_status"] == 200 and after_val == levels[0] and not tgt_changed),
        "M6": bool(res["second_start"]["started"] and res["second_start"]["login"] == 200 and count2 == len(old_instr)
                   and mid["user_version"] == after["user_version"] and data_kept),
    }
    res["escape"] = {
        "rewrote_existing_migration": bool(m.get("rewritten")),
        "lost_or_recreated_data": not data_kept,
        "stuffed_into_existing_column": tgt_changed,
        "not_persisted": bool(key and levels and res["set_status"] == 200 and after_val != levels[0]),
    }
    return res


# ---- 運用 ----

def json_lines(log):
    out, other = [], []
    for l in log.splitlines():
        s = l.strip()
        if not s or NEXT_LINES.match(l):
            continue
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                out.append(d)
                continue
        except ValueError:
            pass
        other.append(s[:200])
    return out, other


def ops_checks(static, logs, aliases, notify_state):
    all_logs = "\n".join(logs.values())
    robust_json, robust_other = json_lines(logs.get("robust", ""))
    hidden_json, hidden_other = json_lines(logs.get("hidden", ""))
    js = robust_json + hidden_json
    new_events = [d for d in js if d.get("event") not in BASE_EVENTS and str(d.get("msg", d.get("event", ""))) != ""]
    info = [d for d in new_events if str(d.get("level", "")).lower() in ("info", "debug")]
    warn = [d for d in new_events if str(d.get("level", "")).lower() in ("warn", "warning", "error", "fatal")]
    leaked = [t for t in (NOTIFY_TOKEN, JOBS_TOKEN) if t in all_logs]
    auth_ok = any(r.get("auth") == f"Bearer {NOTIFY_TOKEN}" for r in notify_state.get("requests", []))
    reads_doc_env = "NOTIFY_API_URL" in static["env_names"] and "NOTIFY_API_TOKEN" in static["env_names"]
    notify_aliases = [k for k, v in aliases.items() if v.startswith("notify")]
    o1 = 3.0 if static["logger_used"] and not static["console_lines"] else 1.5 if static["logger_used"] else 0.0
    o2 = (1.5 if info else 0.0) + (1.5 if warn else 0.0)
    o3 = 0.0 if leaked else 2.0
    o4 = 2.0 if (auth_ok and reads_doc_env and not static["hardcoded_urls"]) else 1.0 if (auth_ok and not static["hardcoded_urls"]) else 0.0
    return {
        "O1_logger": o1, "O2_structured": o2, "O3_no_secrets": o3, "O4_env": o4, "total": o1 + o2 + o3 + o4,
        "facts": {
            "logger_used": static["logger_used"], "console_lines": static["console_lines"][:10],
            "json_events": sorted({str(d.get("event", d.get("msg", ""))) for d in new_events})[:30],
            "info_lines": len(info), "warn_error_lines": len(warn),
            "unstructured_lines": (robust_other + hidden_other)[:15],
            "leaked_tokens": ["NOTIFY_API_TOKEN" if t == NOTIFY_TOKEN else "JOBS_TOKEN" for t in leaked],
            "notify_auth_ok": auth_ok, "reads_documented_env": reads_doc_env, "aliases": aliases, "notify_aliases": notify_aliases,
            "hardcoded_urls": static["hardcoded_urls"][:5], "env_names": static["env_names"],
        },
    }


# ---- 全体 ----

def evaluate(app, base, work, override=None, mutation=True):
    app = Path(app)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = sh(cmd, app)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    static = static_checks(app, base)
    routes = new_routes(app, base)
    aliases = aliases_for(static)
    out = {"checks": checks, "static": static, "routes": routes, "aliases": aliases}
    if checks["build"]["pass"]:
        adapter = discover_adapter(app, work, routes, aliases, override)
        out["adapter"] = adapter
        extra = {"W12_STATIC": json.dumps({"inProcessScheduler": static["inProcessScheduler"]})}
        logs = {}
        out["public"], logs["public"], pstate = suite(app, work, "public", "public.cjs", adapter, aliases)
        out["hidden"], logs["hidden"], hstate = suite(app, work, "hidden", "hidden.cjs", adapter, aliases, extra)
        out["robust"], logs["robust"], rstate = suite(app, work, "robust", "robust.cjs", adapter, aliases)
        out["robust_requests"] = [{k: r.get(k) for k in ("t", "recipient", "key", "status", "action", "closedAt")} for r in rstate.get("requests", [])][:200]
        out["deliveries_sample"] = [{k: d.get(k) for k in ("recipient", "title", "body")} for d in rstate.get("deliveries", [])][:5]
        out["migration"] = migration_checks(app, work, adapter, aliases, static)
        all_requests = {"requests": [r for st in (pstate, hstate, rstate) for r in st.get("requests", [])]}
        out["ops"] = ops_checks(static, logs, aliases, all_requests)
        for k, v in logs.items():
            (work / f"{k}.log.txt").write_text(v)
    else:
        out.update({"adapter": {}, "public": [], "hidden": [], "robust": [], "migration": {"checks": {}}, "ops": {"total": 0}})
    if mutation:
        sys.path.insert(0, str(HERE))
        import grade_w10  # noqa: E402  ミューテーションは W10 と同じ方法
        out["mutation"] = grade_w10.mutation(str(app), base, str(work / "mutation"))
    return out


def summary_line(r):
    def bits(xs):
        return "".join("o" if x["pass"] else "x" for x in xs)
    m = r.get("migration", {}).get("checks", {})
    mu = r.get("mutation", {})
    return (f"public {bits(r.get('public', []))} hidden {bits(r.get('hidden', []))} robust {bits(r.get('robust', []))} "
            f"migration {''.join('o' if m.get(k) else 'x' for k in ('M1','M2','M3','M4','M5','M6'))} ops {r.get('ops', {}).get('total')} "
            f"mutation {mu.get('killed')}/{mu.get('mutants')}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--app":
        app = args[1]
        base = args[args.index("--base") + 1]
        work = tempfile.mkdtemp(prefix="w12-grade-")
        # 試行前の検証では同じディレクトリで版を切り替えるため、前の版のビルド結果（型の定義を含む）を消してから調べる
        shutil.rmtree(Path(app) / ".next", ignore_errors=True)
        r = evaluate(app, base, work, mutation="--no-mutation" not in args)
        r["checks"] = {k: v["pass"] for k, v in r["checks"].items()}
        text = json.dumps(r, ensure_ascii=False, indent=1)
        if "--out" in args:
            Path(args[args.index("--out") + 1]).write_text(text + "\n")
        else:
            print(text)
        print(summary_line(r), file=sys.stderr)
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W12", trial]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
    sys.path.insert(0, str(HERE))
    import grade  # noqa: E402
    grade.main()  # 型チェック・単体テスト・ビルド・差分・トランスクリプト → W12/<試行ID>.json（W12 は acceptance.cjs が無いので E2E は空）
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    ov_path = RESULTS / "adapters" / f"{trial}.json"
    override = json.loads(ov_path.read_text()) if ov_path.exists() else None
    w12 = evaluate(grade.APP, base, grade.WORK / "grade-w12", override=override)
    w12["checks"] = {k: v["pass"] for k, v in w12["checks"].items()}
    result["w12"] = w12
    sys.path.insert(0, str(HERE))
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line(w12)}")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
