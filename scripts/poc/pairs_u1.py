#!/usr/bin/env python3
"""U1〜U3 の画面を二択で比べるページ（人の評価。依頼者の指示で順位付けのページから切り替えた）を作る。

使い方: python3 scripts/poc/pairs_u1.py <出力先ディレクトリ>
  - 作る課題（U1a・b・d・e・f）の全試行（繰り返し 0 の動作確認は除く）の幅 1280px のスクリーンショットを、試行 ID から決まる
    記号の名前で <出力先>/shots/ に写し、<出力先>/index.html を書く。ページは Artifact として公開し、回答はページの db（votes）に保存する。
  - 構成の名前は、ページの「結果を見る」でだけ出す。U3 の構成は仕上げの後の画面。
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gallery_u1 import CONFIG_LABEL, RESULTS, SHOTS  # noqa: E402

CONFIG_LABEL = dict(CONFIG_LABEL, **{"ui-fd-md-wdg": "Frontend Design + 指示 → WDG で仕上げ（U3）",
                                     "ui-fd-md-imp": "Frontend Design + 指示 → Impeccable で仕上げ（U3）"})
TASKS = {
    "U1a": ("紹介ページ", "トップページ（/）を、まだログインしていない社内の人に向けた紹介ページにする。どんなアプリで、何ができて、どう始めればよいかが分かるように。見た目はお任せ。"),
    "U1b": ("タスク一覧の改善", "タスク一覧画面の見た目と使い勝手を良くする。毎日使う画面なので、一覧の見やすさ、絞り込みの使いやすさを改善。今ある機能は残す。見た目はお任せ。"),
    "U1d": ("SaaS の LP", "このタスク管理アプリを社外の中小企業向けに SaaS として販売する。製品紹介のランディングページを作る。機能、始め方、料金、よくある質問。見た目はお任せ。"),
    "U1e": ("ダッシュボード", "チームのリーダーが毎朝見るダッシュボードを作る。ステータスごとの件数、期限切れと今週期限のタスク、担当者ごとの件数が一目で分かるように。見た目はお任せ。"),
    "U1f": ("登録フォーム", "タスクの新規登録画面を作る。現場の人が毎日使う入力画面なので入力しやすさを重視し、入力の誤りは直し方が分かるように。見た目はお任せ。"),
}


def main(out):
    out = Path(out)
    (out / "shots").mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(RESULTS.glob("U1[abdef]-ui-*.json")):
        r = json.loads(f.read_text())
        t = r["trial"]
        if r["rep"] == 0 or not (SHOTS / f"{t}-desktop.jpg").exists() or r["config"] not in CONFIG_LABEL:
            continue
        # 記号（3 文字）は 145 試行で重なることがあるので、ファイル名には試行 ID の長いハッシュを使う
        c = hashlib.sha256(("w21-pairs:" + t).encode()).hexdigest()[:16]
        shutil.copy(SHOTS / f"{t}-desktop.jpg", out / "shots" / f"{c}-desktop.jpg")
        # ページの保存先（db）の回答は改名前の ID で付いているので、ページに出す ID と課題名は改名前の形（W21…）にそろえる
        items.append({"id": "W21" + t[2:], "code": c, "task": "W21" + r["task"][2:], "config": r["config"], "configLabel": CONFIG_LABEL[r["config"]]})
    tasks = {"W21" + k[2:]: {"label": v[0], "brief": f"<b>{v[0]}</b>　{v[1]}"} for k, v in TASKS.items()}
    html = (Path(__file__).resolve().parent / "pairs_u1.html").read_text()
    html = html.replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False)).replace("/*__TASKS__*/{}", json.dumps(tasks, ensure_ascii=False))
    (out / "index.html").write_text(html)
    print(f"{len(items)} 案を書いた: {out}/index.html")


if __name__ == "__main__":
    main(sys.argv[1])
