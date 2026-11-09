# 開発ワークフロー PoC — 全体の再開メモ（コーディネーター）

2026-11-09 06:00 ごろ、usage の上限が近いため、ユーザーの指示で全体を止めた。13:04 にユーザーの指示で再開した（各担当の試行は 1 本ずつ）。

## 進捗（main の状態）

| W | 状態 | 担当セッション | ブランチ | 再開時にやること |
|---|---|---|---|---|
| W1 | 完了（#16。Feature Dev 再試行の補足 #22、2 本立て #27） | — | — | なし |
| W2 | 完了（#17。補足 #22、2 本立て #27） | — | — | なし |
| W3 | 完了（#18。2 本立て #27） | — | — | なし |
| W4 | 試行中に停止（完了: baseline-1・superpowers-1・feature-dev-1・gstack-1・CE-1（flag）・CE-2（watch）。止めた: gstack-2。残り: gstack-2・feature-dev-2・superpowers-2（watch）） | session_01BDZ8Pk6ruHYwYEabNVG5Uu | agent/poc-w4 | `W4/RESUME.md`（W4 のブランチ）を読んで残りの試行 → 採点 → report（2 本立てを主表示）→ PR |
| W5 | 完了（#23。2 本立て #27） | — | — | なし |
| W6 | 試行中に停止（9 本中 8 本採点済み。止めた: CE#2 のやり直し） | session_01BDZ8PoepMKJHnrdZUGq8jE | agent/poc-w6 | `W6/RESUME.md`（W6 のブランチ）を読んで残りの試行 → 採点 → report → PR |
| W7 | 試行中に停止（初期状態 v2。完了: baseline・SP#1・FD#1・gstack#1。止めた: CE#1・#2（W7a 途中）。未着手: gstack#2・FD#2・SP#2・対照。PR #25 は自動マージなし） | session_01BDZ8PmFB12zTZKhufY52Lb | agent/poc-w7 | `W7/RESUME.md`（W7 のブランチ）を読んで残りの試行 → 採点 → report → PR。結果を見て 5 段階への延長を秘書経由でユーザーに提案する |
| W8 | 未着手 | — | agent/poc-w8（予定） | 新しいセッションを立てる（下の「W8 の要点」） |

各担当セッションはアーカイブしていない。再開時は同じセッションに send_message で再開を指示する（セッションが使えなければ、新しいセッションを立てて各ブランチの RESUME.md から続ける）。試行の作業用コピー（`/tmp/poc-trials/<ID>`）はコンテナが入れ替わると消えるため、採点前の試行はやり直しになる可能性がある。

## 決まっている試行条件（W4 以降）

- 課題文の末尾は新文言（工程を省かない。W4 以降の既定。`POC_TASK_SUFFIX`）。
- 費用の上限: 「規模係数（その W の baseline の実額 ÷ W1 baseline $0.15）× W1 の候補平均 × 5、最大 $10/試行」（ユーザー承認済み）。$10 を超える上限が要るときだけユーザーに確認する。
- 上限の守り方: W6 以降は既定で watch（上限を子セッションに見せない。`POC_BUDGET_MODE`）。W4 は 1 回目が flag、2 回目を watch で行い比較する（ユーザー指示）。W8 も watch。
- 試行間の独立性: 作業用コピーはリポジトリの外。`grade.py` の `isolation_suspects` を確認し、各 report に 1 行書く。
- 子セッションの許可リスト: コーディネーターの判断で変更してよい（#20）。開発サーバー起動は W6 から（W6 のブランチで追加。main には W6 の PR で入る）。
- 採点: 品質と効率の 2 本立てを主表示にし、従来の総合点を並記（PLAN.md §4.4、`scripts/poc/two_axis.py`、`docs/poc/results/workflow/summary.md`）。
- 運用: rm -rf を使わない、コマンドを詰め込まずスクリプト化、`merge_pull_request` は使わず自動マージは最後の push の直後に有効化、試行の並列数は各セッション 1〜2 本。
- baseline の 2 回目と Haiku での比較はユーザー未承認なので行わない。

## W8 の要点（未着手）

PLAN.md §5.1 の W8（人の介入なしでの自律実行）。W2 と別の機能、破壊的操作の検出方法を採点手順に固定、新文言・watch・上限は上記、2 本立てで主表示。担当への指示は W6・W7 を立てたときの指示（このセッションの記録）を土台にする。

## ゴールの完了条件

W1〜W8 の結果レポート（report.html と report.md）と PLAN.md §6 の更新を含む PR がすべて main にマージされ、§6 で W1〜W8 が「完了」になったことを、`git log --oneline origin/main -10`・`ls docs/poc/results/workflow/*/report.md`・§6 の表で示す。
