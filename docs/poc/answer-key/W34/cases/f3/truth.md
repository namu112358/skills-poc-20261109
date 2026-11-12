# F3 の正解（本体は正しく、テストが弱い PR）

本体（`src/lib/extend.ts`・API）に不具合は無い。正解はテストの問題だけ。

| ID | 種類 | 場所 | 仕組み（核心） | 正しい直し方 |
|---|---|---|---|---|
| T1 | 何も確かめていないテスト | `tests/extend.test.ts` の "adds days to the due date" | 期待値を同じ関数（`extendDueDate`）で計算して比べているので、計算が間違っていても必ず通る | 期待値を具体的な日付で書く（例: `2026-11-20` + 5 日 = `2026-11-25`） |
| T2 | 例外が出ないことだけを見ている | `tests/extend.test.ts` の "works across months"・"handles a completed task" | `assert.doesNotThrow` だけで、月をまたいだ結果も、完了したタスクが延長できないこと（`reason: "done"`）も確かめていない | 結果の値（`2026-12-03`、`{ ok: false, reason: "done" }`）を確かめる |
| T3 | 誤った入力を確かめていない | `tests/extend.test.ts` の `validateExtendInput` | 正しい値（7）が通ることだけで、0・31・小数・文字列を拒むことを確かめていない。範囲や整数の判定を壊しても通る | 境界（1・30 が通り、0・31 が拒まれる）と、整数でない値を確かめる |
| T4 | 結果を確かめていない | `tests/extend.test.ts` の "extends a task" | `result.ok` だけを見て、期限が延びて保存されたか（`dueDate`）を確かめていない | 延長後の期限と、DB に保存された値を確かめる |

### おとり（不具合ではない変更。指摘したら誤った指摘）

| ID | 場所 | 見た目 | 正しい理由 |
|---|---|---|---|
| D1 | `extendDueDate`（`new Date(\`${dueDate}T00:00:00Z\`)` と `setUTCDate`） | 時差・月末で壊れそう | UTC の 0 時を基準にし、UTC の日付で足しているので、時差の影響を受けず、月・年をまたいでも正しい |
| D2 | `validateExtendInput` の `(body as …)?.days` | 型の断定 | `null`・オブジェクトでない値も `undefined` になり、続く `typeof` で拒まれる |

- 一致の基準: 場所（テストの名前）と問題の核心を述べていれば一致。「テストを足すべき」だけの一般論は一致にしない。
- 直した後の採点は、変異（`mutants.json` の f3。本体に 8 つの改変を入れ、参加者のテストで何個を落とせるか）と、隠しテスト（本体を壊していないか）で行う。
