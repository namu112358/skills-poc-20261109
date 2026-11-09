# 開発ワークフロー PoC — W2 仕様が明確な機能追加

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 docs/poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w2.py` で生成）

<strong>W2（仕様が明確な機能追加）でも、実装の正しさに差は出ませんでした。</strong>4 候補と baseline の全 9 試行が、隠しの受け入れテスト 16 件（API 9・画面 6・既存の動作 1）をすべて通過し、型チェック・単体テスト・ビルドも成功しました。

Feature Dev（平均 96.2 点）と Superpowers（95.3 点）は、候補なしの baseline（97.1 点）とほぼ同じ費用（約 $0.35）・時間（約 1.7 分）で終わりました。ただし Feature Dev は「無人実行のため」と自ら設計案・確認・エージェントの工程を省いており、実質は baseline と同じ進め方でした。

Compound Engineering（87.2 点）は設計・テストの質のブラインドレビューで最も高い評価（平均 24.5 / 25）でしたが、費用が baseline の約 4〜10 倍（$1.25〜$3.35）で費用の点を大きく落としました。

gstack（84.6 点）は、続く `/review` が見つけた修正（CLAUDE.md の追記、文字数の数え方の変更）をコミットせずに終わり、2 回とも「お任せします」での続行（介入）が 1 回ずつ必要でした。費用は baseline の約 2〜3 倍です。

## 課題

タスク詳細画面（/tasks/:id）にコメント機能を追加する。DB（投稿日時は UTC）、API 3 本（`GET/POST /api/tasks/:id/comments`、`DELETE …/:commentId`）、本文の検証（前後の空白を除いて 1〜1000 文字）、本人だけが削除できる権限、画面（一覧・空状態・投稿フォーム・エラー表示・本人だけの削除ボタン）。仕様書は `docs/poc/tasks/wf-W2.md`。

## 結果の概要（平均点）

| 候補 | 回数 | 合計 / 100 | 受け入れ / 40 | 介入 / 20 | 設計・テスト / 25 | 費用 / 15 | 平均費用 | 平均時間（分） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 95.3 | 40.0 | 20 | 21.2 | 14.1 | $0.36 | 1.6 |
| **Feature Dev** | 2 | 96.2 | 40.0 | 20 | 23 | 13.2 | $0.38 | 1.7 |
| Compound Engineering | 2 | 87.2 | 40.0 | 20 | 24.5 | 2.8 | $2.30 | 5.5 |
| gstack | 2 | 84.6 | 40.0 | 15 | 23.2 | 6.3 | $0.83 | 2.9 |
| baseline（候補なし） | 1 | 97.1 | 40.0 | 20 | 22.5 | 14.6 | $0.34 | 1.6 |

## 試行ごとの結果

| 試行 | 点数 | E2E | チェック | 介入 / 質問 | 設計・テスト | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 96.1 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 23 | 234 | 59 | $0.38 | 1.6 | 22 | 0 | 3 | superpowers:test-driven-development |
| Superpowers #2 | 94.5 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 19.5 | 243 | 45 | $0.33 | 1.6 | 19 | 0 | 2 | — |
| Feature Dev #1 | 96.6 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 23 | 255 | 46 | $0.37 | 1.7 | 20 | 0 | 2 | — |
| Feature Dev #2 | 95.8 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 23 | 243 | 54 | $0.39 | 1.8 | 21 | 0 | 4 | — |
| Compound Engineering #1 | 86.5 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 25 | 273 | 180 | $3.35 | 6.9 | 66 | 5 | 13 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-simplify-code, compound-engineering:ce-work |
| Compound Engineering #2 | 88.0 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 24 | 284 | 131 | $1.25 | 4.1 | 57 | 0 | 12 | compound-engineering:ce-code-review |
| gstack #1 | 83.4 | 16/16 | typecheck ✅ test ✅ build ✅ | 1 / 0 | 23.5 | 235 | 44 | $1.01 | 3.2 | 28 | 2 | 3 | — |
| gstack #2 | 85.7 | 16/16 | typecheck ✅ test ✅ build ✅ | 1 / 0 | 23 | 248 | 54 | $0.65 | 2.6 | 29 | 0 | 4 | — |
| baseline（候補なし） #1 | 97.1 | 16/16 | typecheck ✅ test ✅ build ✅ | 0 / 0 | 22.5 | 258 | 60 | $0.34 | 1.6 | 18 | 0 | 3 | — |

## ブラインドレビューの項目別平均（0〜5）

| 候補 | 規約 | 設計 | 認可・入力 | テスト | 過不足 |
|---|---:|---:|---:|---:|---:|
| Superpowers | 4.5 | 3.8 | 5 | 3.2 | 4.8 |
| Feature Dev | 5 | 4 | 5 | 4 | 5 |
| Compound Engineering | 5 | 4.5 | 5 | 5 | 5 |
| gstack | 5 | 4.2 | 5 | 4 | 5 |
| baseline（候補なし） | 5 | 3.5 | 5 | 4 | 5 |

採点者 2 名の差が 3 点以上の項目はありませんでした。

## 所見

- 受け入れテスト・介入・規約・認可と入力の安全性では、ほとんど差が出ませんでした。<strong>差が付いたのは費用と、テストの厚さ・設計の細部だけ</strong>です。仕様が明確な機能追加は、候補なしでも十分にこなせる範囲でした。
- ブラインドレビューの評価が最も高かったのは Compound Engineering の 2 試行（25 点・24 点）で、計画書を作ってから進める分、テストが他の 2〜4 倍の行数（131〜180 行）あり、境界値・並び順・外部キーまで確かめていました。ただし受け入れテストの結果には差が無く、その分の費用（baseline の 4〜10 倍）を回収できていません。
- Feature Dev は 2 回とも、課題文末尾の定型文（無人なので質問には答えられない）を受けて、7 フェーズのうち探索・設計案の比較・レビューを自ら省きました。W1 と同じ傾向で、無人の試行では Feature Dev の特徴が出ません。
- Superpowers の Skill（test-driven-development）が発火したのは 2 回中 1 回でした。発火しなかった回は、削除の権限判定を API Route に書いてテストを付けておらず、品質の評価が 9 試行で最も低くなりました。
- gstack の /review は、W1 と違い作業ブランチの上だったため差分を正しく読み、指摘に基づく修正まで行いました。ただし修正をコミットせずに終わる点が 2 回とも共通で、介入が必要になりました。
- ほぼ全試行が、実サーバーを起動して API を確かめようとし、権限（許可リスト）で拒否されています。最終確認は単体テストと型チェック・ビルドまでで、画面の動作確認はどの候補も行えていません。

## 試行の詳細

### Superpowers #1 — 96.1 点

test-driven-development Skill が発火し、テストを先に書いてから実装した。変更の範囲は baseline と同じ。

ブラインドレビュー（規約 5 ・ 設計 4 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- comments.tsx で Comment 型と同じ形の CommentView を別に定義しており、コメント ID の検証にも parseTaskId を流用している（軽微）。tests/comments.test.ts は権限・別タスク・境界値を押さえているが、1 文字の受理を確かめていない。
- src/lib/comments.ts の validateCommentInput が ValidationResult<string> を返し、既存の validateTaskInput（オブジェクトを返す）と形が揃っていない。comments.tsx で Comment 型を再定義（CommentView）している。テストは権限・別タスク・並び順を押さえているが、1 文字の下限や各ケースが 1 つの it に詰め込まれている。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +25 −0（code）
- `src/app/tasks/[id]/comments.tsx` +86 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +84 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +59 −0（test）

コミット:

- `e276c52 タスクにコメント機能を追加`

### Superpowers #2 — 94.5 点

Skill は発火せず、baseline と同じ進め方。削除の権限・別タスクの判定を src/lib/ ではなく API Route に書いており、その部分の単体テストが無い点で 2 名とも減点（テスト 2.5、規約 4）。※最初の実行は採点スクリプトの不具合（next dev が自動生成する AGENTS.md を未コミット扱い、開発サーバーが残って終了待ち）で介入が誤って 2 回送られたため破棄し、修正後に同条件でやり直した。

ブラインドレビュー（規約 4 ・ 設計 3.5 ・ 認可・入力 5 ・ テスト 2.5 ・ 過不足 4.5）:

- 本人確認とタスクの一致の判定を [commentId]/route.ts に直接書き、lib/comments.ts の deleteComment(id) は無条件に削除するため、認可のロジックが lib に無く単体テストもできない（規約 1・5）。そのため tests に削除権限・別タスク・存在しないコメントのテストが無い。users の LEFT JOIN と author へのフォールバックは外部キーがあるので不要。
- 本人確認と別タスク判定を API Route（[commentId]/route.ts）に直接書いており、src/lib/ に置かれていないため単体テストされていない。tests/comments.test.ts には他人のコメント削除（403）・別タスク・存在しないコメントのテストが無い。users を LEFT JOIN してフォールバックするなど、必要の薄い分岐もある。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comments.tsx` +101 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +77 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +45 −0（test）

コミット:

- `96ec8a6 タスクへのコメント機能を追加`

### Feature Dev #1 — 96.6 点

「無人実行のため、質問フェーズとエージェント起動は省いて」直接実装した（サブエージェント 0）。結果は baseline とほぼ同じ。

ブラインドレビュー（規約 5 ・ 設計 4 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- comments.tsx で Comment と同じ形の CommentView 型を重複して定義しており、コメント ID の検証には parseTaskId を流用している。テストは並び順・権限・別タスクを押さえているが、1001 文字の拒否が他の不正値とまとめて 1 つのループに入っていて、境界の意図が読み取りにくい。
- comments.tsx で lib の Comment と同じ型を CommentView として再定義している。並び順を created_at, id とし、テストで投稿日時の逆順投入まで確認しているのは良い。ケースが少数の it にまとめられ、1001 文字は不正入力の列挙に埋もれている。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comments.tsx` +107 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +83 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +46 −0（test）

コミット:

- `e1d1eb6 タスクへのコメント機能（API・詳細画面）を追加`

### Feature Dev #2 — 95.8 点

1 回目と同じく工程を省いて直接実装。設計案の比較やレビューのフェーズは行われなかった。

ブラインドレビュー（規約 5 ・ 設計 4 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- comments.ts と comment-section.tsx で SQL 断片や URL を + で連結しており、既存コードのテンプレートリテラルと書き方が揃っていない。また 0 件のときも空の <ul> を描画する。テストに 1 文字の境界と、前後の空白を除いた後の長さ判定の確認が無い。
- comment-section.tsx・comments.ts で URL やメッセージを文字列連結で組み立てており、他の箇所のテンプレートリテラルと揃っていない。コメントが無いときも空の <ul> を描画する。テストは権限・別タスク・境界値を押さえているが、下限 1 文字の確認が無い。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +20 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comment-section.tsx` +95 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +84 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +54 −0（test）

コミット:

- `ff8fa12 タスクへのコメント機能を追加`

### Compound Engineering #1 — 86.5 点

計画書（docs/plans/）を作り、/ce-work で 2 コミットに分けて実装、ce-simplify-code・ce-doc-review・ce-code-review の Skill とサブエージェント 5 つを使った。テストは 180 行で最も厚く、ブラインドレビューは 2 名とも満点。費用は全試行で最高の $3.35。

ブラインドレビュー（規約 5 ・ 設計 5 ・ 認可・入力 5 ・ テスト 5 ・ 過不足 5）:

- lib に parseCommentId・formatCommentTime を置き、ページ側は表示と小さなクライアント部品（router.refresh）だけにしていて既存の構成と揃っている。テストは境界値（1/1000/1001・コードポイント・前後空白）、権限、別タスク、同時刻の並び順、カスケード削除まで網羅している。migration テスト名の「idempotent」は実際には検証していない（ごく軽微）。
- 一覧をサーバーコンポーネントで描き、投稿・削除だけをクライアント部品に分けて router.refresh で更新しており、規約 1 に最も忠実。parseCommentId は parseTaskId を再利用。テストは境界値（1/1000/1001・絵文字・trim 後の長さ）、権限、別タスク、削除済み、同時刻の並び順まで網羅している（migration のテスト名の「idempotent」は内容と合わないが軽微）。

変更ファイル:

- `docs/plans/2026-11-09-0331-feat-task-comments-plan.md` +212 −0（tool-artifact）
- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +20 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +25 −0（code）
- `src/app/tasks/[id]/comment-form.tsx` +53 −0（code）
- `src/app/tasks/[id]/delete-comment-button.tsx` +38 −0（code）
- `src/app/tasks/[id]/page.tsx` +25 −1（code）
- `src/lib/comments.ts` +98 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +180 −0（test）

コミット:

- `f61cb73 feat: タスク詳細画面にコメントの API と画面を追加`
- `f6cef56 feat: タスクコメントの保存・取得・削除の処理を追加`

### Compound Engineering #2 — 88.0 点

計画書を作って実装。/ce-code-review は自分の補助スクリプト（先頭に環境変数を付けた python3 の実行）が許可リストに合わず拒否され、レビュアーを起動せずに「スクリプトの実行を承認してください」と止まった（コードはコミット済みのため介入には数えない）。テストは 131 行で厚く、レビューは 24 点。

ブラインドレビュー（規約 5 ・ 設計 4 ・ 認可・入力 5 ・ テスト 5 ・ 過不足 5）:

- comments.ts の parseCommentId が parseTaskId の正規表現を重複して持っている（軽微）。comment-time.ts への分離はクライアントから使うためで理由がある。テストは境界値・権限・別タスク（403 で存在を漏らさない）・同時刻の並び順・外部キーまで網羅している。
- src/lib/comments.ts の parseCommentId が parseTaskId の正規表現を複製しており、再利用すれば済む。権限・別タスク（403 で存在を漏らさない）・境界値・絵文字・SQL/HTML 風の本文・外部キーまで、テストが最も丁寧。

変更ファイル:

- `docs/plans/2026-11-09-0338-feat-task-comments-plan.md` +148 −0（tool-artifact）
- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +25 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comments.tsx` +111 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comment-time.ts` +6 −0（code）
- `src/lib/comments.ts` +98 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +131 −0（test）

コミット:

- `8c79b90 feat: タスクにコメントを付けられるようにする`

### gstack #1 — 83.4 点

実装後の /review でテスト・保守性と adversarial の 2 つのサブエージェントを使い、CLAUDE.md の API 一覧に追記したがコミットせずに終了。介入 1 回で追記をコミット。/review 自身は「実サーバーでの QA ができなかった」として COMPLETED: false と報告した。

ブラインドレビュー（規約 5 ・ 設計 4.5 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- [commentId]/route.ts でコメント ID の検証に parseTaskId を流用している（軽微）。テストは authorName を length>0 でしか確かめておらず、1 文字の受理と、他人による削除が拒否された後もコメントが残ることの確認が無い。
- 削除の権限判定を src/lib/comments.ts の deleteComment に置いて結果型で返す、整った構成。tests/comments.test.ts は authorName を長さ > 0 でしか確認しておらず、境界値・不正入力が 1 つの it にまとめて書かれている。

変更ファイル:

- `CLAUDE.md` +1 −1（doc）
- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comments.tsx` +87 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +83 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +44 −0（test）

コミット:

- `3d90e45 CLAUDE.md の API 一覧にコメント API を追記`
- `3439cc0 タスクにコメント機能を追加`

### gstack #2 — 85.7 点

/review が本文の文字数をコードポイント単位で数えるよう修正したがコミットせずに終了。介入 1 回でコミット。

ブラインドレビュー（規約 5 ・ 設計 4 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- comments.ts の createComment/deleteComment がユーザー ID の文字列ではなく Pick<User,'id'> を受け取り、既存の関数より引数が回りくどい。コメント ID には parseTaskId を流用している。テストに 1 文字の境界と、拒否された削除の後にコメントが残ることの確認が無い。
- src/lib/comments.ts の createComment / deleteComment がユーザーを Pick<User, "id"> で受け取り、ID 文字列を受ける既存の lib 関数と流儀が違う。コードポイントで数える点は良い。テストは要点を押さえているが、下限の 1 文字の確認が無く、ケースがまとめて書かれている。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +25 −0（code）
- `src/app/tasks/[id]/comments.tsx` +98 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +86 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +54 −0（test）

コミット:

- `ae3f584 コメント本文の長さをコードポイント単位で数える`
- `98201c4 タスクにコメント機能を追加`

### baseline（候補なし） #1 — 97.1 点

変更はコード 6 ファイルとテスト 1 ファイル。実サーバーでの確認は権限で拒否され、単体テスト・ビルドまでで完了とした。ブラインドレビューではクライアント側でのコメント型の重複など設計の細かい点で減点。

ブラインドレビュー（規約 5 ・ 設計 3.5 ・ 認可・入力 5 ・ テスト 4 ・ 過不足 5）:

- comments.ts の parseCommentId が parseTaskId の正規表現をそのままコピーしており、comments.tsx でも CommentView 型を重複して定義している。page.tsx では相対 import を @/lib の import の間に挟んでいる。軽微な一貫性の問題が重なっている。テストに 1 文字の境界と前後空白の確認が無い。
- comments.tsx で Comment 型を CommentView として再定義し、src/lib/comments.ts の parseCommentId は parseTaskId と同じ正規表現を複製している。page.tsx の import 順も崩れている。テストは要点を押さえるが、ケースがまとめて書かれている。

変更ファイル:

- `src/app/api/tasks/[id]/comments/[commentId]/route.ts` +21 −0（code）
- `src/app/api/tasks/[id]/comments/route.ts` +26 −0（code）
- `src/app/tasks/[id]/comments.tsx` +103 −0（code）
- `src/app/tasks/[id]/page.tsx` +4 −1（code）
- `src/lib/comments.ts` +90 −0（code）
- `src/lib/db/migrations.ts` +14 −0（code）
- `tests/comments.test.ts` +60 −0（test）

コミット:

- `d3f3bae タスク詳細画面にコメント機能を追加`

## 採点方法

試行前に固定した手順（`docs/poc/answer-key/W2/grading.md`）で採点した。


- <strong>受け入れテスト 40</strong>: 隠しの E2E 16 件 × 1.875 点 + 型チェック・単体テスト・ビルド 各 10/3 点。
- <strong>介入回数 20</strong>: 20 − 5 ×（「お任せします」で続けさせた回数 + 質問ツールの回数）。手順を終えた時点でコミットが無い、または未コミットの変更が残ると自動で続けさせた（最大 2 回）。
- <strong>設計・テストの質 25</strong>: 候補名・テスト結果・費用を伏せ、管理用ファイルと文書を除いた差分に記号を付けて、独立した採点者 2 名（それぞれ新しいサブエージェント、読む順番も別）が 5 項目 × 0〜5 点で採点。2 名の平均。
- <strong>費用 15</strong>: 15 ×（全試行の最安 / 自分）。

## この結果の制約

- 各候補 2 回（baseline 1 回）なので、1〜2 点の差は誤差の範囲です。
- 無人の実行なので、確認・承認を前提にした工程（Feature Dev の設計案の選択、Compound Engineering のレビュー後の修正指示）は評価できていません。
- 子セッションの許可リストでは、サーバーをバックグラウンドで起動するコマンドや、環境変数を前に付けたスクリプトの実行が拒否されます。そのため実サーバー・ブラウザでの確認はどの候補もできておらず、Compound Engineering #2 のレビューは途中で止まりました。
- ブラインドレビューの採点者は人ではなくサブエージェント（同じモデル系統）です。採点者間で 3 点以上の差が出た項目はありませんでした。
- Superpowers #2 は、採点スクリプトの不具合（next dev が自動生成する AGENTS.md の扱い、残った開発サーバー）を直してからやり直した結果です。破棄した 1 回目（$0.52）は集計に含めていません。

## 判断の記録

- <strong>費用の上限</strong>: コーディネーターの式で決めた。規模係数は W2 baseline の実額 ÷ W1 baseline の平均 = $0.34 ÷ $0.15 = 2.21。候補ごとの上限は「W1 平均 × 規模係数 × 5（最大 $9.5）」。
  - baseline: W1 平均 $0.15 → 上限 $1.71（試行時の打ち切り $0.77、W2 の最高額 $0.34）
  - Superpowers: W1 平均 $0.17 → 上限 $1.87（試行時の打ち切り $0.85、W2 の最高額 $0.38）
  - Feature Dev: W1 平均 $0.17 → 上限 $1.90（試行時の打ち切り $0.86、W2 の最高額 $0.39）
  - gstack: W1 平均 $0.46 → 上限 $5.05（試行時の打ち切り $2.29、W2 の最高額 $1.01）
  - Compound Engineering: W1 平均 $1.78 → 上限 $9.50（試行時の打ち切り $8.92、W2 の最高額 $3.35）
  実際の試行は、この式が届く前に、より厳しい W1 平均 × 5 を `--max-budget-usd` の打ち切り額にして実行した。どちらの上限にも達した試行は無い。
- <strong>介入の数え方</strong>: 手順を終えた時点でコミットが無い、または未コミットの変更が残るときに、定型の「お任せします」で続けさせ、その回数を数えた（試行前に固定）。`next dev` が自動で作る `AGENTS.md` は候補の作業ではないので、未コミットの変更から除いた。
- <strong>Superpowers #2 のやり直し</strong>: 1 回目は上記の `AGENTS.md` と、残った開発サーバーによる終了待ちで、介入が誤って 2 回送られた。条件が崩れたので破棄し、スクリプトを直してから同じ条件でやり直した。他の試行はこの不具合に当たっていない（介入が送られていないか、送られた理由が本当の未コミットの修正だった）。
- <strong>Compound Engineering #2 のレビューの停止</strong>: `/ce-code-review` が「スクリプトの実行を承認してください」と止まった。ただしコードはコミット済みで作業ツリーもきれいだったので、固定したルールどおり介入には数えていない。
- <strong>試行の並列度</strong>: 最初は 2 本並列で始めた。子セッションがそろって 3917 番ポートでサーバーを起動しようとするため、取り違えが起きないよう、途中から 1 本ずつ順に実行した。結果的に取り違えは起きていない。
- <strong>ブラインドレビューの対象</strong>: 文書（`*.md`）と候補の管理用ファイルは差分から除いた。gstack #1 の CLAUDE.md への追記と、Compound Engineering の計画書は採点対象外。レビュー担当は人ではなく、互いに独立したサブエージェント 2 名。
- <strong>W1 との後方互換</strong>: 次の変更は W2 以降だけに効く。W1 を同じ手順で再実行したときの動きは変わらない。
  - 作業ブランチは W1 では作らない。
  - 介入は既定で 0 回。
  - 費用の上限は既定で無し。

## 次の対応

- W3（曖昧な要望から要件を固める）では、質問への定型回答シートを用意し、確認の工程を持つ候補（Superpowers の brainstorming、gstack の /office-hours、Compound Engineering の /ce-brainstorm）が無人でも働く条件にする。
- 子セッションの許可リストに、試行用コピー内でのサーバー起動（バックグラウンド実行）を加えるか検討する（権限設定の変更なのでユーザーの承認が必要）。W6 の UI 検証では必須になる。
- gstack の /review が修正を未コミットのまま終える点は、W4 以降でも同じか記録する。

## 補足: 新文言での Feature Dev 再試行

元の試行では、課題文の末尾の定型文（旧文言「…課題文に書かれていないことはお任せします。…」）を受けて、Feature Dev が「無人実行のため」と探索・設計案の比較・レビューの工程を省いていました。そこで、工程を省かないよう明記した新文言（`POC_TASK_SUFFIX=new`）で Feature Dev だけを 2 回やり直しました。<strong>元の点数・順位は置き換えません</strong>（この節は参考値）。

<strong>新文言では、2 回ともレビュー役のサブエージェント（code-reviewer）を 1 体ずつ使いました。</strong>どちらも「確信度の高い指摘なし」で、コードの修正にはつながっていません。探索役（code-explorer）と設計役（code-architect）は 2 回とも使わず、設計案を並べて比べる工程も、確認の質問もありませんでした。#4 は許可リストの範囲（`npx next dev` と `curl -s`）で開発サーバーを立て、API の状態コードを実際に確かめています（元の試行では、どの候補も実サーバーでの確認ができていませんでした）。

受け入れテスト（16/16）・介入（0 回）は元と同じで、ブラインドレビューは平均 23.0 → 23.9 点とわずかに上がりました（テストの網羅が厚くなった分）。一方、費用が平均 $0.38 → $0.53（約 1.4 倍）に増えて費用の点が下がり、合計は平均 96.2 点 → 93.4 点になりました。参考までに元の表に並べると Superpowers（95.3）を下回り、候補の中では 2 位に相当します。差は 2 点ほどで、各 2 回の試行では誤差の範囲です。

| 試行 | 点数 | 受け入れ / 40 | 介入 / 20 | 設計・テスト / 25 | 費用 / 15 | 費用 | 時間（分） | サブエージェント | 使われた Skill |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| **元の Feature Dev（旧文言 #1・#2 の平均）** | 96.2 | 40.0 | 20 | 23 | 13.2 | $0.38 | 1.7 | 0 | — |
| 新文言 #3 | 93.8 | 40.0 | 20 | 24 | 9.8 | $0.51 | 2.1 | 1（code-reviewer ×1） | — |
| 新文言 #4 | 93.0 | 40.0 | 20 | 23.8 | 9.2 | $0.54 | 2.9 | 1（code-reviewer ×1） | — |
| **新文言の平均（2 回）** | 93.4 | 40.0 | 20 | 23.9 | 9.5 | $0.53 | 2.5 | 1 | — |

点数は元の W2 と同じ採点基準（`score_w2.py --supplement`）。費用の点の基準（最安）は元の 9 試行の値に固定した。設計・テストの質は、再試行の 2 試行だけを対象にしたブラインドレビュー（採点者 2 名の平均）。

### 試行ごとの様子

- **新文言 #3**（93.8 点）: 既存コードを読んでそのまま実装し、型チェック・単体テスト・ビルドの後に code-reviewer 1 体でレビュー（指摘なし）。レビューの結果を待たずに一度コミットし、届いた結果を読んで「追加の修正なし」と報告した。テストは 70 行で、投稿日時の順・SQL に見える本文・削除の権限を独立したケースで確かめており、ブラインドレビューのテストの項目は 2 名とも 5 点。
- **新文言 #4**（93.0 点）: 実装後、code-reviewer 1 体のレビュー（指摘なし）と並行して、開発サーバーを立てて API の状態コード（201・400・401・403・404）を確かめてからコミットした。サーバーの起動・停止のための複合コマンドや `pkill` は何度か許可リストで拒否され、残ったサーバーは `run-trial.sh` が止めた。投稿フォームと削除ボタンを別の部品に分け、既存の `createTask` と同じ形の関数にしており、設計の項目は 2 名とも 4.5 点。`next dev` が書き出した `AGENTS.md` は候補がコミットせず、`run-trial.sh` の残りの拾い上げで差分に入った（採点の対象外）。

### 判断の記録（補足）

- <strong>条件</strong>: 元の W2 と同じく、作業ブランチの上で始め、介入の上限 2 回（`POC_MAX_NUDGES=2`）、費用の打ち切り $0.86（元の試行で使った W1 の Feature Dev 平均 × 5）。2 回とも介入は不要で、費用は上限の約 6 割（$0.51・$0.54）で終わった。評価用アプリ・課題文・プラグインの固定コミットは元の W2 と同じ。
- <strong>ブラインドレビュー</strong>: 元と同じ基準（`docs/poc/answer-key/W2/grading.md`）・同じ手順（候補名を伏せた差分に記号 S01・S02 を振り、互いに独立した新しいサブエージェント 2 名が別の順番で読む）で、再試行の 2 試行だけを採点した。元の 9 試行の作業用コピーは残っていないため、元の試行と並べて読ませることはできていない。点の目安（5 = 指摘なし、4 = 軽微な指摘 1〜2 点…）は同じなので大きくはずれないと見ているが、元の点数と 1 点未満の差は比べられない。採点者 2 名の差が 3 点以上の項目は無かった。
- <strong>採点の分け方</strong>: 再試行の結果は `results/workflow/W2/supplement/`（ブラインドレビューは `supplement/review/`）に置き、元の 9 試行の `scores.json`・`review/`・レポートの元の節は変えていない（再生成して差分が無いことを確認）。費用の点の基準は元の 9 試行の最安に固定し、それより安い場合は 15 点で頭打ちにする。
- <strong>並列度</strong>: 他の W の試行と同時に動いていたため、再試行は 1 本ずつ順に実行した（開発サーバーのポート 3917 の取り違えも起きない）。

### 試行間の独立性の確認結果

再試行 2 回とも `transcript.isolation_suspects` は空（自分の作業用コピーの外を参照した形跡なし）。正解データを読んだ形跡（`answer_key_access`）も無い。

