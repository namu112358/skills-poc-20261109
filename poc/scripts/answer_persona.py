#!/usr/bin/env python3
"""依頼者役（W14・W15 用。answer_w12.py を写し、シナリオを引数で受けるようにした。出どころ: origin/agent/poc-w12 b741324）。
poc/answer-key/<W>/persona.md の回答シートから答える。run-trial.sh が使う。
使い方: answer_persona.py <W> serve <raw> <app> <baseline> <sock> / answer_persona.py <W> message <raw> <app> <baseline> <step> <round>
（以下は answer_w12.py の説明）

質問の経路は 2 つで、どちらも同じ記録（<raw>/po-questions.jsonl）と会話の履歴を使う。
  (a) ask-po: 作業中いつでも使える質問コマンド。run-trial.sh が serve を裏で起動し、作業用コピーの外の bin/ask-po が
      UNIX ソケットで質問を送る（ask-po の中身には回答シートの場所は書かれていない）。
        python3 poc/scripts/answer_w12.py serve <raw> <app> <baseline-commit> <socket>
  (b) メッセージ: W3 と同じく、ステップの最後のメッセージに依頼者への質問があれば答える。回答は標準出力（質問が無ければ何も出さない）。
        python3 poc/scripts/answer_w12.py message <raw> <app> <baseline-commit> <step> <round>
記録（1 行 1 回の問い合わせ）: route（ask-po / message）・時刻・実装前か（その時点で src/・tests/ に baseline からの変更が無いか）・
  項目ごとの分類（kind）と回答に使ったシートの ID（Q・O・D）・回答・依頼者役の費用（候補の費用とは別）。
依頼者役は候補の試行とは別の claude -p（ツールなし・設定なし・専用 HOME・作業用コピーの外）で動く。

人間の代理人（W19 から。PROXY_SCENARIOS のシナリオで、環境変数 POC_PROXY が 0 でないとき）:
  候補が人に投げる技術的な判断（案の選択・計画の承認・進めてよいか・やり直すか）には、「お任せします」ではなく
  人間の代理人として poc/proxy/principles.md の原則で決めて答える。業務の事実は従来どおり回答シートだけから答える。
  判断は items の kind=decision と decision（決めたこと・理由・原則の ID・置いた前提）に記録し、report で人に報告する。
  POC_PROXY=0 のとき（対照の試行）は、従来どおり技術的な判断にも「お任せします」と答える。
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
SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "W14"
SHEET = ROOT / "poc" / "answer-key" / SCENARIO / "persona.md"
MODEL = os.environ.get("POC_ANSWER_MODEL", os.environ.get("POC_MODEL", "claude-sonnet-5-5"))
TASK = (ROOT / "poc" / "tasks" / f"wf-{SCENARIO}.md").read_text().strip()
LOCK = threading.Lock()
PROXY_SCENARIOS = {"W19"}
PROXY = SCENARIO in PROXY_SCENARIOS and os.environ.get("POC_PROXY", "1") != "0"
PRINCIPLES = ROOT / "poc" / "proxy" / "principles.md"

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
                    "kind": {"type": "string", "enum": ["requirement", "operations", "documented", "confirmation", "decision", "other"],
                             "description": "requirement=業務の決まり（Q）を聞く、operations=運用の事情（O）を聞く、documented=文書に既に書いてあること（D）、"
                                            "confirmation=案の承認・進めてよいかの確認（代理人がいないとき）、decision=代理人が技術的な判断を下したもの、"
                                            "other=それ以外（範囲の外・お任せ）"},
                    "decision": {"type": "object", "description": "kind=decision のときだけ。代理人が決めた内容",
                                 "properties": {"chosen": {"type": "string"}, "reason": {"type": "string"},
                                                "principles": {"type": "array", "items": {"type": "string"}},
                                                "assumptions": {"type": "string"}}},
                    "sheet_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "回答に使ったシートの項目 ID（Q・O・D の番号。例 Q1・O2・D3）。お任せします・単なる承認なら空"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "kind", "sheet_ids", "answer"],
            },
        },
        "reply": {"type": "string", "description": "候補に返す回答文。質問が無ければ空文字"},
    },
    "required": ["has_questions", "items", "reply"],
}

SYSTEM = f"""あなたは、社内の「計測器 校正台帳」アプリの改善を依頼した「依頼者」の役です。
依頼文は「{TASK}」だけです。
開発を担当する AI から届いた質問・メッセージを読み、依頼者への質問・確認があれば、下の回答シートだけを根拠に答えます。

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

if PROXY:
    SYSTEM += f"""

--- 追加の役割: 人間の代理人 ---
あなたは依頼者であると同時に、開発チーム側の「人間の代理人」も務めます。
- 業務の事実（何を作りたいか・業務の決まり・運用の事情）は、これまでどおり回答シートだけを根拠に答える。代理人の原則で業務の事実を作らない。
- 開発を担当する AI が人に技術的な判断を求めたとき（例: 案 A・B・C のどれにするか、この計画・設計で進めてよいか、やり方を変えるか）は、
  「お任せします」と言わず、下の原則に沿って必ず決めて答える。その質問は kind を decision にし、decision に
  決めたこと（chosen）・理由（reason）・使った原則の ID（principles、例 P1）・置いた前提（assumptions）を書く。
- 技術的な判断に業務の事実が足りないときは、推測で業務の事実を作らず、足りない点を「依頼者として」回答シートの範囲で答えるか、
  シートに無ければ前提として assumptions に書く。
- reply では、代理人として決めたことと理由を短く伝える（原則の ID は reply に書かない）。

--- 代理人の原則 ---
{PRINCIPLES.read_text()}
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def implementation_started(app, baseline):
    """src/・tests/ に baseline からの変更（コミット済み・未コミット・新規ファイル）があれば True。"""
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


def ask_persona(raw, message, route):
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
         "--no-session-persistence", "--system-prompt", SYSTEM, "--json-schema", json.dumps(SCHEMA),
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
        before = not implementation_started(app, baseline)
        t0 = now_iso()
        res = ask_persona(raw, message, route)
        p = raw / "po-questions.jsonl"
        n = (len(p.read_text().splitlines()) if p.exists() else 0) + 1
        rec = {"n": n, "route": route, "asked_at": t0, "answered_at": now_iso(), "before_implementation": before,
               "message": message[:4000], "proxy": PROXY, **extra, **res}
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
    args = sys.argv[2:]  # sys.argv[1] はシナリオ
    mode = args[0]
    raw, app, baseline = Path(args[1]), Path(args[2]), args[3]
    if mode == "serve":
        serve(raw, app, baseline, args[4])
        return
    step, rnd = int(args[4]), int(args[5])
    rec = record(raw, app, baseline, "message", last_message(raw, step), {"step": step, "round": rnd})
    if rec["has_questions"] and rec["reply"].strip():
        print(rec["reply"])


if __name__ == "__main__":
    main()
