#!/usr/bin/env python3
"""W15（テストの無い古いコードの改修: 校正機関 B 社の新しい CSV 形式の取込）の試行を採点用に調べ、results/workflow/W15/<試行ID>.json に書く。
設計は docs/poc/tasks/wf-W15-design.md、採点の決まりは docs/poc/answer-key/W15/grading.md（正解データ。作業用コピーには置かない）。

使い方:
  python3 scripts/poc/grade_w15.py <試行ID> [--cleanup]
  python3 scripts/poc/grade_w15.py --app <アプリのディレクトリ> --base <コミット> [--out <JSON>] [--no-mutation]   試行前の検証用
  python3 scripts/poc/grade_w15.py golden --app <初期状態のアプリ> --base <コミット>   黄金（A 社の CSV の、変更前の取込結果）を作る
    - golden:     A 社の CSV（answer-key/W15/fixtures_w15.py）を 1 ファイルずつ新しい DB で取り込み、応答と DB の変化を黄金と比べる
    - public / hidden: B 社の CSV の受け入れ（新しい DB）
    - characterization: 古い取込処理の元の行をわざと壊した版を、候補のテストが検出した割合と、テストを書いた順番（コミットの履歴）
    - mutation:   候補が src/lib/ に足した行を壊した版を、候補のテストが検出した割合（grade_w10.mutation）
削除はしない（採点用の DB・ログは毎回新しい一時ディレクトリに作り、そのまま残す）。
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W15"
FAKE_NOW = "2027-01-15T03:00:00Z"  # B 社の CSV を確かめるときの採点のサーバーの時計（b_suite を参照）
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W15"
sys.path.insert(0, str(HERE))
import grade_w14 as g14  # noqa: E402  サーバー・HTTP・DB の部品は W14 と同じ

_spec = importlib.util.spec_from_file_location("fixtures_w15", KEY / "fixtures_w15.py")
FIX = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIX)
LEGACY = "src/lib/legacy/calib-import.ts"


def fixtures():
    d = Path(tempfile.mkdtemp(prefix="w15-fix-"))
    FIX.write(d)
    return d


def post_csv(c, data):
    import urllib.request
    import urllib.error
    req = urllib.request.Request(c.base + "/api/calibrations/import", data=data, method="POST", headers={"content-type": "text/csv"})
    t0 = time.time()
    try:
        with c.opener.open(req, timeout=120) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    text = raw.decode("utf-8", "replace")
    try:
        j = json.loads(text)
    except ValueError:
        j = None
    return {"status": status, "json": j, "text": text[:2000], "ms": (time.time() - t0) * 1000}


def db_state(db):
    recs = g14.db_query(db, """SELECT i.management_no AS no, r.calibrated_on AS date, r.result, r.agency, r.certificate_no AS cert
                               FROM calibration_records r JOIN instruments i ON i.id = r.instrument_id ORDER BY 1, 2, 5""")
    inst = g14.db_query(db, "SELECT management_no AS no, status, last_calibrated_on AS last, note FROM instruments ORDER BY 1")
    return {"records": recs, "instruments": inst}


def summarize(res):
    j = res["json"] if isinstance(res["json"], dict) else {}
    lines = lambda k: sorted(x.get("line") for x in j.get(k, []) if isinstance(x, dict) and isinstance(x.get("line"), int)) \
        if isinstance(j.get(k), list) else None
    return {"status": res["status"], "imported": j.get("imported"), "skipped_lines": lines("skipped"), "error_lines": lines("errors")}


def with_server(app, work, name, fn):
    db = Path(work) / f"{name}.db"
    srv = g14.Server(app, work, name, db)
    if not srv.start():
        return {"error": "サーバーが起動しない", "log": srv.log.read_text()[-400:]}
    try:
        c = g14.Client(srv.base()).login()
        return fn(c, db)
    finally:
        srv.stop()


def run_a_files(app, work):
    fx = fixtures()
    out = {}
    for name, *_ in FIX.A_FILES:
        data = (fx / f"{name}.csv").read_bytes()

        def go(c, db, data=data, name=name):
            before = db_state(db)
            res = [summarize(post_csv(c, data))]
            if name in FIX.A_REPEAT:
                res.append(summarize(post_csv(c, data)))
            after = db_state(db)
            added = [r for r in after["records"] if r not in before["records"]]
            changed = [i for i in after["instruments"] if i not in before["instruments"]]
            return {"responses": res, "records_added": added, "instruments_changed": changed}
        out[name] = with_server(app, work, f"a-{name}", go)
    return out


def golden_checks(app, work):
    want = json.loads((KEY / "golden.json").read_text())
    got = run_a_files(app, work)
    checks = []
    for name in want:
        w, g = want[name], got.get(name, {})
        diffs = []
        for k in ("responses", "records_added", "instruments_changed"):
            if w.get(k) != g.get(k):
                diffs.append(k)
        checks.append({"id": name, "pass": not diffs, "diff": diffs,
                       "detail": "" if not diffs else json.dumps({k: {"want": w.get(k), "got": g.get(k)} for k in diffs}, ensure_ascii=False)[:600]})
    return checks


class Probe(g14.Probe):
    pass


def b_suite(app, work):
    fx = fixtures()
    pub, hid = Probe(), Probe()
    need = g14.need

    def go(c, db):
        st = {}

        def send(name):
            return post_csv(c, (fx / f"{name}.csv").read_bytes())

        def recs(no=None):
            rs = db_state(db)["records"]
            return [r for r in rs if no is None or r["no"] == no]

        def p1():
            r = send("b01-public")
            st["b01"] = r
            need(r["status"] == 200, f"取り込めない: {g14.show(r)}")
            need((r["json"] or {}).get("imported") == 3, f"3 件取り込めない: {g14.show(r)}")
            got = {(x["no"], x["date"], x["result"]) for x in recs() if x["date"].startswith("2026-12")}
            need({("MI-0003", "2026-12-01", "pass"), ("MI-0004", "2026-12-01", "fail"), ("MI-0006", "2026-12-02", "pass")} <= got,
                 f"記録が違う: {sorted(got)}")
            inst = {i["no"]: i for i in db_state(db)["instruments"]}
            need(inst["MI-0004"]["status"] == "suspended", "不合格で使用停止にならない")
        pub.check("P1", "B 社の仕様書どおりの CSV（同じ取込の送り先）を取り込める", p1)

        def b02():
            need(st.get("b01", {}).get("status") == 200, "P1 が失敗")
            need(recs("MI-0003") and recs("MI-0006"), "ハイフン無しの機器番号（MI0003）が台帳の計測器に結びつかない")
        hid.check("B02", "ハイフン無しの機器番号（MI0003）を同じ計測器として扱う", b02)

        def b03():
            r = send("b02-cond")
            need(r["status"] == 200, f"取り込めない: {g14.show(r)}")
            rs = [x for x in recs("MI-0010") if x["date"] == "2026-12-03"]
            need(rs and rs[0]["result"] == "pass", f"条件付き合格が合格にならない: {rs}")
            note = next(i for i in db_state(db)["instruments"] if i["no"] == "MI-0010")["note"]
            need("条件付き合格" in note and "2026-12-03" in note and "湿度" in note, f"備考に条件付き合格が書き足されない: {note!r}")
        hid.check("B03", "COND（条件付き合格）は合格として取り込み、計測器の備考に「条件付き合格（校正日）: コメント」を書き足す", b03)

        def b04():
            rs = [x for x in recs() if x["date"].startswith("2026-12")]
            need(rs and all(x["agency"] == "西日本校正センター" for x in rs), f"校正機関が西日本校正センターでない: {sorted({x['agency'] for x in rs})}")
        hid.check("B04", "B 社の校正記録の校正機関は「西日本校正センター」", b04)

        def b05():
            n0 = len(recs())
            r = send("b03-endmismatch")
            need(len(recs()) == n0, "END の件数が合わないファイルの一部が取り込まれた")
            j = r["json"] if isinstance(r["json"], dict) else {}
            need(r["status"] >= 400 or j.get("errors"), f"件数の不一致が誤りとして返らない: {g14.show(r)}")
        hid.check("B05", "END の件数と行数が合わないファイルは 1 件も取り込まず、誤りを返す", b05)

        def b06():
            n0 = len(recs())
            r = send("b01-public")
            need(len(recs()) == n0, "同じファイルを 2 回取り込むと二重になる")
            need(r["status"] == 200 and (r["json"] or {}).get("imported") == 0, f"2 回目の応答が違う: {g14.show(r)}")
        hid.check("B06", "同じ B 社のファイルを 2 回取り込んでも二重にならない", b06)

        def b09():
            r = send("b04-mixed")
            st["b04"] = r
            need(r["status"] == 200, f"取り込めない: {g14.show(r)}")
            j = r["json"] or {}
            # 取り込んだ件数ではなく、記録そのもので見る（同じ日の重複を読み飛ばさないと 3 件になり、B07 と二重に落ちるため。試行の後に直した）
            need(any(x["date"] == "2026-12-05" for x in recs("MI-0001")) and any(x["date"] == "2026-12-06" for x in recs("MI-0009")),
                 f"台帳に無い番号・読めない判定以外の行を取り込まない: {g14.show(r)}")
            need(not any(x["date"] == "2026-12-05" for x in recs("MI-0009")), f"読めない判定（UNKNOWN）の行を取り込んだ: {g14.show(r)}")
            need(len(j.get("errors", [])) >= 2, f"誤りの行が返らない: {g14.show(r)}")
        hid.check("B09", "台帳に無い機器番号・読めない判定の行は誤りにして、ほかの行は取り込む", b09)

        def b07():
            need(st.get("b04", {}).get("status") == 200, "B09 が失敗")
            rs = [x for x in recs("MI-0009") if x["date"] == "2026-12-06"]
            need(len(rs) == 1, f"同じファイルの中の重複（同じ機器・同じ日）が 1 件にならない: {rs}")
        hid.check("B07", "同じファイルの中の重複（同じ機器・同じ校正日）は後の行を読み飛ばす", b07)

        def b08():
            r = send("b05-crlf-bom")
            need(r["status"] == 200 and (r["json"] or {}).get("imported") == 1, f"BOM・CRLF の B 社のファイルを取り込めない: {g14.show(r)}")
        hid.check("B08", "B 社のファイルの形式を自動で見分ける（BOM・CRLF の場合も）", b08)

        def b10():
            j = st.get("b01", {}).get("json")
            need(isinstance(j, dict) and isinstance(j.get("imported"), int) and isinstance(j.get("skipped"), list) and isinstance(j.get("errors"), list),
                 f"応答の形（imported・skipped・errors）が変わった: {j}")
            for k in ("skipped", "errors"):
                for x in j[k]:
                    need(isinstance(x, dict) and isinstance(x.get("line"), int), f"{k} の要素の形が変わった: {x}")
        hid.check("B10", "取込の応答の形（imported・skipped・errors と各要素の line）が変わっていない", b10)
        return {}

    # 採点のサーバーの時計を 2027-01-15 に進める（B 社の CSV の日付が 2026 年 12 月で、採点の日より後のため。未来の日付を
    # 誤りにする作りを誤って落としていたので、試行の後に足した。黄金テスト（A 社）は黄金を作ったときと同じ本当の時計で動かす）
    saved = {k: os.environ.get(k) for k in ("NODE_OPTIONS", "POC_FAKE_NOW")}
    os.environ["NODE_OPTIONS"] = (saved["NODE_OPTIONS"] + " " if saved["NODE_OPTIONS"] else "") + f"--require {KEY / 'fake-now.cjs'}"
    os.environ["POC_FAKE_NOW"] = FAKE_NOW
    try:
        with_server(app, work, "b-suite", go)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    order = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10"]
    hid.results.sort(key=lambda r: order.index(r["id"]))
    return pub.results, hid.results


# ---- 特性テスト ----

def legacy_mutants(app, base):
    """初期状態の古い取込処理の行から作った変異体のうち、候補の木に同じ行がそのまま残っているものを返す。"""
    sys.path.insert(0, str(HERE))
    import grade_w10  # noqa: E402
    bdir = g14.export_base(app, base)
    src = (bdir / LEGACY).read_text()
    # grade_w10 の作り方を、古い取込処理の全行に当てる（初期状態のファイルを「足された行」とみなす）
    fake = Path(tempfile.mkdtemp(prefix="w15-legacy-"))
    subprocess.run(f"git init -q {fake} && mkdir -p {fake}/src/lib/legacy", shell=True, check=True)
    subprocess.run(["git", "-C", str(fake), "-c", "user.name=p", "-c", "user.email=p@x", "commit", "-q", "--allow-empty", "-m", "empty"], check=True)
    (fake / LEGACY).write_text(src)
    subprocess.run(["git", "-C", str(fake), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(fake), "-c", "user.name=p", "-c", "user.email=p@x", "commit", "-q", "-m", "legacy"], check=True)
    muts = grade_w10.mutants_for(str(fake), "HEAD~1")
    lines = src.splitlines(keepends=True)
    offs = [0]
    for l in lines:
        offs.append(offs[-1] + len(l))
    out = []
    files = [p for p in Path(app).glob("src/**/*.ts") if ".test." not in p.name]
    texts = {p: p.read_text() for p in files}
    for m in muts:
        line = lines[m["line"] - 1]
        col = m["pos"] - offs[m["line"] - 1]
        for p, t in texts.items():
            i = t.find(line)
            if i >= 0 and t.count(line) == 1:
                out.append({**m, "file": str(p.relative_to(app)), "pos": i + col})
                break
    return out, len(muts)


A_TEST_MARK = r"管理番号|東日本計測サービス|R8\.|令和|importCalibrationCsv"


def is_importer_src(n):
    return n.startswith("src/lib/") and ("import" in n or "legacy" in n or "csv" in n.lower())


def is_test_file(n):
    return n.startswith("tests/") or ".test." in n


def transcript_order(raw, app):
    """トランスクリプト（raw/<試行ID>/step*.jsonl）で、A 社の形式を確かめるテストのファイルへの最初の書き込みと、
    取込処理のソースへの最初の変更の、どちらが先かを見る（2026-11-10 コーディネーターの指示。最後に 1 回だけコミットする
    候補でも、先にテストを書いていれば点が入るように）。ファイルを書く道具（Write・Edit・MultiEdit）と、Bash のリダイレクト・
    sed -i・tee を数える。テストのファイルは、書いた中身か、作業後のファイルに A 社の印（見出し・値・関数名）があれば数える。"""
    raw, app = Path(raw), Path(app)
    steps = sorted(raw.glob("step*.jsonl"), key=lambda f: int(re.sub(r"\D", "", f.stem) or 0))
    root = str(app.resolve()) + "/"
    seq = 0
    first_test = first_change = None

    def rel(pth):
        pth = str(pth)
        return pth[len(root):] if pth.startswith(root) else pth.lstrip("./")

    def final_has_mark(n):
        f = app / n
        return f.exists() and bool(re.search(A_TEST_MARK, f.read_text(errors="ignore")))

    for f in steps:
        for line in f.read_text(errors="ignore").splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("type") != "assistant":
                continue
            for c in (j.get("message") or {}).get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                seq += 1
                inp = c.get("input") or {}
                writes = []
                if c.get("name") in ("Write", "Edit", "MultiEdit"):
                    body = inp.get("content") or inp.get("new_string") or json.dumps(inp.get("edits") or "", ensure_ascii=False)
                    writes.append((rel(inp.get("file_path", "")), body))
                elif c.get("name") == "Bash":
                    cmd = inp.get("command", "")
                    for m in re.finditer(r"(?:>>?|tee(?:\s+-a)?|sed\s+-i\S*\s+(?:'[^']*'|\"[^\"]*\"|\S+))\s+([\w./@\[\]-]+)", cmd):
                        writes.append((rel(m.group(1)), cmd))
                for n, body in writes:
                    if first_test is None and is_test_file(n) and (re.search(A_TEST_MARK, body) or final_has_mark(n)):
                        first_test = seq
                    if first_change is None and is_importer_src(n):
                        first_change = seq
    return {"tool_calls": seq, "first_characterization_call": first_test, "first_importer_change_call": first_change}


def characterization(app, base, work, raw=None):
    sys.path.insert(0, str(HERE))
    import grade_w10  # noqa: E402
    muts, total = legacy_mutants(app, base)
    res = {"legacy_mutants": total, "found_in_candidate": len(muts)}
    if muts:
        orig = grade_w10.mutants_for
        grade_w10.mutants_for = lambda a, b: muts  # 同じ実行の仕組みで、古い行の変異体だけを流す
        try:
            m = grade_w10.mutation(str(app), base, str(Path(work) / "legacy-mutation"))
        finally:
            grade_w10.mutants_for = orig
        res.update({"killed": m["killed"], "mutants": m["mutants"], "survivors": m.get("survivors", [])[:15],
                    "baseline_tests_pass": m["baseline_tests_pass"]})
    else:
        res.update({"killed": 0, "mutants": 0})
    # 書いた順番: A 社の形式を確かめるテスト（見出し「管理番号」や A 社の値を含むテスト）を足したコミットが、
    # 古い取込処理（またはその置き場所）を変えたコミットより前か同じか
    log = g14.git(app, "log", "--reverse", "--format=%H", f"{base}..HEAD").split()
    first_test = first_change = None
    for i, h in enumerate(log):
        names = g14.git(app, "show", "--name-only", "--format=", h).split()
        if first_change is None and any(is_importer_src(n) for n in names):
            first_change = i
        if first_test is None:
            for n in names:
                if is_test_file(n):
                    body = g14.git(app, "show", f"{h}:{n}") if n else ""
                    if re.search(A_TEST_MARK, body):
                        first_test = i
                        break
    res.update({"commits": len(log), "first_characterization_commit": first_test, "first_importer_change_commit": first_change})
    res["order_by"] = "commits"
    # 試行ではトランスクリプトの順番で判定する（コミットの順番は記録だけ）。トランスクリプトが無い（試行前の確認の実装）ときはコミットの順番
    if raw is not None and any(Path(raw).glob("step*.jsonl")):
        t = transcript_order(raw, app)
        res["transcript"] = t
        res["order_by"] = "transcript"
        first_test, first_change = t["first_characterization_call"], t["first_importer_change_call"]
    if first_test is None:
        res["order"] = "none"
    elif first_change is None or first_test < first_change:
        res["order"] = "before"
    elif first_test == first_change:
        res["order"] = "same"
    else:
        res["order"] = "after"
    return res


def evaluate(app, base, work, mutation=True, raw=None):
    app, work = Path(app), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = g14.sh(cmd, app)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    lines = [(f, l) for f, l in g14.added_lines(app, base, ["src"]) if ".test." not in f]
    code = "\n".join(l for _, l in lines)
    docs = "\n".join(l for _, l in g14.added_lines(app, base, ["docs", "README.md", "CLAUDE.md"]))
    out = {"checks": checks, "routes": g14.new_routes(app, base),
           "static": {"legacy_file_changed": bool(g14.git(app, "diff", "--name-only", base, "HEAD", "--", LEGACY).strip()),
                      "legacy_file_exists": (app / LEGACY).exists(),
                      "changed_src_files": sorted({f for f, _ in lines}),
                      "logger_used": bool(re.search(r"\blogger\.(info|warn|error)\s*\(", code)),
                      "new_deps": g14.git(app, "diff", base, "HEAD", "--", "package.json").count("\n+  ") > 0,
                      "docs_changed": bool(docs.strip())}}
    if checks["build"]["pass"]:
        out["golden"] = golden_checks(app, work)
        out["public"], out["hidden"] = b_suite(app, work)
    else:
        out.update({"golden": [], "public": [], "hidden": []})
    out["characterization"] = characterization(app, base, work, raw)
    if mutation:
        import grade_w10  # noqa: E402
        out["mutation"] = grade_w10.mutation(str(app), base, str(work / "mutation"))
    return out


def summary_line(r):
    def bits(xs):
        return "".join("o" if x["pass"] else "x" for x in xs)
    ch = r.get("characterization", {})
    mu = r.get("mutation", {})
    return (f"public {bits(r.get('public', []))} hidden {bits(r.get('hidden', []))} golden {bits(r.get('golden', []))} "
            f"characterization {ch.get('killed')}/{ch.get('mutants')} (of {ch.get('legacy_mutants')}) order={ch.get('order')} "
            f"mutation {mu.get('killed')}/{mu.get('mutants')}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "golden":
        app = args[args.index("--app") + 1]
        work = tempfile.mkdtemp(prefix="w15-golden-")
        g14.sh("npm run build", app)
        got = run_a_files(app, work)
        (KEY / "golden.json").write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n")
        for k, v in got.items():
            print(k, v["responses"], len(v["records_added"]), len(v["instruments_changed"]))
        return
    if args and args[0] == "--app":
        app = args[1]
        base = args[args.index("--base") + 1]
        work = tempfile.mkdtemp(prefix="w15-grade-")
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
    if args and args[0] == "--recheck-b":
        # 採点の誤検出を直したあと、B 社の CSV の確かめ（公開・隠し）だけをやり直し、結果の JSON の public・hidden を差し替える
        # （ビルド済みの作業用コピーで。黄金テスト・特性テスト・ミューテーションは変えない。前の値は *_before_recheck に残す）
        results = ROOT / "docs" / "poc" / "results" / "workflow" / "W15"
        for trial in args[1:]:
            f = results / f"{trial}.json"
            res = json.loads(f.read_text())
            raw = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / trial
            app = Path((raw / "workdir").read_text().strip()) / "app"
            w = res["w15"]
            pub, hid = b_suite(app, Path(tempfile.mkdtemp(prefix=f"w15-recheck-{trial}-")))
            for k, v in (("public", pub), ("hidden", hid)):
                w.setdefault(f"{k}_before_recheck", w.get(k))
                w[k] = v
            f.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
            print(trial, "public", "".join("o" if x["pass"] else "x" for x in pub), "hidden", "".join("o" if x["pass"] else "x" for x in hid))
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W15", trial]
    import grade  # noqa: E402
    grade.main()
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    w15 = evaluate(grade.APP, base, Path(tempfile.mkdtemp(prefix=f"w15-grade-{trial}-")), raw=grade.RAW)
    w15["checks"] = {k: v["pass"] for k, v in w15["checks"].items()}
    result["w15"] = w15
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line(w15)}")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
