#!/usr/bin/env python3
"""W34（レビューの指摘で直させた後の質）の採点。docs/poc/tasks/wf-W34-design.md の「測るもの」。

使い方:
  python3 scripts/poc/grade_w34.py <試行ID> [--cleanup]
      試行（W34-<設定>-<題材>-<回>）の作業用コピーを採点し、results/workflow/W34/<試行ID>.json に書く。
      レビューの指摘（REVIEW.md）は、REVIEW.md を最初に足したコミットのもの（直す前の指摘）を保存する。
  python3 scripts/poc/grade_w34.py --app <ディレクトリ> --case <f1〜f4>
      任意のアプリのディレクトリ（PR のままの状態など）を採点して、結果を表示する（基準の値を測るため）。

採点はアプリの写し（一時ディレクトリ）で行い、作業用コピーは書き換えない。
  - checks: 型検査・テスト（npm test）
  - hidden: 隠しテスト（answer-key/W34/cases/<題材>/hidden.test.ts）の各項目の合否
  - f1: 登録の仕組み（AttributeRegistry）が残っているか、優先度の値・表示名の書き写しの数
  - f3・f4: 変異（answer-key/W34/mutants.json）を 1 つずつ当て、参加者のテスト（npm test）で落とせた数
  - f4: 時間がたった状態（時計・日本時間の朝・初期データ・文言・負荷）で、集計のテストが落ちるか
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W34"
MUTANTS = json.loads((KEY / "mutants.json").read_text())
NODE_TEST = ["node", "--experimental-strip-types", "--no-warnings", "--test"]


def sh(cmd, cwd, timeout=600, env=None):
    import os
    e = {**os.environ, **(env or {})}
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=e, shell=isinstance(cmd, str))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def copy_app(app: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="w34-grade-"))
    dst = tmp / "app"
    shutil.copytree(app, dst, ignore=shutil.ignore_patterns("node_modules", ".next", ".git"), symlinks=True)
    (dst / "node_modules").symlink_to((app / "node_modules").resolve())
    return dst


def test_counts(out: str):
    p = re.search(r"^# pass (\d+)", out, re.M)
    f = re.search(r"^# fail (\d+)", out, re.M)
    return (int(p.group(1)) if p else 0), (int(f.group(1)) if f else 0)


def run_hidden(app: Path, case: str):
    d = app / "tests-hidden"
    d.mkdir(exist_ok=True)
    shutil.copy(KEY / "cases" / case / "hidden.test.ts", d / "hidden.test.ts")
    code, out = sh(NODE_TEST + ["tests-hidden/hidden.test.ts"], app, timeout=300)
    items = []
    for m in re.finditer(r"^    (ok|not ok) \d+ - (H\d+)\s*(.*)$", out, re.M):
        items.append({"id": m.group(2), "name": m.group(3).strip(), "pass": m.group(1) == "ok"})
    shutil.rmtree(d)
    return {"exit": code, "items": items, "passed": sum(i["pass"] for i in items), "total": len(items),
            "log": out[-1500:] if not items else ""}


def f1_design(app: Path):
    src = app / "src"
    text = {p: p.read_text(errors="ignore") for p in src.rglob("*.ts*")}
    registry = any("AttributeRegistry" in t or "attributeRegistry" in t for t in text.values())
    dup_values = sum(len(re.findall(r'"high",\s*"medium",\s*"low"', t)) for t in text.values())
    dup_labels = sum(len(re.findall(r'high:\s*"高"', t)) for t in text.values())
    return {"registry_remains": registry, "priority_value_lists": dup_values, "priority_label_maps": dup_labels}


def mutation(app: Path, case: str):
    results = []
    for m in MUTANTS.get(case, []):
        target = app / m["file"]
        if not target.exists() or m["find"] not in target.read_text():
            results.append({"id": m["id"], "status": "n/a"})
            continue
        work = copy_app(app)
        t = work / m["file"]
        t.write_text(t.read_text().replace(m["find"], m["replace"], 1))
        code, out = sh("npm test", work, timeout=300)
        results.append({"id": m["id"], "status": "killed" if code != 0 else "survived"})
        shutil.rmtree(work.parent)
    applicable = [r for r in results if r["status"] != "n/a"]
    return {"items": results, "killed": sum(r["status"] == "killed" for r in applicable), "applicable": len(applicable)}


PRELOAD = """
const T = Date.parse(process.env.FAKE_NOW);
const Real = Date;
const off = T - Real.now();
class FakeDate extends Real {
  constructor(...a) { if (a.length === 0) super(Real.now() + off); else super(...a); }
  static now() { return Real.now() + off; }
}
globalThis.Date = FakeDate;
"""


def summary_test_files(app: Path):
    return sorted(str(p.relative_to(app)) for p in (app / "tests").glob("*.test.ts") if "summary" in p.read_text())


def f4_perturb(app: Path):
    files = summary_test_files(app)
    if not files:
        return {"files": [], "note": "集計のテストが無い"}
    code, out = sh(NODE_TEST + files, app, timeout=300)
    base_pass, base_fail = test_counts(out)
    res = {"files": files, "tests": base_pass + base_fail, "baseline_fail": base_fail, "perturbations": []}
    for p in MUTANTS["f4_perturbations"]:
        work = copy_app(app)
        env, failed = None, False
        cmd = NODE_TEST + files
        if p["kind"] == "clock":
            (work / "fake-now.mjs").write_text(PRELOAD)
            cmd = ["node", "--experimental-strip-types", "--no-warnings", "--import", "./fake-now.mjs", "--test"] + files
            env = {"FAKE_NOW": p["now"]}
        elif p["kind"] == "seed":
            seed = work / "src/lib/db/seed.ts"
            s = seed.read_text()
            s2 = re.sub(r"(SEED_TASKS = \[)", r'\1\n  { title: "追加のタスク", status: "todo", assignee: "tanaka", dueDate: "2027-03-31" },', s, count=1)
            seed.write_text(s2)
        elif p["kind"] == "wording":
            f = work / p["file"]
            if f.exists() and p["find"] in f.read_text():
                f.write_text(f.read_text().replace(p["find"], p["replace"]))
            else:
                res["perturbations"].append({"id": p["id"], "status": "n/a"})
                shutil.rmtree(work.parent)
                continue
        if p["kind"] == "load":
            procs = [subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                     for _ in range(p["parallel"])]
            fails = sum(1 for pr in procs if pr.wait(timeout=600) != 0)
            res["perturbations"].append({"id": p["id"], "status": "fail" if fails else "pass", "failed_runs": fails})
        else:
            c, o = sh(cmd, work, timeout=300, env=env)
            _, nf = test_counts(o)
            res["perturbations"].append({"id": p["id"], "status": "fail" if c != 0 else "pass", "failed_tests": nf})
        shutil.rmtree(work.parent)
    res["fragile"] = sum(1 for x in res["perturbations"] if x["status"] == "fail")
    return res


def evaluate(app: Path, case: str):
    work = copy_app(app)
    try:
        tc, tout = sh("npm run typecheck", work, timeout=300)
        nc, nout = sh("npm test", work, timeout=300)
        p, f = test_counts(nout)
        out = {"checks": {"typecheck": tc == 0, "test": nc == 0, "tests_pass": p, "tests_fail": f},
               "hidden": run_hidden(work, case)}
        if case == "f1":
            out["design"] = f1_design(work)
        if case in ("f3", "f4"):
            out["mutation"] = mutation(work, case) if nc == 0 else {"note": "テストが通らないので測らない"}
        if case == "f4":
            out["perturb"] = f4_perturb(work)
        return out
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)


def main():
    if sys.argv[1] == "--app":
        app, case = Path(sys.argv[2]), sys.argv[4]
        print(json.dumps(evaluate(app, case), ensure_ascii=False, indent=1))
        return
    trial = sys.argv[1]
    m = re.fullmatch(r"W34-(.+)-(f\d)-(\d+)", trial)
    if not m:
        sys.exit(f"W34 の試行 ID ではない: {trial}")
    config, case, rep = m.group(1), m.group(2), int(m.group(3))
    sys.argv = [sys.argv[0], "W34", trial] + sys.argv[2:]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import grade  # noqa: E402
    app, raw = grade.APP, grade.RAW
    stats = grade.transcript_stats()
    base = (raw / "baseline-commit").read_text().strip()

    def git(*a):
        return subprocess.run(["git", *a], cwd=app, capture_output=True, text=True).stdout
    review_md, first = "", ""
    for line in git("log", "--reverse", "--format=%H", f"{base}..HEAD").split():
        if subprocess.run(["git", "cat-file", "-e", f"{line}:REVIEW.md"], cwd=app).returncode == 0:
            first = line
            review_md = git("show", f"{line}:REVIEW.md")
            break
    numstat = git("diff", "--numstat", base, "HEAD", "--", ".", ":!REVIEW.md")
    added = deleted = 0
    for l in numstat.splitlines():
        a, d, *_ = l.split("\t")
        if a.isdigit():
            added += int(a)
            deleted += int(d)
    pr_patch = (KEY / "cases" / case / "review.patch").read_text()
    pr_added = sum(1 for l in pr_patch.splitlines() if l.startswith("+") and not l.startswith("+++"))
    pr_deleted = sum(1 for l in pr_patch.splitlines() if l.startswith("-") and not l.startswith("---"))
    final_review = git("show", "HEAD:REVIEW.md")
    result = {
        "trial": trial, "scenario": "W34", "config": config, "case": case, "rep": rep,
        "review_md": review_md, "review_commit": first, "review_md_final": final_review,
        "fixed": {"diff_added": added, "diff_deleted": deleted, "pr_added": pr_added, "pr_deleted": pr_deleted,
                  "commits": git("log", "--oneline", f"{base}..HEAD").strip().splitlines()},
        "eval": evaluate(app, case),
        "transcript": stats,
        "interventions": len((raw / "interventions.log").read_text().splitlines()) if (raw / "interventions.log").exists() else 0,
    }
    out = ROOT / "docs" / "poc" / "results" / "workflow" / "W34" / f"{trial}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    e = result["eval"]
    print(f"{trial}: hidden {e['hidden']['passed']}/{e['hidden']['total']} test={e['checks']['test']} "
          f"mut={e.get('mutation', {}).get('killed')} fragile={e.get('perturb', {}).get('fragile')} cost=${stats.get('cost_usd', 0):.2f}")
    if "--cleanup" in sys.argv:
        (raw / "diff.patch").write_text(git("diff", base, "HEAD"))
        grade.cleanup()


if __name__ == "__main__":
    main()
