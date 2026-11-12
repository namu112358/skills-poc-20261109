#!/usr/bin/env python3
"""W13 の採点用: 候補の予約の API を読んで、アダプター（poc/answer-key/W13/grading.md の「アダプター」）の下書きを作る。

予約の API（パス・本文の項目名・状態の値）は候補ごとに違うため、採点のテストはアダプターを通して操作する。
下書きは、候補とは別の claude -p（ツールなし・設定なし）に、候補のコードの該当部分を読ませて作る。
アダプターが指してよいのは「候補の実装が実際に持っている名前・値・API」だけで、振る舞いの判定はテストが行う。
採点者は下書き（results/workflow/W13/adapters/<試行ID>-<v1|v2>.draft.json）とコードを見比べて確かめ、
<試行ID>-<v1|v2>.json として確定する（直したことは report の「判断の記録」に書く）。

  python3 poc/scripts/adapt_w13.py <アプリ> <初期状態のコミット> <対象のコミット> <v1|v2> [<出力 JSON>]
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = os.environ.get("POC_ADAPT_MODEL", "claude-sonnet-5-5")
REF = ROOT / "poc" / "answer-key" / "W13" / "adapters" / "reference-v2.json"

GUIDE = """あなたは採点の補助です。社内アプリ（計測器の校正台帳、Next.js の API Route）に後から足された「計測器の貸出の予約」の機能のコードを読み、
採点用のテストが予約の API を呼ぶための「アダプター」を JSON で書きます。コードに実際にある名前・値・API だけを書き、無いものは書かない（null か省く）。

アダプターの形（例は参照実装のもの）:
{example}

- create: 予約を作る API。path・body のテンプレートで {{instrumentId}}（計測器の数値 ID）・{{start}}・{{end}}（YYYY-MM-DD）・{{user}}（予約する利用者 ID）が使える。
  値を数値で送る必要があれば "{{instrumentId:n}}" と書く。予約する人がログイン中の本人なら {{user}} は要らない。本文に予約する人の項目が必要なら {{user}} を入れる。
  id は応答の JSON から予約の ID を取り出すパス（例 "reservation.id"）。
- list: 計測器 1 台の予約の一覧を返す API と、応答の中の配列のパス（items）。全体の一覧しか無ければ path にクエリを付けるか、
  filterInstrument に各要素の計測器 ID の項目名を書く。
- cancel / approve / reject: 予約への操作。{{reservationId}} が使える。無い操作は書かない。
- fields: 一覧の各要素の項目名（id・status・start・end・user）。状態が複数の項目の組み合わせなら status に項目名の配列を書く
  （そのときの値は JSON にした各項目を "|" でつないだ文字列。例 "\\"active\\"|0"。項目ごとに "*"（何でもよい）と "@notnull"（null 以外。日時の列など）が使える。例 "\\"active\\"|@notnull|null"）。
- status: 共通の状態名 → 候補の状態の値の配列。共通の状態名は、承認制の前（{phase} が v1）なら active（有効な予約）・cancelled、
  承認制の後（v2）なら pending（仮予約・承認待ち）・approved（確定）・rejected（却下）・cancelled（取消）・expired（期限切れ）。
  候補のコードに無い状態は書かない。
- dateFormat: 日付を YYYY-MM-DD 以外で送る必要があるときだけ書く（{{"start": "{{d}}T00:00:00+09:00", "end": "{{d}}T23:59:59+09:00", "iso": true}} など）。
- jobs: 期限切れの仮予約の処理などを、定期実行のジョブの API（JOBS_TOKEN で呼ぶもの）でしているなら [{{"method": "POST", "path": "/api/jobs/..."}}]。無ければ []。
- notes: 決めきれなかったこと・気になったことを日本語で短く。

JSON だけを出力してください（前後に説明を書かない）。"""


def git(app, *args):
    return subprocess.run(["git", "-C", str(app), *args], capture_output=True, text=True).stdout


def relevant_files(app, base, commit):
    names = git(app, "diff", "--name-only", base, commit, "--", "src").split()
    out = []
    for n in names:
        text = git(app, "show", f"{commit}:{n}")
        if not text:
            continue
        if n.endswith("route.ts") or re.search(r"reserv|予約|booking", n + text, re.I):
            out.append((n, text))
    return out


def draft(app, base, commit, phase, work=None):
    files = relevant_files(app, base, commit)
    body = "\n\n".join(f"=== {n} ===\n{t[:12000]}" for n, t in files)[:120000]
    prompt = f"対象の段階: {phase}\n\n--- 候補のコード（初期状態から足された・変わったファイル） ---\n{body}\n--- ここまで ---"
    system = GUIDE.format(example=REF.read_text(), phase=phase)
    home = Path(work or "/tmp/w13-adapt-home")
    home.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                        "--no-session-persistence", "--system-prompt", system, "--output-format", "json"],
                       cwd=home, env=dict(os.environ, HOME=str(Path.home())), capture_output=True, text=True, timeout=900,
                       stdin=subprocess.DEVNULL)
    out = {"phase": phase, "commit": commit, "files": [n for n, _ in files], "adapter": None, "cost_usd": 0.0}
    try:
        o = json.loads(p.stdout)
        out["cost_usd"] = o.get("total_cost_usd") or 0.0
        text = o.get("result") or ""
        m = re.search(r"\{.*\}", text, re.S)
        out["adapter"] = json.loads(m.group(0)) if m else None
    except (ValueError, AttributeError) as ex:
        out["error"] = f"{ex}: {p.stdout[-400:]} {p.stderr[-400:]}"
    return out


if __name__ == "__main__":
    app, base, commit, phase = sys.argv[1:5]
    d = draft(app, base, commit, phase)
    text = json.dumps(d, ensure_ascii=False, indent=2)
    if len(sys.argv) > 5:
        Path(sys.argv[5]).write_text(text + "\n")
    print(text)
