#!/usr/bin/env python3
"""W13 の結果から、Markdown のレポート（W13/report.md）と、同じ内容の HTML（W13/report.html）を作る。

入力: W13/scores.json（score_w13.py）、W13/prefix/*.json（補正 3・4 の前の採点）、W13/notes.json（要約・所見・条件・判断の記録などの文章）。
使い方: python3 poc/scripts/report_w13.py
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIR = ROOT / "poc" / "results" / "workflow" / "W13"
sys.path.insert(0, str(HERE))
import grade_w13  # noqa: E402
import report_w10  # noqa: E402  Markdown → HTML の変換と CSS を使い回す
import two_axis  # noqa: E402

LABEL = {"superpowers": "Superpowers", "feature-dev": "Feature Dev", "gstack": "gstack",
         "compound-engineering": "Compound Engineering", "baseline": "baseline（候補なし）"}
ORDER = ["superpowers", "feature-dev", "gstack", "compound-engineering", "baseline"]
K_LABEL = {"K01": "過去の日は不可", "K02": "1 日でも重なれば不可", "K03": "取消で枠が空く", "K04": "貸出中は返却予定日の翌日から",
           "K05": "他人の予約期間の貸出はしない", "K06": "使用停止・廃棄は不可", "K07": "取消は本人と管理者", "K08": "不合格で予約を取消"}
C_LABEL = {"C01": "仮予約→確定", "C02": "承認は管理者だけ", "C03": "無効なら代表者", "C04": "却下で枠が空く", "C05": "仮予約も枠を押さえる",
           "C06": "開始日を過ぎた仮予約は期限切れ", "C07": "14 日まで", "C08": "承認は仮予約だけ", "C09": "本人は確定も取消可",
           "C10": "期限切れ・却下は貸出を止めない"}
N_LABEL = {"N1": "新しい番号で追加", "N2": "出荷済みを書き換えない", "N3": "データが残る", "N4": "本番の予約が確定のまま",
           "N5": "本番の DB で承認が動く", "N6": "再起動", "S1": "移行後の状態の値"}


def name(s):
    return f"{LABEL[s['candidate']]} #{s['run']}"


def by_cand(scores):
    out = {}
    for s in scores:
        out.setdefault(s["candidate"], []).append(s)
    return [(c, sorted(out[c], key=lambda x: x["run"])) for c in ORDER if c in out]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 1) if xs else None


def build_md():
    scores = json.loads((DIR / "scores.json").read_text())["scores"]
    notes = json.loads((DIR / "notes.json").read_text())
    L = ["# W13 途中で要件が変わる — 結果レポート", ""]
    L += [f"- {x}" for x in notes["summary"]] + [""]
    L += two_axis.md_section("W13")
    L += ["## 品質の内訳（試行ごと）", ""]
    L += ["| 試行 | 最初の版 / 15 | 変更への追従 / 25 | 変わらない要件・後退 / 15 | マイグレーション / 20 | 古い前提 / 5 | 設計 / 15 | テスト / 5 | 品質 / 100 | 後退した項目 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c, ss in by_cand(scores):
        for s in ss:
            L.append(f"| {name(s)} | {s['v1']} | {s['change']} | {s['unchanged']} | {s['migration']} | {s['stale']} | {s['design']} | "
                     f"{s['test_strength']} | **{s['total']}** | {'、'.join(s['regressions']) or 'なし'} |")
    L += ["", "## 項目ごとの結果（合格した試行の数）", "", "### 変更後の隠しテスト K（最初の依頼の隠れ要件。変更後のアプリで）", ""]

    def item_table(keys, labels, src):
        rows = ["| 候補 | " + " | ".join(f"{k} {labels[k]}" for k in keys) + " |", "|---|" + "---|" * len(keys)]
        for c, ss in by_cand(scores):
            rows.append(f"| {LABEL[c]} | " + " | ".join(f"{sum(1 for s in ss if s[src].get(k))} / {len(ss)}" for k in keys) + " |")
        return rows
    L += item_table(grade_w13.K_ITEMS, K_LABEL, "final_items") + [""]
    L += ["### 変更依頼の後の決まり C（変更後のアプリで）", ""] + item_table(grade_w13.C_ITEMS, C_LABEL, "final_items") + [""]
    L += ["### マイグレーション（本番の DB）と古い前提", ""] + item_table(list(N_LABEL), N_LABEL, "migration_items") + [""]
    L += ["## 手戻りの大きさ（変更依頼の後のステップ）", ""]
    L += ["| 試行 | 全体の費用 | うち変更のステップ | 全体の時間 | うち変更のステップ | 最初の版の行数 | 変更の行数（追加 / 削除） | 介入（v1 / v2） |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c, ss in by_cand(scores):
        for s in ss:
            rw, f = s["rework"], s["facts"]
            cl = rw.get("change_lines") or {}
            L.append(f"| {name(s)} | ${f['cost_usd']:.2f} | ${rw['change_cost_usd']:.2f} | {f['elapsed_seconds'] / 60:.1f} 分 | "
                     f"{rw['change_seconds'] / 60:.1f} 分 | {rw['v1_lines_added']} | {cl.get('added')} / {cl.get('deleted')} | "
                     f"{rw['interventions_v1']} / {rw['interventions_v2']} |")
    L += ["", "| 候補 | 平均の費用 | うち変更のステップ | 平均の時間 | うち変更のステップ |", "|---|---:|---:|---:|---:|"]
    for c, ss in by_cand(scores):
        L.append(f"| {LABEL[c]} | ${mean([s['facts']['cost_usd'] for s in ss])} | ${mean([s['rework']['change_cost_usd'] for s in ss])} | "
                 f"{mean([s['facts']['elapsed_seconds'] / 60 for s in ss])} 分 | {mean([s['rework']['change_seconds'] / 60 for s in ss])} 分 |")
    L += ["", "## 依頼者への質問（品質・効率に入れない指標）", ""]
    L += ["| 試行 | 質問 v1 / v2 | ask-po / メッセージ | 的中（Q・C） | 実装前の割合 v1 / v2 | 聞き直し | Q8（不合格で取消）を聞いた | C11（本番の予約）を聞いた | 依頼者役の費用 |",
          "|---|---:|---:|---:|---:|---:|---|---|---:|"]
    for c, ss in by_cand(scores):
        for s in ss:
            q = s["questions"]
            a, v1, v2 = q["all"], q["v1"], q["v2"]
            L.append(f"| {name(s)} | {v1['total']} / {v2['total']} | {a['by_route']['ask-po']} / {a['by_route']['message']} | {a['hit']}（{a['hit_rate']}） | "
                     f"{v1['before_impl_rate']} / {v2['before_impl_rate']} | {a['reask']} | {'はい' if 'Q8' in a['q_ids'] else 'いいえ'} | "
                     f"{'はい' if q['asked_c11'] else 'いいえ'} | ${q['persona_cost_usd']} |")
    L += [""] + [f"- {x}" for x in notes["questions"]] + [""]
    L += ["## 補正 3・4 の前と後の点数（判断の記録）", ""]
    L += [f"- {x}" for x in notes["prefix_intro"]] + [""]
    L += ["| 試行 | 補正前（設計・テストの強さを除く） | 補正後（同じ範囲） | 差 | 補正前に落ちていた項目 |", "|---|---:|---:|---:|---|"]
    pre_tot, post_tot = {}, {}
    for c, ss in by_cand(scores):
        for s in ss:
            p = DIR / "prefix" / f"{s['trial']}.json"
            if not p.exists():
                L.append(f"| {name(s)} | — | — | — | （補正前の採点なし） |")
                continue
            pr = json.loads(p.read_text())
            pre = round(pr["points_without_design_and_mutation"]["total"], 1)
            post = round(s["total"] - s["design"] - s["test_strength"], 1)
            pre_tot.setdefault(c, []).append(pre)
            post_tot.setdefault(c, []).append(post)
            w = pr["w13"]
            failed_pre = {(ph, x["id"]) for ph, k in (("v1", "v1_tests"), ("v2", "final_tests")) for x in w.get(k, []) if not x["pass"]}
            failed_pre |= {("mig", k) for k, v in w.get("migration", {}).get("checks", {}).items() if not v}
            failed_post = {(f["phase"], f["id"]) for f in s["facts"]["failed"]} | {("mig", k) for k, v in s["migration_items"].items() if not v}
            diff = sorted(failed_pre - failed_post)
            L.append(f"| {name(s)} | {pre} | {post} | {round(post - pre, 1):+} | {'、'.join(f'{a}:{b}' for a, b in diff) or 'なし'} |")
    L += ["", "| 候補 | 補正前の平均 | 補正後の平均 | 補正前の順位 | 補正後の順位 |", "|---|---:|---:|---:|---:|"]
    cands = [c for c, _ in by_cand(scores) if c in pre_tot]
    rank = lambda d: {c: i + 1 for i, c in enumerate(sorted(cands, key=lambda c: -mean(d[c])))}  # noqa: E731
    rp, ra = rank(pre_tot), rank(post_tot)
    for c in cands:
        L.append(f"| {LABEL[c]} | {mean(pre_tot[c])} | {mean(post_tot[c])} | {rp[c]} | {ra[c]} |")
    L += [""] + [f"- {x}" for x in notes["prefix_conclusion"]] + [""]
    L += ["## 所見", ""] + [f"- {x}" for x in notes["findings"]] + [""]
    L += ["## ブラインドレビュー（設計の筋）", ""] + [f"- {x}" for x in notes["review_notes"]] + [""]
    L += ["## 試行の条件", ""] + [f"- {x}" for x in notes["conditions"]] + [""]
    L += ["## 判断の記録", ""] + [f"- {x}" for x in notes["decisions"]] + [""]
    L += ["## データの場所", ""] + [f"- {x}" for x in notes["data"]] + [""]
    return L


def main():
    L = build_md()
    (DIR / "report.md").write_text("\n".join(L).rstrip() + "\n")
    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>W13 結果レポート</title><style>{report_w10.CSS}</style></head>
<body><main>
{report_w10.to_html(L)}
</main></body></html>
"""
    (DIR / "report.html").write_text(doc)
    print(f"wrote {DIR / 'report.md'} and report.html")


if __name__ == "__main__":
    main()
