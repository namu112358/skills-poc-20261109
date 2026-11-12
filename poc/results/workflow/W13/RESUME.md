# W13 再開メモ

最終更新: 2026-11-10

## 状態

- 試行 10 本・最終版での採点・補正前の採点・ブラインドレビュー・report.md / report.html・PLAN.md §4.4・§5.1・§6 への追加まで終わった。
- 作業用コピーは `grade.py W13 <ID> --cleanup-only` で片付けた（成果は raw/ と results/workflow/W13/ に保存済み）。
- 残り: PR を Ready にし、CI が通ったら自動マージ（SQUASH）を有効にする。

## やり直すとき

- 採点し直し: `python3 poc/scripts/grade_w13.py <試行ID>`（作業用コピーが要る。片付けた後は試行のやり直しが必要）。
- 集計とレポート: `python3 poc/scripts/score_w13.py && python3 poc/scripts/two_axis.py && python3 poc/scripts/report_w13.py`（文章は `W13/notes.json`）。
