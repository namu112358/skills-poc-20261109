# W4 の再開メモ（2026-11-09 06:00 頃に中断）

> **完了（2026-11-09 再開後）**: 残りの試行・ブラインドレビュー・採点・レポートまで終えた。結果は [report.md](report.md)。以下は中断時点の記録として残す。

usage の上限が近いため、ユーザーの指示で中断した。PR はまだ作っていない（自動マージも未設定）。

## 使っている方式

- 課題文: `poc/tasks/wf-W4.md`。末尾の定型文は **新文言**（`raw/<ID>/task-suffix` が `new`）。
- 介入: `POC_MAX_NUDGES=2`。ステップの時間上限: `POC_STEP_TIMEOUT=3600`。モデルは run-trial.sh の既定（claude-sonnet-5-5）。
- 1 試行の費用の上限（ユーザー承認済み、04:39 にコーディネーター経由）: 規模係数 8.6（W4 baseline $1.29 ÷ W1 baseline $0.15）× 5 × W1 の候補平均、最大 $10。
  - Superpowers・Feature Dev: **$7.3**、gstack・Compound Engineering: **$10**
- 打ち切り額の見せ方（`POC_BUDGET_MODE`。ユーザーの決定）:
  - 1 回目（baseline と 4 候補の #1）: **flag**（`--max-budget-usd` で子セッションに見える）
  - 2 回目（4 候補の #2）: **watch**（見せない。上限額は同じ）
  - 各試行の方式は `raw/<ID>/budget-mode` に記録している（run-trial.sh は記録しないため、実行用の小さな包みスクリプトで書いた）。

実行のしかた（1 本ずつ。リポジトリのルートで）:

```bash
export POC_MAX_NUDGES=2 POC_MAX_TRIAL_USD=<上限> POC_STEP_TIMEOUT=3600 POC_BUDGET_MODE=watch
poc/scripts/run-trial.sh W4 <候補> 2
echo watch > poc/results/workflow/raw/W4-<候補>-2/budget-mode
python3 poc/scripts/grade.py W4 W4-<候補>-2
```

## 終わった試行（採点に使う）

| 試行 | 方式 | 受け入れ | 認可プローブ | 費用 | 時間 |
|---|---|---:|---:|---:|---:|
| W4-baseline-1 | flag | 26/26 | 9/9 | $1.29 | 6.0 分 |
| W4-superpowers-1 | flag | 26/26 | 9/9 | $1.78 | 7.4 分 |
| W4-feature-dev-1 | flag | 26/26 | 9/9 | $2.26 | 7.3 分 |
| W4-gstack-1 | flag | 26/26 | 9/9 | $8.36 | 21.3 分 |
| W4-compound-engineering-1 | flag | 23/26 | 9/9 | $4.30 | 14.2 分 |
| W4-compound-engineering-2 | watch | 26/26 | 9/9 | $5.69 | 12.5 分 |

- いずれも isolation_suspects 0、介入 0。予算・budget への言及（親セッションの文章）は 1 回目の 5 本で 0 件。
- Compound Engineering #1 の不合格 3 件は、管理者のチーム詳細でメンバー管理の部品が出ないもの（page.tsx が DB の行をそのままクライアント部品に渡している可能性。参照実装を作ったときに同じ問題が出た）。

## 採点に使わない試行（判断の記録に残す）

- W4-baseline-1 の旧文言版: 旧文言で開始後、定型文の変更（コーディネーター指示）で結果の前に中断。費用はトークンからの推定で約 $0.35。
- W4-compound-engineering-2 の flag 版: 26/26・9/9・$7.97・16.1 分・サブエージェント 13。2 回目を watch にする決定で採点から外した（`W4/flag-run/`、`raw/flag-run/`）。
- W4-gstack-2 の flag 版: 同じ決定で、ステップ 1 の途中で中断（result なし。`raw/flag-run/W4-gstack-2`）。
- W4-gstack-2 の watch 版: usage の上限による中断で、ステップ 1 の途中で止めた（result なし）。**やり直し対象**。

## 次にやること

1. 残りの試行（watch、1 本ずつ）: **W4-gstack-2（$10）→ W4-feature-dev-2（$7.3）→ W4-superpowers-2（$7.3）**。gstack は 20 分・$8 程度かかる。
2. 予算への言及の確認: 全試行の親セッションの文章から「予算・budget」などを抜き出し、工程を省いた発言があれば判断の記録へ（1 回目の flag と 2 回目の watch で件数を比べる）。
3. ブラインドレビュー（`poc/answer-key/W4/grading.md`）: `python3 poc/scripts/blind_w4.py <スクラッチ>` で資料を作り、コードの採点者 2 名（影響箇所 16 項目 + 認可 A・B）と設計の採点者 2 名（D1〜D4）を独立したサブエージェントで。結果は `W4/review/code-reviewer-{1,2}.json`・`design-reviewer-{1,2}.json`（形式は `poc/scripts/score_w4.py` の先頭）。
4. `python3 poc/scripts/score_w4.py` → `W4/notes.json`（W2 の形）を書く → `python3 poc/scripts/report_w4.py`。report_w4.py に `two_axis.md_section("W4")`・`html_section("W4")` を主表示として組み込み、「1 回目（flag）と 2 回目（watch）の比較」の節（候補ごとの費用・時間・ターン数・サブエージェント数・点数の差と、打ち切り額に言及した発言の件数。各候補 1 回ずつなので候補間の公平は保たれる旨）と「試行間の独立性の確認結果」の 1 行を足す。
5. `python3 poc/scripts/two_axis.py` で summary を更新。PLAN.md §6 の W4 の行を更新。
6. 採点とレビューが済んだ試行は `python3 poc/scripts/grade.py W4 <ID> --cleanup-only` で片付ける。
7. main を取り込み → PR（`.github/pull_request_template.md`・`docs/github-writing.md`）→ 最後の push の直後に条件を確かめて自動マージ。
