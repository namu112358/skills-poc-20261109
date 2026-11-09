# skills-poc-20261109

新規開発プロジェクト向けの Claude Code 標準構成（Skills / Plugins / MCP）と、比較検討中ツールの PoC 計画をまとめたリポジトリです。

## 導入済みの必須ツール

| 種別 | ツール | 導入方法 | 設定箇所 |
|---|---|---|---|
| MCP | GitHub MCP | リモート MCP（`api.githubcopilot.com/mcp/`） | `.mcp.json` |
| MCP | Playwright MCP | `npx @playwright/mcp@0.0.84` | `.mcp.json` |
| Skill | Frontend Design（Anthropic） | 固定コミットから vendoring | `.claude/skills/frontend-design` |
| Skill | Web Design Guidelines（Vercel） | 固定コミットから vendoring | `.claude/skills/web-design-guidelines` |
| Skill | Webapp Testing（Anthropic） | 固定コミットから vendoring | `.claude/skills/webapp-testing` |
| Skill | Skill Creator（Anthropic） | 固定コミットから vendoring | `.claude/skills/skill-creator` |
| Plugin | Impeccable | marketplace `pbakaus/impeccable` | `.claude/settings.json` |
| Plugin | Security Guidance（Anthropic） | marketplace `claude-plugins-official` | `.claude/settings.json` |
| Plugin | UI/UX Pro Max | marketplace `nextlevelbuilder/ui-ux-pro-max-skill` | `.claude/settings.json` |

### 採用技術・利用サービスに応じて追加するもの

`scripts/add-stack.sh <stack>...` で、該当するプロジェクトにだけ追加します（`.mcp.json` と `.claude/skills/` を更新し、`.claude/settings.json` の `enabledMcpjsonServers` に登録）。

| stack | 対象 | 追加されるもの | 認証 |
|---|---|---|---|
| `react-nextjs` | React / Next.js を使う場合 | Skills: React Best Practices、Composition Patterns、React View Transitions（Vercel）<br>MCP: Next.js DevTools（`next-devtools-mcp@0.4.0`。Next.js 16 以上の `next dev` 起動中に使う） | 不要 |
| `sentry` | Sentry を使う場合 | MCP: Sentry（`https://mcp.sentry.dev/mcp`） | 初回接続時に OAuth（`/mcp` から） |
| `cloudflare` | Cloudflare を使う場合 | MCP: Cloudflare API（`https://mcp.cloudflare.com/mcp`）、Cloudflare Docs（`https://docs.mcp.cloudflare.com/mcp`） | API は OAuth、Docs は不要 |

```bash
scripts/add-stack.sh react-nextjs sentry
```

**このリポジトリでは `react-nextjs` を適用済み**です（PoC 用アプリが Next.js のため）。

Skills の固定コミットとライセンスは [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md) を参照してください。

### 初回セットアップ

1. GitHub MCP 用に、対象リポジトリだけに絞った Fine-grained PAT を発行し、シェルの環境変数に設定します（`.env.example` に推奨権限を記載。実値はコミットしない）。

   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=<your-token>
   ```

2. このディレクトリで Claude Code を起動し、プロジェクトの marketplace・プラグイン・MCP サーバーの信頼確認を承認します。
3. `/plugin` で `security-guidance` と `impeccable` が有効、`/mcp` で `github` と `playwright` が接続済みであることを確認します。
4. security-guidance の LLM レビューには Python 3.8 以上と Claude Code のサインイン（または API キー）が必要です。
5. Impeccable の設計フックやエンジンを使う場合は、必要に応じて `npx impeccable install --providers=claude --scope=project` を実行します。

### 更新

- Skills: `scripts/sync-skills.sh <anthropics/skills のコミット> <vercel-labs/agent-skills のコミット>` を実行し、差分をレビューしてからコミット
- Playwright MCP: `.mcp.json` のバージョンを上げて PR でレビュー
- Plugins: `/plugin` から更新し、動作確認後にチームへ周知

## 比較検討中ツールの PoC

計画書: [docs/poc/PLAN.md](docs/poc/PLAN.md)

| カテゴリ | 第一候補 | 対抗候補 |
|---|---|---|
| 開発ワークフロー | Superpowers | Feature Dev |
| セキュリティ監査 | Claude Security | Cloudflare Security Audit |
| PR レビュー | Code Review | PR Review Toolkit |

ワークフローは勝者を決めた後、Ponytail を併用した場合の効果も検証します（計画書 §5.5）。

候補の切り替えは `scripts/poc-profile.sh <profile>` で行います（`.claude/settings.local.json` に書き込むため、チーム共有の設定は変わりません）。

## 運用上の注意

- MCP の認証情報やトークンを Git にコミットしない（`.env*` と `.claude/settings.local.json` は `.gitignore` 済み）。
- GitHub MCP には業務上必要な最小限の権限だけを付与する。マージ・ファイル削除・リポジトリ作成は `.claude/settings.json` で毎回確認する設定にしている。
- Sentry MCP / Cloudflare MCP はトークンをファイルに書かず OAuth で認証する。Cloudflare API MCP は Cloudflare の API をほぼすべて操作できるため、開発用アカウントで、必要な権限だけを許可する。
- Supabase MCP / Vercel MCP（推奨）を追加する場合は、開発環境のみに接続し、本番への書き込み権限を付けない。
- Skills による品質チェックだけに頼らず、CI で Lint・型チェック・テスト・静的解析を実施する。
