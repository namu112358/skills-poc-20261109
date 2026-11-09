# W10 の再開メモ

## 経緯

- 2026-11-09: 前任の担当（session_01BDZ8PkbhViyWmAsa5GtSjF）が「作業時間の記録」の課題で準備を始め、試行の前に停止した（コミット `01ea514`。下書きは `docs/poc/answer-key/W10/unused-time-entries-draft/` に残した）。
- 2026-11-09 23:00 JST ごろ: 別アカウントの担当が引き継いだ。W7b とほぼ同じ機能だったため、課題を「タスクの期限の延長申請と承認」（API だけ）に替え、課題文・受け入れテスト・隠しテスト・採点手順を作り直して試行前に固定した（`docs/poc/answer-key/W10/grading.md`）。

## 状態

- 準備: 完了（参照実装で公開 13/13・隠し 12/12、仕様どおりだけの版で隠し 2/12、変更なしで隠し 0/12）。
- 試行: このメモの後に、baseline → 4 候補 × 2 回を 1 本ずつ実行する。進み具合は `docs/poc/results/workflow/raw/W10-*` と `W10/W10-*.json` で分かる（採点済みの試行は JSON がある）。

## 再開するとき

1. `bash scripts/poc/fetch-plugins.sh` と `npm --prefix poc-app ci`（コンテナが替わったとき）。
2. 採点済みでない試行は作業用コピー（`/tmp/poc-trials/<ID>`）が残っていなければやり直す（回の番号を変えずに `run-trial.sh` を再実行すると raw が上書きされる）。
3. 試行: `POC_MAX_NUDGES=2 POC_MAX_TRIAL_USD=<上限> bash scripts/poc/run-trial.sh W10 <候補> <回>` → `python3 scripts/poc/grade_w10.py W10-<候補>-<回>`。
4. 全試行の後: `blind_w10.py prepare` → レビュー担当 2 名 → `blind_w10.py collect` → `score_w10.py` → `two_axis.py W10` → `report_w10.py`。
