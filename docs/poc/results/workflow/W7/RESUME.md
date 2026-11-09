# W7 の再開メモ（2026-11-09 06:05 UTC に中断）

usage の上限が近いため、ユーザーの指示（秘書経由）で途中で止めた。PR #25 は未完成で、自動マージは有効にしていない。

## 状態

| 組（W7a → W7b） | 状態 | 結果（途中の scores.json） |
|---|---|---|
| baseline #1 | 完了 | 品質 100・効率 100・総合 93.2。W7a・W7b とも落とし穴 2 件を指摘の前に回避 |
| Superpowers #1 | 完了 | 品質 100・効率 100・総合 94.2。W7a・W7b とも回避 |
| Feature Dev #1 | 完了 | 品質 100・効率 80・総合 98.5。W7a で P2（独自のエラー型）を外して指摘 1 回 → W7b は指摘の前に回避（「学んだ」1 件） |
| gstack #1 | 完了 | 品質 100・効率 53・総合 87.2。W7a・W7b とも回避。W7b の方が遅く高い（$1.81 → $2.37） |
| Compound Engineering #1 | **止めた（やり直し対象）** | W7a の /ce-work の途中で停止。結果は使わない |
| Compound Engineering #2 | **止めた（やり直し対象）** | W7a の /ce-plan の途中で停止。結果は使わない |
| gstack #2・Feature Dev #2・Superpowers #2 | 未着手 | — |
| 対照（各候補 1 回。W7b を W7a を引き継がずに実行、回の番号 11） | 未着手 | — |

止めた 2 組は `docs/poc/results/workflow/raw/W7a-compound-engineering-{1,2}/` に途中の記録がある（Git 管理外）。再開時は run-trial.sh が作業用コピーと raw を作り直すので、そのまま同じ ID で実行してよい。

## 使っている方式

- 初期状態: v2（`docs/poc/answer-key/W7/base.patch`。決まりへの移行の途中。v1 のパイロット結果は `W7/pilot-v1/`）
- 課題文の末尾: 新文言（`raw/<ID>/task-suffix` = new）
- 費用の上限: `POC_BUDGET_MODE=watch`（`--max-budget-usd` は渡さない）、1 試行（W7a・W7b それぞれ）$7.67 = v2 baseline の W7a $0.3566 ÷ $0.15 × W1 候補平均 $0.6457 × 5
- 介入: `POC_MAX_NUDGES=2`、落とし穴の指摘は最大 2 回（既定）。Claude Code の自動メモリは止める（既定）
- 許可リスト: 現行（W6 の開発サーバー許可は使わない）
- 引き継ぎ: W7b は同じ候補・同じ回の W7a の作業用コピー（`/tmp/poc-trials/W7a-<候補>-<回>`）と HOME をそのまま使う。W7a は W7b の前に採点する。コンテナが作り直されると /tmp の作業用コピーは消えるので、再開時は W7a から実行し直す（完了した組は採点済みで、作業用コピーは不要）

## 次にやること

1. 試行の実行（1 組ずつ。並列は 2 本まで）: `POC_BUDGET_MODE=watch POC_MAX_TRIAL_USD=7.67 POC_MAX_NUDGES=2` で
   `scripts/poc/run-trial.sh W7a <候補> <回>` → `python3 scripts/poc/grade_w7.py W7a-<候補>-<回>` → `scripts/poc/run-trial.sh W7b <候補> <回>` → `python3 scripts/poc/grade_w7.py W7b-<候補>-<回>`
   - 残り: compound-engineering 1・2、gstack 2、feature-dev 2、superpowers 2
2. 対照（費用が許せば各候補 1 回）: `POC_W7_CONTROL=1 ... scripts/poc/run-trial.sh W7b <候補> 11` → `grade_w7.py W7b-<候補>-11`
3. `python3 scripts/poc/score_w7.py` → `python3 scripts/poc/two_axis.py W7` → `W7/notes.json`（所見・判断の記録・各候補が残したもの・独立性・「2 段階で言えること・言えないこと」「5 段階に延ばす価値」）を書いて `python3 scripts/poc/report_w7.py`
4. PLAN.md §6 の W7 の行を更新 → main を取り込み → PR #25 の本文を更新 → 条件を確かめて自動マージを有効にする
5. 作業用コピーの片付け: `python3 scripts/poc/grade.py W7a W7a-<候補>-<回> --cleanup-only`

## 判断の記録に書くこと（ここまでの分）

- v1 の初期状態（既存のコメント機能が決まりに沿っていた）では、baseline が W7a・W7b とも既存コードを真似るだけで 2 件とも回避し、学習の効果を測れなかったため、v2 に改めた。パイロットの費用は $0.37 + $0.40。
- v2 でも baseline は `api.ts`・`errors.ts`・`datetime.ts` を最初に読み、2 件とも回避した。これ以上隠すと「作業中に気づける形」を満たさなくなるため、v2 のまま実施した。
- W6 の許可リストの変更は main に入っていなかったため、W7 は現行の許可リストで統一した。
- Claude Code の自動メモリは候補の記憶の仕組みではないため、全候補で止めた。
- 秘書経由のユーザーの要望で、段階を W7c 以降に増やせる形、前の段階の知見を読んだか・同じ間違いの繰り返し・対照の記録を足した。
- コーディネーターの指示で、品質・効率の 2 本立てを主表示にした（`two_axis.py`）。
