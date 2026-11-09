# Vendored Skills（必須）

このディレクトリの Skills は公式リポジトリから**無改変でコピー**し、コミット SHA で固定しています。
更新は `scripts/sync-skills.sh` を実行し、差分をレビューしてからコミットしてください。

| Skill | 提供元 | パス | 固定コミット | ライセンス |
|---|---|---|---|---|
| frontend-design | anthropics/skills | `skills/frontend-design` | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | Apache-2.0（同梱 LICENSE.txt） |
| webapp-testing | anthropics/skills | `skills/webapp-testing` | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | Apache-2.0（同梱 LICENSE.txt） |
| skill-creator | anthropics/skills | `skills/skill-creator` | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | Apache-2.0（同梱 LICENSE.txt） |
| web-design-guidelines | vercel-labs/agent-skills | `skills/web-design-guidelines` | `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62` | MIT |

> `web-design-guidelines` は実行時に `raw.githubusercontent.com/vercel-labs/web-interface-guidelines` から最新ルールを取得します。
> ネットワーク制限のある環境では当該ホストの許可が必要です。
