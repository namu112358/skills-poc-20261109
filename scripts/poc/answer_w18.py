#!/usr/bin/env python3
"""W18 の依頼者役（docs/poc/answer-key/W18/persona-common.md と persona-r<回>.md の回答シートから答える）。run-trial.sh が使う。
W13 の answer_w13.py（origin/agent/poc-w13 a0617be）を写し、段階（v1 / v2）の代わりに「回」（第 1〜6 回）で答えを変えるようにした。
回は試行 ID（W18r<回>-<候補>-<系列>）から決まる。依頼者役は、その回のシートと、それまでの回のシート（前の回で決めたこと）を知っている。
「実装前か」は、その回の初め（baseline-commit。前の回の終わり）から src/・tests/ に変更が無いかで判定する。

質問の経路は 2 つで、どちらも同じ記録（<raw>/po-questions.jsonl）と会話の履歴を使う（W12・W13 と同じ）。
  (a) ask-po:  python3 scripts/poc/answer_w18.py serve <raw> <app> <baseline-commit> <socket>
  (b) メッセージ: python3 scripts/poc/answer_w18.py message <raw> <app> <baseline-commit> <step> <round>
依頼者役は候補の試行とは別の claude -p（ツールなし・設定なし・専用 HOME・作業用コピーの外）で動く。
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W18"
MODEL = os.environ.get("POC_ANSWER_MODEL", os.environ.get("POC_MODEL", "claude-sonnet-5-5"))
TASKS = {k: (ROOT / "docs" / "poc" / "tasks" / f"wf-W18r{k}.md").read_text().strip() for k in range(1, 7)}
LOCK = threading.Lock()

SCHEMA = {
    "type": "object",
    "properties": {
        "has_questions": {"type": "boolean", "description": "依頼者への質問・確認・選択の依頼が 1 つでもあれば true"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "候補の質問（要約してよい）"},
                    "kind": {"type": "string", "enum": ["requirement", "operation", "previous", "documented", "confirmation", "other"],
                             "description": "requirement=今回のシートの業務の決まり（Q・V）を聞く、operation=今回のシートの運用の事情（O）、"
                                            "previous=前の回のシートの項目を聞く、documented=文書・既存の仕組みに既に書いてあること（D）、"
                                            "confirmation=案の承認・進めてよいかの確認、other=それ以外（範囲の外・お任せ）"},
                    "sheet_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "回答に使ったシートの項目 ID。今回のシートは Q1・O1・D1 のように、前の回のシートは r2:Q5 のように回を付ける。お任せします・単なる承認なら空"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "kind", "sheet_ids", "answer"],
            },
        },
        "reply": {"type": "string", "description": "候補に返す回答文。質問が無ければ空文字"},
    },
    "required": ["has_questions", "items", "reply"],
}

def round_of(raw):
    m = re.match(r"^W18r([1-6])-", Path(raw).name)
    return int(m.group(1)) if m else 1


def system_prompt(k):
    prev = "\n\n".join(f"### 第 {i} 回の回答シート（前の回で決めたこと）\n\n" + (KEY / f"persona-r{i}.md").read_text() for i in range(1, k))
    return f"""あなたは、社内の「計測器 校正台帳」アプリの改善を依頼している「依頼者」の役です。今は第 {k} 回の依頼で、依頼文は「{TASKS[k]}」です。
開発を担当する AI から届いた質問・メッセージを読み、依頼者への質問・確認があれば、下の回答シートだけを根拠に答えます。

厳守すること:
- 共通の決まりの「回答のルール」に従う。聞かれたこと（または案・確認の中で触れられたこと）にだけ答え、聞かれていない項目は自分から言わない。
- シートに無い内容を作らない。シートに無いことは「お任せします」と答える。
- 今回のシートを優先し、前の回のシートは「前の回で決めたこと」として使う。
- メッセージに依頼者への質問・確認・選択の依頼が無い（作業の報告だけ、完了の報告だけ）なら has_questions を false にし、reply を空にする。
- 修辞的な問いや、AI が自分で答えを決めている箇所は質問に数えない。依頼者に答えを求めているものだけを数える。
- 質問 1 つごとに items を 1 つ作る。
- reply は依頼者として自然な日本語で書く。シートの項目 ID（Q1 など）や「シート」という言葉は reply に書かない。

--- 共通の決まり ---
{(KEY / "persona-common.md").read_text()}

--- 今回（第 {k} 回）の回答シート ---
{(KEY / f"persona-r{k}.md").read_text()}

--- 前の回の回答シート ---
{prev or "（なし。今回が第 1 回）"}
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def implementation_started(app, baseline, raw=None):
    """src/・tests/ に、その回の初め（baseline）からの変更（コミット済み・未コミット・新規ファイル）があれば True。"""
    changed = subprocess.run(["git", "-C", str(app), "diff", "--name-only", baseline, "--", "src", "tests"],
                             capture_output=True, text=True).stdout.strip()
    untracked = subprocess.run(["git", "-C", str(app), "ls-files", "--others", "--exclude-standard", "--", "src", "tests"],
                               capture_output=True, text=True).stdout.strip()
    return bool(changed or untracked)


def history(raw):
    p = raw / "po-questions.jsonl"
    if not p.exists():
        return "（まだ答えていない）"
    parts = []
    for line in p.read_text().splitlines():
        r = json.loads(line)
        if r.get("reply"):
            parts.append(f"[{r['route']} {r['n']}] 質問: {r['message'][:800]}\n回答: {r['reply']}")
    return "\n\n".join(parts[-20:]) or "（まだ答えていない）"


def ask_persona(raw, message, route, k):
    prompt = (f"これまでの質問と回答:\n{history(raw)}\n\n"
              f"--- 開発を担当する AI からの{'質問（ask-po コマンド）' if route == 'ask-po' else '最新のメッセージ'} ---\n"
              f"{message or '（メッセージなし）'}\n--- ここまで ---\n\n"
              "依頼者への質問・確認があれば、回答シートに沿って答えてください。")
    home = Path(os.environ.get("POC_ANSWER_HOME") or raw / "answerer-home")
    home.mkdir(parents=True, exist_ok=True)
    out = {"has_questions": False, "items": [], "reply": "", "cost_usd": 0.0, "error": ""}
    if not message.strip():
        return out
    p = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
         "--no-session-persistence", "--system-prompt", system_prompt(k), "--json-schema", json.dumps(SCHEMA),
         "--output-format", "json"],
        cwd=home, env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=600,
        stdin=subprocess.DEVNULL)
    try:
        o = json.loads(p.stdout)
        so = o.get("structured_output") or json.loads(o.get("result") or "{}")
        out.update({k: so[k] for k in ("has_questions", "items", "reply")})
        out["cost_usd"] = o.get("total_cost_usd") or 0.0
    except (ValueError, KeyError, TypeError) as ex:
        out["error"] = f"{ex}: {p.stdout[-500:]} {p.stderr[-500:]}"
    return out


def record(raw, app, baseline, route, message, extra):
    with LOCK:
        k = round_of(raw)
        before = not implementation_started(app, baseline, raw)
        t0 = now_iso()
        res = ask_persona(raw, message, route, k)
        p = raw / "po-questions.jsonl"
        n = (len(p.read_text().splitlines()) if p.exists() else 0) + 1
        rec = {"n": n, "route": route, "w18_round": k, "asked_at": t0, "answered_at": now_iso(), "before_implementation": before,
               "message": message[:4000], **extra, **res}
        with p.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


def serve(raw, app, baseline, sock_path):
    sock_path = Path(sock_path).resolve()
    raw, app = Path(raw).resolve(), Path(app).resolve()
    if sock_path.exists():
        sock_path.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # UNIX ソケットのパスは 108 バイトまでなので、ディレクトリに移って相対パスで作る
    os.chdir(sock_path.parent)
    srv.bind(sock_path.name)
    srv.listen(4)

    def handle(conn):
        with conn:
            data = b""
            while not data.endswith(b"\0"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            q = data.rstrip(b"\0").decode("utf-8", "replace").strip()
            if not q:
                conn.sendall("質問が空です。ask-po \"<質問>\" の形で聞いてください。".encode())
                return
            rec = record(raw, app, baseline, "ask-po", q, {})
            reply = rec["reply"].strip() or ("お任せします。" if not rec["error"] else "（依頼者に連絡がつきません。お任せします。）")
            conn.sendall(reply.encode())

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


def last_message(raw, step):
    text = ""
    for line in (raw / f"step{step}.jsonl").open():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result" and d.get("result"):
            text = d["result"]
    return text


def main():
    mode = sys.argv[1]
    raw, app, baseline = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    if mode == "serve":
        serve(raw, app, baseline, sys.argv[5])
        return
    step, rnd = int(sys.argv[5]), int(sys.argv[6])
    rec = record(raw, app, baseline, "message", last_message(raw, step), {"step": step, "round": rnd})
    if rec["has_questions"] and rec["reply"].strip():
        print(rec["reply"])


if __name__ == "__main__":
    main()
