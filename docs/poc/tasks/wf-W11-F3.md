# 機能追加の依頼（click）

このリポジトリ（click）のテスト用の実行器 `CliRunner` について、次の機能を追加してください。

## 背景

`CliRunner.invoke()` は、余分なキーワード引数（`**extra`）をコマンドの `Context` に渡す。ただし `color` だけは `invoke()` 自身の引数と名前がぶつかるため、`Context` の `color` 設定をテストから渡せない。
テストで端末の対応状況（`Context` の設定）と `color` を同じ呼び出しで指定できるようにしたい。

## 仕様（合意済み）

- `CliRunner.invoke()` に引数 `context_settings`（`Mapping[str, Any] | None`、既定は `None`）を追加する。中身はそのコマンドの `Context` の設定として渡る。
- `context_settings` の設定は、コマンド自身が宣言した `context_settings` より優先される。ただしその呼び出しに限り、コマンドの宣言は書き換えない。
- `context_settings={"color": ...}` は `Context` の `color` になり、`invoke()` の `color` 引数より優先される。`{"color": None}`・`{}`・`None` のときは従来どおり `invoke()` の `color` 引数で決まる。
- 同じ設定を `extra` と `context_settings` の両方で渡したときは、キーワード引数を 2 回渡したときと同じ `TypeError`（`multiple values for keyword argument '<名前>'`）にする。
- docstring とドキュメントに追記する。
