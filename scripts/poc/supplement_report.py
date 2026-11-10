"""W1・W2 のレポートに補足の再試行の節を足す（report_w1.py・report_w2.py から使う）。

補足の再試行は、ディレクトリごとに 1 つのまとまり（GROUPS）で、それぞれ別の節になる。
  - supplement/: 新文言での Feature Dev 再試行（W1・W2）
  - supplement-ce-work/: /ce-work 入口での Compound Engineering 再試行（W1。2026-11-10 追加）
データは results/workflow/<W>/<ディレクトリ>/ にある。
  - scores.json: score_w1.py / score_w2.py の --supplement で作る再試行の点数（元の scores.json とは別）
  - <試行ID>.json: grade.py --supplement の採点結果
  - notes.json: 文章（summary・trials・decisions・isolation）
supplement/ が無ければ何も足さない（元の試行だけのレポートは従来どおり）。
"""
import html
import json
import statistics
from pathlib import Path

# 補足の再試行のまとまり（ディレクトリ名 → 見出し・比べる元の候補・行の見出し）
GROUPS = {
    "supplement": {
        "title": "補足: 新文言での Feature Dev 再試行",
        "short": "Feature Dev の補足の再試行",
        "candidate": "feature-dev",
        "orig_label": "元の Feature Dev（旧文言 #1・#2 の平均）",
        "retry": "新文言",
    },
    "supplement-ce-work": {
        "title": "補足: /ce-work 入口での Compound Engineering 再試行",
        "short": "Compound Engineering の補足の再試行",
        "candidate": "compound-engineering",
        "orig_label": "元の Compound Engineering（/ce-plan 入口 #1・#2 の平均）",
        "retry": "/ce-work 入口",
    },
}

# W ごとの内訳の列（キー、見出し、満点）
PARTS = {
    "W1": [("acceptance", "受け入れ", 50), ("efficiency", "時間・費用", 30), ("overengineering", "過剰さ", 20)],
    "W2": [("acceptance", "受け入れ", 40), ("intervention", "介入", 20), ("quality", "設計・テスト", 25), ("cost", "費用", 15)],
}


def e(s):
    return html.escape(str(s))


def load(dir_, group="supplement"):
    sdir = Path(dir_) / group
    if not (sdir / "scores.json").exists() or not (sdir / "notes.json").exists():
        return None
    data = json.loads((sdir / "scores.json").read_text())
    scores = data["scores"] if isinstance(data, dict) else data
    trials = {s["trial"]: json.loads((sdir / f"{s['trial']}.json").read_text()) for s in scores}
    return {"scores": sorted(scores, key=lambda s: s["run"]), "trials": trials,
            "notes": json.loads((sdir / "notes.json").read_text())}


def _subagents(trial):
    types = trial["transcript"].get("subagent_types") or {}
    if not types:
        return str(trial["transcript"]["subagents"])
    detail = "、".join(f"{k.split(':')[-1]} ×{v}" for k, v in sorted(types.items()))
    return f"{trial['transcript']['subagents']}（{detail}）"


def _rows(w, original, supp, g):
    """表の行（dict のリスト）。元の候補 2 回の平均、再試行ごと、再試行の平均の順。"""
    parts = PARTS[w]

    def row(label, ss, subagents, skills, avg=False):
        r = {"label": label, "total": round(statistics.mean(s["total"] for s in ss), 1)}
        for k, _, _ in parts:
            r[k] = round(statistics.mean(s[k] for s in ss), 1)
        r["usd"] = statistics.mean(s["facts"]["cost_usd"] for s in ss)
        r["minutes"] = statistics.mean(s["facts"]["elapsed_seconds"] for s in ss) / 60
        r["subagents"] = subagents
        r["skills"] = skills
        r["avg"] = avg
        return r

    orig = [s for s in original if s["candidate"] == g["candidate"]]
    rows = [row(g["orig_label"], orig,
                f"{statistics.mean(s['facts']['subagents'] for s in orig):g}",
                ", ".join(sorted({k for s in orig for k in s["facts"]["skills_used"]})) or "—", avg=True)]
    for s in supp["scores"]:
        t = supp["trials"][s["trial"]]
        rows.append(row(f"{g['retry']} #{s['run']}", [s], _subagents(t), ", ".join(s["facts"]["skills_used"]) or "—"))
    ss = supp["scores"]
    rows.append(row(f"{g['retry']}の平均（{len(ss)} 回）", ss,
                    f"{statistics.mean(s['facts']['subagents'] for s in ss):g}",
                    ", ".join(sorted({k for s in ss for k in s["facts"]["skills_used"]})) or "—", avg=True))
    return rows


def html_section(w, original, dir_):
    return "".join(_html_group(w, original, dir_, k, g) for k, g in GROUPS.items())


def _html_group(w, original, dir_, key, g):
    supp = load(dir_, key)
    if not supp:
        return ""
    parts = PARTS[w]
    n = supp["notes"]
    head = "".join(f"<th>{e(h)} / {m}</th>" for _, h, m in parts)
    body = []
    for r in _rows(w, original, supp, g):
        cells = "".join(f'<td class="num">{r[k]}</td>' for k, _, _ in parts)
        tag = "strong" if r["avg"] else "span"
        body.append(f"""
        <tr>
          <th scope="row"><{tag}>{e(r['label'])}</{tag}></th>
          <td class="num">{r['total']}</td>{cells}
          <td class="num">${r['usd']:.2f}</td>
          <td class="num">{r['minutes']:.1f}</td>
          <td>{e(r['subagents'])}</td>
          <td>{e(r['skills'])}</td>
        </tr>""")
    trials = "".join(
        f"<li><strong>{e(g['retry'])} #{s['run']}</strong>（{s['total']} 点）: {n['trials'].get(s['trial'], '')}</li>" for s in supp["scores"])
    return f"""
  <h2>{e(g['title'])}</h2>
  <div class="box">{''.join(f'<p>{x}</p>' for x in n['summary'])}</div>
  <div class="table-wrap" style="margin-top:12px">
    <table>
      <thead><tr><th>試行</th><th>点数</th>{head}<th>費用</th><th>時間（分）</th><th>サブエージェント</th><th>使われた Skill</th></tr></thead>
      <tbody>{''.join(body)}</tbody>
    </table>
  </div>
  <p><small>{n.get('table_note', '')}</small></p>
  <h3>試行ごとの様子</h3>
  <div class="box"><ul>{trials}</ul></div>
  <h3>判断の記録（補足）</h3>
  <div class="box"><ul>{''.join(f'<li>{x}</li>' for x in n['decisions'])}</ul></div>
  <h3>試行間の独立性の確認結果</h3>
  <div class="box"><p>{n['isolation']}</p></div>
"""


def md_section(w, original, dir_, md, cell):
    out = []
    for k, g in GROUPS.items():
        sec = _md_group(w, original, dir_, md, cell, k, g)
        if sec:
            out += sec
    return out


def _md_group(w, original, dir_, md, cell, key, g):
    supp = load(dir_, key)
    if not supp:
        return []
    parts = PARTS[w]
    n = supp["notes"]
    out = [f"## {g['title']}", ""] + [md(x) + "\n" for x in n["summary"]]
    out += ["| 試行 | 点数 | " + " | ".join(f"{h} / {m}" for _, h, m in parts) + " | 費用 | 時間（分） | サブエージェント | 使われた Skill |",
            "|---|---:|" + "---:|" * len(parts) + "---:|---:|---|---|"]
    for r in _rows(w, original, supp, g):
        label = f"**{r['label']}**" if r["avg"] else r["label"]
        out.append(f"| {label} | {r['total']} | " + " | ".join(str(r[k]) for k, _, _ in parts)
                   + f" | ${r['usd']:.2f} | {r['minutes']:.1f} | {cell(r['subagents'])} | {cell(r['skills'])} |")
    if n.get("table_note"):
        out += ["", md(n["table_note"])]
    out += ["", "### 試行ごとの様子", ""]
    out += [f"- **{g['retry']} #{s['run']}**（{s['total']} 点）: {md(n['trials'].get(s['trial'], ''))}" for s in supp["scores"]]
    out += ["", "### 判断の記録（補足）", ""] + [f"- {md(x)}" for x in n["decisions"]]
    out += ["", "### 試行間の独立性の確認結果", "", md(n["isolation"]), ""]
    return out
