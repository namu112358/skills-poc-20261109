# W12 の再開メモ

使用量の上限などで止まったときに、次のセッションが続きから始めるためのメモ。節目ごとに更新する。

## 状態（2026-11-10 10:20 UTC）

| 項目 | 状態 |
|---|---|
| 設計書・正解データ・試行前の確認 | 完了（`docs/poc/tasks/wf-W12-design.md`、`docs/poc/answer-key/W12/`） |
| 標準なし 12 本（6 条件 × 2 回） | 完了・採点済み |
| 汎用の開発標準あり 10 本（回 11・12） | 完了・採点済み |
| Haiku（回 21） | 完了・採点済み。回 22 はユーザー判断で流さない |
| 乱れた初期状態（回 31） | 完了・採点済み。回 32 はユーザー判断で流さない |
| 最終版での全試行の採点し直し | 25 本のうち 14 本済み、残り 11 本を実行中（`scripts/poc/w12_regrade_all.sh`、記録は `raw/w12-regrade.log`。済んだものは `regrade-done` の行と試行ごとの行で分かる） |
| 不正の点検（`scripts/poc/audit_w12.py`） | 未（全試行の採点し直しのあと） |
| ブラインドレビュー（`scripts/poc/blind_w12.py`） | 資料作り済み（`W12/blind/mapping.json`）。レビュー担当 2 名 × 4 組（各 8 本）を実行中。結果は `W12/blind/reviewer-1.json`・`reviewer-2.json` にまとめる |
| report（`scripts/poc/report_w12.py`、`notes.json`） | 未（生成スクリプトは作成済み） |
| PLAN.md §5.1・§6 の更新、two_axis の summary | 未 |
| PR（draft → 全部そろったら Ready、自動マージ） | 未 |

## 続きのやり方

1. 走っている試行が無いことを確かめる（`pgrep -af run-trial.sh`）。途中で止まった試行は、`raw/<試行ID>/step*.jsonl` に「hit your ... limit」があれば、作業用コピーと結果を消して同じ ID でやり直す（`POC_W12_BASE=messy bash scripts/poc/run_w12_trials.sh <候補>:31`）。
2. 最終版で採点していない試行があれば `bash scripts/poc/w12_regrade_all.sh <試行ID>...`。
3. `python3 scripts/poc/score_w12.py` → `python3 scripts/poc/audit_w12.py` → `python3 scripts/poc/blind_w12.py prepare <スクラッチ>` → レビュー担当 2 名（サブエージェント）→ `blind_w12.py collect` → `score_w12.py` → `two_axis.py W12` → `report_w12.py`。
4. 判断の記録の下書きは `docs/poc/results/workflow/W12/decisions-draft.md`（report の `notes.json` の decisions に移す）。主な判断は設計書 §5〜§8 と grading.md の補正の注記にも書いてある。
