# CLAUDE.md

- 応答・ドキュメントは日本語で書く。
- `.mcp.json`・`.claude/settings.json` に認証情報を直接書かない。トークンは環境変数（`${VAR}`）で参照する。
- `.claude/skills/` 配下の vendored Skills は手で編集しない。更新は `scripts/sync-skills.sh` で行い、`.claude/skills/SOURCES.md` を更新する。
- PoC の候補ツールは `.claude/settings.json` に追加しない。`scripts/poc-profile.sh` で `.claude/settings.local.json` 側に適用する。
- 本番環境への反映、データ削除、セキュリティ上重要な設定変更は、実行前に必ずユーザーの承認を得る。
  - 例外: PoC の試行で起動する子セッションの許可リスト（`scripts/poc/run-trial.sh` が渡す `--allowedTools`）の変更は、作業用コピーの中でしか効かないため、Skills 検証のコーディネーターが判断してよい。変更した内容と理由は、その W の `report.md` の「判断の記録」に残す。`.claude/settings*.json` の権限、ネットワーク許可の追加、データ削除、Ruleset・`.github/workflows` の変更は、この例外に含まない。

- Issue・PR を作成するときは @docs/github-writing.md の記述ルールに従う。
