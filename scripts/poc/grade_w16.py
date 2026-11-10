#!/usr/bin/env python3
"""W16（ログから障害の原因を探す）の試行を採点用に調べ、results/workflow/W16/<試行ID>.json に書き出す。
設計は docs/poc/tasks/wf-W16-design.md、採点の決まりは docs/poc/answer-key/W16/grading.md（正解データ。作業用コピーには置かない）。

使い方:
  python3 scripts/poc/grade_w16.py <試行ID> [--cleanup]
    1. grade.py と同じ集計（型チェック・単体テスト・ビルド・差分・トランスクリプト）
    2. W16 固有の事実を w16 に足す
       - incident:   原因に効く修正か（I1〜I5。遅い・タイムアウトする偽の通知サービスと、重なったジョブの実行）
       - crash:      実行の途中でサーバーが止まったあとの回復（I6）
       - logs:       ログ・監視の改善（L1〜L3。I1〜I5 のサーバーのログから）
       - regression: 後退が無いか（W12 の受け入れ・隠し・堅牢さのテストのうち、出荷済みの版で通るもの）
       - prod:       本番の DB（11-10 朝の状態。出荷済みの version 5 + 二重の送信記録）で起動・データ・送り直し（M1〜M3）
       - static:     出荷済みのマイグレーション（version 1〜5）の書き換え（M4）、追加・変更したテスト
  python3 scripts/poc/grade_w16.py --app <アプリのディレクトリ> --base <コミット> [--out <JSON>]
    試行前の検証用（参照実装・最短の実装・半分の実装）。
  再発防止のテスト（再注入）は reinject_w16.py、原因の特定は judge_w16.py、点数は score_w16.py。
削除はしない（採点用の DB・ログは毎回新しい一時ディレクトリに作り、そのまま残す）。
"""
import importlib.util
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W16"
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W16"
JOBS_TOKEN = "jobs-tkn-16d0aeSECRETb71c"
NOTIFY_TOKEN = "ntf-tkn-9f20c4SECRET5d18"
# 出荷済みの版が出すログの event（L1 で「新しく足したログ」と区別する）
SHIPPED_EVENTS = {"auth.login_failed", "job.unauthorized", "calibration.failed", "loan.overdue", "job.completed", "job.started",
                  "job.misconfigured", "calibration_reminder.sent", "calibration_reminder.failed", "calibration_reminder.no_manager",
                  "notify.retry"}
# W12 のテストを、出荷済みの版の名前で動かすためのアダプター（候補が名前を変えたときは adapters/<試行ID>.json で補正）
ADAPTER = {"key": "importance", "levels": ["A", "B", "C"], "default": "B", "default_existing": "B", "set": "post",
           "filter": {"api": True, "page": True, "param": "importance"},
           "job": {"method": "POST", "path": "/api/jobs/calibration-reminders", "unauthStatus": 401}}
# 出荷済みの版（base）で合格する W12 の項目（後退の確認に使う。試行前に base で確かめて固定。grading.md）
BASELINE_PASS = json.loads((KEY / "baseline-pass.json").read_text()) if (KEY / "baseline-pass.json").exists() else None

_spec = importlib.util.spec_from_file_location("data_w16", KEY / "data_w16.py")
DATA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DATA)

NODE_PATH = None


def node_path():
    global NODE_PATH
    if NODE_PATH is None:
        NODE_PATH = subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip()
    return NODE_PATH


def sh(cmd, cwd, timeout=900, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout + p.stderr


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, seconds=90):
    for _ in range(seconds * 4):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.25)
    return False


def git(app, *args):
    return subprocess.run(["git", *args], cwd=app, capture_output=True, text=True).stdout


def norm_sql(s):
    return re.sub(r"\s+", " ", s).strip()


def migrations_of(app):
    script = ("import('./src/lib/db/migrations.ts').then(m => console.log(JSON.stringify("
              "(m.MIGRATIONS || []).map(x => ({version: x.version, name: x.name, sql: x.sql})))))")
    code, out = sh(f"node --experimental-strip-types --no-warnings -e \"{script}\"", app, timeout=60)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def export_base(app, base, what="src"):
    d = Path(tempfile.mkdtemp(prefix="w16-base-"))
    subprocess.run(f"git -C {app} archive {base} {what} | tar -x -C {d}", shell=True, check=True)
    return d


def static_checks(app, base):
    bdir = export_base(app, base)
    before, after = migrations_of(bdir), migrations_of(app)
    mig = {"readable": after is not None}
    if after is not None and before is not None:
        old = {m["version"]: norm_sql(m["sql"]) for m in before}
        new = {m["version"]: norm_sql(m["sql"]) for m in after}
        mig["rewritten"] = [v for v in old if new.get(v) != old[v]]
        mig["added"] = [m["version"] for m in after if m["version"] not in old]
    changed = git(app, "diff", "--name-status", base, "HEAD").splitlines()
    tests = [l.split("\t")[-1] for l in changed if re.search(r"(^|/)tests?/|\.test\.", l.split("\t")[-1])]
    src = [l.split("\t")[-1] for l in changed if l.split("\t")[-1].startswith("src/") and ".test." not in l]
    docs = [l.split("\t")[-1] for l in changed if re.search(r"\.(md|txt)$", l.split("\t")[-1])]
    return {"migrations": mig, "changed_tests": tests, "changed_src": src, "changed_docs": docs,
            "incident_log_touched": any("incident/" in l for l in changed)}


# ---- サーバーと偽の通知サービス ----

class Env:
    """偽の通知サービス 1 つと、候補のアプリのサーバー 1 つ（偽の時計・DB ファイル・ログの記録つき）。"""

    def __init__(self, app, work, name, db_path=None, now="2026-11-10T00:00:00.000Z", server_env=None):
        self.app, self.work, self.name = Path(app), Path(work), name
        self.work.mkdir(parents=True, exist_ok=True)
        self.clock = self.work / f"{name}.now"
        self.clock.write_text(now + "\n")
        self.db = Path(db_path) if db_path else self.work / f"{name}.db"
        self.log = self.work / f"{name}.server.log"
        self.server_env = server_env or {}
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
            **self.server_env,
        })
        self.logf = open(self.log, "a")
        self.server = subprocess.Popen(f"npx next start -p {self.port}", cwd=self.app, shell=True, env=env,
                                       stdout=self.logf, stderr=self.logf, start_new_session=True)
        return wait_port(self.port, 90)

    def kill_server(self, sig=signal.SIGTERM):
        if self.server:
            try:
                os.killpg(self.server.pid, sig)
            except ProcessLookupError:
                pass
            try:
                self.server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.server.pid, signal.SIGKILL)
                self.server.wait(timeout=30)
            self.server = None
            self.logf.close()
            time.sleep(1)

    def stop(self):
        self.kill_server()
        if self.notify:
            os.killpg(self.notify.pid, 15)
            self.notify = None

    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def run_cjs(self, name, adapter, args=(), timeout=1800):
        env = dict(os.environ, NODE_PATH=node_path(), W12_ADAPTER=json.dumps(adapter), W12_NOTIFY=f"http://127.0.0.1:{self.notify_port}",
                   W12_JOBS_TOKEN=JOBS_TOKEN, POC_FAKE_NOW_FILE=str(self.clock), W12_STATIC=json.dumps({"inProcessScheduler": []}))
        p = subprocess.run(["node", str(KEY / name), self.base(), *args], cwd=self.app, capture_output=True, text=True,
                           timeout=timeout, env=env)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return [{"id": "X", "name": f"{name} の実行", "pass": False, "detail": (p.stdout + p.stderr)[-800:]}]

    def notify_state(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.notify_port}/__state", timeout=10) as r:
            return json.loads(r.read())


TIMEOUT_ENV = {"NOTIFY_API_TIMEOUT_MS": "2000"}  # 本番の既定 10 秒の代わり（I3・I4・I5 を短い時間で再現する）


def suite(app, work, name, script, adapter, args=(), server_env=None):
    e = Env(app, work, name, server_env=server_env)
    e.start_notify()
    try:
        if not e.start_server():
            return [{"id": "X", "name": "サーバーの起動", "pass": False, "detail": e.log.read_text()[-500:]}], e.log.read_text(), {}
        res = e.run_cjs(script, adapter, args)
        state = e.notify_state()
    finally:
        e.stop()
    return res, e.log.read_text(), state


def crash_suite(app, work, adapter):
    """I6a・I6b: ジョブの途中でサーバーを強制終了し、起動し直して、3 時間後・翌朝の実行で残りが届くか（同じ DB で a → b の順）。"""
    e = Env(app, work, "crash", server_env=TIMEOUT_ENV)
    e.start_notify()
    res_all, states = [], {}
    try:
        if not e.start_server():
            return [{"id": "I6a", "name": "サーバーの起動", "pass": False, "detail": e.log.read_text()[-500:]},
                    {"id": "I6b", "name": "サーバーの起動", "pass": False, "detail": ""}], {}
        for v in ("a", "b"):
            file = Path(work) / f"crash-insts-{v}.json"
            e.run_cjs("incident.cjs", adapter, ["crash-setup", str(file), v], timeout=300)
            mid = e.notify_state()
            e.kill_server(signal.SIGKILL)
            if not e.start_server():
                res_all.append({"id": f"I6{v}", "name": "サーバーの再起動", "pass": False, "detail": e.log.read_text()[-500:]})
                break
            res_all += e.run_cjs("incident.cjs", adapter, ["crash-check", str(file), v], timeout=900)
            states[v] = {"requests_at_kill": len(mid.get("requests", []))}
    finally:
        e.stop()
    return res_all, states


# ---- ログ・監視（L1〜L3） ----

def json_lines(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                v = json.loads(line)
                if isinstance(v, dict):
                    out.append(v)
            except ValueError:
                pass
    return out


LOCK_WORDS = re.compile(r"lock|already|running|concurr|overlap|skip|busy|in.?progress|duplicat|claim|in.?flight|多重|実行中|重複", re.I)
RUN_FIELD = re.compile(r"^(run|exec|trace|request|correlation|invocation|job)_?(id|Id|ID)$|^runId$|^run$", re.I)


def log_checks(log, incident, state):
    lines = json_lines(log)
    # L1: 実行が重なったこと（2 回目を止めた・待たせた・送らなかった）が、出荷済みの版に無い形でログに出る
    new_lines = [l for l in lines if str(l.get("event", l.get("msg", ""))) not in SHIPPED_EVENTS]
    l1_hits = [l for l in new_lines if LOCK_WORDS.search(json.dumps(l, ensure_ascii=False))]
    l1_hits += [l for l in lines if str(l.get("event")) in SHIPPED_EVENTS and any(LOCK_WORDS.search(k) for k in l if k not in ("skipped",))]
    # L2: 通知サービスへの要求の Idempotency-Key が、アプリのログに出る（通知サービス側の記録と突き合わせられる）
    keys = {r.get("key") for r in state.get("requests", []) if r.get("key")}
    text = log
    l2_keys = sorted(k for k in keys if k and k in text)
    # L3: ジョブの実行ごとの識別子が、ジョブの開始・終了などのログに付き、重なった実行を区別できる
    run_ids = {}
    for l in lines:
        if "job" in str(l.get("event", "")) or l.get("job") == "calibration-reminders" or "reminder" in str(l.get("event", "")):
            for k, v in l.items():
                if RUN_FIELD.search(k) and isinstance(v, (str, int)) and str(v) and k != "job":
                    run_ids.setdefault(k, set()).add(str(v))
    l3 = any(len(v) >= 2 for v in run_ids.values())
    return {
        "L1": bool(l1_hits), "L1_examples": [json.dumps(l, ensure_ascii=False)[:200] for l in l1_hits[:3]],
        "L2": bool(l2_keys), "L2_examples": l2_keys[:3], "keys_seen": len(keys),
        "L3": l3, "L3_fields": {k: len(v) for k, v in run_ids.items()},
        "console_lines": [l[:160] for l in log.splitlines() if l.strip() and not l.strip().startswith("{") and not re.match(
            r"^\s*(▲ Next\.js|- Local:|- Network:|✓ Starting|✓ Ready|Starting\.\.\.|> |⚠ |\(node:\d+\)|\(Use `node)", l)][:10],
    }


# ---- 本番の DB（M1〜M3） ----

def make_prod_db(app, base, path):
    """old-db.sql（version 4）に、出荷済みのコード（baseline）でマイグレーションを当て、本番の 11-10 朝の状態を書き込む。"""
    con = sqlite3.connect(path)
    con.executescript((KEY / "old-db.sql").read_text())
    con.close()
    bdir = export_base(app, base)
    (bdir / "mk.mjs").write_text("import { openDb } from './src/lib/db/index.ts';\nopenDb(process.argv[2]).close();\n")
    code, out = sh(f"node --experimental-strip-types --no-warnings mk.mjs {path}", bdir, timeout=120)
    if code != 0:
        raise RuntimeError(out[-500:])
    DATA.build_prod_db(str(path))


def db_rows(path, sql):
    con = sqlite3.connect(path, timeout=30)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def http(base, method, path, body=None, cookie=None, token=None):
    h = {"content-type": "application/json"}
    if cookie:
        h["cookie"] = cookie
    if token:
        h["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode(), r.headers.get_all("set-cookie") or []
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), []
    except OSError as e:
        return 0, str(e), []


def prod_checks(app, base, work):
    work = Path(work)
    db = work / "prod.db"
    make_prod_db(app, base, db)
    before = {
        "instruments": db_rows(db, "SELECT COUNT(*) FROM instruments")[0][0],
        "records": db_rows(db, "SELECT COUNT(*) FROM calibration_records")[0][0],
        "notifications": sorted(r[0] for r in db_rows(db, "SELECT id FROM calibration_notifications")),
    }
    # 11-11 7:30（日本時間）の cron。本番の DB では、送信済みのお知らせはすべて 11-09・11-10 に送ってある
    e = Env(app, work, "prod", db_path=db, now="2026-11-10T22:30:00.000Z", server_env=TIMEOUT_ENV)
    e.start_notify()
    out = {"M1": False, "M2": False, "M3": False, "detail": {}}
    try:
        if not e.start_server():
            out["detail"]["start"] = e.log.read_text()[-800:]
            return out
        code, body, cookies = http(e.base(), "POST", "/api/login", {"userId": "sato", "password": "password"})
        cookie = "; ".join(c.split(";")[0] for c in cookies)
        lc, lbody, _ = http(e.base(), "GET", "/api/instruments", cookie=cookie)
        try:
            n = len(json.loads(lbody).get("instruments", []))
        except ValueError:
            n = -1
        out["M1"] = code == 200 and lc == 200 and n == before["instruments"]
        out["detail"]["start"] = {"login": code, "list": lc, "instruments": n}
        jc, jbody, _ = http(e.base(), "POST", "/api/jobs/calibration-reminders", token=JOBS_TOKEN)
        time.sleep(1.5)
        state = e.notify_state()
        sent = DATA.sent_targets()
        resent = []
        for r in state.get("requests", []):
            text = f"{r.get('title', '')}\n{r.get('body', '')}"
            kind = "overdue" if "期限切れ" in r.get("title", "") or "過ぎて" in text else "due_soon"
            for no, k, due, rcp in sent:
                if no in text and rcp == r.get("recipient") and k == kind:
                    resent.append(f"{no}/{rcp}/{k}")
        others = [f"{r.get('recipient')}:{r.get('title', '')[:40]}" for r in state.get("requests", [])]
        out["M3"] = 200 <= jc < 300 and not resent
        out["detail"]["job"] = {"status": jc, "body": jbody[:300], "resent": resent, "requests": others}
    finally:
        e.stop()
    after_ids = sorted(r[0] for r in db_rows(db, "SELECT id FROM calibration_notifications")) if db_rows(
        db, "SELECT name FROM sqlite_master WHERE name = 'calibration_notifications'") else []
    out["M2"] = (db_rows(db, "SELECT COUNT(*) FROM instruments")[0][0] == before["instruments"]
                 and db_rows(db, "SELECT COUNT(*) FROM calibration_records")[0][0] == before["records"]
                 and set(before["notifications"]) <= set(after_ids))
    out["detail"]["rows"] = {"before": len(before["notifications"]), "after": len(after_ids)}
    return out


# ---- 全体 ----

def evaluate(app, base, work, adapter=None):
    app, work = Path(app), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    adapter = adapter or ADAPTER
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = sh(cmd, app)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    out = {"checks": checks, "static": static_checks(app, base), "adapter": adapter}
    if not checks["build"]["pass"]:
        out.update({"incident": [], "crash": [], "logs": {}, "regression": {}, "prod": {}})
        return out
    inc, inc_log, inc_state = suite(app, work, "incident", "incident.cjs", adapter, ["main"], server_env=TIMEOUT_ENV)
    out["incident"] = [r for r in inc if r["id"] != "_facts"]
    out["incident_facts"] = next((json.loads(r["detail"]) for r in inc if r["id"] == "_facts"), {})
    out["crash"], out["crash_state"] = crash_suite(app, work, adapter)
    out["logs"] = log_checks(inc_log, inc, inc_state)
    reg = {}
    for name in ("public", "hidden", "robust"):
        res, _, _ = suite(app, work, name, f"{name}.cjs", adapter)
        reg[name] = res
    out["regression"] = reg
    out["prod"] = prod_checks(app, base, work)
    return out


def bits(xs):
    return "".join("o" if x["pass"] else "x" for x in xs)


def summary_line(r):
    reg = r.get("regression", {})
    p = r.get("prod", {})
    lg = r.get("logs", {})
    return (f"checks {''.join('o' if r['checks'][k]['pass'] else 'x' for k in ('typecheck', 'test', 'build'))} "
            f"incident {bits(r.get('incident', []))} crash {bits(r.get('crash', []))} "
            f"logs {''.join('o' if lg.get(k) else 'x' for k in ('L1', 'L2', 'L3'))} "
            f"public {bits(reg.get('public', []))} hidden {bits(reg.get('hidden', []))} robust {bits(reg.get('robust', []))} "
            f"prod {''.join('o' if p.get(k) else 'x' for k in ('M1', 'M2', 'M3'))} "
            f"rewritten {r['static']['migrations'].get('rewritten')}")


def load_adapter(trial):
    ov = RESULTS / "adapters" / f"{trial}.json"
    return {**ADAPTER, **json.loads(ov.read_text())} if ov.exists() else ADAPTER


def main():
    args = sys.argv[1:]
    if args and args[0] == "--app":
        app = args[1]
        base = args[args.index("--base") + 1]
        work = tempfile.mkdtemp(prefix="w16-grade-")
        r = evaluate(app, base, work)
        r["checks"] = {k: v["pass"] for k, v in r["checks"].items()}
        r["work"] = work
        text = json.dumps(r, ensure_ascii=False, indent=1)
        if "--out" in args:
            Path(args[args.index("--out") + 1]).write_text(text + "\n")
        else:
            print(text)
        print(summary_line({**r, "checks": {k: {"pass": v} for k, v in r["checks"].items()}}), file=sys.stderr)
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W16", trial]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
    sys.path.insert(0, str(HERE))
    import grade  # noqa: E402
    grade.main()
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    w16 = evaluate(grade.APP, base, Path(tempfile.mkdtemp(prefix=f"w16-grade-{trial}-")), load_adapter(trial))
    w16["checks"] = {k: v["pass"] for k, v in w16["checks"].items()}
    result["w16"] = w16
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line({**w16, 'checks': {k: {'pass': v} for k, v in w16['checks'].items()}})}")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
