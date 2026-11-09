#!/usr/bin/env python3
"""W11（実在する OSS の解決済み課題）の共通処理。

使い方:
  python3 scripts/poc/oss/oss.py prepare <課題ID>
      本家のリポジトリを固定コミットで取得し、
      - 作業用の初期状態（修正の 1 つ前のソース。履歴なし。node の課題は依存も入れる）を
        $POC_OSS_ROOT/<課題ID>/template に作る
      - 隠しテスト（修正で変更されたテストファイル）を、修正前と修正後のソースで実行し、
        F2P（修正前に失敗し修正後に通る）と P2P（修正前後とも通る）を
        docs/poc/answer-key/W11/<課題ID>.json に書く（正解データ。作業用コピーには置かない）
  python3 scripts/poc/oss/oss.py copy-app <課題ID> <コピー先 app> <試行の作業領域>
      run-trial.sh が呼ぶ。初期状態を作業用コピーへ写し（node_modules はハードリンク）、
      python の課題は <試行の作業領域>/venv に環境を作る（app の外なので git に入らない）。

作業用コピーには本家の履歴・修正後のコード・隠しテストを置かない。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASKS = json.loads((Path(__file__).parent / "tasks.json").read_text())
CACHE = Path(os.environ.get("POC_CACHE", ROOT / ".poc-cache")) / "oss"
OSS_ROOT = Path(os.environ.get("POC_OSS_ROOT", "/tmp/poc-oss"))
KEY_DIR = ROOT / "docs" / "poc" / "answer-key" / "W11"
TEST_RE = re.compile(r"(^|/)(testing|tests?|__tests__)/|\.test\.[cm]?[jt]sx?$|(^|/)test_[^/]*\.py$")
PY = os.environ.get("POC_OSS_PYTHON", "3.12")


def sh(cmd, cwd=None, env=None, check=True, timeout=1800):
    e = dict(os.environ, **(env or {}))
    p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise SystemExit(f"failed: {' '.join(map(str, cmd))}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return p


def task(tid):
    if tid not in TASKS or tid.startswith("_"):
        raise SystemExit(f"unknown task: {tid}")
    return TASKS[tid]


def clone(t):
    d = CACHE / t["repo"].split("/")[1]
    if not (d / ".git").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        sh(["git", "clone", "-q", "--filter=blob:none", f"https://github.com/{t['repo']}.git", str(d)], timeout=900)
    if sh(["git", "-C", str(d), "cat-file", "-e", t["fix"]], check=False).returncode != 0:
        sh(["git", "-C", str(d), "fetch", "-q", "origin"], timeout=900)
    return d


def export(repo, commit, dest):
    dest.mkdir(parents=True, exist_ok=True)
    arch = subprocess.Popen(["git", "-C", str(repo), "archive", commit], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=arch.stdout, check=True)
    arch.wait()


def changed_files(repo, t):
    out = sh(["git", "-C", str(repo), "diff", "--name-only", t["fix"] + "^1", t["fix"]]).stdout.split()
    tests = [f for f in out if TEST_RE.search(f)]
    return tests, [f for f in out if f not in tests]


def hidden_tests(repo, t):
    """隠しテスト（修正後のテストファイル）。{パス: 内容 or None（修正で削除）}"""
    tests, _ = changed_files(repo, t)
    res = {}
    for f in tests:
        p = sh(["git", "-C", str(repo), "show", f"{t['fix']}:{f}"], check=False)
        res[f] = p.stdout if p.returncode == 0 else None
    return res


def apply_files(app, files):
    for f, content in files.items():
        p = Path(app) / f
        if content is None:
            if p.exists():
                p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)


def runnable(t, files):
    """実行するテストファイル（削除されたものと、テストでない補助ファイルを除く）"""
    out = []
    for f, c in files.items():
        if c is None:
            continue
        if t["lang"] == "python" and re.search(r"(^|/)test_[^/]*\.py$", f):
            out.append(f)
        if t["lang"] == "node" and re.search(r"\.test\.[cm]?[jt]sx?$", f):
            out.append(f)
    return out


def make_venv(t, app, venv):
    sh(["uv", "venv", "-q", "--python", PY, str(venv)])
    sh(["uv", "pip", "install", "-q", "--python", str(Path(venv) / "bin" / "python"), *t["install"]],
       cwd=app, env=t.get("env"), timeout=1200)


def node_install(app):
    env = {"COREPACK_ENABLE_STRICT": "0", "HUSKY": "0", "CI": "1"}
    # package.json の workspaces だけでワークスペースを定義している版（pnpm 以外の管理ツール向け）は、
    # インストールの間だけ pnpm-workspace.yaml を置く
    ws = Path(app) / "pnpm-workspace.yaml"
    tmp_ws = not ws.exists() and "workspaces" in json.loads((Path(app) / "package.json").read_text())
    if tmp_ws:
        ws.write_text("packages:\n" + "".join(f"  - {w}\n" for w in json.loads((Path(app) / "package.json").read_text())["workspaces"]))
    lock = Path(app) / "pnpm-lock.yaml"
    orig = lock.read_text() if lock.exists() else None
    p = sh(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=app, env=env, check=False, timeout=1500)
    if p.returncode != 0:
        # 修正前の時点の lockfile が壊れている場合（zod の #6738 の 1 つ前など）は、lockfile を直しながら入れる
        sh(["pnpm", "install", "--no-frozen-lockfile", "--ignore-scripts"], cwd=app, env=env, timeout=1500)
        # 直した lockfile は初期状態に含めない（候補の差分に出ないよう、元の版に戻す）
        if orig is not None:
            lock.write_text(orig)
    if tmp_ws:
        ws.unlink()


def run_tests(t, app, venv, files, timeout=1800):
    """テストを実行し、{テスト ID: pass|fail|skip} を返す"""
    out = Path(tempfile.mkdtemp(prefix="w11-res-"))
    t0 = time.time()
    if t["lang"] == "python":
        xml = out / "junit.xml"
        p = sh([str(Path(venv) / "bin" / "python"), "-m", "pytest", "-p", "no:cacheprovider", "-q",
                f"--junitxml={xml}", *files], cwd=app, env=t.get("env"), check=False, timeout=timeout)
        res = {}
        if xml.exists():
            for tc in ET.parse(xml).iter("testcase"):
                key = f"{tc.get('classname')}::{tc.get('name')}"
                if tc.find("failure") is not None or tc.find("error") is not None:
                    res[key] = "fail"
                elif tc.find("skipped") is not None:
                    res[key] = "skip"
                else:
                    res[key] = "pass"
    else:
        js = out / "vitest.json"
        p = sh(["npx", "vitest", "run", *files, "--reporter=json", f"--outputFile={js}"], cwd=app,
               env={"CI": "1"}, check=False, timeout=timeout)
        res = {}
        if js.exists():
            for f in json.loads(js.read_text()).get("testResults", []):
                rel = os.path.relpath(f["name"], app)
                for a in f.get("assertionResults", []):
                    st = a.get("status")
                    res[f"{rel} > {a.get('fullName')}"] = {"passed": "pass", "failed": "fail"}.get(st, "skip")
    log = (p.stdout + p.stderr)[-4000:]
    shutil.rmtree(out, ignore_errors=True)
    return res, log, round(time.time() - t0, 1)


def prepare(tid):
    t = task(tid)
    repo = clone(t)
    base = sh(["git", "-C", str(repo), "rev-parse", t["fix"] + "^1"]).stdout.strip()
    work = OSS_ROOT / tid
    tmpl = work / "template"
    if tmpl.exists():
        shutil.rmtree(tmpl)
    export(repo, base, tmpl)
    if t["lang"] == "node":
        node_install(tmpl)

    # 正解基準: 別のコピーで、修正前 / 修正後のソースに隠しテストを当てて実行する
    prep = work / "prep"
    if prep.exists():
        shutil.rmtree(prep)
    copy_app(tid, tmpl, prep / "app", prep)
    app, venv = prep / "app", prep / "venv"
    hidden = hidden_tests(repo, t)
    files = runnable(t, hidden)
    # 修正前のテストファイルのまま実行した結果（もともとあったテスト）。新しい API の import などで
    # 修正前に丸ごと失敗するテストファイルでも、もともと通っていたテストを「新しいテスト」と区別するため
    old, _, _ = run_tests(t, app, venv, [f for f in files if (app / f).exists()])
    apply_files(app, hidden)
    before, log_b, sec_b = run_tests(t, app, venv, files)
    _, src = changed_files(repo, t)
    diff = sh(["git", "-C", str(repo), "diff", "--binary", base, t["fix"], "--", *src]).stdout
    p = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=app, input=diff, text=True, capture_output=True)
    if p.returncode != 0:
        raise SystemExit("upstream fix did not apply: " + p.stderr)
    after, log_a, sec_a = run_tests(t, app, venv, files)
    f2p = sorted(k for k, v in after.items() if v == "pass" and before.get(k) != "pass")
    p2p = sorted(k for k, v in after.items() if v == "pass" and before.get(k) == "pass")
    # F2P のうち、もともと通っていたテスト（import などに巻き込まれて修正前に失敗したもの）と、新しいテストを分ける
    f2p_old = sorted(k for k in f2p if old.get(k) == "pass")
    f2p_new = sorted(k for k in f2p if old.get(k) != "pass")
    key = {
        "task": tid, "repo": t["repo"], "issue": t.get("issue"), "pr": t["pr"], "fix": t["fix"], "base": base,
        "test_files": sorted(hidden), "run_files": files, "src_files": src,
        "f2p": f2p, "p2p": p2p, "f2p_new": f2p_new, "f2p_old": f2p_old,
        "after_not_pass": sorted(k for k, v in after.items() if v != "pass"),
        "seconds": {"before": sec_b, "after": sec_a},
        "upstream_diff": {"added": diff.count("\n+") - diff.count("\n+++"), "removed": diff.count("\n-") - diff.count("\n---")},
    }
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    (KEY_DIR / f"{tid}.json").write_text(json.dumps(key, ensure_ascii=False, indent=1) + "\n")
    shutil.rmtree(prep)
    print(f"{tid}: base={base[:9]} F2P={len(f2p)}（新しいテスト {len(f2p_new)}）P2P={len(p2p)} after_not_pass={len(key['after_not_pass'])} "
          f"({sec_b}s / {sec_a}s)")
    if not f2p:
        print("  WARNING: F2P が 0 件（課題として使えない）\n" + log_a[-1500:])


def copy_app(tid, src, app, work):
    t = task(tid)
    src, app, work = Path(src), Path(app), Path(work)
    app.mkdir(parents=True, exist_ok=True)
    # node_modules 以外をコピーし、node_modules はハードリンクで写す（容量と時間の節約。候補は依存を入れ替えられない）
    tar = subprocess.Popen(["tar", "-C", str(src), "--exclude=node_modules", "-cf", "-", "."], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(app)], stdin=tar.stdout, check=True)
    tar.wait()
    for nm in src.rglob("node_modules"):
        rel = nm.relative_to(src)
        if any(part == "node_modules" for part in rel.parts[:-1]):
            continue
        sh(["cp", "-al", str(nm), str(app / rel)])
    if t["lang"] == "python":
        make_venv(t, app, work / "venv")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prepare":
        for tid in sys.argv[2:]:
            prepare(tid)
    elif cmd == "copy-app":
        copy_app(sys.argv[2], OSS_ROOT / sys.argv[2] / "template" if len(sys.argv) < 6 else sys.argv[5],
                 sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
