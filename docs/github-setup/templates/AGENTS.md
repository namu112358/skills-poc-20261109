# AGENTS.md

AI エージェント共通の作業ルール。プロジェクトに合わせてコマンドと構成を書き換えること。

## コマンド

- 依存関係のインストール: `npm ci`
- Lint: `npm run lint`
- 型チェック: `npm run typecheck`
- テスト: `npm test`
- ビルド: `npm run build`

PR を作る前に、上記をすべて実行して成功させる。

## 作業の流れ

1. `main` から作業ブランチ（`feature/<内容>`、`fix/<内容>`）を作る。
2. 変更とテストを同じ PR に含める。
3. PR テンプレートの項目をすべて埋める。「AI エージェントの利用」にチェックを入れる。
4. CI が失敗したら、原因を直してから push する。

## 禁止事項

- `main` へ直接 push しない。`git push --force` をしない。
- PR を自分で承認・マージしない。Auto merge を有効にしない（人間が判断する）。
- CI・テスト・Lint を無効化、スキップ、緩和しない（`.skip`、`--no-verify`、閾値の引き下げ、Workflow の変更を含む）。必要な場合は理由を書いて人間に依頼する。
- `.github/`、`CODEOWNERS`、`CLAUDE.md`、`AGENTS.md`、`.claude/` を変更しない（依頼された場合を除く）。
- リポジトリの設定、Rulesets、Secrets、Environments を変更しない。
- `.env` などの認証情報を読まない、出力しない、コミットしない。新しい環境変数は `.env.example` に名前と説明だけを追加する。
- 本番環境へのデプロイ、データの削除をしない。
- 新しい依存関係や GitHub Action を追加する場合は、PR の説明に理由と代替案を書く。
