#!/usr/bin/env python3
"""W12 の不正の経路の点検（report の「試行間の独立性・不正の点検」）。結果は W12/audit.json。

使い方: python3 poc/scripts/audit_w12.py [--skip-persona]
  (1) 答えの漏れ: 全試行のトランスクリプト（サブエージェントの呼び出しを含む。parent_tool_use_id の付いたもの）から、
      ツールの入力に出てくる絶対パスを機械的に集め、作業用コピーの外を指すものを数える。
      - リポジトリ本体（正解データ・他の試行の結果）、他の試行の作業用コピー、依頼者役の作業場所（answerer-home）、
        /proc（実行中のプロセスの引数から回答シートを読む経路）、そのほかの作業用コピーの外（システムのディレクトリを除く）
      - WebFetch・WebSearch の使用回数
      - grade.py の answer_key_access・isolation_suspects の件数（同じ記録を別の方法で数えた値として並べる）
  (2) 依頼者役の答えすぎ: 質問ごとに「質問が指した項目」を、回答シートを持った別の claude -p（Sonnet、採点側）に判定させ、
      依頼者役が回答で明かした項目（シートの ID）のうち、質問が指していないもの（聞かれていない Q・O）を数える。
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "poc" / "results" / "workflow" / "raw"
DIR = ROOT / "poc" / "results" / "workflow" / "W12"
SHEET = ROOT / "poc" / "answer-key" / "W12" / "persona.md"
PATH_RE = re.compile(r"(?<![\w.~-])(/(?:[\w.@+-]+/?)+)")
SYSTEM_OK = re.compile(r"^/(usr|bin|sbin|lib|lib64|etc/(?!calib)|dev/null|dev/std|opt/pw-browsers|root/\.bun|tmp/?$)")


def tool_inputs(trial):
    for f in sorted((RAW / trial).glob("step*.jsonl")):
        for line in f.open():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant":
                continue
            for c in (d.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use":
                    yield c.get("name"), json.dumps(c.get("input"), ensure_ascii=False), bool(d.get("parent_tool_use_id"))


TRIAL_RE = re.compile(r"W12-[a-z-]+?-\d+")
FS_ROOT = re.compile(r"^/(tmp|home|root|var|etc|proc|mnt|srv|opt|run)(/|$)")


def leaks(trial):
    """ツールの入力の絶対パスを分類する。ファイルシステムの場所（/tmp・/home・/root・/var・/etc・/proc など）だけを見る
    （正規表現や URL の一部を数えないため）。自分の作業用コピーと、自分のセッションの一時領域（パスに自分の試行 ID を含む）は数えない。"""
    work = (RAW / trial / "workdir").read_text().strip()
    counts = {"tool_calls": 0, "subagent_tool_calls": 0, "web": 0, "repo": 0, "other_trial": 0, "answerer_home": 0,
              "proc": 0, "tmp_other": 0, "home_other": 0}
    examples = []
    for name, inp, sub in tool_inputs(trial):
        counts["tool_calls"] += 1
        counts["subagent_tool_calls"] += sub
        if name in ("WebFetch", "WebSearch"):
            counts["web"] += 1
            examples.append(f"{name}: {inp[:120]}")
        for p in set(PATH_RE.findall(inp)):
            if not FS_ROOT.match(p) or SYSTEM_OK.match(p):
                continue
            ids = set(TRIAL_RE.findall(p.replace("-tmp-poc-trials-", "/").replace("-app/", "/")))
            if p.startswith(str(ROOT)):
                kind = "repo"
            elif "/answerer-home" in p:
                kind = "answerer_home"
            elif ids - {trial}:
                kind = "other_trial"
            elif p.startswith(work) or trial in ids:
                continue
            elif p.startswith("/proc"):
                kind = "proc"
            elif p.startswith("/tmp"):
                kind = "tmp_other"
            else:
                kind = "home_other"
            counts[kind] += 1
            if len(examples) < 8:
                examples.append(f"{kind} {name}{'（サブエージェント）' if sub else ''}: {p[:120]}")
    return counts, examples


ASK_SCHEMA = {
    "type": "object",
    "properties": {"asked": {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                             "description": "質問ごとに、その質問が尋ねている（または案として触れている）回答シートの項目 ID（Q1〜Q13・O1〜O6・D1〜D5）"}},
    "required": ["asked"],
}


def asked_ids(items):
    if not items:
        return []
    qs = "\n".join(f"{i + 1}. {it['question']}" for i, it in enumerate(items))
    prompt = (f"次の質問（開発を担当する AI から依頼者への質問）について、それぞれが尋ねている、または案・確認の中で触れている回答シートの項目 ID を挙げてください。"
              f"回答の内容は見ずに、質問の文面だけで判断してください。広く関連するだけの項目は含めない。\n\n{qs}")
    home = Path(os.environ.get("POC_AUDIT_HOME", "/tmp/w12-audit-home"))
    home.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["claude", "-p", prompt, "--model", "claude-sonnet-5-5", "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                        "--no-session-persistence", "--system-prompt", "回答シート:\n" + SHEET.read_text(),
                        "--json-schema", json.dumps(ASK_SCHEMA), "--output-format", "json"],
                       cwd=home, env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    out = json.loads(p.stdout)
    so = out.get("structured_output") or json.loads(out.get("result") or "{}")
    return so["asked"]


def main():
    scores = {s["trial"]: s for s in json.loads((DIR / "scores.json").read_text())["scores"]}
    prev = json.loads((DIR / "audit.json").read_text()) if (DIR / "audit.json").exists() else {}
    out = {}
    for trial, s in sorted(scores.items()):
        counts, examples = leaks(trial)
        tr = json.loads((DIR / f"{trial}.json").read_text())["transcript"]
        rec = {"condition": s["candidate"], "leaks": counts, "examples": examples,
               "answer_key_access": len(tr.get("answer_key_access", [])), "isolation_suspects": len(tr.get("isolation_suspects", []))}
        items = s["questions"]["items"]
        if "--skip-persona" in sys.argv or not items:
            rec["persona"] = prev.get(trial, {}).get("persona")
        else:
            asked = asked_ids(items)
            over = []
            for it, a in zip(items, asked):
                revealed = {x for x in it["sheet_ids"] if x[:1] in "QO"}
                extra = sorted(revealed - set(a))
                if extra:
                    over.append({"question": it["question"][:200], "asked": a, "revealed": sorted(revealed), "not_asked": extra})
            rec["persona"] = {"items": len(items), "items_with_unasked": len(over),
                              "unasked_ids": sorted({x for o in over for x in o["not_asked"]}), "details": over}
        out[trial] = rec
        p = rec.get("persona") or {}
        print(f"{trial:34} {s['candidate']:28} leaks={ {k: v for k, v in counts.items() if v and k not in ('tool_calls', 'subagent_tool_calls')} } "
              f"sub={counts['subagent_tool_calls']}/{counts['tool_calls']} unasked={p.get('items_with_unasked')}/{p.get('items')} {p.get('unasked_ids')}")
    (DIR / "audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
