#!/usr/bin/env python3
"""U1 の判定役（docs/poc/tasks/wf-U1-design.md の「採点」）。構成の名前は判定役に伏せる。

使い方:
  python3 scripts/poc/judge_u1.py visual <U1a|U1b|U1d|U1e|U1f> <作業場所>
    - 同じ課題の全試行（繰り返し 0 の動作確認は除く）のスクリーンショット（results/workflow/U1/shots/）を、記号 S01〜 の名前で
      作業場所（リポジトリの外）に写し、判定役（claude-opus-5-5）に 5 項目 × 0〜4 点を付けさせる。並べる順番を変えて 2 回行う。
      U1b は変更前の画面（before）を参考として並べる。結果は results/workflow/U1/judge/visual-<課題>.json。
  python3 scripts/poc/judge_u1.py review <作業場所> [U1c|U1g]
    - U1c の各試行の REVIEW.md を、正解（answer-key/U1/truth-c.md）と突き合わせさせる（W20 の judge_w20.py と同じ形）。
      約 25% は 2 回判定して一致を見る。結果は results/workflow/U1/judge/review.json。
  python3 scripts/poc/judge_u1.py pair <作業場所>
    - U3: 仕上げの工程の前（<ID>-pre-desktop.jpg）と後（<ID>-desktop.jpg）を A・B として、左右を入れ替えて 2 回比べさせる。
      2 回とも同じ方を選んだときだけ、その方を勝ちとする（そろわなければ split）。結果は results/workflow/U1/judge/pairs.json。
  python3 scripts/poc/judge_u1.py score
    - 判定の結果と grade_u1.py の結果から、試行ごとの品質（100 点）を results/workflow/U1/scores.json に書く。
"""
import glob
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "U1"
SHOTS = RESULTS / "shots"
JUDGE = RESULTS / "judge"
TRUTH = ROOT / "docs" / "poc" / "answer-key" / "U1" / "truth-c.md"
MODEL = "claude-opus-5-5"
ITEMS = ["purpose", "hierarchy", "spacing", "color_type", "mobile"]
NAMES = re.compile(r"impeccable|ui[-/ ]?ux[-_ ]?pro[-_ ]?max|frontend[-_ ]design|web[-_ ]design[-_ ]guidelines|ui-(none|all|a|fd|pm)\b", re.I)

VISUAL = """# 画面の見た目と使い勝手の判定

あなたは業務アプリの UI デザインの評価者です。ある会社の社内向けタスク管理アプリについて、複数の開発者が同じ依頼で作った画面の
スクリーンショットを比べて採点します。依頼は次のとおりです。

> {task}

このフォルダの画像を Read ツールで**すべて**見てから採点してください。各案は記号（S01 など）で、`<記号>-desktop.jpg`（幅 1280px）と
`<記号>-mobile.jpg`（幅 375px）の 2 枚です（ページ全体を撮ったもの）。{before}

各案に、次の 5 項目を 0〜4 点で付けてください（4 = とても良い、2 = 普通、0 = 大きな問題がある）。全案を見比べ、差があれば点に差を付けてください。

- purpose: 依頼の目的が伝わるか（{purpose}）
- hierarchy: 情報の階層と読みやすさ（何が大事か、どこから読むかが分かるか）
- spacing: 余白・整列・一貫性（揃っているか、詰まりすぎ・空きすぎがないか）
- color_type: 色と書体の使い方（文字が読みやすいか、目的に合っているか。特定の流行や好みではなく、この会社の社員が使う業務アプリとして）
- mobile: スマートフォンでの見やすさと操作しやすさ（はみ出し・小さすぎる文字や操作の的がないか）

出力は JSON だけにしてください（説明の文は不要）:
{{"S01": {{"purpose": 3, "hierarchy": 2, "spacing": 3, "color_type": 2, "mobile": 3, "comment": "一言"}}, ...}}
"""
TASKS = {
    "U1a": ("トップページ（/）を、まだログインしていない社内の人に向けた紹介ページにしてください。どんなアプリで、何ができて、"
             "どう始めればよいか（ログイン画面へ進む）が分かるようにしたい。スマートフォンでも見られるように。見た目はお任せします。",
             "紹介ページとして、どんなアプリで何ができ、どう始めるかが分かるか"),
    "U1b": ("タスク一覧画面の見た目と使い勝手を良くしてください。チームが毎日使う画面なので、一覧の見やすさ、絞り込みの使いやすさ、"
             "スマートフォンでの使いやすさを改善したい。今ある機能（ステータスでの絞り込み、詳細へのリンク、ステータス・担当者・期限の表示）は残す。",
             "毎日使う一覧として、タスクの状況がすぐ分かり、絞り込みが使いやすいか"),
    "U1d": ("このタスク管理アプリを社外の中小企業向けに SaaS として販売する。製品紹介のランディングページを作る。対象はチームのリーダー。"
             "機能、使い始めるまでの流れ、料金、よくある質問を載せる。スマートフォンでも見られるように。見た目はお任せします。",
             "製品の価値が伝わり、申し込みたくなるか"),
    "U1e": ("チームのリーダーが毎朝見るダッシュボードを作る。ステータスごとの件数、期限切れと今週期限のタスク、担当者ごとの件数が一目で分かるように。"
             "スマートフォンでも見られるように。見た目はお任せします。",
             "毎朝見て、対応が必要なことがすぐ分かるか"),
    "U1f": ("タスクの新規登録画面を作る。タイトル・担当者・期限・ステータスを入力する。現場の人が毎日使う入力画面なので入力しやすさを重視し、"
             "入力の誤りはどこをどう直せばよいか分かるように。スマートフォンでも入力しやすく。見た目はお任せします。",
             "迷わず速く入力でき、誤りがあっても直し方が分かるか"),
}
REVIEW = """# 判定の依頼

あなたは UI レビューの採点者です。下の「レビューの指摘」（REVIEW.md）を、指摘 1 件ずつに分け（見出し・箇条書きの 1 項目を 1 件。
1 項目に別々の問題が 2 つ以上書かれていれば分ける）、それぞれを「正解の一覧」と突き合わせてください。

- match: 正解の ID（B1・D2 など）か none。正解に一致するのは、場所（要素）と問題の核心の両方を述べているときだけ。
  D で始まる ID（おとり）は、そこを「問題がある」と指摘したときに付ける（「問題ない」と書いただけなら付けない）。
- kind（match が none のときだけ）: real = 正解の一覧に無いが本当の問題らしい / wrong = 事実と違う、または直すと害がある /
  nit = 好み・細かい点 / unsure = 判断できない。
- severity: 指摘に付いている重要度（高・中・低。無ければ なし）。

出力は JSON だけにしてください（説明の文は不要）:
{"findings": [{"n": 1, "summary": "指摘の要約（1 文）", "severity": "高", "match": "B1", "kind": ""}, ...]}

---

## 正解の一覧

{truth}

---

## レビューの指摘（REVIEW.md）

{review}
"""


def ask(prompt, cwd, tools=("Read",)):
    flags = ["--allowedTools", *tools] if tools else []
    p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--output-format", "json", *flags],
                       cwd=cwd, capture_output=True, text=True, timeout=1800, stdin=subprocess.DEVNULL)
    d = json.loads(p.stdout)
    text = d.get("result", "")
    mm = re.search(r"\{.*\}", text, re.S)
    return json.loads(mm.group(0)), d.get("total_cost_usd", 0)


def trials(task):
    return sorted(Path(f).stem for f in glob.glob(str(RESULTS / f"{task}-ui-*.json")) if not f.endswith("-0.json"))


def visual(task, work):
    ids = [t for t in trials(task) if (SHOTS / f"{t}-desktop.jpg").exists()]
    out = {"task": task, "rounds": [], "cost_usd": 0}
    for rnd in (1, 2):
        d = Path(work) / f"{task}-r{rnd}"
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        order = ids[:]; random.Random(20261111 + rnd * 7 + (task == "U1b")).shuffle(order)
        mapping = {f"S{i + 1:02d}": t for i, t in enumerate(order)}
        for code, t in mapping.items():
            for v in ("desktop", "mobile"):
                shutil.copy(SHOTS / f"{t}-{v}.jpg", d / f"{code}-{v}.jpg")
        before = ""
        if task == "U1b" and (SHOTS / "U1b-before-desktop.jpg").exists():
            for v in ("desktop", "mobile"):
                shutil.copy(SHOTS / f"U1b-before-{v}.jpg", d / f"before-{v}.jpg")
            before = "`before-desktop.jpg`・`before-mobile.jpg` は変更前の画面です（参考。採点しない）。"
        t, purpose = TASKS[task]
        scores, cost = ask(VISUAL.format(task=t, before=before, purpose=purpose), d)
        out["cost_usd"] += cost
        out["rounds"].append({"mapping": mapping, "scores": scores})
    per = {}
    for r in out["rounds"]:
        for code, t in r["mapping"].items():
            s = r["scores"].get(code) or {}
            per.setdefault(t, []).append({k: s.get(k, 0) for k in ITEMS} | {"comment": s.get("comment", "")})
    out["per_trial"] = {t: {"rounds": v, "mean_total": round(sum(sum(x[k] for k in ITEMS) for x in v) / len(v), 2),
                            "round_diff": abs(sum(v[0][k] for k in ITEMS) - sum(v[-1][k] for k in ITEMS))}
                        for t, v in per.items()}
    JUDGE.mkdir(parents=True, exist_ok=True)
    (JUDGE / f"visual-{task}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"visual {task}: {len(ids)} trials, cost ${out['cost_usd']:.2f}")


PAIR = """# 2 つの画面の比較

ある会社の社内向けタスク管理アプリについて、同じ依頼で作った画面の 2 つの版のスクリーンショット（幅 1280px、ページ全体）を比べてください。
依頼は次のとおりです。

> {task}

`A.jpg` と `B.jpg` を Read ツールで両方見てから、この会社の社員が使う（または見る）画面として、どちらが良いかを選んでください。
見た目の良さ・情報の階層と読みやすさ・余白と整列・色と書体・依頼の目的が伝わるか、を総合して判断します。差がほとんど無ければ "same" にしてください。

出力は JSON だけにしてください（説明の文は不要）:
{{"winner": "A" | "B" | "same", "reason": "一言"}}
"""


def pair(work):
    """U3: 同じ試行の仕上げの前（<ID>-pre）と後（<ID>）を、左右を入れ替えて 2 回比べる。"""
    out = {"pairs": {}, "cost_usd": 0}
    for f in sorted(RESULTS.glob("U1*-ui-fd-md-*-*.json")):
        t = f.stem
        if t.endswith("-0") or not (SHOTS / f"{t}-pre-desktop.jpg").exists():
            continue
        task = t[:4]
        runs = []
        for order in (("pre", "post"), ("post", "pre")):
            d = Path(work) / "pair" / t / "-".join(order)
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            for side, which in zip("AB", order):
                shutil.copy(SHOTS / (f"{t}-pre-desktop.jpg" if which == "pre" else f"{t}-desktop.jpg"), d / f"{side}.jpg")
            res, cost = ask(PAIR.format(task=TASKS[task][0]), d)
            out["cost_usd"] += cost
            w = res.get("winner", "same")
            runs.append({"order": order, "winner": "same" if w == "same" else order["AB".index(w)], "reason": res.get("reason", "")})
        ws = {r["winner"] for r in runs}
        verdict = runs[0]["winner"] if len(ws) == 1 else "split"
        out["pairs"][t] = {"runs": runs, "verdict": verdict}
        print(f"pair {t}: {verdict}")
    JUDGE.mkdir(parents=True, exist_ok=True)
    (JUDGE / "pairs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


def review(work, task="U1c"):
    """task: U1c（簡単な問題 9 件）か U1g（U4。見つけにくい問題 8 件）。結果は judge/review.json・review-U1g.json。"""
    ids = trials(task)
    truth = (TRUTH if task == "U1c" else TRUTH.with_name("truth-g.md")).read_text()
    rnd = random.Random(20261112)
    twice = set(rnd.sample(ids, max(1, round(len(ids) * 0.25))))
    out = {"twice": sorted(twice), "trials": {}, "cost_usd": 0}
    for t in ids:
        body = json.loads((RESULTS / f"{t}.json").read_text()).get("review_md", "")
        body = NAMES.sub("[redacted]", body)
        d = Path(work) / "review"; d.mkdir(parents=True, exist_ok=True)
        runs = []
        for _ in range(2 if t in twice else 1):
            res, cost = ask(REVIEW.replace("{truth}", truth).replace("{review}", body or "（REVIEW.md が無い）"), d, tools=())
            out["cost_usd"] += cost
            runs.append(res.get("findings", []))
        out["trials"][t] = runs
        print(f"review {t}: {len(runs[0])} findings")
    JUDGE.mkdir(parents=True, exist_ok=True)
    (JUDGE / ("review.json" if task == "U1c" else f"review-{task}.json")).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


def review_score(findings, n_bugs=9):
    found = sorted({f["match"] for f in findings if re.fullmatch(r"B\d", f.get("match", ""))})
    decoys = sorted({f["match"] for f in findings if re.fullmatch(r"D\d", f.get("match", ""))})
    wrong = sum(1 for f in findings if f.get("match") == "none" and f.get("kind") == "wrong")
    real = sum(1 for f in findings if f.get("match") == "none" and f.get("kind") == "real")
    nit = sum(1 for f in findings if f.get("match") == "none" and f.get("kind") == "nit")
    q = len(found) / n_bugs * 80 + max(0, 20 - 5 * (len(decoys) + wrong))
    return {"found": found, "decoys": decoys, "wrong": wrong, "extra_real": real, "nits": nit,
            "findings": len(findings), "quality": round(q, 1)}


def score():
    scores = {}
    for task in ("U1a", "U1b", "U1d", "U1e", "U1f"):
        vf = JUDGE / f"visual-{task}.json"
        vis = json.loads(vf.read_text())["per_trial"] if vf.exists() else {}
        for t in trials(task):
            r = json.loads((RESULTS / f"{t}.json").read_text())
            v = vis.get(t, {})
            visual_50 = round(v.get("mean_total", 0) / 20 * 50, 2)
            scores[t] = {"task": task, "config": r["config"], "rep": r["rep"], **r["score"], "visual_50": visual_50,
                         "visual_round_diff": v.get("round_diff"), "quality": round(r["score"]["subtotal_50"] + visual_50, 2),
                         "cost_usd": r["transcript"]["cost_usd"], "seconds": r["elapsed_seconds"], "interventions": r["interventions"],
                         "skills": r["transcript"]["skills_used"], "obs": {k: r["observations"][k] for k in ("hook_outputs", "design_docs", "fonts", "overused_fonts")}}
    for name, task, n_bugs in (("review.json", "U1c", 9), ("review-U1g.json", "U1g", 8)):
        rf = JUDGE / name
        if not rf.exists():
            continue
        rv = json.loads(rf.read_text())
        for t, runs in rv["trials"].items():
            r = json.loads((RESULTS / f"{t}.json").read_text())
            s = [review_score(f, n_bugs) for f in runs]
            scores[t] = {"task": task, "config": r["config"], "rep": r["rep"], **s[0],
                         "rejudge": s[1] if len(s) > 1 else None, "cost_usd": r["transcript"]["cost_usd"],
                         "seconds": r["elapsed_seconds"], "interventions": r["interventions"], "skills": r["transcript"]["skills_used"]}
    (RESULTS / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n")
    print(f"scores: {len(scores)} trials")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "visual":
        visual(sys.argv[2], sys.argv[3])
    elif cmd == "pair":
        pair(sys.argv[2])
    elif cmd == "review":
        review(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "U1c")
    elif cmd == "score":
        score()
    else:
        sys.exit(__doc__)
