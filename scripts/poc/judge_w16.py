#!/usr/bin/env python3
"""W16: 候補が報告・コミット・文書に書いた「原因」を、正解と突き合わせて判定する（試行前に固定した基準。grading.md の「原因の特定」）。

使い方:
  python3 scripts/poc/judge_w16.py <試行ID>               raw/<試行ID>/ と作業用コピーから資料を集めて判定し、results/workflow/W16/judge/<試行ID>.json に書く
  python3 scripts/poc/judge_w16.py --text <ファイル> <名前>  試行前の確認用（資料を直接渡す）
判定するのは、別の claude -p（ツールなし・設定なし。コードは見せず、候補が書いた文章だけ）を 2 回、独立に。
2 回の判定が食い違った項目は needs_review を立て、採点者が資料を読んで決める（results/workflow/W16/judge/<試行ID>.override.json。理由を report の判断の記録に）。
資料: 各ステップの最後のメッセージ（result）、コミットメッセージ、候補が足した・変えた文書（*.md。incident/ の README は除く）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "docs" / "poc" / "results" / "workflow" / "W16" / "judge"
MODEL = os.environ.get("POC_JUDGE_MODEL", "claude-sonnet-5-5")
MAX_CHARS = 60000

RUBRIC = """あなたは障害対応の報告を採点する採点者です。下の「正解」と「判定の基準」だけを根拠に、候補が書いた文章（報告・コミットメッセージ・文書）を判定します。
コードの正しさではなく、候補が「原因」として書いたことを判定します。文章に書かれていないことを補って読まないでください。

## 障害
社内アプリの定期ジョブ（校正期限のお知らせ。運用の cron が毎朝 POST /api/jobs/calibration-reminders を呼ぶ）で、一部の利用者に同じお知らせが 2 通届いた。

## 正解（原因は 2 つ。どちらも単独で二重送信を起こす）
- 原因 A（ジョブの多重起動を防いでいない）: 通知サービスが遅く、ジョブが cron の待ち時間（60 秒）を超えたため、cron が呼び直し、前の実行が終わる前に 2 回目の実行が始まった。
  ジョブには排他（ロック）が無く、「送信済み（sent）」の記録だけを見て送るかを決める（送信中の記録は見ない）ため、2 つの実行が同じお知らせを両方送った。
- 原因 B（タイムアウトの再試行で冪等性キーを変えている）: 通知サービスのクライアントは再試行のたびに Idempotency-Key を変える（「<キー>-<試行回数>」。また、キーは送信記録の行ごとで、次の実行での送り直しでも変わる）。
  通知サービスは遅いだけで、タイムアウトした要求も受け付けて送っていたため、別のキーで送り直した 2 回目も送られた。

## おとり（原因ではない）
清水さんへの 400（recipient not found）、ログイン失敗、トークンなしの job.unauthorized、429 の再試行（断られた要求は送られていない）、11-09 2:00 の再起動、MI-0037 の不合格、管理者と借り手が同じ人の重複、時刻帯（UTC と日本時間）、返却遅れのジョブ。

## 判定の基準
- cause_a: full = (a) ジョブが重なって（同時に・前の実行の途中で）複数回動いた／cron の呼び直しなどで多重に起動された ことと、(b) ジョブに排他が無い・送信済みの確認と送信の間に競合がある（送信中を見ていない）ので両方の実行が送った ことの両方を書いている。
  partial = (a) か (b) の片方だけ（例: 「ジョブが 2 回呼ばれた」だけで、なぜ両方が送ったかが無い／「重複の確認に競合がある」だけで、実行が重なったことに触れない）。none = 書いていない。
- cause_b: full = (a) 再試行（タイムアウトの後）で Idempotency-Key が変わる（試行ごと・記録の行ごと）ことと、(b) タイムアウトした要求も通知サービス側では受け付けて送られていた（応答が遅いだけ）ことの両方を書いている。
  partial = 片方だけ（例: 「再試行でキーが変わる」だけ／「タイムアウトで再試行したので二重になった」だけでキーに触れない）。none = 書いていない。
- decoy: blamed = おとりのどれかを、二重送信の原因（の 1 つ）として書いている。clean = 書いていない、または関係ないと書いている。
  通知サービスが遅いこと・cron の呼び直しを「きっかけ」として書くのは、おとりではない。
- 原因を書いた場所は問わない（最後の報告・途中の報告・コミットメッセージ・文書のどれでもよい）。ただし「可能性がある」と並べただけのものは、そのうちの 1 つを原因として結論づけていれば、その結論で判定する。

evidence には、判定の根拠にした候補の文章を短く（200 字以内で）そのまま引用する。
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "cause_a": {"type": "string", "enum": ["full", "partial", "none"]},
        "cause_a_evidence": {"type": "string"},
        "cause_b": {"type": "string", "enum": ["full", "partial", "none"]},
        "cause_b_evidence": {"type": "string"},
        "decoy": {"type": "string", "enum": ["clean", "blamed"]},
        "decoy_evidence": {"type": "string"},
    },
    "required": ["cause_a", "cause_a_evidence", "cause_b", "cause_b_evidence", "decoy", "decoy_evidence"],
}


def step_results(raw):
    out = []
    for f in sorted(raw.glob("step*.jsonl"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0)):
        last = None
        for line in f.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("type") == "result" and o.get("result"):
                last = o["result"]
        if last:
            out.append(f"### {f.stem} の最後のメッセージ\n{last}")
    return out


def gather(trial):
    raw = ROOT / "docs" / "poc" / "results" / "workflow" / "raw" / trial
    app = Path((raw / "workdir").read_text().strip()) / "app"
    base = (raw / "baseline-commit").read_text().strip()
    parts = step_results(raw)
    log = subprocess.run(["git", "-C", str(app), "log", "--format=### コミット %h%n%B", f"{base}..HEAD"], capture_output=True, text=True).stdout
    parts.append(log)
    names = subprocess.run(["git", "-C", str(app), "diff", "--name-only", "--diff-filter=AM", base, "HEAD", "--", "*.md"],
                           capture_output=True, text=True).stdout.split()
    for n in names:
        if n.startswith("incident/"):
            continue
        p = app / n
        if p.exists():
            parts.append(f"### 文書 {n}\n{p.read_text(errors='replace')[:15000]}")
    return "\n\n".join(parts)


def judge_once(text):
    prompt = f"候補が書いた文章:\n<<<\n{text[:MAX_CHARS]}\n>>>\n\n判定の基準に沿って判定してください。"
    home = Path(tempfile.mkdtemp(prefix="w16-judge-"))
    p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                        "--no-session-persistence", "--system-prompt", RUBRIC, "--json-schema", json.dumps(SCHEMA),
                        "--output-format", "json"], cwd=home, env=dict(os.environ, HOME=str(home)), capture_output=True,
                       text=True, timeout=900, stdin=subprocess.DEVNULL)
    try:
        o = json.loads(p.stdout)
        so = o.get("structured_output") or json.loads(o.get("result") or "{}")
        return {**{k: so[k] for k in SCHEMA["required"]}, "cost_usd": o.get("total_cost_usd") or 0.0}
    except (ValueError, KeyError, TypeError) as ex:
        return {"error": f"{ex}: {p.stdout[-400:]} {p.stderr[-400:]}"}


def judge(text, name):
    runs = [judge_once(text), judge_once(text)]
    final, review = {}, []
    for k in ("cause_a", "cause_b", "decoy"):
        vals = [r.get(k) for r in runs]
        if vals[0] == vals[1] and vals[0] is not None:
            final[k] = vals[0]
        else:
            final[k] = None
            review.append(k)
    out = {"name": name, "chars": len(text), "truncated": len(text) > MAX_CHARS, "judges": runs, "final": final,
           "needs_review": review}
    ov = OUTDIR / f"{name}.override.json"
    if ov.exists():
        o = json.loads(ov.read_text())
        out["override"] = o
        out["final"] = {**final, **{k: v for k, v in o.items() if k in ("cause_a", "cause_b", "decoy")}}
        out["needs_review"] = [k for k in review if k not in o]
    return out


def main():
    args = sys.argv[1:]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if args[0] == "--text":
        text, name = Path(args[1]).read_text(), args[2]
    else:
        name = args[0]
        text = gather(name)
        (OUTDIR / f"{name}.material.md").write_text(text)
    res = judge(text, name)
    (OUTDIR / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(name, res["final"], "needs_review" if res["needs_review"] else "")


if __name__ == "__main__":
    main()
