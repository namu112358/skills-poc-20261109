# 開発ワークフロー PoC — 全体の再開メモ（コーディネーター）

2026-11-09 06:00 ごろ usage の上限で全体を止め、13:04 に再開した。15:30 UTC ごろ、新しいコーディネーターのセッション（session_01QR8ZDMUCQo5J82UtBYZdGD）が引き継ぎ、この表を更新した。

## 進捗（2026-11-09 15:30 UTC 時点）

| W | 状態 | 担当 | ブランチ | 次にやること |
|---|---|---|---|---|
| W1〜W6 | 完了（#16〜#18・#22・#23・#27・#29・#30） | — | — | なし |
| W7 | 完了（#25・#33） | session_01QR8ZDLm1va6Rw1btG8qtrc（このアカウント） | agent/poc-w7 | ユーザー承認済み: 課題を変えて 5 段階（W7c〜W7e）に延長、baseline の 2 組目と対照を追加。担当が課題文を作成中 |
| W8 | 試行中（採点済み: baseline・SP#1・FD#1（参考値）・gstack#1・CE#1（上限 $10 で途中停止）） | 別アカウントのセッション | agent/poc-w8 | 残りの試行 → 採点 → report → PR。`W8/RESUME.md` の「未解決の点」（Superpowers の上限が低い、gstack の手順に実装が無い）は判断待ち |
| W9 | 完了（#31） | — | — | なし |
| W10 | 試行中（採点済み: baseline・4 候補の #1） | 別アカウントのセッション | agent/poc-w10 | 各候補の #2 → ブラインドレビュー → 採点 → report → PR |
| W11 | 準備中（実在 OSS の解決済み課題 6 件 × 5 条件 × 1 回。ユーザー承認済み） | session_01QR8ZDNZtzSVekzVB1b1Dux（このアカウント） | claude/beautiful-davinci-yorkf8 ほか | 正解データ（F2P/P2P）の作成 → 試行 → 採点 → report → PR |

別アカウントのセッションには send_message が届かないため、W8・W10 は各ブランチの RESUME.md とコミットで進み具合を確かめる。試行の作業用コピー（`/tmp/poc-trials/<ID>`）はコンテナが入れ替わると消えるため、採点前の試行はやり直しになる可能性がある。

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
