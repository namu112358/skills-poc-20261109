# 開発ワークフロー PoC — 全体の再開メモ（コーディネーター）

2026-11-09 06:00 ごろ、usage の上限が近いため、ユーザーの指示で全体を止めた。13:04 にユーザーの指示で再開した（各担当の試行は 1 本ずつ）。

## 進捗（2026-11-09 15:35 UTC 時点。コーディネーター session_019av74kFAPVLUpNJaLAxP2B が更新）

| W | 状態 | 担当セッション | ブランチ | 次にやること |
|---|---|---|---|---|
| W1〜W7、W9 | 完了（main にマージ済み。W4 #30、W6 #29、W7 #25・#33、W9 #31） | — | — | なし（W7 の 5 段階への延長はユーザーの判断待ち。`W7/report.md` の「次の対応」） |
| W8 | 試行中（採点済み: baseline-1・superpowers-1・gstack-1・CE-1（上限 $10 で途中停止）。Feature Dev #1 は `W8/reference/` に移動（理由を担当に確認中）。実行中: CE-2 → gstack-2） | session_019av74gE6n8bVet8JqQ3wCU | agent/poc-w8 | `W8/RESUME.md`（W8 のブランチ）。残りの試行 → 採点 → report → draft PR |
| W10 | 試行中（採点済み: baseline-1・superpowers-1・feature-dev-1・gstack-1・CE-1。実行中: CE-2 → gstack-2 → feature-dev-2 → superpowers-2） | session_019av74gC8xeeLG4NtmcmNsP | agent/poc-w10 | `W10/RESUME.md`（W10 のブランチ）。残りの試行 → ブラインドレビュー → 採点 → report → draft PR |
| W11 | 設計案のみ（実在する OSS の解決済み課題。`docs/poc/tasks/wf-W11-design.md`） | session_01QR8ZDNZtzSVekzVB1b1Dux | claude/beautiful-davinci-yorkf8 | PLAN.md に加えるかはユーザーの判断待ち |

PoC 以外: README のツール一覧の分類（PR #34、session_019av74iw5vC2m1g7LPjPZkz）はユーザーの回答待ち。

### コーディネーターが決めたこと（2026-11-09 15:35 UTC）

- W8 の gstack の手順は PLAN §5.1 のまま（`/autoplan` → `/ship`）。#1・#2 をそろえるため。実装に届かなかったことは結果として書く。実装を挟む補足試行は本試行の後にユーザーが判断する。
- W8・W10 の PR は draft で作り、report と PLAN.md §6 の更新がそろったら Ready にする（`docs/github-writing.md` §4、#32）。

### ユーザーの判断待ち

- W8 の Superpowers の上限（承認済みの式で $2.67）が手順に対して低く、#1 は実装の途中で止まった。式を変えるか、このまま「上限内で終わらなかった」を結果とするか。
- W7 の 5 段階への延長、W11 を計画に加えるか。

各担当セッションはアーカイブしていない。止めた後に再開するときは同じセッションに send_message で指示する（使えなければ新しいセッションを立てて各ブランチの RESUME.md から続ける）。試行の作業用コピー（`/tmp/poc-trials/<ID>`）はコンテナが入れ替わると消えるため、採点前の試行はやり直しになる。

## 決まっている試行条件（W4 以降）

- 課題文の末尾は新文言（工程を省かない。W4 以降の既定。`POC_TASK_SUFFIX`）。
- 費用の上限: 「規模係数（その W の baseline の実額 ÷ W1 baseline $0.15）× W1 の候補平均 × 5、最大 $10/試行」（ユーザー承認済み）。$10 を超える上限が要るときだけユーザーに確認する。
- 上限の守り方: W6 以降は既定で watch（上限を子セッションに見せない。`POC_BUDGET_MODE`）。W4 は 1 回目が flag、2 回目を watch で行い比較する（ユーザー指示）。W8 も watch。
- 試行間の独立性: 作業用コピーはリポジトリの外。`grade.py` の `isolation_suspects` を確認し、各 report に 1 行書く。
- 子セッションの許可リスト: コーディネーターの判断で変更してよい（#20）。開発サーバー起動は W6 から（W6 のブランチで追加。main には W6 の PR で入る）。
- 採点: 品質と効率の 2 本立てを主表示にし、従来の総合点を並記（PLAN.md §4.4、`scripts/poc/two_axis.py`、`docs/poc/results/workflow/summary.md`）。
- 運用: rm -rf を使わない、コマンドを詰め込まずスクリプト化、`merge_pull_request` は使わず自動マージは最後の push の直後に有効化、試行の並列数は各セッション 1〜2 本。
- baseline の 2 回目と Haiku での比較はユーザー未承認なので行わない。

## ゴールの完了条件

W1〜W10 の結果レポート（report.html と report.md）と PLAN.md §6 の更新を含む PR がすべて main にマージされ、§6 で W1〜W10 が「完了」になったことを、`git log --oneline origin/main -10`・`ls docs/poc/results/workflow/*/report.md`・§6 の表で示す。
