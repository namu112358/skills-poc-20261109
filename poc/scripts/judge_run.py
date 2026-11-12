#!/usr/bin/env python3
"""judge_w20.py prepare が作った判定の資料（J01.md〜）を、判定役のモデルにヘッドレスで判定させる。

使い方: POC_E2_SCENARIO=W21 python3 poc/scripts/judge_run.py <資料のディレクトリ> [--model claude-opus-5-5] [--jobs 3]
  - 各資料を判定役に渡し、出力の JSON を results/workflow/<W>/judge/<記号>.json に書く（既にあれば飛ばす）。
  - twice.json に載っている記号は、もう 1 回別の会話で判定し <記号>-b.json に書く（判定の一致率を測るため）。
  - 判定役はツールを使わない（資料の中身だけで判定する）。作業ディレクトリは空の一時ディレクトリにする
    （リポジトリの正解データや設定を読めないようにする）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_w20  # noqa: E402

TAIL = "\n\n---\n\n出力は JSON だけを返してください（ファイルには書かず、この返答の本文として返す。前後に説明やコードフェンスを付けない）。\n"


def extract_json(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("JSON が見つからない")
    return json.loads(m.group(0))


def judge_one(src, dest, model):
    if dest.exists():
        return f"skip {dest.name}"
    prompt = src.read_text() + TAIL
    with tempfile.TemporaryDirectory() as cwd:
        for attempt in range(3):
            r = subprocess.run(
                ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", ""],
                cwd=cwd, capture_output=True, text=True, timeout=900,
                env={**os.environ, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
            )
            try:
                out = json.loads(r.stdout)
                data = extract_json(out["result"])
                data["_judge"] = {"model": model, "cost_usd": out.get("total_cost_usd")}
                dest.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
                return f"ok {dest.name} ({len(data.get('findings', []))} 件)"
            except Exception as e:  # noqa: BLE001
                err = f"{e}: {r.stderr[-300:]} {r.stdout[-300:]}"
    return f"FAIL {dest.name}: {err}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    src = Path(a.src)
    judge_w20.JUDGE.mkdir(parents=True, exist_ok=True)
    twice = json.loads((judge_w20.JUDGE / "twice.json").read_text())
    jobs = []
    for f in sorted(src.glob("J*.md")):
        jobs.append((f, judge_w20.JUDGE / f"{f.stem}.json"))
        if f.stem in twice:
            jobs.append((f, judge_w20.JUDGE / f"{f.stem}-b.json"))
    with ThreadPoolExecutor(a.jobs) as ex:
        for msg in ex.map(lambda j: judge_one(j[0], j[1], a.model), jobs):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
