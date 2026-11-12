#!/usr/bin/env python3
"""security-audit の試行 1 回分（poc/results/security/raw/<ID>）を集計して JSON で出す。

使い方: python3 poc/scripts/security_summary.py <raw/<ID> のディレクトリ>
集計するもの: 費用（result の total_cost_usd）、所要時間、ターン数、起動したサブエージェントの数、
監査の出力（findings.json の判定ごとの件数・深刻度、coverage-ledger.json の状態ごとの件数、run_status）。
"""
import glob
import json
import os
import sys
from collections import Counter


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main(out):
    result, agents, tools = None, 0, Counter()
    with open(os.path.join(out, "step1.jsonl")) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result":
                result = d
            if d.get("type") == "assistant":
                for c in d.get("message", {}).get("content", []) or []:
                    if c.get("type") == "tool_use":
                        tools[c["name"]] += 1
                        if c["name"] in ("Task", "Agent"):
                            agents += 1
    s = {
        "id": os.path.basename(out.rstrip("/")),
        "cost_usd": result and result.get("total_cost_usd"),
        "duration_s": result and round(result.get("duration_ms", 0) / 1000),
        "wall_s": int(open(os.path.join(out, "wall-seconds")).read()) if os.path.exists(os.path.join(out, "wall-seconds")) else None,
        "num_turns": result and result.get("num_turns"),
        "is_error": result and result.get("is_error"),
        "subtype": result and result.get("subtype"),
        "subagents": agents,
        "tool_uses": dict(tools.most_common()),
        "model_usage": result and result.get("modelUsage"),
    }
    # Claude Security: リポジトリの中の CLAUDE-SECURITY-<時刻>/ の JSONL（1 行 1 件）
    cs = sorted(glob.glob(os.path.join(out, "audit-out", "CLAUDE-SECURITY-*", "CLAUDE-SECURITY-RESULTS.jsonl")))
    if cs:
        recs = [json.loads(l) for l in open(cs[-1]) if l.strip()]
        s["tool_output"] = os.path.dirname(cs[-1])
        s["findings"] = [
            {k: r.get(k) for k in ("title", "severity", "confidence", "cwe_id", "file", "line", "claudeSecurityPluginFindingId") if k in r}
            or r
            for r in recs
        ]
        s["severity"] = dict(Counter(str(r.get("severity")).lower() for r in recs))
    runs = sorted(d for d in glob.glob(os.path.join(out, "audit-out", "*")) if not os.path.basename(d).startswith("CLAUDE-SECURITY-"))
    run = runs[-1] if runs else None
    if run:
        meta = load(os.path.join(run, "run-metadata.json")) or {}
        s["run_status"] = meta.get("run_status")
        s["incomplete_reason"] = meta.get("incomplete_reason")
        s["profile"] = meta.get("profile")
        findings = load(os.path.join(run, "findings.json"))
        recs = findings.get("findings", findings) if isinstance(findings, dict) else findings
        if isinstance(recs, list) and recs:
            s["verdicts"] = dict(Counter(r.get("verdict") for r in recs))
            s["severity"] = dict(Counter(r.get("severity") for r in recs if r.get("verdict") == "confirmed"))
            s["findings"] = [
                {
                    "verdict": r.get("verdict"),
                    "title": r.get("title"),
                    "severity": r.get("severity"),
                    "files": sorted({t.get("file") for t in r.get("trace", []) + r.get("evidence", []) if t.get("file")}),
                }
                for r in recs
            ]
        ledger = load(os.path.join(run, "coverage-ledger.json"))
        units = ledger.get("units", ledger) if isinstance(ledger, dict) else ledger
        if isinstance(units, list):
            s["ledger_units"] = len(units)
            s["ledger_states"] = dict(Counter(u.get("state") or u.get("status") for u in units))
        s["files"] = sorted(os.listdir(run))
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
