# CLAUDE.md

- 応答・ドキュメントは日本語で書く。
- `.mcp.json`・`.claude/settings.json` に認証情報を直接書かない。トークンは環境変数（`${VAR}`）で参照する。
- `.claude/skills/` 配下の vendored Skills は手で編集しない。更新は `scripts/sync-skills.sh` で行い、`.claude/skills/SOURCES.md` を更新する。
- PoC の候補ツールは `.claude/settings.json` に追加しない。`scripts/poc-profile.sh` で `.claude/settings.local.json` 側に適用する。
- 本番環境への反映、データ削除、セキュリティ上重要な設定変更は、実行前に必ずユーザーの承認を得る。

- Issue・PR を作成するときは @docs/github-writing.md の記述ルールに従う。
