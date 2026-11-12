#!/usr/bin/env python3
"""W14（安全な DB 移行: 設置場所を自由入力から場所マスタへ）の試行を採点用に調べ、results/workflow/W14/<試行ID>.json に書き出す。
設計は poc/tasks/wf-W14-design.md、採点の決まりは poc/answer-key/W14/grading.md（正解データ。作業用コピーには置かない）。

使い方:
  python3 poc/scripts/grade_w14.py <試行ID> [--cleanup]
    1. grade.py と同じ集計（型チェック・単体テスト・ビルド・差分・トランスクリプト）
    2. W14 固有の事実を w14 に足す
       - discovery: 候補の場所マスタの表・計測器の参照の列・API（DB と追加された Route から自動で見つける。補正は W14/adapters/<試行ID>.json）
       - public / hidden: 新しい DB で起動し、場所マスタ・計測器の API・ハンディ端末の古い API を確かめる
       - migration: 旧スキーマ（version 4）+ 本番相当の 5 万件の DB で起動し、データが消えない・起動が止まらない・書き込みが止まらない・
                    埋め戻しが終わる・古い列が残り両方に書かれる・前の版のアプリに戻しても動く、を確かめる
       - normalize: 移行後の DB で、表記ゆれの寄せの正しさ（正解は answer-key/W14/data_w14.py）
       - ops / static / mutation: 構造化ログ・手順書、既存のマイグレーションの書き換え、テストの強さ（grade_w10.mutation）
  python3 poc/scripts/grade_w14.py --app <アプリのディレクトリ> --base <コミット> [--out <JSON>] [--no-mutation]
    試行前の検証用（参照実装・最短の実装・半分の実装）。
削除はしない（採点用の DB・ログは毎回新しい一時ディレクトリに作り、そのまま残す）。
"""
import http.cookiejar
import importlib.util
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "poc" / "answer-key" / "W14"
RESULTS = ROOT / "poc" / "results" / "workflow" / "W14"
JOBS_TOKEN = "jobs-tkn-3f9a14SECRETc07d"
HANDHELD_TOKEN = "hh-tkn-81be55SECRET2a90"

_spec = importlib.util.spec_from_file_location("data_w14", KEY / "data_w14.py")
DATA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DATA)


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


def built_base(app, base):
    """初期状態（base）のアプリを書き出してビルドしたディレクトリを返す。中身（git の木）ごとに 1 回だけ作って使い回す
    （2026-11-10 追加: 採点のたびに書き出してビルドしていたため、一時領域が一杯になった）。失敗したら (None, ログ)。"""
    import fcntl
    tree = git(app, "rev-parse", f"{base}^{{tree}}").strip()
    root = Path("/tmp/poc-base-build")
    root.mkdir(exist_ok=True)
    d = root / tree
    with open(root / f"{tree}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (d / ".next" / "BUILD_ID").exists():
            return d, ""
        d.mkdir(exist_ok=True)
        subprocess.run(f"git -C {app} archive {base} . | tar -x -C {d}", shell=True, check=True)
        if not (d / "node_modules").exists():
            subprocess.run(["cp", "-al", str((Path(app) / "node_modules").resolve()), str(d / "node_modules")], check=False)
        code, out = sh("npx next build", d, timeout=900)
        return (d, "") if code == 0 else (None, out[-400:])


def export_base(app, base, what="src"):
    d = Path(tempfile.mkdtemp(prefix="w14-base-"))
    subprocess.run(f"git -C {app} archive {base} {what} | tar -x -C {d}", shell=True, check=True)
    return d


def added_lines(app, base, paths):
    out, cur = [], None
    for line in git(app, "diff", "-U0", base, "HEAD", "--", *paths).splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and not line.startswith("+++") and cur:
            out.append((cur, line[1:]))
    return out


def static_checks(app, base):
    lines = [(f, l) for f, l in added_lines(app, base, ["src"]) if ".test." not in f]
    code = "\n".join(l for _, l in lines)
    bdir = export_base(app, base)
    before, after = migrations_of(bdir), migrations_of(app)
    mig = {"readable": after is not None}
    if after is not None and before is not None:
        old = {m["version"]: norm_sql(m.get("sql", "")) for m in before}
        new = {m["version"]: norm_sql(m.get("sql", "")) for m in after}
        mig["rewritten"] = [v for v in old if new.get(v) != old[v]]
        mig["added"] = [m["version"] for m in after if m["version"] not in old]
        added_sql = " ".join(m.get("sql", "") for m in after if m["version"] not in old)
        mig["drops_location"] = bool(re.search(r"DROP\s+COLUMN\s+\"?location\"?\b|DROP\s+TABLE\s+\"?instruments\"?", added_sql, re.I))
        mig["rebuilds_instruments"] = bool(re.search(r"CREATE\s+TABLE\s+\"?instruments_\w*|ALTER\s+TABLE\s+\w+\s+RENAME\s+TO\s+\"?instruments", added_sql, re.I))
        mig["updates_in_sql"] = bool(re.search(r"\bUPDATE\s+\"?instruments\b", added_sql, re.I))
    docs = [(f, l) for f, l in added_lines(app, base, ["docs", "README.md", "CLAUDE.md"])]
    doc_text = "\n".join(l for _, l in docs)
    return {
        "migrations": mig,
        "logger_used": bool(re.search(r"\blogger\.(info|warn|error|debug)\s*\(", code)),
        "console_lines": [l.strip()[:160] for f, l in lines if re.search(r"\bconsole\.(log|info|warn|error|debug)\s*\(", l)],
        "doc_files": sorted({f for f, _ in docs}),
        "doc_rollback": bool(re.search(r"戻し|戻す|ロールバック|rollback|切り戻", doc_text, re.I)),
        "doc_steps": bool(re.search(r"手順|段階|移行", doc_text)),
        "new_deps": git(app, "diff", base, "HEAD", "--", "package.json").count("\n+  ") > 0,
        "changed_src_files": sorted({f for f, _ in lines}),
    }


def new_routes(app, base):
    names = git(app, "diff", "--name-only", "--diff-filter=AM", base, "HEAD", "--", "src/app").split()
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


# ---- HTTP ----

class Client:
    def __init__(self, base, token=None):
        self.base = base
        self.token = token
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None, headers=None, timeout=120):
        data = json.dumps(body).encode() if body is not None else None
        h = {"content-type": "application/json", **(headers or {})}
        if self.token:
            h["authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        t0 = time.time()
        try:
            with self.opener.open(req, timeout=timeout) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            return {"status": 0, "json": None, "text": str(e), "ms": (time.time() - t0) * 1000}
        text = raw.decode("utf-8", "replace")
        try:
            j = json.loads(text)
        except ValueError:
            j = None
        return {"status": status, "json": j, "text": text[:2000], "ms": (time.time() - t0) * 1000}

    def login(self, user="sato"):
        r = self.call("POST", "/api/login", {"userId": user, "password": "password"})
        if r["status"] != 200:
            raise RuntimeError(f"login {r['status']} {r['text'][:200]}")
        return self


class Server:
    def __init__(self, app, work, name, db_path):
        self.app, self.work, self.name, self.db = Path(app), Path(work), name, Path(db_path)
        self.log = self.work / f"{name}.server.log"
        self.proc = None

    def start(self):
        self.port = free_port()
        env = dict(os.environ, DATABASE_PATH=str(self.db), JOBS_TOKEN=JOBS_TOKEN, HANDHELD_TOKEN=HANDHELD_TOKEN, NODE_ENV="production")
        self.logf = open(self.log, "a")
        self.proc = subprocess.Popen(f"npx next start -p {self.port}", cwd=self.app, shell=True, env=env,
                                     stdout=self.logf, stderr=self.logf, start_new_session=True)
        return wait_port(self.port, 90)

    def stop(self):
        if self.proc:
            try:
                os.killpg(self.proc.pid, 15)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, 9)
            self.proc = None
            self.logf.close()
            time.sleep(1)

    def base(self):
        return f"http://127.0.0.1:{self.port}"


# ---- DB ----

def make_old_db(app, base, path):
    """初期状態（baseline）のコードで旧スキーマ + 初期データの DB を作り、本番相当の 5 万件を足す。"""
    bdir = export_base(app, base)
    script = bdir / "mk.mjs"
    script.write_text("import { openDb } from './src/lib/db/index.ts';\nopenDb(process.argv[2]).close();\n")
    code, out = sh(f"node --experimental-strip-types --no-warnings mk.mjs {path}", bdir, timeout=120)
    if code != 0:
        raise RuntimeError(out[-500:])
    DATA.build_db(str(path))


def copy_db(src, dst):
    s = sqlite3.connect(src)
    d = sqlite3.connect(dst)
    s.backup(d)
    d.close()
    s.close()


def db_query(path, sql, args=()):
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


BASE_COLS = ["id", "management_no", "name", "model", "location", "manager_id", "interval_months", "last_calibrated_on", "status", "note"]


def discover_schema(db_path, base_tables):
    """候補の場所マスタの表・名前の列・使用中の列と、計測器から参照する列を DB から見つける。"""
    tables = [r["name"] for r in db_query(db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    new_tables = [t for t in tables if t not in base_tables]
    cols = {t: db_query(db_path, f'PRAGMA table_info("{t}")') for t in tables}
    inst_cols = [c["name"] for c in cols.get("instruments", [])]
    fks = db_query(db_path, 'PRAGMA foreign_key_list("instruments")')
    out = {"new_tables": new_tables, "instrument_new_columns": [c for c in inst_cols if c not in BASE_COLS], "master": None,
           "name_col": None, "active_col": None, "fk_col": None, "location_col_kept": "location" in inst_cols, "notes": []}
    cand = [f for f in fks if f["table"] in new_tables]
    if cand:
        out["master"], out["fk_col"] = cand[0]["table"], cand[0]["from"]
    else:
        for t in new_tables:
            if re.search(r"loc|place|site|area|場所", t, re.I):
                out["master"] = t
                break
        for c in out["instrument_new_columns"]:
            if re.search(r"loc|place|site|area", c, re.I) and re.search(r"_id$|Id$|^id_", c):
                out["fk_col"] = c
                out["notes"].append(f"外部キーの宣言が無い。列名から {c} とした")
                break
    if out["master"]:
        mcols = cols[out["master"]]
        texts = [c["name"] for c in mcols if "CHAR" in (c["type"] or "").upper() or "TEXT" in (c["type"] or "").upper() or not c["type"]]
        for c in texts:
            if re.fullmatch(r"(name|label|title|display_name|location_name|place_name)", c, re.I):
                out["name_col"] = c
                break
        out["name_col"] = out["name_col"] or (texts[0] if texts else None)
        for c in mcols:
            if re.search(r"active|retired|disabled|archived|deleted|status|in_use|enabled|obsolete|ended", c["name"], re.I):
                out["active_col"] = c["name"]
                break
    return out


def norm_name(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


# ---- API の見つけ方 ----

def camel(s):
    return re.sub(r"_([a-z])", lambda m: m.group(1).upper(), s)


def discover_api(c, routes, schema):
    """場所マスタの一覧・追加・変更の API と、計測器で場所を指定する項目名を見つける。"""
    out = {"list": None, "item": None, "id_key": None, "notes": []}
    cands = [r for r in routes if re.search(r"loc|place|site|area", r["path"], re.I) and "[" not in r["path"]]
    for r in cands:
        if "GET" in r["methods"]:
            res = c.call("GET", r["path"])
            items = list_from(res["json"])
            if res["status"] == 200 and items:
                out["list"] = r["path"]
                break
    if out["list"]:
        for r in routes:
            if r["path"].startswith(out["list"] + "/[") and r["path"].count("[") == 1:
                out["item"] = r["path"]
                out["item_methods"] = r["methods"]
    keys = []
    if schema.get("fk_col"):
        keys.append(camel(schema["fk_col"]))
        keys.append(schema["fk_col"])
    keys += ["locationId", "location_id", "placeId", "siteId"]
    out["id_key_candidates"] = list(dict.fromkeys(keys))
    return out


def list_from(j):
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def item_from(j):
    if isinstance(j, dict):
        for k in ("location", "place", "site", "data", "item"):
            if isinstance(j.get(k), dict):
                return j[k]
        if "id" in j:
            return j
    return None


def retired_mark(item):
    """場所マスタの 1 件に、使用終了の印が付いているか。"""
    for k in ("active", "isActive", "inUse", "enabled", "available", "selectable"):
        if item.get(k) is False or item.get(k) == 0:
            return True
    for k in ("retired", "archived", "isRetired", "inactive", "disabled", "ended"):
        if item.get(k) is True or item.get(k) == 1:
            return True
    for k in ("retiredAt", "archivedAt", "endedAt", "inactiveAt", "deactivatedAt", "retired_at", "archived_at"):
        if item.get(k):
            return True
    return str(item.get("status", "")).lower() in ("retired", "inactive", "ended", "archived", "disabled", "使用終了")


def filter_params(app):
    """一覧の絞り込みに使えそうなクエリ（キー=値）を作る。既定の候補に、候補のコードにあるクエリの名前と値を足す
    （試行の採点で ?location=pending・?locationCheck=…・?locationPending=… を見落としていたので直した。判断の記録に書く）。"""
    keys = ["locationStatus", "unresolved", "pending", "needsReview", "unmapped", "unmatched", "location", "locationState", "status",
            "location_status", "review", "unconfirmed", "locationUnresolved", "filter", "locationCheck", "locationPending", "locationReview",
            "locationUnmatched", "locationId"]
    vals = ["unresolved", "pending", "unmatched", "unmapped", "unconfirmed", "review", "needsReview", "needs_review", "1", "true",
            "unknown", "check", "unassigned"]
    for f in list((Path(app) / "src" / "app").rglob("*.ts*")):
        if "instruments" not in str(f) and "locations" not in str(f):
            continue
        t = f.read_text(errors="ignore")
        keys += re.findall(r"searchParams\.get\(\s*[\"'](\w+)[\"']", t)
        keys += re.findall(r"(\w+)\?\s*:\s*string", t)
        vals += re.findall(r"===\s*[\"']([A-Za-z_]+)[\"']", t)
    keys = [k for k in dict.fromkeys(keys) if k not in ("id", "name", "password", "userId", "q")]
    vals = list(dict.fromkeys(vals))
    out = []
    for k in keys:
        for v in vals:
            out.append(f"{k}={v}")
    return out


def loc_name(item):
    for k in ("name", "label", "title", "displayName", "locationName"):
        if isinstance(item.get(k), str):
            return item[k]
    return None


class Probe:
    """公開・隠しの項目の結果を集める。"""

    def __init__(self):
        self.results = []

    def check(self, id, name, fn):
        try:
            detail = fn()
            self.results.append({"id": id, "name": name, "pass": True, "detail": str(detail or "")[:300]})
        except Exception as e:  # noqa: BLE001
            self.results.append({"id": id, "name": name, "pass": False, "detail": str(e)[:400]})


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def show(r):
    return f"{r['status']} {r['text'][:200]}"


def api_suite(app, work, routes, base):
    """新しい DB（初期データ）で起動し、課題文の範囲（公開）と隠れ要件（隠し）を確かめる。"""
    db = Path(work) / "suite.db"
    srv = Server(app, work, "suite", db)
    pub, hid = Probe(), Probe()
    info = {}
    if not srv.start():
        return [{"id": "X", "name": "サーバーの起動", "pass": False, "detail": srv.log.read_text()[-400:]}], [], info
    try:
        c = Client(srv.base()).login()
        c.call("GET", "/api/instruments")
        time.sleep(3)  # 裏で寄せる実装のために少し待つ
        schema = discover_schema(db, base_tables=["departments", "users", "sessions", "instruments", "loans", "calibration_records"])
        api = discover_api(c, routes, schema)
        override = json.loads(os.environ.get("W14_OVERRIDE") or "{}")
        api.update({k: v for k, v in override.items() if k in ("list", "item", "id_key")})
        info.update({"schema": schema, "api": api})
        state = {}

        def create_loc(name):
            r = c.call("POST", api["list"], {"name": name})
            need(r["status"] in (200, 201), f"場所を追加できない: {show(r)}")
            it = item_from(r["json"])
            if not it or "id" not in it:
                lst = list_from(c.call("GET", api["list"])["json"])
                it = next((x for x in lst if loc_name(x) == name), None)
            need(it and "id" in it, f"追加した場所の ID が分からない: {show(r)}")
            return it["id"]

        def make(no, extra):
            body = {"managementNo": no, "name": f"検証用 {no}", "model": "T-1", "managerId": "sato", "intervalMonths": 12,
                    "lastCalibratedOn": "2026-04-01", **extra}
            return c.call("POST", "/api/instruments", body)

        def find_key(loc_id):
            for k in ([api["id_key"]] if api.get("id_key") else api["id_key_candidates"]):
                r = make(f"PK-{len(state) + 1:04d}", {k: loc_id})
                state[f"probe{len(state)}"] = 1
                if r["status"] == 201:
                    it = (r["json"] or {}).get("instrument") or r["json"]
                    if it and any(v == loc_id for v in it.values() if isinstance(v, int)) or (it or {}).get(k) == loc_id:
                        api["id_key"] = k
                        return k
            raise AssertionError("場所の ID で計測器を登録できる項目名が見つからない")

        def get_inst(iid):
            r = c.call("GET", f"/api/instruments/{iid}")
            return (r["json"] or {}).get("instrument") or {}

        # 公開（課題文の範囲）
        def p1():
            need(api["list"], "場所マスタの一覧の API が見つからない")
            items = list_from(c.call("GET", api["list"])["json"])
            need(len(items) >= 1 and loc_name(items[0]) is not None, "一覧に名前のある場所が無い")
            state["master_names"] = [loc_name(x) for x in items]
            return f"{api['list']} {len(items)} 件"
        pub.check("P1", "場所マスタの一覧を取得できる", p1)

        def p2():
            state["locA"] = create_loc("検証用 場所 A")
            state["locB"] = create_loc("検証用 場所 B")
            names = [loc_name(x) for x in list_from(c.call("GET", api["list"])["json"])]
            need("検証用 場所 A" in names, "追加した場所が一覧に出ない")
        pub.check("P2", "場所マスタに場所を追加できる", p2)

        def p3():
            key = find_key(state["locA"])
            r = make("PV-0001", {key: state["locA"]})
            need(r["status"] == 201, f"登録できない: {show(r)}")
            iid = ((r["json"] or {}).get("instrument") or {}).get("id")
            state["inst1"] = iid
            g = get_inst(iid)
            need(g.get(key) == state["locA"], f"場所の ID が保存されない: {g}")
            need(g.get("location") == "検証用 場所 A", f"location が場所の名前になっていない: {g.get('location')!r}")
            return key
        pub.check("P3", "計測器の登録で場所マスタの場所を選べる", p3)

        def p4():
            key = api["id_key"]
            r = c.call("PATCH", f"/api/instruments/{state['inst1']}", {key: state["locB"]})
            need(r["status"] == 200, f"変更できない: {show(r)}")
            lst = list_from(c.call("GET", "/api/instruments")["json"])
            row = next((x for x in lst if x.get("id") == state["inst1"]), {})
            need(row.get("location") == "検証用 場所 B", f"一覧の場所の名前が変わらない: {row.get('location')!r}")
        pub.check("P4", "計測器の編集で場所を変えられ、一覧に場所の名前が出る", p4)

        # 隠し（隠れ要件）
        def h01():
            key = api["id_key"]
            need(key, "場所の項目名が分からない")
            r = make("PV-0002", {key: 999999})
            need(400 <= r["status"] < 500, f"存在しない場所で登録できてしまう: {show(r)}")
            r2 = make("PV-0003", {"location": "勝手に書いた場所"})
            g = None
            if r2["status"] == 201:
                g = ((r2["json"] or {}).get("instrument") or {})
                need(g.get("location") != "勝手に書いた場所" or g.get(key) is not None,
                     "新しい API で自由入力の場所がそのまま登録できてしまう")
            return f"存在しない ID: {r['status']} / 自由入力: {r2['status']}"
        hid.check("H01", "場所マスタに無い場所（存在しない ID・自由入力）では登録できない", h01)

        def h03():
            r = make("PV-0004", {})
            need(r["status"] == 201, f"場所なしで登録できない: {show(r)}")
            g = ((r["json"] or {}).get("instrument") or {})
            need(not g.get("location"), f"未設定のはずが {g.get('location')!r}")
            if api.get("id_key"):
                r2 = make("PV-0005", {api["id_key"]: None})
                need(r2["status"] == 201, f"場所を null で登録できない: {show(r2)}")
        hid.check("H03", "設置場所は未設定のまま登録できる（必須にしない）", h03)

        def retire(loc_id):
            need(api.get("item"), "場所の変更の API が見つからない")
            path = re.sub(r"\[[^\]]+\]", str(loc_id), api["item"])
            for body in ({"active": False}, {"isActive": False}, {"retired": True}, {"status": "retired"}, {"status": "inactive"},
                         {"inUse": False}, {"enabled": False}, {"archived": True}, {"status": "ended"}):
                for m in ("PATCH", "PUT", "POST"):
                    if m not in api.get("item_methods", ["PATCH"]):
                        continue
                    r = c.call(m, path, body)
                    if r["status"] in (200, 201, 204):
                        # 使用終了の場所が一覧から消える作りと、一覧に残して使用終了の印を付ける作りの両方を受け付ける
                        # （試行の採点で、一覧に active: false で残す作りを誤って落としていたので直した。判断の記録に書く）
                        items = list_from(c.call("GET", api["list"])["json"])
                        mine = [x for x in items if loc_name(x) == "検証用 場所 C"]
                        if not mine or any(retired_mark(x) for x in mine):
                            return f"{m} {body}"
            raise AssertionError("場所を使用終了にできない")

        def h04():
            key = api["id_key"]
            state["locC"] = create_loc("検証用 場所 C")
            r = make("PV-0006", {key: state["locC"]})
            need(r["status"] == 201, f"登録できない: {show(r)}")
            before = ((r["json"] or {}).get("instrument") or {})["id"]
            how = retire(state["locC"])
            r2 = make("PV-0007", {key: state["locC"]})
            need(400 <= r2["status"] < 500, f"使用終了の場所で新しく登録できてしまう: {show(r2)}")
            g = get_inst(before)
            need(g.get("location") == "検証用 場所 C", f"使用終了の場所の計測器の表示が変わった: {g.get('location')!r}")
            return how
        hid.check("H04", "使用終了の場所は新しく選べないが、既存の計測器はそのまま表示される", h04)

        def h05():
            if not api.get("item") or "DELETE" not in api.get("item_methods", []):
                return "削除の API なし"
            path = re.sub(r"\[[^\]]+\]", str(state["locB"]), api["item"])
            r = c.call("DELETE", path)
            if r["status"] in (200, 204):
                rows = db_query(db, f'SELECT * FROM "{schema["master"]}" WHERE id = ?', (state["locB"],)) if schema["master"] else []
                g = get_inst(state["inst1"])
                need(rows and g.get("location") == "検証用 場所 B", "使用中の場所が消えた（計測器の場所が失われた）")
            return f"DELETE {r['status']}"
        hid.check("H05", "場所は消さない（使用中の場所を削除できない）", h05)

        def h06():
            need(api.get("item"), "場所の変更の API が見つからない")
            path = re.sub(r"\[[^\]]+\]", str(state["locB"]), api["item"])
            ok = None
            for m in [x for x in ("PATCH", "PUT") if x in api.get("item_methods", ["PATCH"])]:
                r = c.call(m, path, {"name": "検証用 場所 B 改"})
                if r["status"] in (200, 201, 204):
                    ok = m
                    break
            need(ok, "場所の名前を変えられない")
            g = get_inst(state["inst1"])
            need(g.get("location") == "検証用 場所 B 改", f"計測器の表示が新しい名前にならない: {g.get('location')!r}")
            rows = db_query(db, "SELECT location FROM instruments WHERE id = ?", (state["inst1"],))
            need(rows and rows[0]["location"] == "検証用 場所 B 改", f"古い列 location が古い名前のまま: {rows}")
        hid.check("H06", "場所の名前を変えると、計測器の表示（と古い列）も新しい名前になる", h06)

        def h07():
            lst = list_from(c.call("GET", "/api/instruments")["json"])
            need(lst and all(isinstance(x.get("location"), str) for x in lst), "一覧の location が文字列でない（古いクライアントが読めない）")
            g = get_inst(lst[0]["id"])
            need(isinstance(g.get("location"), str), "詳細の location が文字列でない")
        hid.check("H07", "一覧・詳細の location は場所の名前の文字列のまま（古い読み手の互換）", h07)

        hh = Client(srv.base(), token=HANDHELD_TOKEN)

        def h09():
            r = hh.call("POST", "/api/handheld/inventory", {"managementNo": "MI-0003", "location": "製造部　第３ライン"})
            need(r["status"] == 200, f"端末の送信が受け付けられない: {show(r)}")
            g = next((x for x in list_from(c.call("GET", "/api/instruments")["json"]) if x.get("managementNo") == "MI-0003"), {})
            need(norm_name(g.get("location")) == norm_name("製造部 第 3 ライン"), f"正式な場所に寄せられない: {g.get('location')!r}")
            if api.get("id_key"):
                need(isinstance(g.get(api["id_key"]), int), f"場所の ID が付かない: {g}")
        hid.check("H09", "ハンディ端末の自由入力で、寄せられる文字は正式な場所になる", h09)

        def h10():
            r = hh.call("POST", "/api/handheld/inventory", {"managementNo": "MI-0004", "location": "A社 貸出中"})
            need(r["status"] == 200, f"端末の送信が受け付けられない（未送信がたまる）: {show(r)}")
            g = next((x for x in list_from(c.call("GET", "/api/instruments")["json"]) if x.get("managementNo") == "MI-0004"), {})
            if api.get("id_key"):
                need(g.get(api["id_key"]) in (None, ""), f"寄せられない文字なのに場所が付いた: {g}")
            rows = db_query(db, "SELECT * FROM instruments WHERE management_no = 'MI-0004'")
            need(rows and any(v == "A社 貸出中" for v in rows[0].values() if isinstance(v, str)) or "A社 貸出中" in json.dumps(g, ensure_ascii=False),
                 "送られた元の文字が残っていない")
            state["unresolved_no"] = "MI-0004"
        hid.check("H10", "ハンディ端末の寄せられない文字は、受け付けて元の文字を残す（どこかの場所にしない）", h10)

        def h11():
            r = hh.call("POST", "/api/handheld/inventory", {"managementNo": "MI-0001", "location": "品質保証部 測定室"})
            need(r["status"] == 200 and isinstance(r["json"], dict) and r["json"].get("ok") is True, f"応答の形が変わった: {show(r)}")
            need({"ok", "managementNo", "location"} <= set(r["json"]), f"応答の項目が足りない: {r['json']}")
            anon = Client(srv.base()).call("POST", "/api/handheld/inventory", {"managementNo": "MI-0001", "location": "x"})
            need(anon["status"] == 401, f"トークンなしで受け付けた: {anon['status']}")
        hid.check("H11", "ハンディ端末の API の応答の形・認証が変わっていない", h11)

        def h08():
            no = state.get("unresolved_no")
            need(no, "確認中の計測器を作れていない（H10 が失敗）")
            target = next((x for x in list_from(c.call("GET", "/api/instruments")["json"]) if x.get("managementNo") == no), None)
            resolved = next((x for x in list_from(c.call("GET", "/api/instruments")["json"]) if x.get("managementNo") == "MI-0001"), None)
            params = filter_params(app)
            for p in params:
                lst = list_from(c.call("GET", f"/api/instruments?{p}")["json"])
                nos = {x.get("managementNo") for x in lst}
                if no in nos and "MI-0001" not in nos:
                    return f"API ?{p}"
            for r in routes:
                if re.search(r"unresolved|pending|unmatched|unmapped|review|confirm|triage", r["path"], re.I) and "GET" in r["methods"] and "[" not in r["path"]:
                    res = c.call("GET", r["path"])
                    if no in res["text"] and "MI-0001\"" not in res["text"]:
                        return f"API {r['path']}"
            for p in params:
                res = c.call("GET", f"/instruments?{p}")
                if res["status"] == 200 and no in res["text"] and "MI-0001" not in res["text"]:
                    return f"画面 ?{p}"
            raise AssertionError(f"確認中の計測器だけを一覧で絞り込む方法が見つからない（対象 {target}・寄せ済み {bool(resolved)}）")
        hid.check("H08", "確認中（寄せられない値）の計測器を一覧で絞り込める", h08)
    finally:
        srv.stop()
    order = ["H01", "H03", "H04", "H05", "H06", "H07", "H08", "H09", "H10", "H11"]
    hid.results.sort(key=lambda r: order.index(r["id"]))
    return pub.results, hid.results, info


# ---- 移行（5 万件）----

def instruments_fingerprint(db, cols):
    rows = db_query(db, f"SELECT {', '.join(cols)} FROM instruments ORDER BY id")
    return rows


def migration_suite(app, base, work, routes, static):
    work = Path(work)
    old = work / "old.db"
    make_old_db(app, base, old)
    before = instruments_fingerprint(old, BASE_COLS)
    truth = DATA.truth()
    raw_by_id = {r["id"]: r["location"] for r in before}
    keep_cols = [c for c in BASE_COLS if c != "location"]
    res = {"checks": {}, "detail": {}}
    ck, dt = res["checks"], res["detail"]
    db = work / "migrate.db"
    copy_db(old, db)
    srv = Server(app, work, "migration", db)
    if not srv.start():
        dt["start"] = srv.log.read_text()[-500:]
        return res, None
    jobs = [r for r in routes if r["path"].startswith("/api/jobs/") and "[" not in r["path"] and r["path"] != "/api/jobs/overdue-loans"]
    # 補正（W14/adapters/<試行ID>.json の "job_query"）: 候補の手順書が、ジョブを特定のクエリ（例 ?dryRun=false）で呼ぶよう
    # 定めているときは、そのクエリを付けて呼ぶ（既定が試しの実行で、書き込まないジョブ。採点の誤検出の補正。判断の記録に書く）
    jq = json.loads(os.environ.get("W14_OVERRIDE") or "{}").get("job_query", "")
    if jq:
        jobs = [{**j, "path": j["path"] + jq} for j in jobs]
        dt["job_query"] = jq
    try:
        t0 = time.time()  # ログイン自体が最初の要求（DB を開き、マイグレーションが当たる）
        c = Client(srv.base())
        lr = c.call("POST", "/api/login", {"userId": "sato", "password": "password"}, timeout=600)
        first = c.call("GET", "/api/instruments", timeout=600) if lr["status"] == 200 else lr
        dt["first_request_seconds"] = round(time.time() - t0, 2)
        ck["M7"] = first["status"] == 200 and dt["first_request_seconds"] <= 30
        # 移行の間の書き込み: 0.5 秒おきに 60 秒、既存の計測器の備考を書き換える（場所は触らない）
        lat, fails = [], 0
        tw = time.time()
        k = 0
        job_called = False
        while time.time() - tw < 60:
            k += 1
            r = c.call("PATCH", "/api/instruments/1", {"note": f"移行中の書き込み {k}"}, timeout=60)
            lat.append(r["ms"])
            if r["status"] != 200:
                fails += 1
            if not job_called and time.time() - tw > 5:
                job_called = True
                for j in jobs:
                    jc = Client(srv.base(), token=JOBS_TOKEN)
                    for m in [x for x in ("POST", "GET") if x in j["methods"]]:
                        jr = jc.call(m, j["path"], timeout=600)
                        dt.setdefault("jobs", []).append({"path": j["path"], "method": m, "status": jr["status"], "ms": round(jr["ms"])})
                        if 200 <= jr["status"] < 300:
                            break
            time.sleep(0.5)
        dt["write_latency_ms_max"] = round(max(lat)) if lat else None
        dt["write_failures"] = fails
        ck["M8"] = bool(lat) and fails == 0 and max(lat) <= 3000
        # 埋め戻しが終わるのを待つ（最初の要求から最大 180 秒。ジョブがあれば上で 1 回呼んだ。残りがあれば 30 秒おきに呼び直す）
        schema = discover_schema(db, base_tables=["departments", "users", "sessions", "instruments", "loans", "calibration_records"])
        dt["schema"] = schema
        canon_names = {n for _, n, _ in DATA.CANONICAL}
        targets = [i for i, v in raw_by_id.items() if v in canon_names]
        linked_ratio = 0.0
        while time.time() - t0 < 180:
            if schema["fk_col"]:
                rows = db_query(db, f'SELECT id, "{schema["fk_col"]}" AS f FROM instruments')
                fk = {r["id"]: r["f"] for r in rows}
                linked_ratio = sum(1 for i in targets if fk.get(i) is not None) / max(1, len(targets))
                if linked_ratio >= 0.97:
                    break
            if jobs and int(time.time() - t0) % 30 < 5:
                for j in jobs:
                    Client(srv.base(), token=JOBS_TOKEN).call("POST" if "POST" in j["methods"] else "GET", j["path"], timeout=600)
            time.sleep(5)
            schema = discover_schema(db, base_tables=["departments", "users", "sessions", "instruments", "loans", "calibration_records"])
        dt["linked_ratio_of_exact_names"] = round(linked_ratio, 4)
        dt["backfill_seconds"] = round(time.time() - t0, 1)
        ck["M9"] = linked_ratio >= 0.97
        after = instruments_fingerprint(db, [c for c in BASE_COLS if c in [x["name"] for x in db_query(db, 'PRAGMA table_info("instruments")')]])
        by_id = {r["id"]: r for r in after}
        lost = [r["id"] for r in before if r["id"] not in by_id]
        changed = [r["id"] for r in before if r["id"] in by_id and r["id"] != 1 and any(by_id[r["id"]].get(k) != r[k] for k in keep_cols)]
        dt["lost_rows"], dt["changed_rows"] = len(lost), len(changed)
        ck["M1"] = not lost and not changed
        ck["M2"] = static["migrations"].get("readable", False) and not static["migrations"].get("rewritten")
        # 古い列が残り、元が空でない行は空にされていない
        cols_now = [x["name"] for x in db_query(db, 'PRAGMA table_info("instruments")')]
        emptied = [r["id"] for r in after if "location" in r and raw_by_id.get(r["id"], "").strip() and not (r.get("location") or "").strip()] if "location" in cols_now else []
        dt["location_emptied"] = len(emptied)
        ck["M4"] = "location" in cols_now and len(emptied) == 0
        # 両方に書く: 新しい API で場所を変えたら、古い列にも場所の名前が入る
        api = discover_api(c, routes, schema)
        override = json.loads(os.environ.get("W14_OVERRIDE") or "{}")
        api.update({k: v for k, v in override.items() if k in ("list", "item", "id_key")})
        m5_target = None
        if api["list"]:
            items = list_from(c.call("GET", api["list"])["json"])
            pick = next((x for x in items if norm_name(loc_name(x)) == norm_name("技術部 電波暗室")), items[0] if items else None)
            if pick:
                for key in ([api["id_key"]] if api.get("id_key") else api["id_key_candidates"]):
                    r = c.call("PATCH", "/api/instruments/2", {key: pick["id"]})
                    if r["status"] == 200:
                        m5_target = loc_name(pick)
                        dt["m5_key"] = key
                        break
        row2 = db_query(db, "SELECT * FROM instruments WHERE id = 2")[0]
        dt["m5"] = {"target": m5_target, "old_column": row2.get("location")}
        ck["M5"] = bool(m5_target) and row2.get("location") == m5_target
        # 2 回起動しても壊れない
        srv.stop()
        uv = db_query(db, "PRAGMA user_version")[0]["user_version"]
        n_before = db_query(db, "SELECT COUNT(*) AS n FROM instruments")[0]["n"]
        ok3 = srv.start()
        r3 = Client(srv.base()).login().call("GET", "/api/instruments", timeout=300) if ok3 else {"status": 0}
        time.sleep(3)
        srv.stop()
        ck["M3"] = ok3 and r3["status"] == 200 and db_query(db, "PRAGMA user_version")[0]["user_version"] == uv and \
            db_query(db, "SELECT COUNT(*) AS n FROM instruments")[0]["n"] == n_before
        dt["user_version"] = uv
    finally:
        srv.stop()
    # 前の版のアプリに戻す（DB はそのまま）
    ck["M6"], dt["rollback"] = rollback_check(app, base, work, db, m5_target)
    return res, db


def rollback_check(app, base, work, db, m5_target):
    bdir, out = built_base(app, base)
    if bdir is None:
        return False, {"error": "前の版をビルドできない", "log": out}
    rdb = Path(work) / "rollback.db"
    copy_db(db, rdb)
    srv = Server(bdir, work, "rollback", rdb)
    detail = {}
    try:
        if not srv.start():
            return False, {"error": "前の版が起動しない", "log": srv.log.read_text()[-400:]}
        c = Client(srv.base()).login()
        g = c.call("GET", "/api/instruments/2")
        loc = ((g["json"] or {}).get("instrument") or {}).get("location")
        detail["shows"] = loc
        lst = c.call("GET", "/api/instruments")
        body = {"managementNo": "RB-0001", "name": "戻した版での登録", "managerId": "sato", "intervalMonths": 12,
                "lastCalibratedOn": "2026-04-01", "location": "製造部 検査室"}
        p = c.call("POST", "/api/instruments", body)
        e = c.call("PATCH", "/api/instruments/3", {"location": "製造部 恒温室"})
        detail.update({"get": g["status"], "list": lst["status"], "create": p["status"], "edit": e["status"]})
        ok = g["status"] == 200 and lst["status"] == 200 and p["status"] == 201 and e["status"] == 200 and bool(m5_target) and loc == m5_target
        return ok, detail
    finally:
        srv.stop()


def normalize_checks(db):
    """移行後の DB で、表記ゆれの寄せの正しさを測る（場所マスタの各行が正解のどの場所かは、結びついた計測器の多数決で決める）。"""
    out = {"available": False}
    if db is None or not Path(db).exists():
        return out
    schema = discover_schema(db, base_tables=["departments", "users", "sessions", "instruments", "loans", "calibration_records"])
    out["schema"] = schema
    if not (schema["master"] and schema["fk_col"]):
        return out
    truth = DATA.truth()
    values = DATA.distribution()
    # 生の値は「旧 DB の行の並び」で決まる（data_w14.build_db と同じ順で入れたので、初期データの 10 件の後に続く）
    has_loc = "location" in [x["name"] for x in db_query(db, 'PRAGMA table_info("instruments")')]
    rows = db_query(db, f'SELECT id, management_no, {"location" if has_loc else "NULL AS location"}, "{schema["fk_col"]}" AS f FROM instruments ORDER BY id')
    big = [r for r in rows if re.match(r"K[A-F]-\d{4}$", r["management_no"])]
    big.sort(key=lambda r: (DATA.PREFIXES.index(r["management_no"][:2]), int(r["management_no"][3:])))
    if len(big) != len(values):
        out["error"] = f"5 万件の行が揃っていない（{len(big)}）"
        return out
    pairs = [(values[i], big[i]) for i in range(len(values))]
    votes = {}
    for raw, r in pairs:
        t = truth[raw]
        if r["f"] is not None and t["id"]:
            votes.setdefault(r["f"], {}).setdefault(t["id"], 0)
            votes[r["f"]][t["id"]] += 1
    identity = {mid: max(v, key=v.get) for mid, v in votes.items()}
    # 正式な場所ごとの「本来の場所マスタ」= その場所の計測器がいちばん多く結びついた行。同じ場所が複数の行に分かれていたら、
    # 本来の行以外に結びついた計測器は「寄せられていない」と数える（表記ゆれの数だけ場所を作っても正解にしない）
    home = {}
    for mid, v in votes.items():
        for cid, n in v.items():
            if cid not in home or n > votes[home[cid]].get(cid, 0):
                home[cid] = mid
    stats = {k: [0, 0] for k in ("target_export", "target_hidden")}
    wrong, wrong_detail, unresolved_kept, unresolved_total = 0, {}, 0, 0
    for raw, r in pairs:
        t = truth[raw]
        cls = t["class"]
        ident = identity.get(r["f"]) if r["f"] is not None else None
        if cls == "target":
            k = "target_hidden" if t.get("hidden") else "target_export"
            stats[k][1] += 1
            if r["f"] is not None and r["f"] == home.get(t["id"]):
                stats[k][0] += 1
            elif r["f"] is not None:
                wrong += 1
                wrong_detail[raw] = wrong_detail.get(raw, 0) + 1
        elif cls == "either":
            if r["f"] is not None and ident != t["id"]:
                wrong += 1
                wrong_detail[raw] = wrong_detail.get(raw, 0) + 1
        elif cls in ("unresolved", "blank"):
            if r["f"] is not None:
                wrong += 1
                wrong_detail[raw] = wrong_detail.get(raw, 0) + 1
            if cls == "unresolved":
                unresolved_total += 1
                if raw.strip() and raw.strip() in (r["location"] or ""):
                    unresolved_kept += 1
    masters = db_query(db, f'SELECT COUNT(*) AS n FROM "{schema["master"]}"')[0]["n"]
    out.update({
        "available": True,
        "export_accuracy": round(stats["target_export"][0] / max(1, stats["target_export"][1]), 4),
        "hidden_accuracy": round(stats["target_hidden"][0] / max(1, stats["target_hidden"][1]), 4),
        "wrong_links": wrong,
        "wrong_rate": round(wrong / len(pairs), 5),
        "wrong_examples": sorted(wrong_detail.items(), key=lambda x: -x[1])[:10],
        "unresolved_kept_ratio": round(unresolved_kept / max(1, unresolved_total), 4),
        "master_rows": masters,
        "distinct_identities": len(set(identity.values())),
        "split_places": sum(1 for cid in {t for v in votes.values() for t in v} if sum(1 for v in votes.values() if max(v, key=v.get) == cid) > 1),
    })
    return out


def ops_checks(static, logs):
    lines = []
    for text in logs:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    lines.append(json.loads(line))
                except ValueError:
                    pass
    progress = [l for l in lines if re.search(r"locat|backfill|migrat|場所", str(l.get("event", "")), re.I)]
    counted = [l for l in progress if any(isinstance(v, int) for v in l.values())]
    o1 = static["logger_used"] and bool(counted)
    o2 = static["doc_rollback"] and static["doc_steps"]
    return {"O1": o1, "O2": o2, "progress_events": [l.get("event") for l in progress][:10], "total": 2.5 * o1 + 2.5 * o2}


def evaluate(app, base, work, mutation=True):
    app, work = Path(app), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = sh(cmd, app)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    static = static_checks(app, base)
    routes = new_routes(app, base)
    out = {"checks": checks, "static": static, "routes": routes}
    if checks["build"]["pass"]:
        out["public"], out["hidden"], out["discovery"] = api_suite(app, work, routes, base)
        out["migration"], db = migration_suite(app, base, work, routes, static)
        out["normalize"] = normalize_checks(db)
        logs = [p.read_text() for p in work.glob("*.server.log") if not p.name.startswith("rollback")]
        out["ops"] = ops_checks(static, logs)
    else:
        out.update({"public": [], "hidden": [], "discovery": {}, "migration": {"checks": {}}, "normalize": {"available": False},
                    "ops": {"total": 0}})
    if mutation:
        sys.path.insert(0, str(HERE))
        import grade_w10  # noqa: E402  ミューテーションは W10 と同じ方法
        out["mutation"] = grade_w10.mutation(str(app), base, str(work / "mutation"))
    return out


def summary_line(r):
    def bits(xs):
        return "".join("o" if x["pass"] else "x" for x in xs)
    m = r.get("migration", {}).get("checks", {})
    n = r.get("normalize", {})
    mu = r.get("mutation", {})
    return (f"public {bits(r.get('public', []))} hidden {bits(r.get('hidden', []))} "
            f"migration {''.join('o' if m.get(k) else 'x' for k in ('M1','M2','M3','M4','M5','M6','M7','M8','M9'))} "
            f"normalize exp={n.get('export_accuracy')} hid={n.get('hidden_accuracy')} wrong={n.get('wrong_links')} "
            f"kept={n.get('unresolved_kept_ratio')} masters={n.get('master_rows')} ops {r.get('ops', {}).get('total')} "
            f"mutation {mu.get('killed')}/{mu.get('mutants')}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--app":
        app = args[1]
        base = args[args.index("--base") + 1]
        work = tempfile.mkdtemp(prefix="w14-grade-")
        r = evaluate(app, base, work, mutation="--no-mutation" not in args)
        r["checks"] = {k: v["pass"] for k, v in r["checks"].items()}
        r["work"] = work
        text = json.dumps(r, ensure_ascii=False, indent=1)
        if "--out" in args:
            Path(args[args.index("--out") + 1]).write_text(text + "\n")
        else:
            print(text)
        print(summary_line(r), file=sys.stderr)
        return
    if args and args[0] == "--recheck-api":
        # 採点の誤検出を直したあと、公開・隠しの API の確かめだけをやり直し、結果の JSON の public・hidden・discovery を差し替える
        # （ビルド済みの作業用コピーで。移行・表記ゆれ・ミューテーションは変えない。差し替える前の値は *_before_recheck に残す）
        for trial in args[1:]:
            f = RESULTS / f"{trial}.json"
            res = json.loads(f.read_text())
            raw = ROOT / "poc" / "results" / "workflow" / "raw" / trial
            app = Path((raw / "workdir").read_text().strip()) / "app"
            base = (raw / "baseline-commit").read_text().strip()
            ov_path = RESULTS / "adapters" / f"{trial}.json"
            os.environ["W14_OVERRIDE"] = ov_path.read_text() if ov_path.exists() else "{}"
            w = res["w14"]
            pub, hid, disc = api_suite(app, Path(tempfile.mkdtemp(prefix=f"w14-recheck-{trial}-")), w["routes"], base)
            for k, v in (("public", pub), ("hidden", hid), ("discovery", disc)):
                w.setdefault(f"{k}_before_recheck", w.get(k))
                w[k] = v
            f.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
            print(trial, "public", "".join("o" if x["pass"] else "x" for x in pub), "hidden", "".join("o" if x["pass"] else "x" for x in hid))
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W14", trial]  # grade.py はモジュールの読み込み時に sys.argv からシナリオと試行 ID を読む
    sys.path.insert(0, str(HERE))
    import grade  # noqa: E402
    grade.main()
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    ov_path = RESULTS / "adapters" / f"{trial}.json"
    if ov_path.exists():
        os.environ["W14_OVERRIDE"] = ov_path.read_text()
    w14 = evaluate(grade.APP, base, Path(tempfile.mkdtemp(prefix=f"w14-grade-{trial}-")))
    w14["checks"] = {k: v["pass"] for k, v in w14["checks"].items()}
    result["w14"] = w14
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line(w14)}")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
