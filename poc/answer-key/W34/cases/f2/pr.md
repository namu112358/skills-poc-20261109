# PR: タスクの機能を、型・検証・DB の読み書きのファイルに分ける（振る舞いは変えない）

## 概要

`src/lib/tasks.ts` が大きくなり、どこに何があるか分かりにくくなったため、型と値の定義・入力の検証・DB の読み書きを別々のファイルに分けます。テストも同じ単位に分けました。**振る舞いは変えていません。**

## 変更内容

| | 変更前 | 変更後 |
|---|---|---|
| タスクの機能 | `src/lib/tasks.ts` 1 つ | `src/lib/tasks/` の `model.ts`（型・値）・`validation.ts`（入力の検証・ID の検証）・`repository.ts`（DB の読み書き）、まとめて書き出す `index.ts` |
| 呼び出し側 | `@/lib/tasks` | `@/lib/tasks/index` |
| テスト | `tests/tasks.test.ts` | `tests/task-model.test.ts`・`task-validation.test.ts`・`task-repository.test.ts` |
| 振る舞い | — | 変えない |

## 検証結果

- `npm run typecheck`・`npm test` が通ることを確認した。
