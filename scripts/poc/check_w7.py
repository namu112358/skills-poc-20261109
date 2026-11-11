#!/usr/bin/env python3
"""W7（続けて行う作業での学習効果）の落とし穴 2 件を、試行のコードについて判定する。

使い方: python3 scripts/poc/check_w7.py <W7a|W7b|W7c|W7d|W7e> <作業用コピーの app> <結果の JSON> [--feedback]
  1. app で npm run build し、DATABASE_PATH（一時ファイル）・TZ=UTC で next start する。
  2. docs/poc/answer-key/W7/pitfalls.cjs で P1（日時を UTC で保存し JST で表示）・P2（独自のエラー型）を判定し、JSON に書く。
  --feedback: 避けられなかった落とし穴について、レビューの定型の指摘文を標準出力に出す（run-trial.sh が次のステップとして送る）。
              ビルドに失敗したときや、すべて避けられたときは何も出さない。
判定方法は docs/poc/answer-key/W7/grading.md。正解データは作業用コピーに置かない（このスクリプトがリポジトリから読む）。
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = ROOT / "docs" / "poc" / "answer-key" / "W7"

FEEDBACK = {
    "P1": "このプロジェクトでは、日時は ISO 8601 形式の UTC（例: 2026-11-09T03:04:05.000Z）で DB に保存し、画面では日本時間（JST）で表示する決まりです"
          "（保存は src/lib/datetime.ts の toUtcIso、表示は formatJst を使う。サーバーやブラウザの時刻設定に頼らない）。今回追加した部分の日時の保存または表示が、この決まりに沿っていません。",
    "P2": "このプロジェクトでは、新しく作る API は、エラーを独自のエラー型（src/lib/errors.ts の AppError とその派生クラス）で投げ、API Route を withApi（src/lib/api.ts）で包んで"
          " { error, code, details? } の形で返す決まりです（ログインの確認は currentApiUser。jsonError・requireApiUser は移行前の古い書き方）。今回追加した API のエラー応答が、この決まりに沿っていません。",
}
# W7c 以降（日付の絞り込み・日本時間の入力・CSV など、保存と画面表示以外にも決まりが及ぶ段階）の P1 の指摘。
# 決まり自体は W7a・W7b と同じで、及ぶ範囲を書き足している。P2 は W7a・W7b と同じ文。
FEEDBACK_LATER_P1 = (
    "このプロジェクトでは、日時は ISO 8601 形式の UTC（例: 2026-11-09T03:04:05.000Z）で DB に保存し、利用者に関わる日時は日本時間（JST）として扱う決まりです"
    "（保存は src/lib/datetime.ts の toUtcIso、表示は formatJst。利用者が指定する日付・日時や、人が読む出力の日時も日本時間として扱い、UTC との時差を変換する。"
    "サーバーやブラウザの時刻設定に頼らない）。今回追加した部分の日時の扱い（保存・絞り込み・表示のいずれか）が、この決まりに沿っていません。"
)
FEEDBACK_HEAD = "レビューで次の指摘がありました。"
FEEDBACK_TAIL = "直して、変更を git にコミットしてください。"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check(scenario, app):
    app = Path(app)
    started = time.time()
    b = subprocess.run("npm run build", cwd=app, shell=True, capture_output=True, text=True, timeout=900)
    if b.returncode != 0:
        return {"scenario": scenario, "build": False, "log": (b.stdout + b.stderr)[-1500:], "seconds": round(time.time() - started)}
    with tempfile.TemporaryDirectory(prefix="poc-w7-db-") as tmp:
        db = Path(tmp) / "pitfalls.db"
        port = free_port()
        env = dict(os.environ, DATABASE_PATH=str(db), TZ="UTC")
        server = subprocess.Popen(f"npx next start -p {port}", cwd=app, shell=True, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            for _ in range(60):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=1).close()
                    break
                except OSError:
                    time.sleep(1)
            nenv = dict(os.environ, NODE_PATH=subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip())
            p = subprocess.run(["node", "--no-warnings", str(KEY / "pitfalls.cjs"), scenario, f"http://127.0.0.1:{port}", str(db)],
                               capture_output=True, text=True, timeout=300, env=nenv)
            try:
                res = json.loads(p.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                res = {"error": (p.stdout + p.stderr)[-500:]}
        finally:
            os.killpg(server.pid, 15)
    res["build"] = True
    res["seconds"] = round(time.time() - started)
    return res


def feedback(res, scenario="W7a"):
    if not res.get("build") or "error" in res:
        return ""
    missed = [k for k in ("P1", "P2") if not (res.get(k) or {}).get("pass")]
    if not missed:
        return ""
    texts = dict(FEEDBACK)
    if scenario not in ("W7a", "W7b"):
        texts["P1"] = FEEDBACK_LATER_P1
    return "\n".join([FEEDBACK_HEAD] + [f"- {texts[k]}" for k in missed] + [FEEDBACK_TAIL])


def main():
    scenario, app, out = sys.argv[1:4]
    res = check(scenario, app)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    if "--feedback" in sys.argv[4:]:
        text = feedback(res, scenario)
        if text:
            print(text)


if __name__ == "__main__":
    main()
