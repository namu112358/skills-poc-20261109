#!/usr/bin/env python3
"""W18（長期品質: 積み重ね開発と引き継ぎ）の採点。docs/poc/answer-key/W18/grading.md。

1 回分（第 k 回の終わりのコード、または引き継ぎの後のコード）について、次を調べて JSON に書く。
  - checks:   型チェック・単体テスト（通った数・失敗の数）・ビルド
  - suites:   後退テスト base と、第 1 回〜第 k 回の機能の隠しテスト f1〜fk（引き継ぎなら f1〜f6 と h1 か h2）。
              第 3 回以降は、第 2 回の終わりの版で作ったデータを今の版で起動する移行のテスト（f3-upgrade、L08）も行う。
              偽の時計・偽の通知サービス・偽の受付システムを使い、API の名前の違いはアダプターで吸収する。
  - static:   アプリの中の定期実行、出荷済みのマイグレーションの書き換え（前の回の終わりと比べる）
  - metrics:  コードの指標（scripts/poc/w18-metrics/metrics.mjs）
  - mutation: 第 1 回の初期状態から足された src/lib/ の行をわざと壊し、候補の npm test で検出した割合（grade_w10.mutation）

使い方:
  python3 scripts/poc/grade_w18.py <試行ID> [--no-mutation]
      試行 ID は W18r<k>-<候補>-<系列>（第 k 回）か W18h<1|2|3>-<候補>-<系列>（引き継ぎ）。
      アダプターは results/workflow/W18/adapters/<系列ID>-r<k>.json（系列 ID は <候補>-<系列>。引き継ぎは -h1・-h2）。
      無ければ adapt_w18.py が下書きを作り（.draft.json）、それで採点する（採点者が確かめて確定する）。
      結果は results/workflow/W18/<試行ID>.json。
  python3 scripts/poc/grade_w18.py --repo <git の作業ディレクトリ> --commit <コミット> --round <1-6|h1|h2|h3>
        --base <初期状態のコミット> --adapter <JSON> [--prev <前の回のコミット>] [--r2 <第 2 回の終わりのコミット>]
        [--out <JSON>] [--no-mutation]
      試行前の確認用（参照の系列・最短の系列）。
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W18"
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W18"
RAWS = ROOT / "docs" / "poc" / "results" / "workflow" / "raw"
JOBS_TOKEN = "jobs-tkn-7c21e0SECRETa58b"
NOTIFY_TOKEN = "ntf-tkn-1d9e44SECRET02af"
AGENCY_KEY = "agc-key-5f30b7SECRET9d1c"
TOOLS = Path(os.environ.get("W18_METRICS_TOOLS", "/tmp/poc-w18-metrics"))
START_NOW = "2026-11-09T22:30:00.000Z"  # 日本時間 2026-11-10 7:30


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


_NODE_PATH = None


def node_path():
    global _NODE_PATH
    if _NODE_PATH is None:
        _NODE_PATH = subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip()
    return _NODE_PATH


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def export_commit(repo, commit, dest):
    """コミットの中身を dest に取り出し、node_modules をハードリンクで写す（git の履歴は付けない）。"""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(f"git -C '{repo}' archive {commit} | tar -x -C '{dest}'", shell=True, check=True)
    if not (dest / "node_modules").exists():
        subprocess.run(["cp", "-al", str(Path(repo) / "node_modules"), str(dest / "node_modules")], check=True)
    return dest


def rounds_of(round_):
    """その回までに動くはずの機能の隠しテスト"""
    if str(round_).startswith("h"):
        return [f"f{i}" for i in range(1, 7)] + [str(round_)]
    return [f"f{i}" for i in range(1, int(round_) + 1)]


def slice_adapter(adapter, round_):
    keep = set(rounds_of(round_)) | {"instrument", "env"}
    return {k: v for k, v in (adapter or {}).items() if k in keep}


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
    return re.sub(r"\s+", " ", s or "").strip()


def static_checks(repo, app, base, commit, prev, work):
    out = {}
    lines = []
    for f in Path(app, "src").rglob("*"):
        if f.suffix in (".ts", ".tsx") and ".test." not in f.name:
            for l in f.read_text(errors="replace").splitlines():
                lines.append((str(f.relative_to(app)), l))
    sched = [l.strip()[:160] for _, l in lines if re.search(r"setInterval\s*\(|node-cron|cron\.schedule|\bschedule\s*\(", l)]
    sched += [str(p.relative_to(app)) for p in Path(app).glob("**/instrumentation.*") if "node_modules" not in str(p) and ".next" not in str(p)]
    out["inProcessScheduler"] = sched
    mig = {"readable": False}
    if prev:
        pd = Path(tempfile.mkdtemp(prefix="w18-prev-src-", dir=work))
        subprocess.run(f"git -C '{repo}' archive {prev} src | tar -x -C '{pd}'", shell=True, check=True)
        before, after = migrations_of(pd), migrations_of(app)
        if before is not None and after is not None:
            old = {m["version"]: norm_sql(m["sql"]) for m in before}
            new = {m["version"]: norm_sql(m["sql"]) for m in after}
            mig = {"readable": True, "prev_versions": sorted(old), "versions": [m["version"] for m in after],
                   "rewritten": [v for v in old if new.get(v) != old[v]],
                   "added": [v for v in new if v not in old]}
    out["migrations"] = mig
    out["new_dependencies"] = [l[1:].strip() for l in git(repo, "diff", base, commit, "--", "package.json").splitlines()
                               if l.startswith("+") and not l.startswith("+++") and re.search(r'^\+\s+"[^"]+":\s*"', l)]
    return out


# ---- サーバーと偽物 ----

class Env:
    """偽の通知サービス・偽の受付システム・候補のアプリ（next start）を起動する。"""

    def __init__(self, app, work, name, db, adapter):
        self.app, self.work, self.name, self.db = Path(app), Path(work), name, Path(db)
        self.work.mkdir(parents=True, exist_ok=True)
        self.clock = self.work / f"{name}.now"
        self.clock.write_text(START_NOW + "\n")
        self.adapter = adapter or {}
        self.procs = []
        self.logs = []

    def _spawn(self, args, cwd, env, log):
        f = open(self.work / log, "a")
        self.logs.append(f)
        p = subprocess.Popen(args, cwd=cwd, env=env, stdout=f, stderr=f, start_new_session=True,
                             shell=isinstance(args, str))
        self.procs.append(p)
        return p

    def start(self):
        self.notify_port, self.agency_port, self.port = free_port(), free_port(), free_port()
        self._spawn(["node", str(KEY / "fake-notify.cjs"), str(self.notify_port), NOTIFY_TOKEN], self.work, dict(os.environ), f"{self.name}.notify.log")
        self._spawn(["node", str(KEY / "fake-agency.cjs"), str(self.agency_port), AGENCY_KEY], self.work, dict(os.environ), f"{self.name}.agency.log")
        env = dict(os.environ)
        values = {"notify_url": f"http://127.0.0.1:{self.notify_port}", "notify_token": NOTIFY_TOKEN, "jobs_token": JOBS_TOKEN,
                  "agency_url": f"http://127.0.0.1:{self.agency_port}", "agency_key": AGENCY_KEY}
        env.update({"DATABASE_PATH": str(self.db), "JOBS_TOKEN": JOBS_TOKEN, "POC_FAKE_NOW_FILE": str(self.clock),
                    "NOTIFY_API_URL": values["notify_url"], "NOTIFY_API_TOKEN": NOTIFY_TOKEN,
                    "AGENCY_API_URL": values["agency_url"], "AGENCY_API_KEY": AGENCY_KEY, "NODE_ENV": "production",
                    "NODE_OPTIONS": (env.get("NODE_OPTIONS", "") + f" --require {KEY / 'fake-clock.cjs'}").strip()})
        # 候補が文書と違う名前の環境変数で読む場合は、アダプターの env で同じ値を渡す（採点者が確かめて書く。report に記録）
        for k, v in (self.adapter.get("env") or {}).items():
            env[k] = values.get(v, v)
        self.server_log = self.work / f"{self.name}.server.log"
        self._spawn(f"npx next start -p {self.port}", self.app, env, f"{self.name}.server.log")
        ok = wait_port(self.notify_port, 20) and wait_port(self.agency_port, 20) and wait_port(self.port, 120)
        return ok

    def stop(self):
        for p in reversed(self.procs):
            try:
                os.killpg(p.pid, 15)
            except ProcessLookupError:
                pass
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, 9)
        self.procs = []
        for f in self.logs:
            f.close()
        self.logs = []
        time.sleep(1)

    def run(self, script, adapter, args=(), extra=None, timeout=2400):
        env = dict(os.environ, NODE_PATH=node_path(), W18_ADAPTER=json.dumps(adapter or {}),
                   W18_NOTIFY=f"http://127.0.0.1:{self.notify_port}", W18_AGENCY=f"http://127.0.0.1:{self.agency_port}",
                   W18_JOBS_TOKEN=JOBS_TOKEN, POC_FAKE_NOW_FILE=str(self.clock), **(extra or {}))
        try:
            return subprocess.run(["node", str(KEY / script), f"http://127.0.0.1:{self.port}", *args], cwd=self.work,
                                  capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as e:
            return subprocess.CompletedProcess(e.cmd, 124, e.stdout or "", f"timeout {timeout}s")


def parse_results(p, name):
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert isinstance(out, list)
        return out
    except (ValueError, IndexError, AssertionError):
        return [{"id": "X", "name": f"{name} の実行", "pass": False, "detail": (p.stdout + p.stderr)[-800:]}]


def run_suites(app, work, adapter, round_, static):
    """後退テスト base と各機能の隠しテストを、1 つのサーバーで順に行う。"""
    env = Env(app, work, "suites", Path(work) / "suites.db", adapter)
    out = {}
    try:
        if not env.start():
            tail = env.server_log.read_text()[-600:] if env.server_log.exists() else ""
            return {"_start": [{"id": "X", "name": "サーバーの起動", "pass": False, "detail": tail}]}
        extra = {"W18_STATIC": json.dumps({"inProcessScheduler": static.get("inProcessScheduler", [])})}
        for s in ["base", *rounds_of(round_)]:
            t0 = time.time()
            out[s] = parse_results(env.run(f"{s}.cjs", adapter, extra=extra), s)
            out[s + "_seconds"] = round(time.time() - t0)
    finally:
        env.stop()
    return out


def upgrade_check(app, r2app, work, adapter_now, adapter_r2):
    """L08: 第 2 回の終わりの版で作った DB を、今の版で起動する。"""
    db = Path(work) / "upgrade.db"
    made_env = Env(r2app, work, "upgrade-r2", db, adapter_r2)
    made = None
    try:
        if made_env.start():
            p = made_env.run("f3-upgrade.cjs", slice_adapter(adapter_r2, 2), args=("make",))
            line = next((l for l in p.stderr.splitlines() if l.startswith("UPG ")), None)
            made = line[4:] if line else None
            note = "" if made else (p.stdout + p.stderr)[-400:]
        else:
            note = "第 2 回の版のサーバーが起動しない"
    finally:
        made_env.stop()
    if not made:
        return [{"id": "L08", "name": "移行（第 2 回の版のデータ）", "pass": False, "detail": f"前の版でデータを作れない: {note}"}]
    now_env = Env(app, work, "upgrade-now", db, adapter_now)
    try:
        if not now_env.start():
            return [{"id": "L08", "name": "移行（第 2 回の版のデータ）", "pass": False, "detail": "今の版のサーバーが移行後の DB で起動しない: "
                     + (now_env.server_log.read_text()[-400:] if now_env.server_log.exists() else "")}]
        return parse_results(now_env.run("f3-upgrade.cjs", adapter_now, args=("check",), extra={"W18_UPG": made}), "f3-upgrade")
    finally:
        now_env.stop()


def checks_of(app):
    out = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        try:
            code, log = sh(cmd, app, timeout=1200)
        except subprocess.TimeoutExpired:
            code, log = 124, "timeout"
        out[name] = code == 0
        if name == "test":
            m = re.search(r"^# pass (\d+)", log, re.M)
            f = re.search(r"^# fail (\d+)", log, re.M)
            out["tests_pass"], out["tests_fail"] = int(m.group(1)) if m else 0, int(f.group(1)) if f else 0
        if code != 0:
            out.setdefault("logs", {})[name] = log[-800:]
    return out


def ensure_tools():
    """コードの指標の道具（eslint・jscpd・typescript）を TOOLS に入れる（package-lock.json の版のまま）。"""
    src = HERE / "w18-metrics"
    TOOLS.mkdir(parents=True, exist_ok=True)
    for f in ("package.json", "package-lock.json", "metrics.mjs", "eslint.config.mjs"):
        shutil.copy(src / f, TOOLS / f)
    if not (TOOLS / "node_modules" / ".bin" / "eslint").exists():
        sh("npm ci --no-audit --no-fund", TOOLS, timeout=600)


def metrics_of(app):
    ensure_tools()
    code, out = sh(f"node '{TOOLS / 'metrics.mjs'}' '{app}'", TOOLS, timeout=600)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": out[-600:]}


def evaluate(repo, commit, round_, base, adapter, work, prev=None, r2=None, mutation=True):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    app = export_commit(repo, commit, work / "app")
    out = {"round": str(round_), "commit": commit, "adapter": adapter}
    out["checks"] = checks_of(app)
    out["static"] = static_checks(repo, app, base, commit, prev, work)
    if out["checks"].get("build"):
        out["suites"] = run_suites(app, work / "suites", slice_adapter(adapter, round_), round_, out["static"])
        rn = int(str(round_)[1:]) if str(round_).startswith("h") else int(round_)
        if (str(round_).startswith("h") or rn >= 3) and r2:
            r2app = export_commit(repo, r2, work / "r2app")
            if not (r2app / ".next").exists():
                sh("npm run build", r2app, timeout=1200)
            out["suites"]["f3-upgrade"] = upgrade_check(app, r2app, work / "upgrade", slice_adapter(adapter, round_),
                                                        json.loads((work / "adapter-r2.json").read_text()) if (work / "adapter-r2.json").exists() else {})
    else:
        out["suites"] = {"_build": [{"id": "X", "name": "ビルド", "pass": False, "detail": out["checks"].get("logs", {}).get("build", "")[-400:]}]}
    out["metrics"] = metrics_of(app)
    if mutation:
        out["mutation"] = mutation_cumulative(repo, base, commit, work / "mutation")
    out["points"] = points(out)
    return out


def mutation_cumulative(repo, base, commit, scratch):
    """grade_w10.mutation を、base（第 1 回の初期状態）からの変更行に対して行う。"""
    sys.path.insert(0, str(HERE))
    import grade_w10  # noqa: E402
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    clone = scratch / "repo"
    if not clone.exists():
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(repo), str(clone)], check=True)
        subprocess.run(["git", "-C", str(clone), "checkout", "-q", commit], check=True)
        subprocess.run(["cp", "-al", str(Path(repo) / "node_modules"), str(clone / "node_modules")], check=True)
    return grade_w10.mutation(str(clone), base, str(scratch / "work"))


# ---- 点数 ----

def items(out, suite):
    return [x for x in out.get("suites", {}).get(suite, []) if isinstance(x, dict)]


def rate(xs):
    return round(sum(1 for x in xs if x.get("pass")) / len(xs), 3) if xs else 0.0


def points(out):
    """その回の点（品質の内訳。系列の点の計算は report_w18.py）"""
    r = out["round"]
    feats = rounds_of(r)
    p = {"current": rate(items(out, feats[-1]))}
    allx = [x for s in ["base", *feats] for x in items(out, s)]
    allx += items(out, "f3-upgrade") if "f3-upgrade" in out.get("suites", {}) else []
    p["all"] = rate(allx)
    p["passed"] = {f"{s}:{x['id']}": bool(x.get("pass")) for s in ["base", *feats, "f3-upgrade"] for x in items(out, s)}
    p["mutation"] = (out.get("mutation") or {}).get("kill_rate")
    return p


# ---- 試行 ----

def raw(trial):
    return RAWS / trial


def series_of(trial):
    m = re.match(r"^W18(r[1-6]|h[123])-(.+)-(\d+)$", trial)
    if not m:
        sys.exit(f"W18 の試行 ID ではない: {trial}")
    return m.group(1), m.group(2), m.group(3)


def load_adapter(trial, repo, base, commit, round_, work):
    phase, cand, n = series_of(trial)
    sid = f"{cand}-{n}"
    name = f"{sid}-{'r' + str(round_) if not str(round_).startswith('h') else round_}"
    p = RESULTS / "adapters" / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text()), False
    whole = RESULTS / "adapters" / f"{sid}.json"  # 系列のすべての回で同じアダプター（参照の系列・最短の系列）
    if whole.exists():
        return json.loads(whole.read_text()), False
    sys.path.insert(0, str(HERE))
    import adapt_w18  # noqa: E402
    prev_adapter = None
    if not str(round_).startswith("h") and int(round_) > 1:
        q = RESULTS / "adapters" / f"{sid}-r{int(round_) - 1}.json"
        prev_adapter = json.loads(q.read_text()) if q.exists() else None
    elif str(round_).startswith("h"):
        q = RESULTS / "adapters" / f"{sid}-r6.json"
        prev_adapter = json.loads(q.read_text()) if q.exists() else None
    draft = adapt_w18.draft(repo, base, commit, round_, prev_adapter, Path(work) / "adapt")
    p.parent.mkdir(parents=True, exist_ok=True)
    (RESULTS / "adapters" / f"{name}.draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
    return draft.get("adapter") or {}, True


def main():
    args = sys.argv[1:]
    mutation = "--no-mutation" not in args
    arg = lambda k, d=None: args[args.index(k) + 1] if k in args else d  # noqa: E731
    if args and args[0] == "--repo":
        repo = Path(arg("--repo")).resolve()
        work = Path(tempfile.mkdtemp(prefix="w18-grade-"))
        adapter = json.loads(Path(arg("--adapter")).read_text())
        if arg("--adapter-r2"):
            shutil.copy(arg("--adapter-r2"), work / "adapter-r2.json")
        out = evaluate(repo, arg("--commit"), arg("--round"), arg("--base"), adapter, work, prev=arg("--prev"), r2=arg("--r2"), mutation=mutation)
        text = json.dumps(out, ensure_ascii=False, indent=1)
        if arg("--out"):
            Path(arg("--out")).write_text(text + "\n")
        else:
            print(text)
        print(summary_line(out), file=sys.stderr)
        return
    trial = args[0]
    phase, cand, n = series_of(trial)
    rw = raw(trial)
    repo = Path((rw / "workdir").read_text().strip()) / "app"
    base = (raw(f"W18r1-{cand}-{n}") / "baseline-commit").read_text().strip()
    commit = (rw / "final-commit").read_text().strip()
    round_ = phase[1:] if phase.startswith("r") else phase
    prev = base  # 第 1 回は初期状態と比べる（出荷済みのマイグレーションの書き換え）
    if phase.startswith("r") and int(round_) > 1:
        prev = (raw(f"W18r{int(round_) - 1}-{cand}-{n}") / "final-commit").read_text().strip()
    elif phase.startswith("h"):
        prev = (raw(f"W18r6-{cand}-{n}") / "final-commit").read_text().strip()
    r2f = raw(f"W18r2-{cand}-{n}") / "final-commit"
    r2 = r2f.read_text().strip() if r2f.exists() else None
    work = Path(tempfile.mkdtemp(prefix=f"grade-{trial}-"))
    adapter, drafted = load_adapter(trial, repo, base, commit, round_, work)
    for a2 in (RESULTS / "adapters" / f"{cand}-{n}-r2.json", RESULTS / "adapters" / f"{cand}-{n}.json"):
        if a2.exists():
            shutil.copy(a2, work / "adapter-r2.json")
            break
    out = evaluate(repo, commit, round_, base, adapter, work, prev=prev, r2=r2, mutation=mutation)
    out["adapter_drafted"] = drafted
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{trial}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"{trial}: {summary_line(out)}")


def summary_line(out):
    s = out.get("suites", {})
    parts = []
    for k, v in s.items():
        if k.endswith("_seconds") or not isinstance(v, list):
            continue
        parts.append(f"{k} {''.join('o' if x.get('pass') else 'x' for x in v)}")
    c = out.get("checks", {})
    m = out.get("metrics", {})
    mu = out.get("mutation") or {}
    return (f"[r{out['round']}] tc{'o' if c.get('typecheck') else 'x'} test{c.get('tests_pass')}/{c.get('tests_fail')} "
            f"build{'o' if c.get('build') else 'x'} | " + " | ".join(parts)
            + f" | cx mean {m.get('complexity', {}).get('mean')} max {m.get('complexity', {}).get('max')} dup {m.get('duplication', {}).get('percentage')}% "
            f"lint {m.get('lint', {}).get('warnings')} | mut {mu.get('killed')}/{mu.get('mutants')} | mig-rewritten {out.get('static', {}).get('migrations', {}).get('rewritten')}")


if __name__ == "__main__":
    main()
