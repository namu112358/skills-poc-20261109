# C5 の正解（機械的な名前の変更に紛れた不具合）

| ID | 種類 | 場所 | 仕組み（核心） | 正しい直し方 |
|---|---|---|---|---|
| B1 | 公開 API の非互換 | `src/lib/tasks.ts` の `Task` 型・`validateTaskInput`（`need("assigneeId")`）と、それをそのまま返す・受け取る API（`/api/tasks`・`/api/tasks/:id`） | `Task` を JSON にそのまま返しているため、API の応答の項目名が `assignee` から `assigneeId` に変わる。リクエストも `assigneeId` しか読まないため、今までどおり `assignee` を送ると、作成は 400、更新（PATCH）は黙って無視されて 200（担当者が変わらないのに成功に見える）。PR の説明「API の入出力は変えない」に反する | API の境界で `assignee` との対応を取る（応答を詰め直す・リクエストの `assignee` を読む）か、API の変更として扱い PR の説明と利用者への周知を直す |
| B2 | 名前の変更の漏れ | `src/lib/tasks.ts` の `listTasks` の SQL（`assignee_id AS assignee`） | 列に `assignee` という別名を付けているのに、`toTask` は `row.assignee_id` を読むため、一覧（画面・`GET /api/tasks`）だけ担当者が `undefined`（空欄）になる。`getTask` は正しいので詳細画面は正しく、テストも一覧の担当者を確かめていないので気づかない | 別名を外して `assignee_id` のまま読む。一覧の担当者を確かめるテストを足す |

### おとり（不具合ではない変更。指摘したら誤った指摘）

| ID | 場所 | 見た目 | 正しい理由 |
|---|---|---|---|
| D1 | マイグレーション 3 の `ALTER TABLE tasks RENAME COLUMN assignee TO assignee_id` | 既存の DB で列の変更が危ない・インデックスや外部キーが壊れる | 規約 7 どおり末尾に新しい番号で追加している。SQLite（3.25 以降、Node の `node:sqlite` も該当）は列名の変更でインデックス・外部キーの参照も付け替える |
| D2 | マイグレーション 1 の `assignee` と `tasks_assignee` のインデックス名が残っている | 書き換え漏れ | 既存のマイグレーションは書き換えない（規約 7）。インデックスの名前は動作に関係しない |

- 一致の基準: 場所（ファイルと関数）と仕組みの核心の両方を述べていれば一致。B1 は「API の応答の項目名が変わる」「`assignee` を送るクライアントが壊れる／更新が黙って無視される」のどれかを述べていれば一致。
