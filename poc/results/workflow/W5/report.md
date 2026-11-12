# 開発ワークフロー PoC — W5 バグ修正

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `poc/scripts/report_w5.py` で生成）

<strong>W5（バグ修正）では、修正の正しさに差は出ませんでした。</strong>4 候補と baseline の全 9 試行が、報告された 3 件のバグをすべて根本原因から直し（隠しの E2E 8 件・隠しの単体テスト 3 件がすべて通過）、3 件それぞれに回帰テストを足し、元からある単体テスト 19 件も全部通りました。症状の場所と原因が離れたバグ（B3: 一覧に反映されない。原因は src/lib/ の一覧キャッシュ）でも、画面や Next.js のキャッシュを疑って手当てだけする試行はありませんでした。

点差は所要時間だけで付きました。最短は baseline（45 秒・$0.17、100 点）です。候補では Superpowers（平均 96.2 点、60 秒・$0.24）と gstack（96.2 点、50〜76 秒・$0.31〜0.37）が並び、Feature Dev（94.2 点、約 73 秒）、Compound Engineering（90.5 点、約 2 分・$0.60〜0.66）の順でした。

Superpowers は 2 回とも systematic-debugging Skill が発火しました。gstack の /qa はブラウザ無しの環境でも、API と単体テストで確認する形に切り替えて最後まで進みました。Compound Engineering の /ce-debug は、修正方針の確認で止まらずに直しましたが、承認の要るスクリプト（レビュー用など）は権限で動かせず、手作業の確認に置き換えています。

## 課題

利用者からの不具合報告 3 件（再現手順と期待する動作だけ。原因の場所やテストの追加は指示しない）を渡し、原因を調べて直させた。課題文は `poc/tasks/wf-W5.md`。バグは正解データのパッチ（`poc/answer-key/W5/bugs.patch`）として、試行の作業用コピーにだけ仕込んだ（main の poc-app には入れていない）。


- <strong>B1</strong> タイトルがちょうど 200 文字のタスクを登録できない（原因: 入力検証の境界値）
- <strong>B2</strong> ログインして 10 分ほどで切れる（原因: セッションの期限に秒の値をミリ秒として足している。Cookie は正しく 7 日）
- <strong>B3</strong> ステータスを変えても一覧の絞り込みに反映されない（症状は一覧画面、原因は `src/lib/tasks.ts` の一覧キャッシュが更新時に破棄されないこと。症状と原因が離れている）

## 結果の概要（平均点）

| 候補 | 回数 | 合計 / 100 | 根本原因 / 50 | 回帰テスト / 25 | 既存テスト / 10 | 所要時間 / 15 | 直せたバグ | 回帰テスト | 平均費用 | 平均時間（分） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Superpowers** | 2 | 96.2 | 50.0 | 25.0 | 10.0 | 11.2 | 6 / 6 | 6 / 6 | $0.24 | 1.0 |
| Feature Dev | 2 | 94.2 | 50.0 | 25.0 | 10.0 | 9.2 | 6 / 6 | 6 / 6 | $0.28 | 1.2 |
| Compound Engineering | 2 | 90.5 | 50.0 | 25.0 | 10.0 | 5.5 | 6 / 6 | 6 / 6 | $0.63 | 2.0 |
| **gstack** | 2 | 96.2 | 50.0 | 25.0 | 10.0 | 11.2 | 6 / 6 | 6 / 6 | $0.34 | 1.1 |
| baseline（候補なし） | 1 | 100.0 | 50.0 | 25.0 | 10.0 | 15.0 | 3 / 3 | 3 / 3 | $0.17 | 0.8 |

## バグごとの結果

根本原因から直せた試行の数 / 回帰テストを足した試行の数（候補ごとの試行数のうち）。

| 候補 | 直せた: B1 タイトル 200 文字 | 直せた: B2 ログインが切れる | 直せた: B3 一覧に反映されない | 回帰テスト: B1 | 回帰テスト: B2 | 回帰テスト: B3 |
|---|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| Feature Dev | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| Compound Engineering | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| gstack | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| baseline（候補なし） | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |

## 試行ごとの結果

B1〜B3: ✅ = 根本原因から直せた、△ 症状だけ = 報告の症状は消えたが原因の層（`src/lib/`）では直っていない、❌ = 直っていない。

| 試行 | 点数 | B1 | B2 | B3 | 回帰テスト | 元のテスト | チェック | 介入 / 質問 | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |
|---|---:|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 96.2 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 30 | $0.24 | 1.0 | 18 | 0 | 2 | superpowers:systematic-debugging |
| Superpowers #2 | 96.2 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 3 | 29 | $0.24 | 1.0 | 18 | 0 | 1 | superpowers:systematic-debugging |
| Feature Dev #1 | 94.0 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 29 | $0.27 | 1.2 | 2 | 1 | 2 | — |
| Feature Dev #2 | 94.5 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 18 | $0.28 | 1.2 | 2 | 1 | 2 | feature-dev:feature-dev |
| Compound Engineering #1 | 90.4 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 27 | $0.60 | 2.1 | 37 | 0 | 5 | compound-engineering:ce-code-review, compound-engineering:ce-commit, compound-engineering:ce-simplify-code |
| Compound Engineering #2 | 90.6 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 3 | 34 | $0.66 | 2.0 | 38 | 0 | 7 | compound-engineering:ce-code-review, compound-engineering:ce-commit |
| gstack #1 | 98.5 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 43 | $0.31 | 0.8 | 8 | 0 | 0 | — |
| gstack #2 | 93.9 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 4 | 44 | $0.37 | 1.3 | 12 | 0 | 0 | — |
| baseline（候補なし） #1 | 100.0 | ✅ | ✅ | ✅ | B1✅ B2✅ B3✅ | 19/19 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 3 | 21 | $0.17 | 0.8 | 12 | 0 | 1 | — |

## 所見

- 全試行が 3 件とも同じ場所を同じ直し方（`> 200`、`SESSION_TTL_MS`、`updateTask` でのキャッシュ破棄）で直し、コードの変更は 2 ファイル・3〜5 行に収まりました。キャッシュを無くす・画面側に `force-dynamic` を足すといった別の手当てをした試行はありません。今回の 3 件は、原因の候補が少なく、コードを読めば一本道で辿れる規模でした。
- 回帰テストは 9 試行すべてが 3 件分を足しました（`poc/app/CLAUDE.md` の規約 5 に従ったもの）。テストの行数は baseline の 21 行から gstack #2 の 44 行まで差がありますが、どれも「正解の修正では通り、バグを戻すと落ちる」条件を満たしています。gstack #1 だけは既存のファイルに足さず、新しいファイル（`tests/qa.regression-1.test.ts`）を作りました。
- Superpowers は 2 回とも `systematic-debugging` が発火し、原因を確かめてから直しました。それでも baseline より 15 秒・$0.07 ほど多くかかった程度で、費用の増え方は小さいです。
- gstack の `/qa` は、ブラウザ（Chrome for Testing）が無いため、API と単体テストで確かめる進め方に切り替えて完了しました。#1 は QA レポート（`.gstack/qa-reports/`）をコミットし、#2 は開発サーバーで 3 件の挙動を確かめたと報告しています（バグごとにコミットを分けた）。
- Compound Engineering の `/ce-debug` は、対話モードでは修正方針をユーザーに確認する手順ですが、2 回とも確認せずに直しました（質問ツールの呼び出し 0 回）。続けて `ce-code-review`・`ce-commit` を使いましたが、レビュー用のスクリプトなどは許可リストで拒否され（5〜7 件）、手作業の確認で代えています。所要時間は baseline の約 2.7 倍、費用は約 3.8 倍です。
- Feature Dev は W5 では通常の指示で、#2 だけ `feature-dev` Skill が発火しました（質問と設計案の承認の工程は、無人のため省いたと明記）。2 回ともサブエージェント 1 体に差分のレビューをさせており、その分だけ時間がかかっています。
- 介入（「お任せします」での続行）・質問はどの試行でも 0 回でした。

## 試行の詳細

### Superpowers #1 — 96.2 点

systematic-debugging が発火。原因を確かめてから 3 件を直し、回帰テストを既存のテストファイルに追加して 1 コミット。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a title of exactly 200 characters and rejects 201
- B2: tests/auth.test.ts: stays valid for 7 days
- B3: tests/tasks.test.ts: reflects updateTask in filtered lists

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/auth.test.ts` +8 −0（test）
- `tests/tasks.test.ts` +22 −0（test）

コミット:

- `22ea565 fix: タイトル200文字の検証、セッション有効期限、一覧キャッシュの更新漏れを修正`

### Superpowers #2 — 96.2 点

systematic-debugging が発火。#1 とほぼ同じ進め方・同じ差分で、時間も同じ 60 秒。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a 200-character title and rejects 201
- B2: tests/auth.test.ts: stays valid for 7 days
- B3: tests/tasks.test.ts: reflects updateTask in filtered lists

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +2 −1（code）
- `tests/auth.test.ts` +7 −0（test）
- `tests/tasks.test.ts` +22 −0（test）

コミット:

- `b58d8bb fix: タイトル200文字の上限・セッション有効期間・一覧キャッシュの不具合を修正`

### Feature Dev #1 — 94.0 点

Skill は発火せず、通常の指示のまま修正。最後にサブエージェント 1 体に差分をレビューさせ、同種の見落とし（tasks テーブルへの書き込み箇所）も確認させた。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: タイトルは 200 文字ちょうどまで許可し、201 文字は拒否する
- B2: tests/auth.test.ts: 作成から 7 日間は有効（Cookie の有効期間と一致）
- B3: tests/tasks.test.ts: updateTask のあと、一覧（絞り込み含む）に変更が反映される

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/auth.test.ts` +8 −0（test）
- `tests/tasks.test.ts` +21 −0（test）

コミット:

- `2c25775 不具合修正: タイトル長の上限・セッション有効期間・一覧キャッシュの更新漏れ`

### Feature Dev #2 — 94.5 点

feature-dev Skill が発火したが、質問と設計案の承認は無人のため省くと明記して直した。サブエージェント 1 体でレビュー。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a 200-character title and rejects 201
- B2: tests/auth.test.ts: resolves a token to its user until it expires or is deleted
- B3: tests/tasks.test.ts: reflects updates in filtered lists despite the list cache

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/auth.test.ts` +1 −0（test）
- `tests/tasks.test.ts` +17 −0（test）

コミット:

- `6853209 不具合修正: タイトル200文字の検証、セッション有効期限、タスク更新時の一覧キャッシュ破棄`

### Compound Engineering #1 — 90.4 点

/ce-debug。修正方針を確認せずに直し、ce-simplify-code・ce-code-review・ce-commit まで進んだ。レビュー用スクリプトは許可リストで拒否され、差分を手作業で確認したと報告。コミットメッセージは英語。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a title of exactly 200 characters and rejects 201 (create and partial update)
- B2: tests/auth.test.ts: resolves a token to its user until it expires or is deleted
- B3: tests/tasks.test.ts: reflects an update in cached list results, including status filters

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/auth.test.ts` +3 −0（test）
- `tests/tasks.test.ts` +24 −0（test）

コミット:

- `6cb85ee Fix 200-char titles, 10-minute logouts, and stale task list after update`

### Compound Engineering #2 — 90.6 点

/ce-debug。B1 と B3 を 1 コミット、B2 を別コミットにした。ce-code-review は #1 と同じくスクリプトが拒否され、手作業の確認に置き換え。コミットメッセージは英語。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a title of exactly 200 characters and rejects 201 (create and update)
- B2: tests/auth.test.ts: stays valid for the full 7 days (not minutes)
- B3: tests/tasks.test.ts: reflects updateTask in both the unfiltered and the status-filtered lists

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +2 −1（code）
- `tests/auth.test.ts` +8 −0（test）
- `tests/tasks.test.ts` +26 −0（test）

コミット:

- `fe61ae7 Fix 200-character titles being rejected and stale task lists after update`
- `2510335 Fix sessions expiring after about 10 minutes instead of 7 days`

### gstack #1 — 98.5 点

/qa。ブラウザ無しで、API と単体テストで確認。回帰テストを新しいファイル tests/qa.regression-1.test.ts にまとめ、QA レポートも一緒にコミットした。拒否された操作 0。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/qa.regression-1.test.ts: accepts exactly 200 chars and rejects 201 (create and partial update)
- B2: tests/qa.regression-1.test.ts: session is still valid just under 7 days and expires after
- B3: tests/qa.regression-1.test.ts: reflects status/title changes in filtered and unfiltered lists

変更ファイル:

- `.gstack/qa-reports/qa-report-poc-app-2026-11-09.md` +11 −0（doc）
- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/qa.regression-1.test.ts` +43 −0（test）

コミット:

- `9f845cd fix(qa): 3 件の不具合を修正（タイトル 200 文字・セッション期限・一覧キャッシュ）`

### gstack #2 — 93.9 点

/qa。回帰テストを先に足して 3 件とも落ちることを確かめてから直し、バグごとにコミットを分けた（2 コミット）。next dev が書き出した AGENTS.md は自分の作ったものではないとしてコミットせず、run-trial.sh が最後に拾った（介入には数えない）。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts 200 characters and rejects 201 (create and partial update)
- B2: tests/auth.test.ts: stays valid for 7 days
- B3: tests/tasks.test.ts: reflects status changes in filtered and unfiltered lists

変更ファイル:

- `AGENTS.md` +9 −0（doc）
- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +3 −2（code）
- `tests/auth.test.ts` +12 −0（test）
- `tests/tasks.test.ts` +32 −0（test）

コミット:

- `f8ec42f poc: uncommitted leftovers`
- `b29d1ea fix(qa): ISSUE-001/003 — タイトル 200 文字の許可と一覧キャッシュの破棄`
- `e94d8c0 fix(qa): ISSUE-002 — セッションの有効期限を 7 日にする`

### baseline（候補なし） #1 — 100.0 点

3 件をまとめて直し、既存の tests/tasks.test.ts と tests/auth.test.ts に回帰テストを足して 1 コミット。最短・最安。

回帰テストの根拠（正解の修正で通り、バグを戻すと落ちるテスト）:

- B1: tests/tasks.test.ts: accepts a 200-character title and rejects 201
- B2: tests/auth.test.ts: resolves a token to its user until it expires or is deleted
- B3: tests/tasks.test.ts: reflects updates in filtered lists

変更ファイル:

- `src/lib/auth.ts` +1 −1（code）
- `src/lib/tasks.ts` +2 −1（code）
- `tests/auth.test.ts` +1 −0（test）
- `tests/tasks.test.ts` +20 −0（test）

コミット:

- `d769ca5 不具合修正: タイトル200文字の検証・セッション有効期限・一覧キャッシュの破棄`

## 採点方法

配点は PLAN.md §5.1 の W5、手順は試行前に固定した `poc/answer-key/W5/grading.md` のとおり（`poc/scripts/grade_w5.py` → `score_w5.py`）。


- <strong>根本原因を正しく直せた数（50）</strong>: バグ 1 件ごとに 50/3 点。隠しの E2E（報告の症状が消えたか）と、`src/lib/` の関数を直接呼ぶ隠しの単体テスト（原因の層で直ったか）の両方が通ったら「直せた」。
- <strong>回帰テストの追加（25）</strong>: バグ 1 件ごとに 25/3 点。候補が足したテストを、参照用のコード（仕込みバグ + 正解の修正）と、そこからバグを 1 つだけ戻したコードで実行し、前者で通り後者で落ちるテストがあれば「ある」。
- <strong>既存テストの維持（10）</strong>: 元からある単体テスト 19 件（候補が書き換えていても元の版）を試行のコードで実行した合格率 × 10。
- <strong>所要時間（15）</strong>: 15 ×（W5 の全試行の最短の時間 / 自分の時間）。壁時計の時間（`elapsed-seconds`）。

## この結果の制約

- バグ 3 件は、どれも原因が 1〜2 行で、コードを読めば一本道で辿れる規模でした。全試行が満点を取ったため、根本原因・回帰テスト・既存テストの 85 点分では差が付かず、点差は所要時間（15 点）だけから来ています。より深い調査が要るバグ（複数の原因が重なる、再現条件が揃いにくいなど）での差は、この結果からは分かりません。
- 所要時間は 2 本並列で実行したときの壁時計の時間です。並列の相手によって数秒〜十数秒の揺れがあり得ます（Superpowers の 2 回は同じ 60 秒、gstack は 50 秒と 76 秒）。
- B2（10 分でログインが切れる）は、サーバーの時計を進められないため、隠しの E2E では Cookie の有効期限が変わっていないことだけを確かめ、セッションの期限そのものは隠しの単体テストで確かめました。
- 子セッションはサーバーのバックグラウンド起動などが許可リストに無く（W6 から許可する予定）、画面での確認は限られた形でしか行えていません。gstack の /qa のブラウザ機能は環境の制約で使えていません。
- 各試行は 2 回（baseline は 1 回）だけで、ばらつきの評価には足りません。

## 判断の記録

- <strong>文言の切り替えによるやり直し</strong>: 最初は旧文言（「課題文に書かれていないことはお任せします」）で baseline を 1 回、ほかの 2 試行を途中まで実行した。コーディネーターから W4 以降は新文言（工程を省かずに進める）にすると連絡があったため、それらを止めて破棄し、main（#21）を取り込んでから 9 試行すべてを新文言でやり直した。全試行の `raw/<ID>/task-suffix` が `new` であることを確認した。旧文言の baseline の結果（55 秒・$0.17、3 件とも修正）はレポートに使っていない。
- <strong>費用の上限</strong>: 試行は W3 と同じ「W1 の候補ごとの平均費用 × 5」（baseline $0.77、Superpowers $0.85、Feature Dev $0.86、gstack $2.29、Compound Engineering $8.92）を打ち切り額にして実行した。途中でコーディネーターから、規模係数を使う上限（規模係数 × W1 平均 × 5、最大 $10）を使ってよいと連絡があった。W5 の規模係数は W5 baseline の実額 ÷ W1 baseline = $0.1675 ÷ $0.15 = 1.12 で、上限は baseline $0.84、Superpowers $0.95、Feature Dev $0.95、gstack $2.57、Compound Engineering $9.97 になる。実行時の打ち切り額はこれより低いが、打ち切られた試行は無く（最高額は Compound Engineering #2 の $0.66）、新しい上限でやり直す必要は無かった。
- <strong>バグの決め方</strong>: 3 件とも「元からある単体テストでは見つからない」「再現手順だけで症状を確かめられる」ものにした。B3 は、最初に作った案（一覧キャッシュをモジュールの変数に持つ）だと、Next.js が画面と API Route で別々にモジュールを読み込むため、正しく直しても画面だけ古いままになることが試行前の確認で分かった。原因が 2 つ重なる状態は採点がぶれるので、キャッシュを DB の接続と同じく `globalThis` に持たせ、原因を 1 つにした。課題文の「新しく登録したときはすぐ出てくる」もこの形で正しいことを確かめた。
- <strong>課題文で指示しないこと</strong>: 利用者からの報告という形にしたので、原因の場所と、テストを足すことは課題文で指示していない。テストについては、全候補が読む `poc/app/CLAUDE.md` の規約 5（ロジックを変えたらテストを足す）に任せた。
- <strong>「直せた」の判定</strong>: 症状が消えただけ（画面や API Route の側だけの手当て）では根本原因を直したとは言えないので、E2E と `src/lib/` の隠しの単体テストの両方を条件にした。今回は「症状だけ」に当たる試行は無かった。
- <strong>回帰テストの判定</strong>: 候補のテストを候補自身のコードでなく参照用のコードで動かすのは、候補が直した後のコードにバグを戻すパッチは当てられない（同じ行を書き換えている）ため。候補が新しく作った関数を import していて参照用のコードで動かない場合は採点者が読んで判断する手順にしていたが、今回は該当なし（`ref_failures` は全試行で 0）。
- <strong>質問ツール</strong>: W1・W2 と同じく外していない（W3 だけの措置）。今回はどの試行も呼んでいない。
- <strong>試行の並列度と順番</strong>: 2 本並列（W4 の担当と並行するため 1〜2 本に抑えた）。1 本目のレーンが baseline → Superpowers #1 → gstack #1 → Compound Engineering #2 → Feature Dev #2、2 本目のレーンが Feature Dev #1 → Compound Engineering #1 → gstack #2 → Superpowers #2。
- <strong>子セッションの許可リスト</strong>: W5 では変えていない（比較の条件を揃えるため。サーバー起動の許可は W6 から）。
- <strong>W1〜W4 との後方互換</strong>: `run-trial.sh` の変更は、仕込みバグのパッチを当てる処理・W5 の手順・W5 の介入の文言のすべてが `W5` のときだけ働く（パッチは `POC_INJECT_PATCH` で明示したときだけほかの W でも当てられる）。課題文の末尾の定型文の箇所には触れていない。W1〜W4 を同じ手順で再実行したときの動きは変わらない。

## 試行間の独立性の確認結果

`grade.py` の検出（自分の作業用コピーの外への参照）は全 9 試行で 0 件、正解データ（`answer-key`）を読んだ形跡も 0 件でした（検出であり、完全な防止ではありません）。

## 次の対応

- W6（UI 実装からブラウザ検証・PR 作成まで）では、子セッションにサーバーの起動を許可し、画面での確認ができる条件にする（予定どおり）。
- バグ修正の差を見たいなら、原因が複数重なるバグや、調べる範囲が広いバグを使った追加の試行を検討する（今回の規模では候補なしでも十分にこなせた）。
- Compound Engineering の承認が要るスクリプト（ce-debug・ce-code-review の補助スクリプト）が無人では動かない点は、W8（人の介入なしでの自律実行）でも同じか記録する。

## 2 本立ての点数（品質・効率）

- 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.4 倍・時間 1.3 倍）、Feature Dev（費用 1.7 倍・時間 1.6 倍）、baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは gstack 95.0、Compound Engineering 74.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: Superpowers・Feature Dev・Compound Engineering・gstack・baseline（候補なし））。

### 候補ごとの平均

| 候補 | 回数 | 品質 / 100 | 2 回の差 | 効率 / 100 | 総合点（従来） | 費用（baseline 比） | 時間（baseline 比） | 介入 | 質問（参考） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 100.0（最高） | 0.0 | 100.0 | 96.2 | $0.24（1.4 倍） | 1.0 分（1.3 倍） | 0 回 | 0 回 |
| Feature Dev | 2 | 100.0（最高） | 0.0 | 100.0 | 94.2 | $0.28（1.7 倍） | 1.2 分（1.6 倍） | 0 回 | 0 回 |
| Compound Engineering | 2 | 100.0（最高） | 0.0 | 74.0 | 90.5 | $0.63（3.8 倍） | 2.0 分（2.7 倍） | 0 回 | 0 回 |
| gstack | 2 | 100.0（最高） | 0.0 | 95.0 | 96.2 | $0.34（2.0 倍） | 1.1 分（1.4 倍） | 0 回 | 0 回 |
| baseline（候補なし） | 1 | 100.0（最高） | — | 100.0 | 100.0 | $0.17（1.0 倍） | 0.8 分（1.0 倍） | 0 回 | 0 回 |

### 試行ごとの内訳

| 試行 | 根本原因 / 50 | 回帰テスト / 25 | 既存テストの維持 / 10 | 品質 / 100 | 費用 / 50 | 時間 / 30 | 介入 / 20 | 効率 / 100 | 総合点（従来） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers #1 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 96.2 |
| Superpowers #2 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 96.2 |
| Feature Dev #1 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 94.0 |
| Feature Dev #2 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 94.5 |
| Compound Engineering #1 | 50 | 25 | 10 | 100.0 | 30.0 | 24.0 | 20 | 74.0 | 90.4 |
| Compound Engineering #2 | 50 | 25 | 10 | 100.0 | 30.0 | 24.0 | 20 | 74.0 | 90.6 |
| gstack #1 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 98.5 |
| gstack #2 | 50 | 25 | 10 | 100.0 | 40.0 | 30.0 | 20 | 90.0 | 93.9 |
| baseline（候補なし） #1 | 50 | 25 | 10 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 100.0 |

### 計算方法と判断の記録

- 品質 = （根本原因 50 + 回帰テスト 25 + 既存テストの維持 10）の得点 ÷ 85 × 100。
- 効率 = 費用 50 + 時間 30 + 介入 20。費用・時間は baseline（$0.1675・45 秒）に対する倍率で、2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。介入は 0 回 = 20、1 回 = 10、2 回以上 = 0。
- 質問の回数は効率から引かない（参考値）。品質の差が、比べる 2 候補の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする。
- 定義は poc/PLAN.md §4.4。計算は poc/scripts/two_axis.py。従来の総合点・順位はこの節では変えない。
