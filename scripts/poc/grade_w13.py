#!/usr/bin/env python3
"""W13（途中で要件が変わる）の試行を採点用に調べ、results/workflow/W13/<試行ID>.json に書き出す。

使い方:
  python3 scripts/poc/grade_w13.py <試行ID> [--cleanup] [--no-mutation]
    1. grade.py と同じ集計（型チェック・単体テスト・ビルド・差分・トランスクリプト）
    2. W13 固有の事実（docs/poc/answer-key/W13/grading.md）を w13 に足す
       - adapters:  最初の版（v1）と変更後（v2）の予約の API（採点者が W13/adapters/<試行ID>-v1.json・-v2.json に書く。
                    無ければ adapt_w13.py が下書きを作る）
       - v1:        変更依頼の時点のコミット（raw/<ID>/v1-commit）を取り出し、型チェック・単体テスト・ビルドと
                    受け入れ（P01・P02）・隠しテスト K01〜K08
       - final:     変更後の型チェック・単体テスト・ビルドと、P02・P03・K01〜K08・C01〜C10
       - migration: 旧スキーマの DB（old-db.sql）を v1 のアプリで起動して予約を入れた「本番の DB」を、変更後のアプリで 2 回起動する
       - static:    出荷済みのマイグレーションの書き換え・v1 だけの状態の値の残り・手戻りの量
       - mutation:  候補が src/lib/ に足した行をわざと壊した版を、候補の npm test が検出した割合（grade_w10.py と同じ方法）
  python3 scripts/poc/grade_w13.py --app <アプリ> --base <初期状態のコミット> --v1 <v1 のコミット>
                                   --adapter-v1 <JSON> --adapter-v2 <JSON> [--out <JSON>] [--no-mutation]
    試行前の確認用（参照実装・最短の実装・半分の実装）。
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
KEY = ROOT / "docs" / "poc" / "answer-key" / "W13"
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W13"
JOBS_TOKEN = "jobs-tkn-3f9a71SECRETc04d"
BASE_TABLES = ("departments", "users", "instruments", "loans", "calibration_records")
K_ITEMS = [f"K0{i}" for i in range(1, 9)]
C_ITEMS = [f"C{i:02d}" for i in range(1, 11)]


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


def git(app, *args):
    return subprocess.run(["git", *args], cwd=app, capture_output=True, text=True).stdout


# ---- コードから分かること ----

def migrations_of(app):
    script = ("import('./src/lib/db/migrations.ts').then(m => console.log(JSON.stringify("
              "(m.MIGRATIONS || []).map(x => ({version: x.version, name: x.name, sql: x.sql})))))")
    code, out = sh(f"node --experimental-strip-types --no-warnings -e \"{script}\"", app, timeout=60)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def norm_sql(s):
    return re.sub(r"\s+", " ", s).strip()


def export_commit(app, commit, dest):
    """コミットの中身を dest に取り出し、node_modules をハードリンクで写す。"""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(f"git -C {app} archive {commit} | tar -x -C {dest}", shell=True, check=True)
    if not (dest / "node_modules").exists():
        subprocess.run(["cp", "-al", str(Path(app) / "node_modules"), str(dest / "node_modules")], check=True)
    return dest


def string_literals(code):
    return set(re.findall(r"""["'`]([a-z_]{3,20})["'`]""", code))


def static_checks(app, base, v1, work, adapters):
    tmp = Path(tempfile.mkdtemp(prefix="w13-mig-", dir=work))
    mig = {}
    for name, commit in (("base", base), ("v1", v1)):
        d = tmp / name
        d.mkdir()
        subprocess.run(f"git -C {app} archive {commit} src | tar -x -C {d}", shell=True, check=True)
        mig[name] = migrations_of(d)
    mig["final"] = migrations_of(app)
    out = {"readable": all(mig[k] is not None for k in mig)}
    if out["readable"]:
        ver = {k: [m["version"] for m in v] for k, v in mig.items()}
        out["versions"] = ver
        v1_sql = {m["version"]: norm_sql(m["sql"]) for m in mig["v1"]}
        fin_sql = {m["version"]: norm_sql(m["sql"]) for m in mig["final"]}
        base_sql = {m["version"]: norm_sql(m["sql"]) for m in mig["base"]}
        out["v1_added"] = [v for v in ver["v1"] if v not in base_sql]
        out["v1_rewrote_base"] = [v for v in base_sql if v1_sql.get(v) != base_sql[v]]
        out["final_rewrote_shipped"] = [v for v in v1_sql if fin_sql.get(v) != v1_sql[v]]
        out["final_added"] = [v for v in ver["final"] if v not in v1_sql]
        out["appended_in_order"] = bool(out["final_added"]) and min(out["final_added"]) > max(v1_sql) \
            and ver["final"] == sorted(ver["final"])
    # v1 だけの状態の値（v1 のアダプターの状態の値のうち、v2 に無いもの）が、変更後のコード（マイグレーションとテストを除く）に残っていないか
    def vals(ad):
        """状態の値（複数の項目を組み合わせた値 '"active"|0' は、項目ごとの値に分ける）"""
        out = set()
        for vs in (ad or {}).get("status", {}).values():
            for v in (vs if isinstance(vs, list) else [vs]):
                for part in (str(v).split("|") if isinstance(v, str) and "|" in v else [v]):
                    try:
                        part = json.loads(part) if isinstance(part, str) and part[:1] in '"[{0123456789tfn' else part
                    except ValueError:
                        pass
                    if isinstance(part, str):
                        out.add(part)
        return out
    v1_vals, v2_vals = vals(adapters.get("v1")), vals(adapters.get("v2"))
    stale_vals = sorted(v1_vals - v2_vals)
    hits = []
    for f in git(app, "ls-files", "src").split():
        if f.endswith("migrations.ts") or ".test." in f:
            continue
        text = (Path(app) / f).read_text(errors="replace")
        for v in stale_vals:
            if v in string_literals(text):
                hits.append(f"{f}: '{v}'")
    out["stale_status_values"] = stale_vals
    out["stale_hits"] = hits[:20]
    # 手戻りの量（v1 → 変更後）
    num = git(app, "diff", "--numstat", v1, "HEAD", "--", "src", "tests")
    add = dele = 0
    for line in num.splitlines():
        a, d, _ = line.split("\t", 2)
        if a.isdigit():
            add += int(a)
            dele += int(d)
    out["change_lines"] = {"added": add, "deleted": dele}
    num1 = git(app, "diff", "--numstat", base, v1, "--", "src", "tests")
    out["v1_lines_added"] = sum(int(l.split("\t")[0]) for l in num1.splitlines() if l.split("\t")[0].isdigit())
    return out  # 一時ディレクトリは消さずに残す（削除の運用）


# ---- サーバー ----

class Server:
    def __init__(self, app, work, name, db, now):
        self.app, self.work, self.name = Path(app), Path(work), name
        self.work.mkdir(parents=True, exist_ok=True)
        self.clock = self.work / f"{name}.now"
        self.clock.write_text(now + "\n")
        self.db = Path(db)
        self.log = self.work / f"{name}.server.log"
        self.proc = None

    def start(self):
        self.port = free_port()
        env = dict(os.environ)
        env.update({"DATABASE_PATH": str(self.db), "JOBS_TOKEN": JOBS_TOKEN, "POC_FAKE_NOW_FILE": str(self.clock),
                    "NODE_ENV": "production",
                    "NODE_OPTIONS": (env.get("NODE_OPTIONS", "") + f" --require {KEY / 'fake-clock.cjs'}").strip()})
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
            self.proc.wait(timeout=30)
            self.proc = None
            self.logf.close()
            time.sleep(1)

    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def node(self, script, adapter, phase, args=(), extra=None, timeout=1800):
        env = dict(os.environ, NODE_PATH=node_path(), W13_ADAPTER=json.dumps(adapter or {}), W13_PHASE=phase,
                   W13_JOBS_TOKEN=JOBS_TOKEN, POC_FAKE_NOW_FILE=str(self.clock), **(extra or {}))
        p = subprocess.run(["node", str(KEY / script), *args, self.base()], cwd=self.app, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p


def parse_results(p, name):
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return [{"id": "X", "name": f"{name} の実行", "pass": False, "detail": (p.stdout + p.stderr)[-800:]}]


def suite(app, work, name, adapter, phase):
    s = Server(app, work, name, Path(work) / f"{name}.db", "2026-11-09T22:30:00.000Z")
    try:
        if not s.start():
            return [{"id": "X", "name": "サーバーの起動", "pass": False, "detail": s.log.read_text()[-500:]}]
        return parse_results(s.node("tests.cjs", adapter, phase), name)
    finally:
        s.stop()


# ---- マイグレーション（本番の DB） ----

def snapshot(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    out = {"user_version": con.execute("PRAGMA user_version").fetchone()[0],
           "tables": sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))}
    for t in BASE_TABLES:
        try:
            out[t] = [dict(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        except sqlite3.DatabaseError:
            out[t] = None
    con.close()
    return out


def migration_checks(app, v1app, work, adapters, static):
    work = Path(work)
    prod = work / "prod.db"
    con = sqlite3.connect(prod)
    con.executescript((KEY / "old-db.sql").read_text())
    con.commit()
    con.close()
    res = {}
    # 1) 最初の版で本番の DB を作る（v1 のマイグレーションの適用と、予約の投入）
    s1 = Server(v1app, work, "prod-v1", prod, "2026-11-09T22:30:00.000Z")
    made = {"made": [], "errors": ["v1 のサーバーが起動しない"]}
    try:
        if s1.start():
            p = s1.node("prod.cjs", adapters.get("v1"), "v1", args=("make",))
            line = next((l for l in p.stderr.splitlines() if l.startswith("PROD ")), None)
            made = json.loads(line[5:]) if line else {"made": [], "errors": [p.stderr[-500:]]}
    finally:
        s1.stop()
    res["prod"] = made
    shipped = snapshot(prod)
    res["prod_user_version"] = shipped["user_version"]
    # 2) 変更後のアプリで 2 回起動する
    runs = []
    for n, name in enumerate(("mig-1", "mig-2")):
        s = Server(app, work, name, prod, "2026-11-14T22:30:00.000Z")
        try:
            started = s.start()
            r = parse_results(s.node("prod.cjs", adapters.get("v2"), "v2", args=("check",),
                                     extra={"W13_PROD": json.dumps(made)}), name) if started else []
        finally:
            s.stop()
        snap = snapshot(prod)
        runs.append({"started": started, "results": r, "user_version": snap["user_version"], "snap": snap,
                     "log_errors": [l[:200] for l in s.log.read_text().splitlines() if re.search(r"Error|SQLITE|no such", l)][:8]})
    res["runs"] = [{k: v for k, v in r.items() if k != "snap"} for r in runs]

    def kept(snap):
        return {t: (shipped[t] == snap[t]) for t in BASE_TABLES}
    k1, k2 = kept(runs[0]["snap"]), kept(runs[1]["snap"])
    res["base_tables_kept"] = {"first": k1, "second": k2}

    def ok(run, item):
        return any(x["id"] == item and x["pass"] for x in run["results"])
    login_ok = runs[0]["started"] and not any(x["id"] == "X" for x in runs[0]["results"])
    m = static
    res["checks"] = {
        "N1": bool(m.get("appended_in_order")) and runs[0]["user_version"] > shipped["user_version"],
        "N2": bool(m.get("readable")) and not m.get("final_rewrote_shipped") and not m.get("v1_rewrote_base"),
        "N3": bool(login_ok and all(k1.values()) and ok(runs[0], "N3x")),
        "N4": ok(runs[0], "N4"),
        "N5": ok(runs[0], "N5"),
        "N6": bool(runs[1]["started"] and runs[1]["user_version"] == runs[0]["user_version"] and all(k2.values())
                   and ok(runs[1], "N3x")),
        "S1": ok(runs[0], "S1"),
    }
    return res


# ---- 全体 ----

def checks_of(app):
    out = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = sh(cmd, app)
        out[name] = {"pass": code == 0, "log": log[-800:]}
    return out


def evaluate(app, base, v1, work, adapters, mutation=True):
    app, work = Path(app), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    v1app = export_commit(app, v1, work / "v1app")
    out = {"adapters": adapters, "v1_commit": v1}
    out["v1_checks"] = checks_of(v1app)
    out["checks"] = checks_of(app)
    out["static"] = static_checks(app, base, v1, work, adapters)
    out["v1_tests"] = suite(v1app, work, "v1", adapters.get("v1"), "v1") if out["v1_checks"]["build"]["pass"] else []
    out["final_tests"] = suite(app, work, "final", adapters.get("v2"), "v2") if out["checks"]["build"]["pass"] else []
    if out["checks"]["build"]["pass"] and out["v1_checks"]["build"]["pass"]:
        out["migration"] = migration_checks(app, v1app, work, adapters, out["static"])
    else:
        out["migration"] = {"checks": {}, "note": "ビルドに失敗したため動かせない"}
    if mutation:
        sys.path.insert(0, str(HERE))
        import grade_w10  # noqa: E402
        out["mutation"] = grade_w10.mutation(str(app), base, str(work / "mutation"))
    for k in ("v1_checks", "checks"):
        out[k] = {n: v["pass"] for n, v in out[k].items()} | {"logs": {n: v["log"] for n, v in out[k].items() if not v["pass"]}}
    return out


def passed(tests, item):
    return any(t["id"] == item and t["pass"] for t in tests)


def points(r, design=None):
    """配点（grading.md）。design はブラインドレビューの 2 名の合計の平均（18 点満点）。無ければ 0。"""
    v1c, fc = r.get("v1_checks", {}), r.get("checks", {})
    v1t, ft = r.get("v1_tests", []), r.get("final_tests", [])
    mig = r.get("migration", {}).get("checks", {})
    st = r.get("static", {})
    p = {}
    p["v1"] = sum(1 for k in ("typecheck", "test", "build") if v1c.get(k)) + passed(v1t, "P01") + passed(v1t, "P02") \
        + 10 / 8 * sum(passed(v1t, k) for k in K_ITEMS)
    p["change"] = 4 * passed(ft, "P03") + 2.1 * sum(passed(ft, c) for c in C_ITEMS)
    kept_items = ["P02"] + K_ITEMS
    was = [k for k in kept_items if passed(v1t, k)]
    still = [k for k in was if passed(ft, k)]
    p["unchanged"] = sum(1 for k in ("typecheck", "test", "build") if fc.get(k)) + 2 * passed(ft, "P02") \
        + 5 / 8 * sum(passed(ft, k) for k in K_ITEMS) + (5 * len(still) / len(was) if was else 0)
    p["migration"] = sum(w for k, w in (("N1", 3), ("N2", 5), ("N3", 4), ("N4", 3), ("N5", 3), ("N6", 2)) if mig.get(k))
    p["stale"] = 2.5 * bool(mig.get("S1")) + 2.5 * bool(fc.get("build") and not st.get("stale_hits"))
    p["design"] = (design or 0) * 15 / 18
    p["test_strength"] = 5 * (r.get("mutation", {}).get("kill_rate") or 0)
    p = {k: round(v, 2) for k, v in p.items()}
    p["total"] = round(sum(p.values()), 2)
    p["regressions"] = [k for k in was if k not in still]
    return p


def summary_line(r):
    def bits(xs, ids):
        return "".join("o" if passed(xs, i) else "x" for i in ids)
    m = r.get("migration", {}).get("checks", {})
    mu = r.get("mutation", {})
    return (f"v1 {''.join('o' if r['v1_checks'].get(k) else 'x' for k in ('typecheck','test','build'))} "
            f"P01-02 {bits(r['v1_tests'], ['P01','P02'])} K {bits(r['v1_tests'], K_ITEMS)} | "
            f"final {''.join('o' if r['checks'].get(k) else 'x' for k in ('typecheck','test','build'))} "
            f"P02-03 {bits(r['final_tests'], ['P02','P03'])} K {bits(r['final_tests'], K_ITEMS)} C {bits(r['final_tests'], C_ITEMS)} | "
            f"mig {''.join('o' if m.get(k) else 'x' for k in ('N1','N2','N3','N4','N5','N6','S1'))} "
            f"stale {r['static'].get('stale_hits')} mutation {mu.get('killed')}/{mu.get('mutants')}")


def load_adapters(trial, app, base, v1, work):
    out = {}
    for ph, commit in (("v1", v1), ("v2", "HEAD")):
        p = RESULTS / "adapters" / f"{trial}-{ph}.json"
        if p.exists():
            out[ph] = json.loads(p.read_text())
            continue
        sys.path.insert(0, str(HERE))
        import adapt_w13  # noqa: E402
        draft = adapt_w13.draft(app, base, commit, ph, Path(work) / f"adapt-{ph}")
        p.parent.mkdir(parents=True, exist_ok=True)
        (RESULTS / "adapters" / f"{trial}-{ph}.draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
        out[ph] = draft.get("adapter") or {}
        out.setdefault("drafted", []).append(ph)
    return out


def main():
    args = sys.argv[1:]
    mutation = "--no-mutation" not in args
    if args and args[0] == "--app":
        arg = lambda k: args[args.index(k) + 1]  # noqa: E731
        app = arg("--app")
        work = tempfile.mkdtemp(prefix="w13-grade-")
        # 前の版のビルド結果を退避してから調べる（削除しない）
        if (Path(app) / ".next").exists():
            shutil.move(str(Path(app) / ".next"), tempfile.mkdtemp(prefix="w13-old-next-"))
        adapters = {"v1": json.loads(Path(arg("--adapter-v1")).read_text()), "v2": json.loads(Path(arg("--adapter-v2")).read_text())}
        r = evaluate(app, arg("--base"), arg("--v1"), work, adapters, mutation=mutation)
        r["points"] = points(r, float(arg("--design")) if "--design" in args else None)
        text = json.dumps(r, ensure_ascii=False, indent=1)
        if "--out" in args:
            Path(arg("--out")).write_text(text + "\n")
        else:
            print(text)
        print(summary_line(r), file=sys.stderr)
        print(json.dumps(r["points"], ensure_ascii=False), file=sys.stderr)
        return
    trial = args[0]
    sys.argv = [sys.argv[0], "W13", trial]
    sys.path.insert(0, str(HERE))
    import grade  # noqa: E402
    grade.main()
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    v1 = (grade.RAW / "v1-commit").read_text().strip()
    # 作り直すときは新しい名前のディレクトリにする（削除しない）
    grade.WORK.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="grade-w13-", dir=grade.WORK))
    adapters = load_adapters(trial, grade.APP, base, v1, work)
    w13 = evaluate(grade.APP, base, v1, work, adapters, mutation=mutation)
    w13["points_without_design"] = points(w13)
    result["w13"] = w13
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line(w13)}")
    print(json.dumps(w13["points_without_design"], ensure_ascii=False))
    if "--cleanup" in args:
        grade.cleanup()


if __name__ == "__main__":
    main()
