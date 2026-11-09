# 開発ワークフロー PoC — W6 UI 実装からブラウザ検証・PR 作成まで

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 docs/poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w6.py` で生成）

<strong>W6（UI 実装からブラウザ検証・PR 作成まで）では、画面の出来に差は出ませんでした。</strong>4 候補と baseline の全 9 試行が、UI チェックリスト 8 項目（空状態・入力エラー・通信エラー・二重送信の防止・ステータス変更の失敗時・幅 375px など）を隠しの E2E 16 件ですべて満たし、9 試行とも実際のブラウザで画面を操作して、幅 375px での確認とスクリーンショットのコミットまで行いました。型チェック・単体テスト・ビルドも全試行で通っています。

品質（UI・証跡・PR の完成度）の差は PR の説明の書き方だけ（12 点中 10〜12 点）で、最大でも 1.8 点です。2 本立ての判定規則では Superpowers・Feature Dev・gstack が「差あり」になりますが、内容は「注意点の書き漏れ」「変更内容がファイル単位」といった説明文の軽微な差です。<strong>同じ品質での効率は、Superpowers（baseline 比 費用 1.3 倍・時間 1.0 倍、効率 100 点）が最も良く</strong>、Feature Dev（2.2 倍・1.1 倍）と Compound Engineering（2.5 倍・1.3 倍）が 95 点、gstack は #2 が $7.34・23 分かかり 71.5 点でした。baseline（$0.88・7 分）は品質も効率も満点です。

候補ごとの手順では、gstack の `/qa` が事前インストール済みの Chromium（`GSTACK_CHROMIUM_PATH`）で動き、ブラウザでの QA まで進みました。Compound Engineering の `/ce-test-browser` は「Playwright MCP は使わない」という自身の規則で 2 回ともテストを始めず、`/ce-commit-push-pr`・gstack の `/ship`・Superpowers の `finishing-a-development-branch` は、リモートが無いため push と PR 作成の手前で止まりました（PR は全候補とも課題文の指示どおり `PR.md` に書いています）。

## 課題

「マイタスク」画面（`/my-tasks`）を追加させた。自分の担当タスクを期限順に並べ、空状態の文言、タスクの追加（入力エラー・通信エラー・サーバーエラーの表示、二重送信の防止）、その場でのステータス変更（失敗したら知らせて元に戻す）、幅 375px での表示を含む。実装後にブラウザで確認し（スマートフォンの幅を含む）、証跡をリポジトリに保存して PR から参照させた。リモートが無いため、PR はタイトルと本文を `PR.md` に書いてコミットする形にした（全候補に同じ文面）。課題文は `docs/poc/tasks/wf-W6.md`。

## 2 本立ての点数（品質・効率）

- 品質: 最高は baseline（候補なし）（100.0 点）。これと差なし（差がばらつき以下）: Compound Engineering（99.7）、baseline（候補なし）（100.0）。差あり: Superpowers（98.2、−1.8）、Feature Dev（98.2、−1.8）、gstack（99.1、−0.9）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 95.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: baseline（候補なし））。

### 候補ごとの平均

| 候補 | 回数 | 品質 / 100 | 2 回の差 | 効率 / 100 | 総合点（従来） | 費用（baseline 比） | 時間（baseline 比） | 介入 | 質問（参考） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 98.2 | 1.2 | 100.0 | 95.3 | $1.17（1.3 倍） | 7.1 分（1.0 倍） | 0 回 | 0 回 |
| Feature Dev | 2 | 98.2 | 1.2 | 95.0 | 90.4 | $1.93（2.2 倍） | 7.5 分（1.1 倍） | 0 回 | 0 回 |
| Compound Engineering | 2 | 99.7（差なし） | 0.6 | 95.0 | 91.2 | $2.15（2.5 倍） | 9.1 分（1.3 倍） | 0 回 | 0 回 |
| gstack | 2 | 99.1 | 0.6 | 71.5 | 88.0 | $4.80（5.5 倍） | 17.4 分（2.6 倍） | 0 回 | 0 回 |
| baseline（候補なし） | 1 | 100.0（最高） | — | 100.0 | 100.0 | $0.88（1.0 倍） | 6.8 分（1.0 倍） | 0 回 | 0 回 |

### 試行ごとの内訳

| 試行 | UI チェックリスト / 40 | 検証の証跡 / 15 | PR の完成度 / 30 | 品質 / 100 | 費用 / 50 | 時間 / 30 | 介入 / 20 | 効率 / 100 | 総合点（従来） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers #1 | 40 | 15 | 28 | 97.6 | 50.0 | 30.0 | 20 | 100.0 | 92.3 |
| Superpowers #2 | 40 | 15 | 29 | 98.8 | 50.0 | 30.0 | 20 | 100.0 | 98.3 |
| Feature Dev #1 | 40 | 15 | 28 | 97.6 | 40.0 | 30.0 | 20 | 90.0 | 89.2 |
| Feature Dev #2 | 40 | 15 | 29 | 98.8 | 50.0 | 30.0 | 20 | 100.0 | 91.6 |
| Compound Engineering #1 | 40 | 15 | 30 | 100.0 | 40.0 | 30.0 | 20 | 90.0 | 90.0 |
| Compound Engineering #2 | 40 | 15 | 29.5 | 99.4 | 50.0 | 30.0 | 20 | 100.0 | 92.3 |
| gstack #1 | 40 | 15 | 29 | 98.8 | 40.0 | 30.0 | 20 | 90.0 | 89.8 |
| gstack #2 | 40 | 15 | 29.5 | 99.4 | 15.0 | 18.0 | 20 | 53.0 | 86.3 |
| baseline（候補なし） #1 | 40 | 15 | 30 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 100.0 |

### 計算方法と判断の記録

- 品質 = （UI チェックリスト 40 + 検証の証跡 15 + PR の完成度 30）の得点 ÷ 85 × 100。
- 効率 = 費用 50 + 時間 30 + 介入 20。費用・時間は baseline（$0.8769・409 秒）に対する倍率で、2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。介入は 0 回 = 20、1 回 = 10、2 回以上 = 0。
- 質問の回数は効率から引かない（参考値）。品質の差が、比べる 2 候補の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする。
- 定義は docs/poc/PLAN.md §4.4。計算は scripts/poc/two_axis.py。従来の総合点・順位はこの節では変えない。

## 従来の総合点（平均点）

| 候補 | 回数 | 合計 / 100 | UI チェックリスト / 40 | 証跡 / 15 | PR / 30 | 費用 / 15 | 不具合なしの項目 | 平均費用 | 平均時間（分） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Superpowers** | 2 | 95.3 | 40 | 15 | 28.5 | 11.8 | 16 / 16 | $1.17 | 7.1 |
| Feature Dev | 2 | 90.4 | 40 | 15 | 28.5 | 6.9 | 16 / 16 | $1.93 | 7.5 |
| Compound Engineering | 2 | 91.2 | 40 | 15 | 29.8 | 6.4 | 16 / 16 | $2.15 | 9.1 |
| gstack | 2 | 88.0 | 40 | 15 | 29.2 | 3.8 | 16 / 16 | $4.80 | 17.4 |
| baseline（候補なし） | 1 | 100.0 | 40 | 15 | 30.0 | 15.0 | 8 / 8 | $0.88 | 6.8 |

## UI チェックリストの項目ごとの結果

その項目に不具合が残っていなかった試行の数（候補ごとの試行数のうち）。

| 候補 | U1 表示・並び順 | U2 空状態 | U3 追加・二重送信 | U4 入力エラー | U5 通信エラー | U6 ステータス変更 | U7 レスポンシブ | U8 導線・ラベル |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| Feature Dev | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| Compound Engineering | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| gstack | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| baseline（候補なし） | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |

## 試行ごとの結果

UI チェックリスト: ✅ = 不具合なし、❌ = 不具合が残った項目。証跡: E1 ブラウザ操作 / E2 スクリーンショット / E3 スマートフォン幅（各 5 点）。PR: 説明（12）/ テスト（8）/ CI（10）。

| 試行 | 点数 | UI チェックリスト | 証跡 | PR（説明 / テスト / CI） | チェック | 介入 / 質問 | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |
|---|---:|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 92.3 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 10.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 278 | 32 | $1.41 | 8.3 | 5 | 1 | 9 | superpowers:brainstorming, superpowers:requesting-code-review |
| Superpowers #2 | 98.3 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 11.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 191 | 20 | $0.92 | 5.9 | 60 | 0 | 6 | superpowers:brainstorming |
| Feature Dev #1 | 89.2 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 10.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 257 | 54 | $2.12 | 7.4 | 97 | 7 | 12 | — |
| Feature Dev #2 | 91.6 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 11.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 405 | 75 | $1.73 | 7.5 | 3 | 7 | 5 | — |
| Compound Engineering #1 | 90.0 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 12.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 244 | 47 | $2.61 | 10.3 | 137 | 5 | 17 | compound-engineering:ce-code-review, compound-engineering:ce-simplify-code |
| Compound Engineering #2 | 92.3 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 11.5 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 238 | 30 | $1.69 | 7.9 | 86 | 0 | 13 | compound-engineering:ce-code-review |
| gstack #1 | 89.8 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 11.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 239 | 16 | $2.27 | 11.9 | 100 | 0 | 8 | review, ship |
| gstack #2 | 86.3 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 11.5 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 340 | 91 | $7.34 | 22.9 | 213 | 8 | 11 | code-review, review |
| baseline（候補なし） #1 | 100.0 | U1✅ U2✅ U3✅ U4✅ U5✅ U6✅ U7✅ U8✅ | E1 5 E2 5 E3 5 | 12.0 / 8 / 10.0 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 224 | 20 | $0.88 | 6.8 | 1 | 0 | 5 | — |

## 所見

- UI チェックリストの 8 項目は全 9 試行で不具合なし（隠しの E2E 16/16）。実装の形は試行ごとに違い（クライアント部品から既存 API を呼ぶもの、失敗時の処理を `src/lib/` に切り出してテストしたもの、CSS Modules を使うものなど）、どの形でも仕様を満たしました。課題文に表示要素・文言・失敗時の振る舞いまで書いたので、仕様の読み落としが起きにくい課題でした。
- ブラウザでの確認は 9 試行とも Playwright MCP（gstack #1・#2 の `/qa` は gstack の browse も）で行い、幅 375px と 1280px のスクリーンショットを 6〜17 枚コミットしました。通信の失敗やサーバーエラーは、多くの試行がリクエストを差し替えて再現していました。担当タスクが 0 件の状態は初期データに無いため、ブラウザで確かめなかった試行が多く、その多くは PR.md に「未確認」と書いています。
- PR の説明は 2 名のブラインドレビューで 10〜12 点（12 点満点）。減点は、Superpowers #1 が注意点・未確認事項を書いていない（d 1 点）、Feature Dev・gstack #1・Superpowers #2 が変更内容をファイル単位で書いている（b 2 点）、gstack #2 が工程の記録（カバレッジ表・レビューの経過）まで載せて長い（a）といった点でした。実施していない確認を確認済みと書いた試行はありません。
- Superpowers は 2 回とも `brainstorming` が発火し、#1 は `requesting-code-review` でサブエージェントにレビューさせました。2 ステップ目の `finishing-a-development-branch` は、テストを確かめてから「ローカルでマージ / push して PR / 残す」の選択肢を示して止まりました（無人なので答えは来ない。PR.md は 1 ステップ目で作成済み）。
- Feature Dev は 2 回とも code-explorer 2・code-architect 2・code-reviewer 3 のサブエージェントを使う 7 フェーズで進めました（#2 は「無人実行のため推奨案で確定」と明記）。#1 は最初のコミットにテストが入っておらず（追記のコマンドが拒否されていた）、2 ステップ目の「PR 作成の指示」で気づいて追加しました。
- gstack は 1 ステップ目で実装とブラウザ確認・PR.md まで済ませ、`/qa` で追加の観点（長いタイトル、HTML 文字列、タッチ操作、セッション切れ）を確かめました。#2 は `/qa` でセッション切れ（401）の表示を ISSUE-001 として直し、`/ship` がリモート無しでも進められる工程（レビュー、テストの網羅率の確認、PR.md の最終版）を進めたため、費用 $7.34・所要時間 23 分と 9 試行で最も多くかかりました。#1 の `/ship` はプリフライトの `git fetch origin` の失敗で止まりました。`gstack-egress list` の外部送信の記録は 2 回とも無し。
- Compound Engineering は `/ce-work` の中で実装・ブラウザ確認・レビュー（ce-code-review の簡易パス）・PR.md まで済ませました。`/ce-test-browser` は「ホスト組み込みのブラウザか agent-browser だけを使う」規則のため Playwright MCP を使わず、agent-browser の有無を確かめるコマンドも承認が要るため、2 回ともテストを始めずに止まりました（その前の工程の Playwright MCP での確認は、このスキルの結果としては数えないと明記）。補助スクリプト（review-scope など）も承認が要り、手作業で代えています。
- 介入（定型の「お任せします」）は、やり直した後の 9 試行ではどれも 0 回、質問ツールの呼び出しも 0 回でした。費用の上限（watch）で止めた試行もありません。

## 試行の詳細

### Superpowers #1 — 92.3 点

brainstorming が発火。実装後にサブエージェントでレビュー（requesting-code-review）し、指摘（エラー表示のキー）を直して PR.md を追加。finishing-a-development-branch は選択肢を示して止まった。PR.md に注意点・未確認事項が無い点で減点。

PR の説明のブラインドレビュー（R01）: 採点者 1 = 10、採点者 2 = 10（各 12 点満点）

- 冒頭と概要で利用者から見た振る舞いが分かり、0件表示も含めて画像付きで具体的に確認している。一方で残課題・注意点（未確認事項や既存APIの制約）の記載がまったくない。
- 冒頭と概要が利用者の振る舞い中心で分かりやすく、0 件表示を含むブラウザ確認も証跡と一致する。一方で残課題・注意点（未確認事項や制約）の記載がまったく無い。

変更ファイル:

- `PR.md` +34 −0（doc）
- `docs/evidence/my-tasks-1280.png` +0 −0（code）
- `docs/evidence/my-tasks-375-add-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-after-add.png` +0 −0（code）
- `docs/evidence/my-tasks-375-empty.png` +0 −0（code）
- `docs/evidence/my-tasks-375-initial.png` +0 −0（code）
- `docs/evidence/my-tasks-375-status-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-validation-error.png` +0 −0（code）
- `src/app/globals.css` +90 −0（code）
- `src/app/layout.tsx` +4 −2（code）
- `src/app/my-tasks/my-tasks.tsx` +147 −0（code）
- `src/app/my-tasks/page.tsx` +18 −0（code）
- `src/lib/task-order.ts` +7 −0（code）
- `src/lib/tasks.ts` +12 −0（code）
- `tests/tasks.test.ts` +32 −0（test）

コミット:

- `8d5ae6c PR.md を追加し、エラー表示のキーを修正`
- `defa35f マイタスク画面（/my-tasks）を追加`

### Superpowers #2 — 98.3 点

許可リストの漏れを直した後のやり直し（1 回目は `W6/excluded/`）。brainstorming が発火。`feat/my-tasks` ブランチを切って実装し、ブラウザ確認とスクリーンショット 6 枚まで 1 ステップ目で完了。finishing-a-development-branch は選択肢を示して止まった。

PR の説明のブラインドレビュー（R06）: 採点者 1 = 11、採点者 2 = 11（各 12 点満点）

- 検証表は具体的で事実と一致し、0件表示が未確認であることとクリックの代替手段も明記している。概要がすぐファイル単位の列挙になっており、振る舞いの説明はその中に混在している。
- 検証表と証跡が具体的で、0 件表示を未確認と明記しクリック操作の制約も書いている。概要の箇条書きがファイル名を主語にしており、振る舞いの整理が弱い。

変更ファイル:

- `PR.md` +44 −0（doc）
- `docs/evidence/my-tasks-1280.png` +0 −0（code）
- `docs/evidence/my-tasks-375-add-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-after-add.png` +0 −0（code）
- `docs/evidence/my-tasks-375-initial.png` +0 −0（code）
- `docs/evidence/my-tasks-375-status-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-validation-error.png` +0 −0（code）
- `src/app/layout.tsx` +2 −1（code）
- `src/app/my-tasks/my-tasks.module.css` +11 −0（code）
- `src/app/my-tasks/my-tasks.tsx` +152 −0（code）
- `src/app/my-tasks/page.tsx` +16 −0（code）
- `src/lib/tasks.ts` +10 −0（code）
- `tests/tasks.test.ts` +20 −0（test）

コミット:

- `05684f4 マイタスク画面（/my-tasks）を追加`

### Feature Dev #1 — 89.2 点

7 フェーズ（サブエージェント 7 体）。最初のコミットにテストが入っておらず、PR 作成の指示のステップで気づいて追加し、PR.md のテスト件数も直した。最後に残った変更は run-trial.sh が拾った。

PR の説明のブラインドレビュー（R07）: 採点者 1 = 10、採点者 2 = 10（各 12 点満点）

- 検証は0件表示まで画像付きで具体的に示している。変更内容はファイル・コンポーネント単位の説明が中心である。注意点は既存APIの所有者チェックだけで、未確認事項や制約の記載が薄い。
- 0 件表示を含む検証表と証跡は事実と一致し具体的。変更内容はファイル単位で実装寄り、注意点は API の所有者チェックのみで未確認事項の記載が無い。

変更ファイル:

- `.playwright-mcp/console-2026-11-09T05-21-46-764Z.log` +6 −0（code）
- `PR.md` +44 −0（doc）
- `docs/evidence/01-375-initial.png` +0 −0（code）
- `docs/evidence/02-375-validation-error.png` +0 −0（code）
- `docs/evidence/03-375-added.png` +0 −0（code）
- `docs/evidence/04-375-status-error.png` +0 −0（code）
- `docs/evidence/05-375-add-error.png` +0 −0（code）
- `docs/evidence/06-1280.png` +0 −0（code）
- `docs/evidence/07-375-empty.png` +0 −0（code）
- `src/app/layout.tsx` +2 −1（code）
- `src/app/my-tasks/MyTaskItem.tsx` +57 −0（code）
- `src/app/my-tasks/TaskAddForm.tsx` +61 −0（code）
- `src/app/my-tasks/my-tasks.module.css` +77 −0（code）
- `src/app/my-tasks/page.tsx` +27 −0（code）
- `src/lib/task-form.ts` +17 −0（code）
- `src/lib/tasks.ts` +10 −0（code）
- `tests/task-form.test.ts` +30 −0（test）
- `tests/tasks.test.ts` +24 −0（test）

コミット:

- `5c51718 poc: uncommitted leftovers`
- `1e25774 listTasksByAssignee のテストを追加し、PR.md のテスト件数を更新する`
- `05df139 マイタスク画面（/my-tasks）を追加する`

### Feature Dev #2 — 91.6 点

7 フェーズ（サブエージェント 7 体）。確認中に一度だけステータス変更が再読み込み後に保持されない場面があり、再現しなかったことを PR.md に書いた。next dev が書き出した AGENTS.md が残り、run-trial.sh が拾った。

PR の説明のブラインドレビュー（R05）: 採点者 1 = 11、採点者 2 = 11（各 12 点満点）

- 検証表は具体的で、再現しなかった不具合も正直に書いている。変更内容はファイル単位の構成で、testid・ref などの実装の詳細が多い。
- 確認表と証跡は具体的で、hydration 警告や再現しなかった不具合など注意点も開示している。変更内容がファイル単位の構成で、振る舞いの変化が読み取りにくい。

変更ファイル:

- `.playwright-mcp/console-2026-11-09T05-44-24-051Z.log` +86 −0（code）
- `.playwright-mcp/console-2026-11-09T05-46-08-743Z.log` +5 −0（code）
- `.playwright-mcp/console-2026-11-09T05-46-21-621Z.log` +94 −0（code）
- `AGENTS.md` +9 −0（doc）
- `PR.md` +50 −0（doc）
- `docs/evidence/01-mobile-375-list.png` +0 −0（code）
- `docs/evidence/02-mobile-375-validation-error.png` +0 −0（code）
- `docs/evidence/03-mobile-375-server-error.png` +0 −0（code）
- `docs/evidence/04-mobile-375-after-add.png` +0 −0（code）
- `docs/evidence/05-mobile-375-status-error.png` +0 −0（code）
- `docs/evidence/06-desktop-1280.png` +0 −0（code）
- `src/app/layout.tsx` +2 −1（code）
- `src/app/my-tasks/add-task-form.tsx` +73 −0（code）
- `src/app/my-tasks/page.tsx` +44 −0（code）
- `src/app/my-tasks/status-select.tsx` +47 −0（code）
- `src/lib/task-client.ts` +44 −0（code）
- `src/lib/tasks.ts` +10 −0（code）
- `tests/task-client.test.ts` +54 −0（test）
- `tests/tasks.test.ts` +21 −0（test）

コミット:

- `3d93cd8 poc: uncommitted leftovers`
- `bd3c100 マイタスク画面（/my-tasks）を追加`

### Compound Engineering #1 — 90.0 点

`/ce-work` で 4 コミット（関数とテスト、画面、コメントの削除、証跡と PR.md）。ce-simplify-code・ce-code-review（簡易パス）を使用。`/ce-test-browser` は規則によりテストを始めず、`/ce-commit-push-pr` はリモート無しで停止。

PR の説明のブラインドレビュー（R04）: 採点者 1 = 12、採点者 2 = 12（各 12 点満点）

- 振る舞いを概要で説明し、本番ビルドでの確認を表で具体的に示している。二重クリックや0件表示を確認していないことも正直に書いている。残るリスクと環境上の注意も明記している。
- 概要で振る舞いを平易に説明し、確認表と証跡が揃っている。二重クリックや 0 件表示を未確認と正直に書き、開発サーバーの DB の注意点など残リスクも明記している。

変更ファイル:

- `PR.md` +57 −0（doc）
- `docs/evidence/desktop-1280.png` +0 −0（code）
- `docs/evidence/mobile-375-add-error.png` +0 −0（code）
- `docs/evidence/mobile-375-added.png` +0 −0（code）
- `docs/evidence/mobile-375-initial.png` +0 −0（code）
- `docs/evidence/mobile-375-status-error.png` +0 −0（code）
- `docs/evidence/mobile-375-validation-error.png` +0 −0（code）
- `src/app/globals.css` +79 −0（code）
- `src/app/layout.tsx` +3 −1（code）
- `src/app/my-tasks/my-tasks.tsx` +134 −0（code）
- `src/app/my-tasks/page.tsx` +16 −0（code）
- `src/lib/task-order.ts` +4 −0（code）
- `src/lib/tasks.ts` +8 −0（code）
- `tests/my-tasks.test.ts` +47 −0（test）

コミット:

- `b31492e docs: マイタスク画面のブラウザ確認の証跡と PR 本文を追加`
- `e75995f refactor(tasks): 内容を言い直しているだけのコメントを削除`
- `3df74ba feat(my-tasks): 担当タスクを確認・追加・更新できるマイタスク画面を追加`
- `7186862 feat(tasks): 担当者でタスクを絞り込み、期限順に並べる関数を追加`

### Compound Engineering #2 — 92.3 点

許可リストの漏れを直した後のやり直し（1 回目は `W6/excluded/`。中断を挟み、再開後に最初から実行）。`/ce-work` で実装・ブラウザ確認・PR.md まで完了。ce-code-review（lite）は指摘 0 件、補助スクリプトは承認が要り手作業で代替。`/ce-test-browser`・`/ce-commit-push-pr` は #1 と同じく停止。

PR の説明のブラインドレビュー（R09）: 採点者 1 = 12、採点者 2 = 11（各 12 点満点）

- 振る舞いの節があり、検証表で証跡の有無まで正直に区別している。0件表示も確認している。クリック操作の代替や残余リスクも書いているが、レビュー工程の記録は読み手に不要な情報を含む。
- 検証表が具体的で証跡・0 件表示の確認も事実と一致し、残余リスクやブラウザ操作の制約も書いている。変更内容の前半はファイル・関数名主体で、振る舞いは別節に分かれている。

変更ファイル:

- `PR.md` +56 −0（doc）
- `docs/evidence/01-mobile-375-list.png` +0 −0（code）
- `docs/evidence/02-mobile-375-validation-error.png` +0 −0（code）
- `docs/evidence/03-mobile-375-after-add.png` +0 −0（code）
- `docs/evidence/04-mobile-375-status-error.png` +0 −0（code）
- `docs/evidence/05-mobile-375-add-failed.png` +0 −0（code）
- `docs/evidence/06-desktop-1280.png` +0 −0（code）
- `docs/evidence/07-mobile-375-empty.png` +0 −0（code）
- `src/app/globals.css` +72 −0（code）
- `src/app/layout.tsx` +3 −1（code）
- `src/app/my-tasks/MyTasks.tsx` +140 −0（code）
- `src/app/my-tasks/page.tsx` +15 −0（code）
- `src/lib/tasks.ts` +8 −0（code）
- `tests/tasks.test.ts` +30 −0（test）

コミット:

- `dd27d1c docs: マイタスク画面の確認証跡と PR 本文を追加`
- `304c814 docs: マイタスク画面の確認証跡と PR 本文を追加`
- `168ecd6 feat(my-tasks): マイタスク画面（/my-tasks）を追加`

### gstack #1 — 89.8 点

1 ステップ目で実装・Playwright MCP での確認・PR.md を済ませ、`/qa` は gstack の browse（事前インストール済みの Chromium）で追加の観点を確認（指摘 1 件・低、保留）。`/ship` は origin が無くプリフライトで停止。

PR の説明のブラインドレビュー（R02）: 採点者 1 = 11、採点者 2 = 11（各 12 点満点）

- 検証は本番ビルドで状態ごとに具体的に書かれ、事実と一致する。変更内容はファイル単位の列挙が中心で、振る舞いはその中に埋もれている。開発インジケーターと0件表示が未確認であることも明記している。
- 確認内容は具体的で、0 件表示の未確認や開発サーバーの注意点も正直に書いている。変更内容はファイル単位の箇条書きが主で、振る舞いの整理はやや弱い。

変更ファイル:

- `AGENTS.md` +9 −0（doc）
- `PR.md` +50 −0（doc）
- `evidence/01-mobile-list.png` +0 −0（code）
- `evidence/02-mobile-validation-error.png` +0 −0（code）
- `evidence/03-mobile-after-add.png` +0 −0（code）
- `evidence/04-mobile-status-error.png` +0 −0（code）
- `evidence/05-mobile-add-error.png` +0 −0（code）
- `evidence/06-desktop.png` +0 −0（code）
- `src/app/layout.tsx` +2 −1（code）
- `src/app/my-tasks/my-tasks.module.css` +52 −0（code）
- `src/app/my-tasks/my-tasks.tsx` +161 −0（code）
- `src/app/my-tasks/page.tsx` +16 −0（code）
- `src/lib/tasks.ts` +8 −0（code）
- `tests/tasks.test.ts` +16 −0（test）

コミット:

- `44f5ffc poc: uncommitted leftovers`
- `1986766 マイタスク画面（/my-tasks）を追加`

### gstack #2 — 86.3 点

`/qa` でセッション切れの表示を直し（ISSUE-001）、QA レポートとスクリーンショットをコミット。`/ship` はレビュー（gstack の `/review` が動かず code-review で代替）と網羅率の確認、失敗時の処理の `src/lib/` への切り出しとテスト追加まで進めた。$7.34・23 分で最多。

PR の説明のブラインドレビュー（R03）: 採点者 1 = 12、採点者 2 = 11（各 12 点満点）

- 振る舞いの一覧、検証表、証跡、未検証の点の開示はそろっている。ただし英語のカバレッジ表やレビュー工程の記録が長く、変更の大きさに対して読み手の負担が大きい。
- 冒頭がリモート無しの説明から始まり、カバレッジ表やレビュー工程の記述が多く非エンジニアには読みにくい。振る舞いの記述・検証表・証跡・未検証点の開示は充実している。

変更ファイル:

- `.gstack/qa-reports/run-20261109T054759Z/baseline.json` +11 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/deadline.json` +1 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-001.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-002.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-003.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-004.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-005.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-006.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-007.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/exploration-008.json` +6 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/qa-report-localhost-2026-11-09.md` +132 −0（doc）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/final-1280.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/final-375.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/initial.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/issue-001-after.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/issue-001-before.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-002.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-003.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-004-empty.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-004-first.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-005.jpg` +0 −0（code）
- `.gstack/qa-reports/run-20261109T054759Z/screenshots/probe-006.jpg` +0 −0（code）
- `PR.md` +113 −0（doc）
- `docs/evidence/01-mobile-375-list.png` +0 −0（code）
- `docs/evidence/02-mobile-375-validation-error.png` +0 −0（code）
- `docs/evidence/03-mobile-375-added.png` +0 −0（code）
- `docs/evidence/04-mobile-375-status-error.png` +0 −0（code）
- `docs/evidence/05-mobile-375-add-failed.png` +0 −0（code）
- `docs/evidence/06-desktop-1280.png` +0 −0（code）
- `src/app/globals.css` +67 −0（code）
- `src/app/layout.tsx` +3 −1（code）
- `src/app/my-tasks/my-tasks.tsx` +153 −0（code）
- `src/app/my-tasks/page.tsx` +16 −0（code）
- `src/lib/my-tasks.ts` +25 −0（code）
- `src/lib/task-order.ts` +8 −0（code）
- `src/lib/tasks.ts` +8 −0（code）
- `tests/my-tasks.test.ts` +91 −0（test）

コミット:

- `3219709 docs: PR の本文（タイトル・カバレッジ・レビュー・検証結果）を最終版にする`
- `35e7985 docs: 証跡のスクリーンショットを最終の見た目に更新する`
- `ccb19f5 マイタスクの失敗時処理を src/lib に切り出してテストを追加し、レビュー指摘を反映する`
- `0979ff3 docs(qa): /my-tasks の QA レポートと証跡を追加`
- `c2af21e fix(qa): ISSUE-001 — セッション切れ（401）のときにログインし直す案内を表示する`
- `3cc922d マイタスク画面（/my-tasks）を追加`

### baseline（候補なし） #1 — 100.0 点

候補なし。Playwright MCP で 375px・1280px を操作し、入力エラー・500 / 通信失敗・二重クリック・ステータス変更の失敗まで確かめ、スクリーンショット 6 枚を `docs/evidence/` にコミット。PR.md には 0 件表示を未確認と明記。最安・最短。

PR の説明のブラインドレビュー（R08）: 採点者 1 = 12、採点者 2 = 12（各 12 点満点）

- 概要で振る舞いを簡潔に列挙し、確認項目と証跡のリンクもそろっている。未確認の項目と既存APIの制約を短くまとめており、分量も適切である。
- 簡潔に振る舞いを説明し、確認項目と証跡を列挙、0 件表示の未確認や既存 API の制約も明記している。分量も変更に見合っている。

変更ファイル:

- `PR.md` +40 −0（doc）
- `docs/evidence/my-tasks-1280.png` +0 −0（code）
- `docs/evidence/my-tasks-375-add-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-after-add.png` +0 −0（code）
- `docs/evidence/my-tasks-375-status-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375-validation-error.png` +0 −0（code）
- `docs/evidence/my-tasks-375.png` +0 −0（code）
- `src/app/layout.tsx` +3 −2（code）
- `src/app/my-tasks/my-tasks.module.css` +49 −0（code）
- `src/app/my-tasks/my-tasks.tsx` +146 −0（code）
- `src/app/my-tasks/page.tsx` +18 −0（code）
- `src/lib/tasks.ts` +8 −0（code）
- `tests/tasks.test.ts` +20 −0（test）

コミット:

- `d746d0d マイタスク画面（/my-tasks）を追加`

## 採点方法

配点は PLAN.md §5.1 の W6、手順は試行前に固定した `docs/poc/answer-key/W6/grading.md` のとおり（`scripts/poc/grade_w6.py` → `blind_w6.py` → `score_w6.py`）。2 本立ての点数は PLAN.md §4.4（`scripts/poc/two_axis.py`）。


- <strong>UI チェックリスト（40）</strong>: 8 項目それぞれ 5 点。隠しの E2E（`acceptance.cjs`、16 件）で、その項目のチェックがすべて通れば不具合なし。通信の失敗は、ページからの GET 以外のリクエストを止める・500 を返すことで再現（実装の方式に依存しない）。
- <strong>検証の証跡（15）</strong>: ブラウザで `/my-tasks` を開いて操作した 5、スクリーンショットをコミットした 5（撮影のみ 3）、幅 480px 以下で確認した 5。トランスクリプトのツール呼び出し（サブエージェントを含む）から自動で判定。
- <strong>PR の完成度（30）</strong>: PR.md の説明 12（2 名のブラインドレビュー、4 項目 × 0〜3 点の平均）、テスト 8（tests/ の追加・変更があり npm test が通る）、CI 10（型チェック・単体テスト・ビルド）。
- <strong>費用（15）</strong>: 15 ×（最安 / 自分）。
- <strong>2 本立て</strong>: 品質 = (UI + 証跡 + PR) / 85 × 100。効率 = 費用 50 + 時間 30 + 介入 20（baseline の実額 $0.8769・実時間 409 秒に対する倍率の段階）。

## この結果の制約

- 課題文に表示要素・文言・失敗時の振る舞いまで細かく書いたため、UI チェックリストでは差が付きませんでした（全試行が満点）。仕様の書かれていない UI の気配り（仕様外の状態の扱い、見た目の質）での差は、この結果からは分かりません。
- 見た目の質（レイアウトの美しさ・一貫性）は採点に入れていません。E2E で測れるのは、幅に収まるか・要素が表示されるかまでです。
- PR はリモートが無い環境でローカルの PR.md に書かせたため、`/ship`・`/ce-commit-push-pr`・`finishing-a-development-branch` の本来の工程（push、PR の作成、CI の監視）は評価できていません。リモートがある環境では結果が変わり得ます。
- Compound Engineering の `/ce-test-browser` は、この環境では使える駆動手段（ホスト組み込みのブラウザか agent-browser）が無く、機能そのものは評価できていません。
- 検証の証跡は、ツールの呼び出しから自動で判定しています（スクリーンショットの中身の正しさまでは見ていません）。
- 所要時間は 2 本並列で実行したときの壁時計の時間（CE #2 は再開後に 1 本で実行）で、並列の相手によって揺れがあります。各候補 2 回（baseline は 1 回）だけで、ばらつきの評価には足りません。

## 判断の記録

- <strong>課題の作り方</strong>: 「空状態・エラー表示・レスポンシブ」を含む新しい画面として、既存の API をそのまま使える「マイタスク」画面にした（スキーマ変更なし）。採点を自動で再現できるよう、要素の目印（`data-testid`、フォームの `aria-label`、`role="alert"`）と文言を課題文に書いた。隠しの E2E は、参照実装で 16/16、変更なしの poc-app で 1/16、参照実装から 4 つの不具合を入れた版で該当の 4 件だけ落ちることを試行前に確かめた。
- <strong>費用の上限</strong>: `POC_BUDGET_MODE=watch`（上限を子セッションに見せない）。規模係数 = W6 baseline の実額 $0.8769 ÷ W1 baseline $0.15 = 5.85。上限 = 5.85 × W1 の候補平均 × 5（最大 $10）で、Superpowers $4.96、Feature Dev $5.02、gstack $10（計算値 $13.4）、Compound Engineering $10（計算値 $52.2）。baseline は規模係数を決める前に暫定 $5 で実行した。上限で止まった試行は無い（最高は gstack #2 の $7.34）。
- <strong>子セッションの許可リスト（W6 以降だけ追加。W1〜W5 は変えていない）</strong>: 開発サーバーの起動（`npm run dev` / `npm run start` / `npm start` / `npx next dev` / `npx next start`、`timeout` 付き、`PORT=…` 付き）、Playwright MCP と Next.js DevTools MCP のツール、gstack の browse。理由: W6 はブラウザでの確認が課題の一部で、サーバーを起動できないと確認ができないため（コーディネーターの判断・ユーザー委任済み）。試行後のサーバーとブラウザは reap_servers（結果の 30 秒後と試行の終了時）が止める。
- <strong>許可リストの漏れとやり直し</strong>: 最初の許可リストに `npm start` と `PORT=3100 npm run start` などの形が無く（私の書き漏れ）、Superpowers #2 と Compound Engineering #2 はサーバーを起動できず、ブラウザ確認をしないまま終わった（証跡 0 点）。この形を足して 2 本をやり直し、元の結果は `W6/excluded/` に残して点数には使っていない。足す前に終わったほかの 7 本の `permission_denials` を調べ、足した形の拒否が 0 件だったので、やり直していない（全試行が実質的に同じ許可リストで動いた）。
- <strong>ブラウザ</strong>: gstack の setup の Chrome 取得（cdn.playwright.dev）はネットワーク制限で使えないため `--no-browser` のまま、W6 以降だけ環境変数 `GSTACK_CHROMIUM_PATH=/opt/pw-browsers/chromium` で事前インストール済みの Chromium を使わせた。gstack の browse と `/qa` はこれで動いた。Playwright MCP は全候補で同じ設定で動いた。Compound Engineering の `/ce-test-browser` は規則で Playwright MCP を使わず、agent-browser も無いため動かなかった（挙動として記録）。ネットワーク許可は追加していない。
- <strong>PR の作り方（候補間で公平にするため）</strong>: GitHub には出さず、課題文で全候補に「作成するはずだった PR のタイトルと本文を PR.md に書いてコミットする」と指示した。作業用コピーにはリモートが無く、`git push` と `gh` は許可リストに無い。Feature Dev の「PR 作成の指示」も同じ趣旨の定型文にした。PR の完成度は PR.md・テスト・チェック結果で判定した。push や gh を試みた試行は無かった（全試行が先にリモートの有無を確かめて止まった）。
- <strong>候補ごとの手順</strong>: PLAN §5.1 の W6 の行のとおり（Superpowers: 課題 → `/superpowers:finishing-a-development-branch`、Feature Dev: `/feature-dev:feature-dev` → PR 作成の指示、gstack: 課題 → `/qa` → `/ship`、Compound Engineering: `/ce-work` → `/ce-test-browser` → `/ce-commit-push-pr`）。全候補とも作業ブランチの上で開始。末尾の定型文は新文言（全試行の `task-suffix` が `new`）。
- <strong>PR の説明の採点</strong>: 人が読む文章の質なので、W2 と同じく 2 名のブラインドレビュー（候補名を伏せ、試行ごとの事実の要約を添え、順番を変えて渡す）にした。伏せ字の漏れ（「Compound Pack」）を見つけて伏せ字の規則を強め、資料を作り直してから渡した。2 名の差が 2 点以上の項目は無かった。
- <strong>2 本立ての点数</strong>: コーディネーター経由のユーザー指示で、品質・効率の 2 本立てを主表示にし、従来の総合点も並記した。W6 には介入の仕組みがあるので効率は 費用 50 + 時間 30 + 介入 20。基準は W6 baseline の $0.8769・409 秒。
- <strong>中断と再開</strong>: usage の上限が近いというユーザーの指示で、Compound Engineering #2 のやり直しを 1 ステップ目の途中で止めた（途中の記録は採点に使わない）。再開後に同じ方式（watch・上限 $10・同じ許可リスト）で最初から実行した。
- <strong>並列度と順番</strong>: 2 本並列（W4・W7 の担当と並行するため 1〜2 本に抑えた）。baseline を先に 1 本で実行して規模係数を決め、レーン A が gstack #1 → Superpowers #1 → Compound Engineering #2 → Feature Dev #2、レーン B が Feature Dev #1 → Compound Engineering #1 → Superpowers #2 → gstack #2。やり直しの Superpowers #2 は 2 本並列、Compound Engineering #2 は再開後に 1 本で実行。
- <strong>W1〜W5 との後方互換</strong>: `run-trial.sh` の変更は、W6 の手順・介入の文言・PR.md の完了条件・許可の追加・`GSTACK_CHROMIUM_PATH`・終了時のサーバー停止のすべてが W6 以降（`SCN_NUM >= 6` か `SCENARIO == W6`）のときだけ働く。共通部分の変更は、reap_servers が止める対象に browse・chrome を足したこと（W5 までは起動されない）と、未コミットの判定から `.playwright-mcp/` を除いたこと（W5 までは作られない）だけ。

## 試行間の独立性の確認結果

`grade.py` の検出（自分の作業用コピーの外への参照）は全 9 試行で 0 件、正解データ（`answer-key`）を読んだ形跡も 0 件でした（検出であり、完全な防止ではありません）。

## 次の対応

- UI の差を見たいなら、仕様を細かく書かない課題（画面の目的だけを渡し、空状態やエラーの扱いを候補に考えさせる）で、見た目の質も含めたブラインドレビューを検討する。
- `/ship`・`/ce-commit-push-pr` の本来の工程（push・PR 作成・CI の監視）は、PoC 専用のリモート（使い捨てのリポジトリ）を用意できる場合だけ別に評価する（ネットワーク・権限の追加が要るので、要否をユーザーに確認する）。
- Compound Engineering の `/ce-test-browser` を評価するには agent-browser の導入が要る（候補固有の追加依存として、導入するかを判断する）。
