#!/usr/bin/env python3
"""W18 の設計のブラインドレビュー（docs/poc/answer-key/W18/grading.md の「設計の筋」）。
W13 の blind_w13.py（origin/agent/poc-w13 a0617be）の資料の作り方を写し、第 6 回の終わりのコード全体（初期状態からの差分）を渡すようにした。

使い方:
  python3 scripts/poc/blind_w18.py prepare <出力先ディレクトリ> <系列ID>...
    - 出力先に R01.md〜 と CONTEXT.md を書く。記号と系列の対応は results/workflow/W18/blind/mapping.json（レビュー担当には渡さない）。
  python3 scripts/poc/blind_w18.py review <出力先ディレクトリ>
    - 2 名のレビュー担当（別々の claude -p。観点は同じで、立場の説明だけが違う）が各 R を読み、
      results/workflow/W18/blind/reviewer-1.json・reviewer-2.json（{"R01": {"a": 0-3, ..., "f": 0-3, "comment": ".."}, ...}）を書く。
  python3 scripts/poc/blind_w18.py collect
    - 2 名の点を集計し、results/workflow/W18/blind/scores.json（by_series）を書く。
"""
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "W18"
RAW = ROOT / "docs" / "poc" / "results" / "workflow" / "raw"
BLIND = RESULTS / "blind"
SEED = 20261118
MODEL = os.environ.get("POC_BLIND_MODEL", "claude-sonnet-5-5")
NAMES = re.compile(r"superpowers|feature[-_ ]?dev|gstack|compound(?:[-_ ]?engineering)?|\bce-[a-z-]+|ponytail|claude|baseline|reference|shortest", re.I)
ITEMS = ["a", "b", "c", "d", "e", "f"]
TOOL = re.compile(r"^(package-lock\.json|docs/(plans|solutions|superpowers|specs|brainstorms)/|\.compound-engineering/|\.claude/|AGENTS\.md$|\.playwright-mcp/|\.gstack/|\.mcp\.json$)")
DOC = re.compile(r"\.(md|mdx|txt)$")

RUBRIC = """観点（各 0〜3 点。0 = できていない、1 = 弱い、2 = おおむねできている、3 = よくできている）:
a 層と責務の分け方: 業務の判断（ルール）と入出力（DB・HTTP・画面）が分かれ、API Route が薄いか。
b 重複の少なさと部品の再利用: 同じ処理（SQL・検証・外部呼び出し・日付の計算）を複製せず、既存・共通の部品を使っているか。
c 横断的な関心事の一元化: 外部呼び出しの再試行・権限の判定・変更履歴・状態の変化（予約の取消など）が、1 か所で扱われ、漏れが無いか。
d 変更のしやすさ: 次の機能や仕様変更（例: 管理者の代わりの人を足す、状態を 1 つ足す）を入れるとき、直す場所が少なく、分かりやすいか。
e テストの網羅と質: 業務の決まり・境界・失敗時の動きを確かめる単体テストがあり、テストのしやすい作り（時刻・外部サービスの差し替え）か。
f 引き継ぐ人が読める文書と命名: 業務の言葉での命名、決まりや前提を書いたコメント・文書があり、初めて読む人が分かるか。"""


def split(text):
    code, docs = [], []
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", chunk)
        if not m or TOOL.match(m.group(2)):
            continue
        (docs if DOC.search(m.group(2)) else code).append(chunk)
    return "".join(code), "".join(docs)


def final_diff(sid):
    r1 = RAW / f"W18r1-{sid}"
    r6 = RAW / f"W18r6-{sid}"
    repo = Path((r1 / "workdir").read_text().strip()) / "app"
    base = (r1 / "baseline-commit").read_text().strip()
    final = (r6 / "final-commit").read_text().strip()
    diff = subprocess.run(["git", "-C", str(repo), "diff", base, final, "--", ".", ":!package-lock.json"], capture_output=True, text=True).stdout
    return split(diff)


def prepare(out, sids):
    out.mkdir(parents=True, exist_ok=True)
    codes = [f"R{i:02d}" for i in range(1, len(sids) + 1)]
    order = list(sids)
    random.Random(SEED).shuffle(order)
    mapping = dict(zip(codes, order))
    for code, sid in mapping.items():
        c, d = final_diff(sid)
        body = (f"# {code}\n\n6 回の機能追加の後のコード（初期状態からの差分）。\n\n"
                f"## 文書の差分（README・設計メモなど。ツールの管理用ファイルは除く）\n\n```diff\n{d[:30000] or '（なし）'}\n```\n\n"
                f"## コードの差分\n\n```diff\n{c or '（コードの変更なし）'}\n```\n")
        (out / f"{code}.md").write_text(NAMES.sub("[redacted]", body))
    tasks = "\n".join(f"{k}. {(ROOT / f'docs/poc/tasks/wf-W18r{k}.md').read_text().strip()}" for k in range(1, 7))
    (out / "CONTEXT.md").write_text(
        "# 題材\n\n社内の「計測器 校正台帳」（Next.js の App Router・TypeScript・SQLite（node:sqlite）・node:test）。"
        "初期状態には、計測器の台帳・貸出・校正記録・ログイン・定期実行のジョブの決まり（運用の cron が POST /api/jobs/<名前> を JOBS_TOKEN で呼ぶ）・"
        "構造化ログ（src/lib/logger.ts）・社内通知サービスの API 文書がある。\n\n"
        f"# 6 回の依頼（この順に、毎回新しい作業として 1 つずつ足した。依頼者に質問できた）\n\n{tasks}\n")
    BLIND.mkdir(parents=True, exist_ok=True)
    (BLIND / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(mapping)} files -> {out}")


SCHEMA = {"type": "object", "properties": {k: {"type": "integer", "minimum": 0, "maximum": 3} for k in ITEMS} | {"comment": {"type": "string"}},
          "required": ITEMS + ["comment"]}
ROLES = {
    1: "あなたは、このアプリを来月から引き継いで保守する、経験 10 年のバックエンドの開発者です。",
    2: "あなたは、社内システムの設計を審査するアーキテクトです。",
}


def review(out):
    out = Path(out)
    ctx = (out / "CONTEXT.md").read_text()
    for rv, role in ROLES.items():
        path = BLIND / f"reviewer-{rv}.json"
        res = json.loads(path.read_text()) if path.exists() else {}
        for f in sorted(out.glob("R*.md")):
            code = f.stem
            if code in res:
                continue
            system = (f"{role} コードの差分を読み、下の観点で採点します。どのツール・開発者が書いたかは伏せてあります。\n\n{RUBRIC}\n\n"
                      "comment には、点の根拠を日本語で 3〜5 文で書く（具体的なファイル・関数に触れる）。")
            prompt = f"{ctx}\n\n--- 採点するコード ---\n{f.read_text()[:300000]}"
            home = BLIND / f"home-{rv}"
            home.mkdir(parents=True, exist_ok=True)
            p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                                "--no-session-persistence", "--system-prompt", system, "--json-schema", json.dumps(SCHEMA),
                                "--output-format", "json"], cwd=home, capture_output=True, text=True, timeout=1800, stdin=subprocess.DEVNULL)
            try:
                o = json.loads(p.stdout)
                so = o.get("structured_output") or json.loads(o.get("result") or "{}")
                res[code] = {k: int(so[k]) for k in ITEMS} | {"comment": so.get("comment", ""), "cost_usd": o.get("total_cost_usd")}
            except (ValueError, KeyError, TypeError) as ex:
                print(f"reviewer {rv} {code}: {ex} {p.stdout[-300:]} {p.stderr[-300:]}", file=sys.stderr)
                continue
            path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
            print(f"reviewer {rv} {code}: {sum(res[code][k] for k in ITEMS)}")


def collect():
    mapping = json.loads((BLIND / "mapping.json").read_text())
    revs = [json.loads((BLIND / f"reviewer-{i}.json").read_text()) for i in (1, 2)]
    by_series = {}
    for code, sid in mapping.items():
        totals = [sum(int(r[code][k]) for k in ITEMS) for r in revs]
        gaps = [k for k in ITEMS if abs(int(revs[0][code][k]) - int(revs[1][code][k])) >= 2]
        by_series[sid] = {"code": code, "totals": totals, "mean": sum(totals) / 2,
                          "items": {k: [int(r[code][k]) for r in revs] for k in ITEMS}, "gaps": gaps,
                          "comments": [r[code].get("comment", "") for r in revs]}
    (BLIND / "scores.json").write_text(json.dumps({"by_series": by_series}, ensure_ascii=False, indent=2) + "\n")
    for sid, v in sorted(by_series.items()):
        print(f"{sid:28} {v['code']} totals={v['totals']} mean={v['mean']} gaps={v['gaps']}")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]), sys.argv[3:])
    elif sys.argv[1] == "review":
        review(sys.argv[2])
    else:
        collect()
