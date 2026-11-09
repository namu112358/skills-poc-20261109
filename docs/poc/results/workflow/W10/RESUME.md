# W10 の再開メモ

## 経緯

- 2026-11-09: 前任の担当（session_01BDZ8PkbhViyWmAsa5GtSjF）が「作業時間の記録」の課題で準備を始め、試行の前に停止した（コミット `01ea514`。下書きは `docs/poc/answer-key/W10/unused-time-entries-draft/` に残した）。
- 2026-11-09 23:00 JST ごろ: 別アカウントの担当が引き継いだ。W7b とほぼ同じ機能だったため、課題を「タスクの期限の延長申請と承認」（API だけ）に替え、課題文・受け入れテスト・隠しテスト・採点手順を作り直して試行前に固定した（`docs/poc/answer-key/W10/grading.md`）。

## 状態

- 準備: 完了（参照実装で公開 13/13・隠し 12/12、仕様どおりだけの版で隠し 2/12、変更なしで隠し 0/12）。
- 試行・採点・レポート: 完了（2026-11-09 16:30 UTC ごろ。9 試行すべて採点、ブラインドレビュー 2 名、`W10/report.md`・`report.html`、PLAN.md §6 を「完了」に更新）。残りは PR のマージだけ。

## 判断の記録（試行中）

- 上限: 規模係数 = baseline $0.7308 ÷ $0.15 = 4.87。Superpowers $4.13・Feature Dev $4.18・gstack $10（計算値 $11.1）・Compound Engineering $10（計算値 $43.5）。
- 2026-11-09 15:33 UTC、コーディネーター（session_019av74kFAPVLUpNJaLAxP2B）から「ユーザーの指示で、これ以降の試行は費用の上限なしで行う」との連絡があった（正本は `claude/intelligent-mendel-hyx7aa` の RESUME.md）。この担当が直接受けた指示は「最大 $10、超える上限が要るなら止めて PR に書く」なので、残りの試行も上の上限のまま続ける。watch 方式では上限が子セッションに見えないため、上限に届かなければ結果は同じ。上限に届いた試行があれば、PR 本文に「ユーザーの判断が必要」と書き、上限なしでのやり直しはユーザーの確認後に行う。
- 採点済みの試行は、すべて上限内で終わった（上限で止まった試行は無い）。
- 2026-11-09、ユーザーがこの担当に直接「上限なしで進めてよい」と指示した。Feature Dev #2・Superpowers #2 は `POC_MAX_TRIAL_USD` を渡さずに行う（歯止めは 1 ステップ 40 分のタイムアウトだけ）。実行中だった gstack #2 は上限 $10 のまま続け、上限で止まった場合は上限なしでやり直す。上限内で終わった試行（baseline・4 候補の #1・Compound Engineering #2）はやり直さない。

## 再開するとき

1. `bash scripts/poc/fetch-plugins.sh` と `npm --prefix poc-app ci`（コンテナが替わったとき）。
2. 採点済みでない試行は作業用コピー（`/tmp/poc-trials/<ID>`）が残っていなければやり直す（回の番号を変えずに `run-trial.sh` を再実行すると raw が上書きされる）。
3. 試行: `POC_MAX_NUDGES=2 POC_MAX_TRIAL_USD=<上限> bash scripts/poc/run-trial.sh W10 <候補> <回>` → `python3 scripts/poc/grade_w10.py W10-<候補>-<回>`。
4. 全試行の後: `blind_w10.py prepare` → レビュー担当 2 名 → `blind_w10.py collect` → `score_w10.py` → `two_axis.py W10` → `report_w10.py`。
