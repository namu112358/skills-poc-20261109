#!/usr/bin/env python3
"""W18 の採点用: 候補のコードを読んで、アダプター（docs/poc/answer-key/W18/grading.md の「アダプター」）の下書きを作る。

API の名前（重要度の項目・予約・場所・発注・履歴・副管理者の API と値）は系列ごと・回ごとに違うため、採点のテストはアダプターを通して操作する。
下書きは、候補とは別の claude -p（ツールなし・設定なし）に、候補のコード（初期状態から足された・変わったファイル）と、
前の回で確定したアダプターを読ませて作る（W13 の adapt_w13.py と同じ方法）。アダプターが指してよいのは「候補の実装が実際に持っている
名前・値・API」だけで、振る舞いの判定はテストが行う。採点者は下書き（results/workflow/W18/adapters/<系列ID>-r<回>.draft.json）と
コードを見比べて確かめ、<系列ID>-r<回>.json（引き継ぎは -h1・-h2）として確定する（直したことは report の「判断の記録」に書く）。

  python3 scripts/poc/adapt_w18.py <リポジトリ> <初期状態のコミット> <対象のコミット> <回（1〜6・h1・h2）> [<前の回のアダプター JSON>] [<出力 JSON>]
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = os.environ.get("POC_ADAPT_MODEL", "claude-sonnet-5-5")
REF = ROOT / "docs" / "poc" / "answer-key" / "W18" / "adapters" / "reference.json"

SECTIONS = {
    "f1": "重要度（第 1 回）: key（計測器の API の項目名）、levels（受け付ける値を高い順に。例 [\"A\",\"B\",\"C\"]）、set（登録の本文で受け付けるなら \"post\"、編集でしか設定できなければ \"patch\"）、"
          "filter.param（一覧の API で重要度で絞り込むクエリの名前。無ければ filter は {}）、job（校正期限のお知らせのジョブの API。{method, path}）",
    "f2": "予約（第 2 回）: create（{method, path, body, id}。path・body で {instrumentId}・{start}・{end}（YYYY-MM-DD）・{user} が使える。id は応答から予約の ID を取るパス）、"
          "list（{path, items}。計測器 1 台の予約の一覧と、応答の中の配列のパス。全体の一覧しか無ければ filterInstrument に各要素の計測器 ID の項目名）、"
          "cancel（{method, path}。{reservationId} が使える）、fields（一覧の各要素の id・status・start・end・user の項目名）、status（active（有効）・cancelled（取消）→ 候補の値の配列）",
    "f3": "設置場所の一覧（第 3 回）: list（{path, items}）、create（{method, path, body, id}。{name} が使える）、rename（{method, path, body}。{locationId}・{name}）、delete（{method, path}）、"
          "fields（場所の id・name の項目名）、instrumentSet（計測器の登録・編集の本文で場所を指定する形。例 {\"locationId\": \"{locationId:n}\"}。数値なら :n。名前で指定する形しか無ければ {\"location\": \"{name}\"}）、"
          "instrumentIdField（計測器の API の応答にある場所の ID の項目名。無ければ省く）、filter（一覧を場所で絞り込むクエリ {param, value}。value は \"id\" か \"name\"）",
    "f4": "校正の発注（第 4 回）: create（{method, path, body, id}。{instrumentId} が使える。本文が要らなければ body は {}）、list（{path, items}。計測器 1 台の発注の一覧。"
          "全体の一覧しか無ければ filterInstrument）、fields（id・status・externalId（受付番号）・returnOn（返却予定日）の項目名）、"
          "status（pending（未送信）・accepted（受付済み）・completed（完了）・failed（受付システムに断られた）→ 候補の値の配列。無い状態は書かない）、job（未送信の発注を送り直すジョブの API。無ければ省く）",
    "f5": "変更履歴（第 5 回）: list（{path, items}。計測器 1 台の履歴の API と、応答の中の配列のパス）、fields（id の項目名）",
    "f6": "部署ごとの権限（第 6 回）: 書くことは無い（{}）",
    "h1": "副管理者（引き継ぎ h1）: field（計測器の API の応答にある副管理者の項目名）、set（副管理者を設定する操作 {method, path, body}。{instrumentId}・{subManager}（利用者 ID。解除は null）が使える）",
    "h2": "（引き継ぎ h2）: 書くことは無い（{}）",
}

GUIDE = """あなたは採点の補助です。社内アプリ（計測器の校正台帳、Next.js の API Route）に、毎回 1 つずつ足された機能のコードを読み、
採点用のテストが API を呼ぶための「アダプター」を JSON で書きます。コードに実際にある名前・値・API だけを書き、無いものは書かない（省く）。
推測で API を作らない。コードに無ければ、その項目を省き、notes に書く。

アダプターの例（参照実装のもの）:
{example}

対象の回までのセクション（{sections}）と、必要なら instrument（計測器の登録の本文に追加で必須の項目がある場合だけ {{"createExtra": {{...}}}}）・
env（候補が文書と違う名前の環境変数で通知サービス・受付システムを読んでいる場合だけ、{{"<候補が読む名前>": "notify_url|notify_token|agency_url|agency_key|jobs_token"}}）を書く。

各セクションの意味:
{guide}

前の回で確定したアダプターがあれば渡すので、前の回のセクションは、今のコードでも正しいかを確かめて、変わっていればコードに合わせて直し、
変わっていなければそのまま写す。notes に、決めきれなかったこと・前の回から変えたことを日本語で短く書く。

JSON だけを出力してください（前後に説明を書かない）。最上位のキーは f1〜（対象の回まで）・instrument・env・notes。"""


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def relevant_files(repo, base, commit):
    names = git(repo, "diff", "--name-only", base, commit, "--", "src", "docs", "CLAUDE.md").split()
    out = []
    for n in names:
        if n.startswith("docs/") and not n.endswith(".md"):
            continue
        text = git(repo, "show", f"{commit}:{n}")
        if text:
            out.append((n, text))
    # API Route を先に（アダプターに要るのは主に API の形）
    out.sort(key=lambda x: (0 if "/api/" in x[0] else 1 if x[0].startswith("src/lib") else 2, x[0]))
    return out


def keys_for(round_):
    r = str(round_)
    if r.startswith("h"):
        return [f"f{i}" for i in range(1, 7)] + [r]
    return [f"f{i}" for i in range(1, int(r) + 1)]


def draft(repo, base, commit, round_, prev_adapter=None, work=None):
    files = relevant_files(repo, base, commit)
    body = "\n\n".join(f"=== {n} ===\n{t[:14000]}" for n, t in files)[:160000]
    keys = keys_for(round_)
    prompt = (f"対象の回: {round_}（セクション {', '.join(keys)}）\n\n"
              f"--- 前の回で確定したアダプター ---\n{json.dumps(prev_adapter, ensure_ascii=False, indent=1) if prev_adapter else '（なし）'}\n\n"
              f"--- 候補のコード（初期状態から足された・変わったファイル） ---\n{body}\n--- ここまで ---")
    system = GUIDE.format(example=REF.read_text(), sections="・".join(keys), guide="\n".join(f"- {k}: {SECTIONS[k]}" for k in keys))
    home = Path(work or "/tmp/w18-adapt-home")
    home.mkdir(parents=True, exist_ok=True)
    # コードが大きいとコマンドの引数に入りきらないので、依頼は標準入力で渡す
    p = subprocess.run(["claude", "-p", "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                        "--no-session-persistence", "--system-prompt", system, "--output-format", "json"],
                       cwd=home, env=dict(os.environ, HOME=str(Path.home())), capture_output=True, text=True, timeout=1200,
                       input=prompt)
    out = {"round": str(round_), "commit": commit, "files": [n for n, _ in files], "adapter": None, "cost_usd": 0.0}
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
    repo, base, commit, round_ = sys.argv[1:5]
    prev = json.loads(Path(sys.argv[5]).read_text()) if len(sys.argv) > 5 and sys.argv[5] != "-" else None
    d = draft(repo, base, commit, round_, prev)
    text = json.dumps(d, ensure_ascii=False, indent=2)
    if len(sys.argv) > 6:
        Path(sys.argv[6]).write_text(text + "\n")
    print(text)
