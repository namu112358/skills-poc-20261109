#!/usr/bin/env python3
"""W13 の依頼者役（poc/answer-key/W13/persona.md の回答シートから答える）。run-trial.sh が使う。
W12 の answer_w12.py（origin/agent/poc-w12 03b1d05）を写し、変更依頼の前後（段階 v1 / v2）で答えを変えるようにした。
段階は run-trial.sh が <raw>/phase に書く（v1 → 変更依頼を送る直前に v2）。v2 の「実装前か」は、
変更依頼の時点のコミット（<raw>/phase-base）から src/・tests/ に変更が無いかで判定する。

質問の経路は 2 つで、どちらも同じ記録（<raw>/po-questions.jsonl）と会話の履歴を使う。
  (a) ask-po: 作業中いつでも使える質問コマンド。run-trial.sh が serve を裏で起動し、作業用コピーの外の bin/ask-po が
      UNIX ソケットで質問を送る（ask-po の中身には回答シートの場所は書かれていない）。
        python3 poc/scripts/answer_w13.py serve <raw> <app> <baseline-commit> <socket>
  (b) メッセージ: W3 と同じく、ステップの最後のメッセージに依頼者への質問があれば答える。回答は標準出力（質問が無ければ何も出さない）。
        python3 poc/scripts/answer_w13.py message <raw> <app> <baseline-commit> <step> <round>
記録（1 行 1 回の問い合わせ）: route（ask-po / message）・時刻・実装前か（その時点で src/・tests/ に baseline からの変更が無いか）・
  項目ごとの分類（kind）と回答に使ったシートの ID（Q・O・D）・回答・依頼者役の費用（候補の費用とは別）。
依頼者役は候補の試行とは別の claude -p（ツールなし・設定なし・専用 HOME・作業用コピーの外）で動く。
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "poc" / "answer-key" / "W13" / "persona.md"
MODEL = os.environ.get("POC_ANSWER_MODEL", os.environ.get("POC_MODEL", "claude-sonnet-5-5"))
TASK = (ROOT / "poc" / "tasks" / "wf-W13.md").read_text().strip()
CHANGE = (ROOT / "poc" / "tasks" / "wf-W13-change.md").read_text().strip()
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
                    "kind": {"type": "string", "enum": ["requirement", "change", "documented", "confirmation", "other"],
                             "description": "requirement=最初の依頼の業務の決まり（Q・V1）を聞く、change=変更依頼の後の決まり（C）を聞く、"
                                            "documented=文書・既存の仕組みに既に書いてあること（D）、"
                                            "confirmation=案の承認・進めてよいかの確認、other=それ以外（範囲の外・お任せ）"},
                    "sheet_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "回答に使ったシートの項目 ID（Q1〜Q11・V1a・V1b・C1〜C12・D1〜D4）。お任せします・単なる承認なら空"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "kind", "sheet_ids", "answer"],
            },
        },
        "reply": {"type": "string", "description": "候補に返す回答文。質問が無ければ空文字"},
    },
    "required": ["has_questions", "items", "reply"],
}

SYSTEM_HEAD = {
    "v1": f"""あなたは、社内の「計測器 校正台帳」アプリの改善を依頼した「依頼者」の役です。
最初の依頼文は「{TASK}」だけです。今は段階 v1（変更依頼の前）です。シートの「v1 の時点の答え」を使い、C の項目（変更依頼の後の決まり）は使いません。
""",
    "v2": f"""あなたは、社内の「計測器 校正台帳」アプリの改善を依頼した「依頼者」の役です。
最初の依頼文は「{TASK}」でした。最初の版が本番に出た後、次の変更を依頼しました: 「{CHANGE}」
今は段階 v2（変更依頼の後）です。Q の項目と C の項目を使います（承認・期間の上限は C のとおり。「v1 の時点の答え」は使いません）。
""",
}
SYSTEM_BODY = f"""開発を担当する AI から届いた質問・メッセージを読み、依頼者への質問・確認があれば、下の回答シートだけを根拠に答えます。

厳守すること:
- シートの「回答のルール」に従う。聞かれたこと（または案・確認の中で触れられたこと）にだけ答え、聞かれていない項目は自分から言わない。
- シートに無い内容を作らない。シートに無いことは「お任せします」と答える。
- メッセージに依頼者への質問・確認・選択の依頼が無い（作業の報告だけ、完了の報告だけ）なら has_questions を false にし、reply を空にする。
- 修辞的な問いや、AI が自分で答えを決めている箇所は質問に数えない。依頼者に答えを求めているものだけを数える。
- 質問 1 つごとに items を 1 つ作る。
- reply は依頼者として自然な日本語で書く。シートの項目 ID（Q1 など）や「シート」という言葉は reply に書かない。

--- 回答シート ---
{SHEET.read_text()}
"""


def phase_of(raw):
    p = raw / "phase"
    return p.read_text().strip() if p.exists() else "v1"


def system_prompt(phase):
    return SYSTEM_HEAD.get(phase, SYSTEM_HEAD["v1"]) + SYSTEM_BODY


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def implementation_started(app, baseline, raw=None):
    """src/・tests/ に baseline からの変更（コミット済み・未コミット・新規ファイル）があれば True。
    段階 v2 では、変更依頼の時点のコミット（<raw>/phase-base）を基準にする。"""
    if raw is not None and (raw / "phase-base").exists():
        baseline = (raw / "phase-base").read_text().strip()
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
            parts.append(f"[{r['route']} {r['n']} 段階 {r.get('phase', 'v1')}] 質問: {r['message'][:800]}\n回答: {r['reply']}")
    return "\n\n".join(parts[-20:]) or "（まだ答えていない）"


def ask_persona(raw, message, route, phase):
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
         "--no-session-persistence", "--system-prompt", system_prompt(phase), "--json-schema", json.dumps(SCHEMA),
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
        phase = phase_of(raw)
        before = not implementation_started(app, baseline, raw)
        t0 = now_iso()
        res = ask_persona(raw, message, route, phase)
        p = raw / "po-questions.jsonl"
        n = (len(p.read_text().splitlines()) if p.exists() else 0) + 1
        rec = {"n": n, "route": route, "phase": phase, "asked_at": t0, "answered_at": now_iso(), "before_implementation": before,
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
