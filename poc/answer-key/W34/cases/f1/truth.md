# F1 の正解（作りすぎ・重複・不具合が混ざった PR）

| ID | 種類 | 場所 | 仕組み（核心） | 正しい直し方 |
|---|---|---|---|---|
| B1 | 不具合 | `src/lib/tasks.ts` の `updateTask`（`UPDATE tasks SET title = ?, status = ?, assignee = ?, due_date = ?`） | 更新の SQL に `priority` が無いため、`PATCH` で優先度を変えても保存されず、応答も元の値のまま。テストは作成・絞り込みだけで、更新を確かめていない | `UPDATE` に `priority = ?` を足す。更新のテストを足す |
| P1 | 作りすぎ（YAGNI・KISS） | `src/lib/attributes/registry.ts`（`AttributeRegistry`・`whereClause`・グローバルな `attributeRegistry`）と `src/lib/attributes/priority.ts`（読み込み時の登録） | 項目 1 つのために、汎用の登録の仕組み・SQL の組み立て・読み込み時の副作用での登録を作っている。「今後足しやすいように」は、今の要件に無い | 優先度の値・表示名の定数と型ガード（`isTaskPriority`）を `tasks.ts` に置き、SQL は `status` と同じ形で書く。登録の仕組みは消す |
| P2 | 重複（DRY） | `src/app/api/tasks/route.ts` の `PRIORITIES = ["high", "medium", "low"]`、`src/app/tasks/page.tsx` の `PRIORITY_LABELS`（定義の `labels`・`values` と同じ内容） | 優先度の値と表示名を 3 か所に書き写している。値を増やすと直し漏れが出る（定義を作ったのに使っていない） | 1 か所の定数（と型ガード）を使う |

### おとり（不具合ではない変更。指摘したら誤った指摘）

| ID | 場所 | 見た目 | 正しい理由 |
|---|---|---|---|
| D1 | マイグレーション 3 の `ALTER TABLE tasks ADD COLUMN priority … DEFAULT 'medium' CHECK (…)` | 既存の行の扱い・制約の追加が危ない | 規約 7 どおり末尾に追加している。既定値があるので既存の行は「中」になり、SQLite は既定値つきの列の追加と CHECK を受け付ける |

- 一致の基準: 場所と仕組みの核心の両方を述べていれば一致。P1 は「1 つの項目のための汎用の仕組みで作りすぎ」、P2 は「値・表示名の書き写し（定義を使っていない）」を述べていれば一致。
- 直した後の採点は、隠しテスト（`hidden.test.ts`）・差分の行数・登録の仕組みが残っているか・書き写しが残っているかで行う（`grade_w34.py`）。
