# poc-app（PoC 評価用アプリ）

タスク管理アプリ。Next.js（App Router）+ TypeScript + SQLite（Node 標準の `node:sqlite`）。

## コマンド

- `npm run typecheck` — 型チェック
- `npm test` — 単体テスト（Node 標準のテストランナー `node:test`）
- `npm run build` — 本番ビルド

## DB

- `src/lib/db/index.ts` の `getDb()` が共有の接続を返す。接続先は環境変数 `DATABASE_PATH`（既定は `:memory:`。サーバーを起動するたびに `src/lib/db/seed.ts` の初期データから始まる）。
- スキーマは `src/lib/db/migrations.ts`（`PRAGMA user_version` で管理）。
- テストでは `openDb()` で独立したインメモリ DB を作り、`src/lib/` の関数の引数 `db` に渡す。

## コーディング規約

1. データの取得・絞り込みは `src/lib/` の関数に置き、ページコンポーネントには表示の処理だけを書く。
2. URL のクエリパラメータは、型ガード（例: `isTaskStatus`）で検証してから使う。不正な値は「指定なし」として扱う。
3. 画面の文言は日本語にする。
4. 新しい外部ライブラリは追加しない。
5. ロジックを追加・変更したら `tests/` に単体テストを追加する。
6. 変更は依頼された範囲にとどめる。
7. スキーマを変えるときは `src/lib/db/migrations.ts` の末尾に新しい番号のマイグレーションを追加する。既存のマイグレーションは書き換えない。
8. SQL に値を埋め込むときは必ずプレースホルダ（`?` / `:name`）を使い、文字列連結で組み立てない。
