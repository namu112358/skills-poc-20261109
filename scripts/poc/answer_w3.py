#!/usr/bin/env python3
"""W3 の依頼者役（定型回答シートから答える）。run-trial.sh が W3 の各ステップの後に呼ぶ。

使い方: python3 scripts/poc/answer_w3.py <試行の raw ディレクトリ> <ステップ番号> <回答の通し番号>
  - そのステップの最後のメッセージ（result）を読み、依頼者への質問・確認があれば、
    docs/poc/answer-key/W3/answers.md のルールに沿った回答を作る。
  - 結果は <raw>/qa-<通し番号>.json に書く。質問があれば回答文を標準出力に出す（無ければ何も出さない）。
  - 回答役は候補の試行とは別の claude -p（ツールなし・設定なし・専用 HOME・作業用コピーの外）で動く。
    候補のセッションからは回答シートが見えない。回答役の費用は候補の費用に含めない（qa-*.json に別に記録）。
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "docs" / "poc" / "answer-key" / "W3" / "answers.md"
MODEL = os.environ.get("POC_ANSWER_MODEL", os.environ.get("POC_MODEL", "claude-sonnet-5-5"))

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
                    "kind": {"type": "string", "enum": ["requirement", "context", "confirmation"],
                             "description": "requirement=作るものの中身・範囲を聞く質問、context=背景を聞く質問、confirmation=案の選択・承認・理解の確認"},
                    "sheet_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "回答に使ったシートの項目 ID（B1〜B4・H1〜H10・S1〜S5）。お任せします・単なる承認なら空"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "kind", "sheet_ids", "answer"],
            },
        },
        "reply": {"type": "string", "description": "候補に送る回答文（番号付き）。質問が無ければ空文字"},
    },
    "required": ["has_questions", "items", "reply"],
}

SYSTEM = f"""あなたは、社内のタスク管理アプリの改善を依頼した「依頼者」の役です。
依頼文は「チームの進捗が見えにくいので、何とかしたいです。」だけです。
開発を担当する AI から届いたメッセージを読み、依頼者への質問・確認があれば、下の定型回答シートだけを根拠に答えます。

厳守すること:
- シートの「回答のルール」に従う。聞かれたこと（または提案の中で触れられたこと）にだけ答え、聞かれていない項目は自分から言わない。
- シートに無い内容を作らない。シートに無いことは「お任せします」と答える。
- メッセージに依頼者への質問・確認・選択の依頼が無い（作業の報告だけ、完了の報告だけ）なら has_questions を false にし、reply を空にする。
- 修辞的な問いや、AI が自分で答えを決めている箇所は質問に数えない。依頼者に答えを求めているものだけを数える。
- reply は依頼者として自然な日本語で書く。シートの項目 ID（H1 など）や「シート」という言葉は reply に書かない。

--- 定型回答シート ---
{SHEET.read_text()}
"""


def last_message(raw: Path, step: int) -> str:
    text = ""
    for line in (raw / f"step{step}.jsonl").open():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result" and d.get("result"):
            text = d["result"]
    return text


def history(raw: Path) -> str:
    parts = []
    for p in sorted((p for p in raw.glob("qa-*.json") if re.fullmatch(r"qa-\d+\.json", p.name)),
                    key=lambda p: int(re.search(r"qa-(\d+)", p.name).group(1))):
        q = json.loads(p.read_text())
        if q.get("has_questions"):
            parts.append(f"[{q['round']} 回目の回答]\n{q['reply']}")
    return "\n\n".join(parts) or "（まだ回答していない）"


def main():
    raw, step, rnd = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    message = last_message(raw, step)
    prompt = (f"これまでに依頼者が返した回答:\n{history(raw)}\n\n"
              f"--- 開発を担当する AI からの最新のメッセージ ---\n{message or '（メッセージなし）'}\n--- ここまで ---\n\n"
              "このメッセージに依頼者への質問・確認があれば、シートに沿って答えてください。")
    home = Path(os.environ.get("POC_ANSWER_HOME") or raw / "answerer-home")
    home.mkdir(parents=True, exist_ok=True)
    result = {"round": rnd, "step": step, "message": message, "has_questions": False, "items": [], "reply": "",
              "cost_usd": 0.0, "error": ""}
    if message.strip():
        p = subprocess.run(
            ["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
             "--no-session-persistence", "--system-prompt", SYSTEM, "--json-schema", json.dumps(SCHEMA),
             "--output-format", "json"],
            cwd=home, env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=600,
            stdin=subprocess.DEVNULL)
        try:
            out = json.loads(p.stdout)
            so = out.get("structured_output") or json.loads(out.get("result") or "{}")
            result.update({k: so[k] for k in ("has_questions", "items", "reply")})
            result["cost_usd"] = out.get("total_cost_usd") or 0.0
        except (ValueError, KeyError, TypeError) as ex:
            result["error"] = f"{ex}: {p.stdout[-500:]} {p.stderr[-500:]}"
    (raw / f"qa-{rnd}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if result["has_questions"] and result["reply"].strip():
        print(result["reply"])


if __name__ == "__main__":
    main()
