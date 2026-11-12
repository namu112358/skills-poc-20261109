#!/usr/bin/env python3
"""W12 の結果から、Markdown のレポート（W12/report.md）と、同じ内容の HTML（W12/report.html）を作る。

データ: W12/scores.json（score_w12.py）、W12/<試行ID>.json（grade_w12.py）、W12/blind/scores.json（blind_w12.py）、
W12/adapters/<試行ID>.json（採点者の補正）、W12/notes.json（採点者の所見・判断の記録。Markdown の文字列のリスト）。
HTML は Markdown を変換して作る（report_w10.py と同じ変換）。
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import two_axis  # noqa: E402
from report_w10 import CSS, to_html  # noqa: E402
from score_w12 import HIDDEN_LABELS, M_LABELS, ROBUST_LABELS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "poc" / "results" / "workflow" / "W12"
LABEL = two_axis.LABEL
ORDER = two_axis.ORDER
PARTS = [("business", "業務", 30), ("migration", "マイグレーション", 20), ("robustness", "外部呼び出し", 15),
         ("ops", "運用", 10), ("design", "設計", 15), ("test_strength", "テスト", 10)]


BASES = ["superpowers", "feature-dev", "compound-engineering", "gstack", "baseline"]
GROUPS = [("", "標準なし（Sonnet・きれいな初期状態）"), ("+std", "汎用の開発標準あり"), ("@haiku", "Haiku（標準なし）"),
          ("+messy", "乱れた初期状態（標準なし）")]
BL = {"superpowers": "Superpowers", "feature-dev": "Feature Dev", "compound-engineering": "Compound Engineering",
      "gstack": "gstack", "baseline": "baseline"}


def group_tables(by, mean):
    """条件のまとまり（標準の有無・モデル・初期状態）ごとの比較表。"""
    L = ["## 条件のまとまりごとの比較（品質の平均）", ""]
    L += ["| 候補 | " + " | ".join(g for _, g in GROUPS) + " |", "|---|" + "---|" * len(GROUPS)]
    for b in BASES:
        L.append(f"| {BL[b]} | " + " | ".join(str(mean(b + suf, "total")) if b + suf in by else "—" for suf, _ in GROUPS) + " |")
    L += ["", "### プラグインの上乗せ（各候補 − 同じまとまりの baseline、品質の平均の差）", ""]
    L += ["| 候補 | " + " | ".join(g for _, g in GROUPS) + " |", "|---|" + "---|" * len(GROUPS)]
    for b in BASES[:-1]:
        row = []
        for suf, _ in GROUPS:
            if b + suf in by and "baseline" + suf in by:
                row.append(f"{mean(b + suf, 'total') - mean('baseline' + suf, 'total'):+.1f}")
            else:
                row.append("—")
        L.append(f"| {BL[b]} | " + " | ".join(row) + " |")
    L += ["", "### 汎用の開発標準の効果（標準あり − 標準なし、内訳ごと）", ""]
    L += ["| 候補 | 品質 | " + " | ".join(lab for _, lab, _ in PARTS) + " |", "|---|---|" + "---|" * len(PARTS)]
    for b in BASES:
        if b in by and b + "+std" in by:
            L.append(f"| {BL[b]} | {mean(b + '+std', 'total') - mean(b, 'total'):+.1f} | "
                     + " | ".join(f"{mean(b + '+std', k) - mean(b, k):+.1f}" for k, _, _ in PARTS) + " |")
    L += ["", "### 乱れた初期状態の影響（乱れ − きれい、内訳ごと）", ""]
    L += ["| 候補 | 品質 | " + " | ".join(lab for _, lab, _ in PARTS) + " |", "|---|---|" + "---|" * len(PARTS)]
    for b in BASES:
        if b in by and b + "+messy" in by:
            L.append(f"| {BL[b]} | {mean(b + '+messy', 'total') - mean(b, 'total'):+.1f} | "
                     + " | ".join(f"{mean(b + '+messy', k) - mean(b, k):+.1f}" for k, _, _ in PARTS) + " |")
    L.append("")
    return L


def messy_breakdown(by):
    """乱れた初期状態で落ちた点を、乱れの種類に分ける（採点項目との対応は notes の説明）。"""
    rows = []
    for b in BASES:
        for suf in ("", "+messy"):
            c = b + suf
            if c not in by:
                continue
            ss = by[c]
            n = len(ss)
            log_ok = sum(1 for s in ss if s["ops_facts"].get("logger_used") and not s["ops_facts"].get("console_lines")) 
            old_log = sum(1 for s in ss if any("log(" in l for l in s["facts"]["static"].get("console_lines") or []) or s["ops_detail"].get("O1_logger", 0) == 0)
            jst = sum(1 for s in ss if s["hidden_items"]["H05"])
            tests = statistics.mean(s["test_strength"] for s in ss)
            design = statistics.mean((s.get("review_detail") or {}).get("items", {}).get("a", [0, 0])[0] + (s.get("review_detail") or {}).get("items", {}).get("a", [0, 0])[1] for s in ss) / 2
            reuse = statistics.mean(sum((s.get("review_detail") or {}).get("items", {}).get("b", [0, 0])) for s in ss) / 2
            rows.append(f"| {LABEL.get(c, c)} | {log_ok} / {n} | {old_log} / {n} | {jst} / {n} | {fmt(design)} / {fmt(reuse)} | {fmt(tests)} |")
    if not rows:
        return []
    return ["## 乱れた初期状態で落ちた点の内訳（乱れの種類ごと）", "",
            "| 条件 | 既存の logger を使った（ログの見本） | logger を使わなかった | 日本時間で判断（H05、日付の関数） | 層の分け方 / 既存の抽象の再利用（ブラインド a / b、3 点満点の 2 名平均）（業務の判断の置き場所） | テストの強さ（テストの少なさ） |",
            "|---|---|---|---|---|---|"] + rows + [""]


def models_table(scores):
    rows = []
    for s in sorted(scores, key=lambda s: s["trial"]):
        mu = s.get("models_used") or {}
        if len(mu) > 1 or s.get("model", "").find("haiku") >= 0:
            rows.append(f"| {s['trial']} | {s.get('model')} | " + "、".join(f"{m} ${c:.2f}" for m, c in sorted(mu.items(), key=lambda x: -x[1])) + " |")
    return ["## 実際に使われたモデルと費用（試行する側のモデル以外も使われた試行、Haiku の試行）", "",
            "| 試行 | 試行のモデル | 実際に使われたモデルと費用 |", "|---|---|---|"] + rows + [""] if rows else []


def sensitivity(by, mean):
    L = ["## 測り方の版による違い（堅牢さのテストの旧版 v1 との比較）", ""]
    L += ["| 条件 | 品質（最終版） | 品質（旧版 v1 で計算） | 堅牢さ（最終版） | 堅牢さ（v1） |", "|---|---|---|---|---|"]
    order = []
    for c in by:
        ss = by[c]
        if any(s.get("total_v1") is None for s in ss):
            continue
        t1 = round(statistics.mean(s["total_v1"] for s in ss), 1)
        r1 = round(statistics.mean(s["robustness_v1"] for s in ss), 1)
        order.append((c, mean(c, "total"), t1))
        L.append(f"| {LABEL.get(c, c)} | {mean(c, 'total')} | {t1} | {mean(c, 'robustness')} | {r1} |")
    rank = lambda i: [c for c, *_ in sorted(order, key=lambda x: -x[i])]
    L += ["", f"順位（最終版）: {' > '.join(LABEL.get(c, c) for c in rank(1))}", "",
          f"順位（v1）: {' > '.join(LABEL.get(c, c) for c in rank(2))}", ""]
    return L


def audit_section():
    p = DIR / "audit.json"
    if not p.exists():
        return []
    a = json.loads(p.read_text())
    keys = ["repo", "other_trial", "answerer_home", "proc", "web", "tmp_other", "home_other"]
    L = ["## 試行間の独立性・不正の点検", "",
         "| 試行 | 条件 | ツール呼び出し（うちサブエージェント） | リポジトリ | 他の試行 | 依頼者役の作業場所 | /proc | Web | /tmp のほか | そのほか | answer_key_access | isolation_suspects | 依頼者役が聞かれていない項目を明かした質問 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, r in sorted(a.items()):
        lk = r["leaks"]
        p_ = r.get("persona") or {}
        L.append(f"| {t} | {LABEL.get(r['condition'], r['condition'])} | {lk['tool_calls']}（{lk['subagent_tool_calls']}） | "
                 + " | ".join(str(lk.get(k, 0)) for k in keys) + f" | {r['answer_key_access']} | {r['isolation_suspects']} | "
                 f"{p_.get('items_with_unasked', '—')} / {p_.get('items', '—')}（{'、'.join(p_.get('unasked_ids') or []) or 'なし'}） |")
    L.append("")
    return L


def fmt(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


def build_md():
    notes = json.loads((DIR / "notes.json").read_text())
    scores = json.loads((DIR / "scores.json").read_text())["scores"]
    by = {}
    for s in scores:
        by.setdefault(s["candidate"], []).append(s)
    cands = [c for c in ORDER if c in by]

    def mean(c, k):
        return round(statistics.mean(s[k] for s in by[c]), 1)

    def mfact(c, k):
        return statistics.mean(s["facts"][k] for s in by[c])

    def mq(c, k):
        xs = [s["questions"][k] for s in by[c] if s["questions"][k] is not None]
        return statistics.mean(xs) if xs else None

    L = ["# W12 短い要件から、運用まで考えて作る — 結果レポート", ""]
    L += [f"- {x}" for x in notes["summary"]] + [""]

    L += ["## 品質の内訳（6 観点、候補ごとの平均）", ""]
    L += ["| 候補 | 回数 | 品質 / 100 | " + " | ".join(f"{lab} / {mx}" for _, lab, mx in PARTS) + " |",
          "|---|---|---|" + "---|" * len(PARTS)]
    for c in cands:
        L.append(f"| {LABEL[c]} | {len(by[c])} | {mean(c, 'total')} | " + " | ".join(str(mean(c, k)) for k, _, _ in PARTS) + " |")
    L += ["", "業務 = 公開（課題文の範囲）8 + 隠れ要件 22。設計はブラインドレビュー（2 名）。詳細は [grading.md](../../../answer-key/W12/grading.md)。", ""]

    L += ["## 質問の指標（品質・効率には入れない）", ""]
    L += ["| 候補 | 質問の数（平均） | ask-po / メッセージ | 的中率 | 引き出した隠れ要件（Q、13 中） | 運用の事情（O、6 中） | 聞き直し | 実装前の割合 | 依頼者役の費用 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        qs = [s["questions"] for s in by[c]]
        L.append(f"| {LABEL[c]} | {fmt(statistics.mean(q['total'] for q in qs))} | "
                 f"{fmt(statistics.mean(q['by_route']['ask-po'] for q in qs))} / {fmt(statistics.mean(q['by_route']['message'] for q in qs))} | "
                 f"{fmt(mq(c, 'hit_rate'), 2)} | {fmt(statistics.mean(len(q['q_ids']) for q in qs))} | "
                 f"{fmt(statistics.mean(len(q['o_ids']) for q in qs))} | {fmt(statistics.mean(q['reask'] for q in qs))} | "
                 f"{fmt(mq(c, 'before_impl_rate'), 2)} | ${statistics.mean(q['persona_cost_usd'] for q in qs):.2f} |")
    L += ["", "的中率 = 回答に業務の決まり（Q）か運用の事情（O）を使った質問の割合。聞き直し = 文書に既に書いてあること（D）を聞いた数。"
          "実装前 = 質問した時点で `src/`・`tests/` に変更が無かった割合。", ""]

    L += ["## 費用・時間（実額。候補ごとの平均）", ""]
    L += ["| 候補 | 費用 | 時間 | 介入 | 品質 1 点あたりの費用 |", "|---|---|---|---|---|"]
    for c in cands:
        cost = mfact(c, "cost_usd")
        L.append(f"| {LABEL[c]} | ${cost:.2f} | {mfact(c, 'elapsed_seconds') / 60:.1f} 分 | "
                 f"{sum(s['facts']['interventions'] for s in by[c])} | ${cost / max(mean(c, 'total'), 1):.3f} |")
    L += ["", "依頼者役の費用は含めない（上の表）。効率の点数（下の「2 本立ての点数」）は baseline 2 回の平均を基準にした補助の値。", ""]

    L += ["## 隠れ要件の項目ごとの結果（通過した試行の数）", ""]
    ids = list(HIDDEN_LABELS)
    L += ["| 候補 | " + " | ".join(f"{i} {HIDDEN_LABELS[i]}" for i in ids) + " |", "|---|" + "---|" * len(ids)]
    for c in cands:
        L.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by[c] if s['hidden_items'][i])} / {len(by[c])}" for i in ids) + " |")
    L += ["", "## 外部呼び出しの堅牢さの項目ごとの結果", ""]
    ids = list(ROBUST_LABELS)
    L += ["| 候補 | " + " | ".join(f"{i} {ROBUST_LABELS[i]}" for i in ids) + " |", "|---|" + "---|" * len(ids)]
    for c in cands:
        L.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by[c] if s['robust_items'][i])} / {len(by[c])}" for i in ids) + " |")
    L += ["", "## DB マイグレーションの項目ごとの結果と逃げ方", ""]
    ids = list(M_LABELS)
    L += ["| 候補 | " + " | ".join(f"{i} {M_LABELS[i]}" for i in ids) + " | 逃げ方 |", "|---|" + "---|" * (len(ids) + 1)]
    names = {"rewrote_existing_migration": "既存の書き換え", "lost_or_recreated_data": "データ消失", "stuffed_into_existing_column": "既存の列に詰め込み", "not_persisted": "保存されない"}
    for c in cands:
        esc = sorted({names[k] for s in by[c] for k, v in s["escape"].items() if v})
        L.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in by[c] if s['migration_items'][i])} / {len(by[c])}" for i in ids)
                 + f" | {'、'.join(esc) or 'なし'} |")
    L.append("")

    L += ["## 試行ごとの内訳", ""]
    L += ["| 試行 | 品質 | 業務（公開＋隠し） | 隠し | 移行 | 堅牢 | 運用 | 設計（2 名） | テスト（検出 / 壊した数） | 質問（Q の数） | 費用 | 時間 | 介入 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in cands:
        for s in sorted(by[c], key=lambda s: s["run"]):
            f = s["facts"]
            hid = "".join("○" if v else "×" for v in s["hidden_items"].values())
            rv = s.get("review_detail") or {}
            q = s["questions"]
            L.append(f"| {LABEL[c]} #{s['run']} | {s['total']} | {s['business_public']} + {s['business_hidden']} | {hid} | {s['migration']} | "
                     f"{s['robustness']} | {s['ops']} | {rv.get('totals', '—')} | {f['killed']} / {f['mutants']} | {q['total']}（{len(q['q_ids'])}） | "
                     f"${f['cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} 分 | {f['interventions']} |")
    L += ["", "隠しの ○× は H01〜H13 の順。", ""]

    L += ["## アダプターの補正（採点者がコードを読んで決めた箇所）", ""]
    rows = []
    for c in cands:
        for s in sorted(by[c], key=lambda s: s["run"]):
            a = s.get("adapter") or {}
            if a.get("overridden") or a.get("needs_review"):
                rows.append(f"| {s['trial']} | {', '.join(a.get('overridden', [])) or '（補正なし）'} | {'; '.join(a.get('notes', []))[:200]} |")
    if rows:
        L += ["| 試行 | 補正した項目 | 自動検出のメモ |", "|---|---|---|"] + rows
    else:
        L.append("補正した試行はない（すべて自動で検出できた）。")
    L += [""] + [f"- {x}" for x in notes.get("adapter_notes", [])] + [""]

    L += group_tables(by, mean)
    L += messy_breakdown(by)
    L += models_table(scores)
    L += sensitivity(by, mean)
    L += audit_section() + [f"- {x}" for x in notes.get("audit_notes", [])] + [""]
    L += two_axis.md_section("W12")
    L += ["## 所見", ""] + [f"- {x}" for x in notes["findings"]] + [""]
    if notes.get("review_notes"):
        L += ["## ブラインドレビュー", ""] + [f"- {x}" for x in notes["review_notes"]] + [""]
    L += ["## 制約", ""] + [f"- {x}" for x in notes["limits"]] + [""]
    L += ["## 試行の条件", ""] + [f"- {x}" for x in notes["conditions"]] + [""]
    L += ["## 判断の記録", ""] + [f"- {x}" for x in notes["decisions"]] + [""]
    L += ["## データの場所", ""] + [f"- {x}" for x in notes["data"]] + [""]
    return L


def main():
    L = build_md()
    (DIR / "report.md").write_text("\n".join(L).rstrip() + "\n")
    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>W12 結果レポート</title><style>{CSS}</style></head>
<body><main>
{to_html(L)}
</main></body></html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.md'} and report.html")


if __name__ == "__main__":
    main()
