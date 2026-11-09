# 開発ワークフロー PoC — W1 小さな変更

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 docs/poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w1.py` で生成）

<strong>W1（小さな変更）では、実装の正しさに差は出ませんでした。</strong>4 候補と baseline の全 9 試行が、隠しの受け入れテスト 6 件をすべて通過し、型チェック・単体テスト・ビルドも成功しました。

差が出たのは費用・時間と、作るものの多さです。Superpowers（平均 98.0 点）と Feature Dev（97.5 点）は、候補なしの baseline（99.3 点）とほぼ同じ費用（約 $0.17）・時間（約 40 秒）で終わりました。

gstack（85.1 点）は実装自体は同じ内容でしたが、続く `/review` を含めて費用が約 3 倍（約 $0.46）、時間が約 1.5 倍（約 1 分）でした。`/review` は作業ブランチが無いため「レビュー対象なし」で止まりました。

Compound Engineering（70.0 点）は、計画書の作成とレビューまで進めるため、費用が約 10 倍（$1.66〜$1.91）、時間が約 5 倍（約 3.5 分）かかり、120 行超の計画書もコミットしました。小さな変更には重い進め方です。

## 課題

タスク一覧画面（/tasks）に、担当者で絞り込むフィルタ（`<select name="assignee">`、`?assignee=`）を追加する。ステータスとの同時指定、存在しない担当者は「指定なし」。課題文: `docs/poc/tasks/wf-W1.md`

## 結果の概要（平均点）

| 候補 | 回数 | 合計 / 100 | 受け入れ / 50 | 時間・費用 / 30 | 過剰さ / 20 | 平均費用 | 平均時間（分） |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Superpowers** | 2 | 98.0 | 50.0 | 28.0 | 20 | $0.17 | 0.7 |
| Feature Dev | 2 | 97.5 | 50.0 | 27.5 | 20 | $0.17 | 0.7 |
| Compound Engineering | 2 | 70.0 | 50.0 | 4.0 | 16 | $1.78 | 3.7 |
| gstack | 2 | 85.1 | 50.0 | 15.1 | 20 | $0.46 | 1.0 |
| baseline（候補なし） | 1 | 99.3 | 50.0 | 29.3 | 20 | $0.15 | 0.7 |

## 試行ごとの結果

| 試行 | 点数 | E2E | チェック | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 97.5 | 6/6 | typecheck ✅ test ✅ build ✅ | 37 | 28 | $0.17 | 0.7 | 14 | 0 | 1 | superpowers:test-driven-development |
| Superpowers #2 | 98.5 | 6/6 | typecheck ✅ test ✅ build ✅ | 36 | 28 | $0.17 | 0.7 | 14 | 0 | 2 | superpowers:test-driven-development |
| Feature Dev #1 | 97.9 | 6/6 | typecheck ✅ test ✅ build ✅ | 37 | 31 | $0.17 | 0.7 | 12 | 0 | 1 | — |
| Feature Dev #2 | 97.1 | 6/6 | typecheck ✅ test ✅ build ✅ | 37 | 27 | $0.17 | 0.7 | 12 | 0 | 1 | — |
| Compound Engineering #1 | 70.3 | 6/6 | typecheck ✅ test ✅ build ✅ | 36 | 39 | $1.66 | 3.5 | 61 | 1 | 7 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-work |
| Compound Engineering #2 | 69.8 | 6/6 | typecheck ✅ test ✅ build ✅ | 36 | 37 | $1.91 | 3.8 | 38 | 1 | 10 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-work |
| gstack #1 | 84.8 | 6/6 | typecheck ✅ test ✅ build ✅ | 29 | 25 | $0.47 | 1.0 | 14 | 0 | 1 | — |
| gstack #2 | 85.4 | 6/6 | typecheck ✅ test ✅ build ✅ | 36 | 26 | $0.45 | 1.0 | 14 | 0 | 1 | — |
| baseline（候補なし） #1 | 99.3 | 6/6 | typecheck ✅ test ✅ build ✅ | 29 | 24 | $0.15 | 0.7 | 13 | 0 | 2 | — |

## 所見

- <strong>全候補が同じ構成で実装しました。</strong>変更は `src/lib/tasks.ts`（`listAssignees` / `isAssignee` / 絞り込み条件）、`src/app/tasks/page.tsx`（選択欄）、`tests/tasks.test.ts` の 3 ファイルで、コードの追加は 29〜38 行でした。`CLAUDE.md` の規約（lib に処理を置く、型ガードで検証、テストを追加、ライブラリを足さない）も全試行で守られています。
- <strong>Superpowers</strong> は 2 回とも `test-driven-development` Skill が自動で発火し、テストを先に書いて失敗を確認してから実装しました。結果は baseline と同じでしたが、費用の増加は約 1 割にとどまりました。`brainstorming` は発火しませんでした（課題が明確なため）。
- <strong>Feature Dev</strong> は `/feature-dev:feature-dev` が動きましたが、「無人のため確認・設計案の比較・レビューのフェーズを省略」と判断し、サブエージェント（code-explorer / code-architect）を一度も使いませんでした。W1 では実質的に baseline と同じ動きで、特長は出ていません。
- <strong>Compound Engineering</strong> は `/ce-plan` の中で計画書を作り、`ce-doc-review`（サブエージェント）で計画をレビューしたうえで、そのまま実装・コミットまで進めました。そのため続く `/ce-work` は「作業なし」で終わりました。作業ブランチも自分で作ります。`/ce-code-review` は、範囲判定のスクリプトが権限で拒否されたため簡易レビューに切り替え、指摘はありませんでした。
- <strong>gstack</strong> は 50 以上の Skill が読み込まれましたが、実装の段階ではどの Skill も自動で発火せず、通常の実装と同じ内容になりました（gstack の初期設定では、自動で発火するのは `/office-hours`・`/review`・`/qa`・`/ship` だけ）。読み込まれる Skill が多い分、実装段階だけで baseline の約 2 倍の費用（約 $0.32）がかかりました。続く `/review` は、作業ブランチが無く `master` に直接コミットされていたため、スキルの規定どおり「レビュー対象なし」で停止しました（1 回目は代わりに差分を自分で読み直し）。外部送信の記録（`gstack-egress list`）は 2 回とも「no receipts」でした。
- <strong>拒否された操作</strong>は、baseline・Superpowers・Feature Dev が 1〜2 件（Bash でのファイル書き換え。Edit ツールで代替）だったのに対し、Compound Engineering は 7〜10 件でした。内訳は、プラグイン自身のスクリプトの実行と、動作確認のための開発サーバー起動です。対話で使う場合は人が承認する操作で、無人実行では不利に働きます。
- W1 は計画どおり「差の確認」用のシナリオです。候補の特長（要件の掘り下げ、既存コードの読み込み、学習の蓄積など）は W2 以降で比べます。

## 試行の詳細

### Superpowers #1 — 97.5 点

変更は 3 ファイルのみ。TDD Skill でテストを先に書いた。

変更ファイル:

- `src/app/tasks/page.tsx` +23 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +28 −1（test）

コミット:

- `9284741 タスク一覧に担当者フィルタを追加`

### Superpowers #2 — 98.5 点

変更は 3 ファイルのみ。TDD Skill でテストを先に書いた。

変更ファイル:

- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +28 −1（test）

コミット:

- `74b682f タスク一覧に担当者での絞り込みを追加`

### Feature Dev #1 — 97.9 点

変更は 3 ファイルのみ。確認・承認フェーズは無人のため省略。

変更ファイル:

- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +15 −1（code）
- `tests/tasks.test.ts` +31 −1（test）

コミット:

- `ce809d9 タスク一覧に担当者での絞り込みフィルタを追加`

### Feature Dev #2 — 97.1 点

変更は 3 ファイルのみ。フェーズ 3・4・6 は無人のため省略。

変更ファイル:

- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +15 −1（code）
- `tests/tasks.test.ts` +27 −1（test）

コミット:

- `af6e471 タスク一覧に担当者での絞り込みフィルタを追加`

### Compound Engineering #1 — 70.3 点

コードは 3 ファイルのみ。計画書（docs/plans/）を別コミットで追加。作業ブランチを作成。

変更ファイル:

- `docs/plans/2026-11-09-0139-feat-tasks-assignee-filter-plan.md` +126 −0（tool-artifact）
- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +39 −1（test）

コミット:

- `d36f010 docs: 担当者フィルタの実装計画を追加`
- `d3e6235 feat: タスク一覧に担当者での絞り込みを追加`

### Compound Engineering #2 — 69.8 点

コードは 3 ファイルのみ。計画書（docs/plans/）を同じコミットに含めた。作業ブランチを作成。

変更ファイル:

- `docs/plans/2026-11-09-0139-feat-task-assignee-filter-plan.md` +136 −0（tool-artifact）
- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +37 −1（test）

コミット:

- `e7aca4e feat(tasks): 担当者でタスク一覧を絞り込めるようにする`

### gstack #1 — 84.8 点

変更は 3 ファイルのみ。/review は master 上のためベースブランチとの差分がなく「レビュー対象なし」で停止し、自分で差分を読み直した。

変更ファイル:

- `src/app/tasks/page.tsx` +15 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +25 −1（test）

コミット:

- `e13e3cb タスク一覧に担当者での絞り込みフィルタを追加`

### gstack #2 — 85.4 点

変更は 3 ファイルのみ。/review は規定どおり「Nothing to review」で停止。

変更ファイル:

- `src/app/tasks/page.tsx` +22 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +26 −1（test）

コミット:

- `96e3a19 タスク一覧に担当者フィルタを追加`

### baseline（候補なし） #1 — 99.3 点

変更は lib・ページ・テストの 3 ファイルのみ。

変更ファイル:

- `src/app/tasks/page.tsx` +15 −3（code）
- `src/lib/tasks.ts` +14 −1（code）
- `tests/tasks.test.ts` +24 −1（test）

コミット:

- `db24069 タスク一覧に担当者での絞り込みフィルタを追加`

## 採点方法

100 点満点（計画書 §5.1 の W1）。


- <strong>受け入れ 50</strong>: 隠しの E2E 6 件 × 5 点、型チェック・単体テスト・ビルド 10 点、規約（テスト追加 5 点・ライブラリを足さない 5 点）
- <strong>時間・費用 30</strong>: 費用 15 × 最安 / 自分、時間 15 × 最速 / 自分（W1 の全試行で比較）
- <strong>過剰さ 20</strong>: コード追加 41〜80 行 −4・81 行以上 −8、テスト以外の新規ファイル 1 つ −2（最大 −4）、計画書などの文書・管理ファイルをコミット −4、依頼範囲外の変更 −4

採点スクリプト: `scripts/poc/grade.py`、`scripts/poc/score_w1.py`。受け入れテスト: `docs/poc/answer-key/W1/acceptance.cjs`。

## この結果の制約

- <strong>無人（ヘッドレス）実行です。</strong>確認の質問に答えられないため、対話を前提にしたフェーズ（Feature Dev の確認・設計比較、Superpowers の brainstorming など）は評価できていません。
- <strong>権限を絞っています。</strong>全許可での子セッション起動は安全判定で止められたため、編集と決まったコマンドだけを許可しました。プラグイン自身のスクリプトや開発サーバーの起動が拒否されることがあり、Compound Engineering に不利に働いた可能性があります。
- <strong>gstack はブラウザなしで入れています。</strong>setup 中の Chrome for Testing のダウンロード（`cdn.playwright.dev`）が環境のネットワーク制限で失敗するため `--no-browser` を付けました。W1 では使いませんが、ブラウザを使う W6 の前にこのホストの許可が必要です。
- <strong>試行はデフォルトブランチ（master）上で始めています。</strong>作業ブランチを前提にする gstack の `/review` が「レビュー対象なし」になりました（Compound Engineering は自分でブランチを作成）。W2 以降は全候補とも作業ブランチの上で始めます。
- <strong>採点は自動テストと Claude（このセッション）による差分の確認です。</strong>人のブラインドレビューは未実施です（W1 の配点には含まれません）。
- <strong>試行回数は候補ごとに 2 回、baseline は 1 回です。</strong>
- モデルは `claude-sonnet-5-5` に固定しています。この実行環境に元からあるプラグイン・Skill（`cc-plugin-*` など）も全試行で読み込まれています（条件は全試行で同じ）。GitHub MCP は認証情報がないため外しています（W1 では不要）。
- 最初の実行で、ハーネスに 3 つの不具合（プラグインの参照ファイルを読めない、Feature Dev のコマンド名の誤り、費用の二重計上）が見つかりました。修正後に全試行をやり直した結果だけを載せています。

## 次の対応

- <strong>W2（仕様が明確な機能追加）</strong>: コメント機能（DB + API + UI）を課題にします。評価用アプリに DB 層を足してから開始します。
- <strong>試行環境の見直し</strong>: 全候補とも作業ブランチの上で始める（gstack の `/review` が動くように）。W6 の前に `cdn.playwright.dev` の通信許可を相談します。
- <strong>権限設定の見直し</strong>: Compound Engineering・gstack のスクリプトが拒否されないよう、許可リストの書き方（環境変数付き・cd 付きのコマンド）を改善するか、拒否の影響を別集計にします。
