#!/usr/bin/env python3
"""W14・W15・W19 の結果から、scores.json（two_axis.py が読む形）と、Markdown のレポート（<W>/report.md）・同じ内容の HTML（report.html）を作る。

使い方: python3 poc/scripts/report_w14.py W14   （W15・W19 も同じ）

データ: <W>/<試行ID>.json（grade_w14.py・grade_w15.py）、<W>/blind/scores.json（blind_w14.py・blind_w15.py collect）、
<W>/adapters/<試行ID>.json（採点者の補正）、<W>/notes.json（採点者の所見・判断の記録。Markdown の文字列のリスト）、
raw/<試行ID>/po-questions.jsonl（依頼者への質問）。質問の指標は report_w12.py（origin/agent/poc-w12 b741324 の score_w12.questions）と同じ数え方。
"""
import glob
import importlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import two_axis  # noqa: E402
from report_w10 import CSS, to_html  # noqa: E402

ROOT = HERE.parents[1]
RAWDIR = ROOT / "poc" / "results" / "workflow" / "raw"
LABEL = two_axis.LABEL
ORDER = two_axis.ORDER

CONF = {
    "W14": {
        "title": "安全な DB 移行（止めずに切り替える）",
        "parts": [("business", "業務", 25), ("migration", "移行", 30), ("normalize", "表記ゆれ", 15), ("ops", "運用", 5),
                  ("design", "設計", 15), ("test_strength", "テスト", 10)],
        "q_total": 8, "o_total": 6,
        "items": [("hidden", "隠れ要件"), ("migration", "移行の安全さ")],
    },
    "W15": {
        "title": "テストの無い古いコードの改修",
        "parts": [("business", "新形式", 30), ("golden", "後退なし", 25), ("characterization", "特性テスト", 20),
                  ("design", "設計", 15), ("test_strength", "テスト", 10)],
        "q_total": 9, "o_total": 3,
        "items": [("hidden", "隠れ要件"), ("golden", "黄金テスト（A 社の CSV）")],
    },
    "W19": {
        "title": "粗悪な既存実装に引っ張られない",
        "parts": [("business", "業務", 25), ("structure", "持ち方", 25), ("migration", "移行", 20), ("scope", "範囲", 5),
                  ("design", "設計", 15), ("test_strength", "テスト", 10)],
        "q_total": 7, "o_total": 3,
        "items": [("hidden", "隠れ要件"), ("structure", "データの持ち方・移行・範囲")],
    },
}
# W19 の Feature Dev の代理人なし（raw/<試行ID>/proxy が 0）は、別の候補として並べる
EXTRA_ORDER = ["feature-dev-noproxy"]


def candidate_of(r):
    if r["candidate"] == "feature-dev" and (RAWDIR / r["trial"] / "proxy").exists() \
            and (RAWDIR / r["trial"] / "proxy").read_text().strip() == "0":
        return "feature-dev-noproxy"
    return r["candidate"]


def decisions(trial):
    """代理人の判断（W19）。po-questions.jsonl の kind=decision の項目。"""
    p = RAWDIR / trial / "po-questions.jsonl"
    recs = [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []
    out = []
    for r in recs:
        for it in r.get("items") or []:
            if it.get("kind") == "decision":
                d = it.get("decision") or {}
                out.append({"question": it.get("question", "")[:160], "chosen": d.get("chosen", ""), "reason": d.get("reason", ""),
                            "principles": d.get("principles") or [], "assumptions": d.get("assumptions") or [],
                            "route": r["route"], "before": r["before_implementation"]})
    return out


def questions(trial):
    p = RAWDIR / trial / "po-questions.jsonl"
    recs = [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []
    items = []
    for r in recs:
        its = r.get("items") or []
        if r["route"] == "ask-po" and not its:
            its = [{"question": r["message"][:200], "kind": "other", "sheet_ids": [], "answer": r.get("reply", "")}]
        if r["route"] == "message" and not r.get("has_questions"):
            continue
        for it in its:
            items.append({**it, "route": r["route"], "before": r["before_implementation"]})
    n = len(items)
    hit = [i for i in items if any(s[:1] in "QO" for s in i["sheet_ids"])]
    ids = {s for i in items for s in i["sheet_ids"]}
    return {
        "total": n,
        "by_route": {k: sum(1 for i in items if i["route"] == k) for k in ("ask-po", "message")},
        "hit_rate": round(len(hit) / n, 2) if n else None,
        "reask": sum(1 for i in items if i["kind"] == "documented" or any(s.startswith("D") for s in i["sheet_ids"])),
        "before_impl_rate": round(sum(1 for i in items if i["before"]) / n, 2) if n else None,
        "q_ids": sorted((s for s in ids if s.startswith("Q")), key=lambda s: int(s[1:])),
        "o_ids": sorted((s for s in ids if s.startswith("O")), key=lambda s: int(s[1:])),
        "persona_cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 4),
    }


def build_scores(w):
    d = ROOT / "poc" / "results" / "workflow" / w
    conf = CONF[w]
    sc = importlib.import_module(f"score_{w.lower()}")
    blind = json.loads((d / "blind" / "scores.json").read_text())["by_trial"] if (d / "blind" / "scores.json").exists() else {}
    out = []
    for f in sorted(glob.glob(str(d / f"{w}-*.json"))):
        r = json.loads(Path(f).read_text())
        trial = r["trial"]
        g = r[w.lower()]
        b = blind.get(trial)
        parts = sc.score(g, 15 * b["mean"] / 18 if b else None)
        q = questions(trial)
        mu = g.get("mutation") or {}
        s = {"trial": trial, "candidate": candidate_of(r), "run": int(r["run"]), "total": parts["quality"],
             **{k: parts[k] for k, _, _ in conf["parts"]},
             "two_axis_quality": {lab: [parts[k] or 0, mx] for k, lab, mx in conf["parts"]},
             "review_detail": b,
             "public": {x["id"]: x["pass"] for x in g.get("public", [])},
             "hidden_items": {x["id"]: x["pass"] for x in g.get("hidden", [])},
             "hidden_names": {x["id"]: x["name"] for x in g.get("hidden", [])},
             "adapter": json.loads((d / "adapters" / f"{trial}.json").read_text()) if (d / "adapters" / f"{trial}.json").exists() else None,
             "questions": q,
             "facts": {"cost_usd": r["transcript"]["cost_usd"], "elapsed_seconds": r["elapsed_seconds"],
                       "interventions": int(r.get("interventions") or 0), "questions": q["total"],
                       "turns": r["transcript"].get("turns"), "permission_denials": len(r["transcript"].get("permission_denials") or []),
                       "killed": mu.get("killed"), "mutants": mu.get("mutants")}}
        if w == "W14":
            s["migration_items"] = g["migration"]["checks"]
            n = g.get("normalize", {})
            s["normalize_facts"] = {k: n.get(k) for k in ("export_accuracy", "hidden_accuracy", "wrong_links", "unresolved_kept_ratio", "master_rows")}
            s["ops_items"] = {k: g["ops"].get(k) for k in ("O1", "O2")}
        elif w == "W19":
            s["structure_items"] = {**g.get("structure", {}).get("checks", {}), **g.get("migration", {}).get("checks", {}),
                                    **g.get("scope", {}).get("checks", {})}
            s["migration_facts"] = {k: g.get("migration", {}).get("detail", {}).get(k)
                                    for k in ("linked_ratio", "unresolved_kept_ratio", "first_request_seconds")}
            s["decisions"] = decisions(trial)
        else:
            s["golden_items"] = {x["id"]: x["pass"] for x in g.get("golden", [])}
            s["characterization_facts"] = {k: g["characterization"].get(k) for k in ("killed", "legacy_mutants", "found_in_candidate", "order", "order_by")}
        out.append(s)
    (d / "scores.json").write_text(json.dumps({"scores": out}, ensure_ascii=False, indent=1) + "\n")
    return out


def fmt(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def build_md(w, scores):
    d = ROOT / "poc" / "results" / "workflow" / w
    conf = CONF[w]
    notes = json.loads((d / "notes.json").read_text())
    by = {}
    for s in scores:
        by.setdefault(s["candidate"], []).append(s)
    cands = sorted((c for c in ORDER + EXTRA_ORDER if c in by), key=lambda c: -statistics.mean(s["total"] for s in by[c]))

    def mean(c, k):
        return round(statistics.mean(s[k] for s in by[c]), 1)

    def mfact(c, k):
        return statistics.mean(s["facts"][k] for s in by[c])

    L = [f"# {w} {conf['title']} — 結果レポート", ""]
    L += [f"- {x}" for x in notes["summary"]] + [""]
    parts = conf["parts"]
    L += ["## 品質の内訳（候補ごとの平均。品質の高い順）", ""]
    L += ["| 候補 | 回数 | 品質 / 100 | 1 回目 / 2 回目 | " + " | ".join(f"{lab} / {mx}" for _, lab, mx in parts) + " |",
          "|---|---|---|---|" + "---|" * len(parts)]
    for c in cands:
        runs = " / ".join(str(s["total"]) for s in sorted(by[c], key=lambda s: s["run"]))
        L.append(f"| {LABEL[c]} | {len(by[c])} | {mean(c, 'total')} | {runs} | " + " | ".join(str(mean(c, k)) for k, _, _ in parts) + " |")
    L += ["", f"配点の詳細は [grading.md](../../../answer-key/{w}/grading.md)。設計はブラインドレビュー（2 名、18 点満点の平均を 15 点に換算）。"
          "テスト（ミューテーション）の点は条件どうしの比較に使い、絶対値では評価しない。", ""]

    L += ["## 費用・時間（実額。候補ごとの平均）", ""]
    L += ["| 候補 | 費用 | 時間 | 介入 | ターン | 許可で止められた操作 | 品質 1 点あたりの費用 |", "|---|---|---|---|---|---|---|"]
    for c in cands:
        cost = mfact(c, "cost_usd")
        L.append(f"| {LABEL[c]} | ${cost:.2f} | {mfact(c, 'elapsed_seconds') / 60:.1f} 分 | {sum(s['facts']['interventions'] for s in by[c])} | "
                 f"{mfact(c, 'turns'):.0f} | {mfact(c, 'permission_denials'):.0f} | ${cost / max(mean(c, 'total'), 1):.3f} |")
    L += ["", "依頼者役の費用は含めない（下の表）。効率の点数（下の「2 本立ての点数」）は baseline 2 回の平均を基準にした補助の値。", ""]

    L += ["## 質問の指標（品質・効率には入れない）", ""]
    L += [f"| 候補 | 質問の数（平均） | ask-po / メッセージ | 的中率 | 引き出した隠れ要件（Q、{conf['q_total']} 中） | 運用の事情（O、{conf['o_total']} 中） | 聞き直し | 実装前の割合 | 依頼者役の費用 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        qs = [s["questions"] for s in by[c]]
        hr = [q["hit_rate"] for q in qs if q["hit_rate"] is not None]
        br = [q["before_impl_rate"] for q in qs if q["before_impl_rate"] is not None]
        L.append(f"| {LABEL[c]} | {fmt(statistics.mean(q['total'] for q in qs))} | "
                 f"{fmt(statistics.mean(q['by_route']['ask-po'] for q in qs))} / {fmt(statistics.mean(q['by_route']['message'] for q in qs))} | "
                 f"{fmt(statistics.mean(hr) if hr else None, 2)} | {fmt(statistics.mean(len(q['q_ids']) for q in qs))} | "
                 f"{fmt(statistics.mean(len(q['o_ids']) for q in qs))} | {fmt(statistics.mean(q['reask'] for q in qs))} | "
                 f"{fmt(statistics.mean(br) if br else None, 2)} | ${statistics.mean(q['persona_cost_usd'] for q in qs):.2f} |")
    L += ["", "質問の数は、1 回の問い合わせに含まれる個別の質問を数えたもの。的中率 = 回答に業務の決まり（Q）か運用の事情（O）を使った質問の割合。"
          "聞き直し = 文書に既に書いてあること（D）を聞いた数。実装前 = 質問した時点で `src/`・`tests/` に変更が無かった割合。", ""]

    names = scores[0]["hidden_names"]
    L += ["## 隠れ要件の項目ごとの結果（通過した試行の数）", ""]
    L += ["| 項目 | " + " | ".join(LABEL[c] for c in cands) + " | 計 |", "|---|" + "---|" * (len(cands) + 1)]
    for i, nm in names.items():
        L.append(f"| {i} {nm} | " + " | ".join(f"{sum(1 for s in by[c] if s['hidden_items'].get(i))} / {len(by[c])}" for c in cands)
                 + f" | {sum(1 for s in scores if s['hidden_items'].get(i))} / {len(scores)} |")
    L.append("")
    if w == "W14":
        mw = {"M1": 4, "M2": 3, "M3": 2, "M4": 4, "M5": 4, "M6": 4, "M7": 3, "M8": 3, "M9": 3}
        ml = {"M1": "計測器が消えない", "M2": "既存のマイグレーションを書き換えない", "M3": "2 回起動しても壊れない", "M4": "古い列を残す",
              "M5": "古い列にも書く", "M6": "前の版に戻せる", "M7": "起動 30 秒以内", "M8": "移行中の書き込み 3 秒以内", "M9": "移行が終わる"}
        L += ["## 移行の安全さの項目ごとの結果（通過した試行の数）", ""]
        L += ["| 項目（重み） | " + " | ".join(LABEL[c] for c in cands) + " | 計 |", "|---|" + "---|" * (len(cands) + 1)]
        for i in mw:
            L.append(f"| {i} {ml[i]}（{mw[i]}） | " + " | ".join(f"{sum(1 for s in by[c] if s['migration_items'].get(i))} / {len(by[c])}" for c in cands)
                     + f" | {sum(1 for s in scores if s['migration_items'].get(i))} / {len(scores)} |")
        L += ["", "移行の 30 点は、データ・止めない（M1〜M3・M7〜M9、計 18）と互換性（M4〜M6、計 12）に分けて読む（grading.md の末尾）。", ""]
        L += ["### 移行の点の内訳（試行ごと）", "", "| 試行 | データ・止めない / 18 | 互換性 / 12 | 落とした項目 |", "|---|---|---|---|"]
        for c in cands:
            for s in sorted(by[c], key=lambda s: s["run"]):
                m = s["migration_items"]
                a = sum(mw[k] for k in ("M1", "M2", "M3", "M7", "M8", "M9") if m.get(k))
                b = sum(mw[k] for k in ("M4", "M5", "M6") if m.get(k))
                L.append(f"| {LABEL[c]} #{s['run']} | {a} | {b} | {'・'.join(k for k in mw if not m.get(k)) or 'なし'} |")
        L.append("")
    elif w == "W19":
        sl = {"S1": "記録の専用の表（6）", "S2": "担当者が extra の外（6）", "S3": "記録が extra に無い（5）", "S4": "新しいコードが点検の情報を extra で読み書きしない（4）",
              "S5": "索引（4）", "M1": "計測器が消えない・変わらない（3）", "M2": "既存のマイグレーションを書き換えない（2）", "M3": "2 回起動しても壊れない（2）",
              "M4": "extra.dept が変わらない（3）", "M5": "点検者を利用者に寄せる 95%（3）", "M6": "分からない値を残す（2）", "M7": "最初の応答 30 秒以内（2）",
              "M8": "前の版で動く（3）", "R1": "要らない部分を壊さない（3）", "R2": "残した課題を書き残す（2）"}
        L += ["## データの持ち方・移行・範囲の項目ごとの結果（通過した試行の数）", ""]
        L += ["| 項目（重み） | " + " | ".join(LABEL[c] for c in cands) + " | 計 |", "|---|" + "---|" * (len(cands) + 1)]
        for i, nm in sl.items():
            L.append(f"| {i} {nm} | " + " | ".join(f"{sum(1 for s in by[c] if s['structure_items'].get(i))} / {len(by[c])}" for c in cands)
                     + f" | {sum(1 for s in scores if s['structure_items'].get(i))} / {len(scores)} |")
        L += ["", "移行の点は、旧データの点検者を移していない（M5 の割合が 5 割未満）試行では M1・M4 だけを数える（grading.md）。", ""]
        L += ["### 移行の実測（試行ごと）", "", "| 試行 | 点検者を寄せた割合 | 分からない値を残した割合 | 最初の応答（秒） |", "|---|---|---|---|"]
        for c in cands:
            for s in sorted(by[c], key=lambda s: s["run"]):
                m = s["migration_facts"]
                L.append(f"| {LABEL[c]} #{s['run']} | {m['linked_ratio']} | {m['unresolved_kept_ratio']} | {m['first_request_seconds']} |")
        L.append("")
        L += ["## 代理人の判断（試行の中で、候補が人に投げた技術的な判断に代理人が答えたもの）", ""]
        L += ["| 候補 | 判断の数（平均） | 実装前の割合 | よく使った原則 |", "|---|---|---|---|"]
        for c in cands:
            ds = [s["decisions"] for s in by[c]]
            flat = [d for x in ds for d in x]
            pr = {}
            for d in flat:
                for p in d["principles"]:
                    pr[p] = pr.get(p, 0) + 1
            top = "・".join(f"{p}（{n}）" for p, n in sorted(pr.items(), key=lambda x: -x[1])[:3]) or "—"
            L.append(f"| {LABEL[c]} | {fmt(statistics.mean(len(x) for x in ds))} | "
                     f"{fmt(sum(1 for d in flat if d['before']) / len(flat) if flat else None, 2)} | {top} |")
        L += ["", "原則は poc/proxy/principles.md。代理人なし（対照）の試行では、技術的な判断にも「お任せします」と答えた。", ""]
        L += ["### 判断の一覧（試行ごと）", ""]
        for c in cands:
            for s in sorted(by[c], key=lambda s: s["run"]):
                if not s["decisions"]:
                    continue
                L += [f"#### {LABEL[c]} #{s['run']}", "", "| 問い | 決めたこと | 理由 | 原則 | 置いた前提 |", "|---|---|---|---|---|"]
                for d in s["decisions"]:
                    cell = lambda x: str(x).replace("|", "／").replace("\n", " ")  # noqa: E731
                    L.append(f"| {cell(d['question'])} | {cell(d['chosen'])} | {cell(d['reason'])} | {'・'.join(d['principles'])} | "
                             f"{cell('；'.join(d['assumptions']) or '—')} |")
                L.append("")
        if notes.get("proxy_prep"):
            L += ["### 準備の中の代理人の判断", ""] + [f"- {x}" for x in notes["proxy_prep"]] + [""]
    else:
        L += ["## 黄金テスト（A 社の CSV）の項目ごとの結果（同じ結果になった試行の数）", ""]
        gids = list(scores[0]["golden_items"])
        L += ["| ファイル | " + " | ".join(LABEL[c] for c in cands) + " | 計 |", "|---|" + "---|" * (len(cands) + 1)]
        for i in gids:
            L.append(f"| {i} | " + " | ".join(f"{sum(1 for s in by[c] if s['golden_items'].get(i))} / {len(by[c])}" for c in cands)
                     + f" | {sum(1 for s in scores if s['golden_items'].get(i))} / {len(scores)} |")
        L.append("")

    L += ["## 試行ごとの内訳", ""]
    head = " | ".join(lab for _, lab, _ in parts)
    L += [f"| 試行 | 品質 | {head} | 隠し | 設計（2 名） | テスト（検出 / 壊した数） | 質問（Q の数） | 費用 | 時間 | 介入 |",
          "|---|---|" + "---|" * len(parts) + "---|---|---|---|---|---|---|"]
    for c in cands:
        for s in sorted(by[c], key=lambda s: s["run"]):
            f = s["facts"]
            hid = "".join("○" if v else "×" for v in s["hidden_items"].values())
            rv = s.get("review_detail") or {}
            q = s["questions"]
            L.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | " + " | ".join(str(s[k]) for k, _, _ in parts)
                     + f" | {hid} | {rv.get('totals', '—')} | {f['killed']} / {f['mutants']} | {q['total']}（{len(q['q_ids'])}） | "
                     f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} 分 | {f['interventions']} |")
    L += ["", f"隠しの ○× は {', '.join(names)} の順。", ""]

    adapters = [s for s in scores if s.get("adapter")]
    L += ["## 採点の補正（採点者がコードを読んで決めた箇所）", ""]
    if adapters:
        L += ["| 試行 | 補正 | 理由 |", "|---|---|---|"]
        for s in adapters:
            a = s["adapter"]
            L.append(f"| {s['trial']} | {', '.join(f'{k}={v}' for k, v in a.items() if k != 'reason')} | {a.get('reason', '')} |")
    else:
        L.append("補正した試行はない（すべて自動で検出できた）。")
    L += [""] + [f"- {x}" for x in notes.get("adapter_notes", [])] + [""]

    L += two_axis.md_section(w)
    L += ["## 所見", ""] + [f"- {x}" for x in notes["findings"]] + [""]
    if notes.get("review_notes"):
        L += ["## ブラインドレビュー", ""] + [f"- {x}" for x in notes["review_notes"]] + [""]
    L += ["## 制約", ""] + [f"- {x}" for x in notes["limits"]] + [""]
    L += ["## 試行の条件", ""] + [f"- {x}" for x in notes["conditions"]] + [""]
    L += ["## 判断の記録", ""] + [f"- {x}" for x in notes["decisions"]] + [""]
    L += ["## データの場所", ""] + [f"- {x}" for x in notes["data"]] + [""]
    return L


def main():
    w = sys.argv[1]
    d = ROOT / "poc" / "results" / "workflow" / w
    scores = build_scores(w)
    (d / "two_axis.json").write_text(json.dumps(two_axis.compute(w), ensure_ascii=False, indent=2) + "\n")
    if not (d / "notes.json").exists():
        print("notes.json が無いので scores.json と two_axis.json だけ書いた")
        return
    L = build_md(w, scores)
    (d / "report.md").write_text("\n".join(L).rstrip() + "\n")
    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{w} 結果レポート</title><style>{CSS}</style></head>
<body><main>
{to_html(L)}
</main></body></html>
"""
    (d / "report.html").write_text(doc)
    print(f"wrote {d / 'report.md'} and report.html")


if __name__ == "__main__":
    main()
