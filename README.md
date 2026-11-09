# skills-poc-20261109

新規開発プロジェクト向けの Claude Code 標準構成（Skills / Plugins / MCP）と、比較検討中ツールの PoC 計画をまとめたリポジトリです。

## 導入済みの必須ツール

| 種別 | ツール | 提供元 | リポジトリ | 導入方法 | 設定箇所 |
|---|---|---|---|---|---|
| MCP | GitHub MCP | GitHub | [github/github-mcp-server](https://github.com/github/github-mcp-server) | リモート MCP（`api.githubcopilot.com/mcp/`） | `.mcp.json` |
| MCP | Playwright MCP | Microsoft | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | `npx @playwright/mcp@0.0.84` | `.mcp.json` |
| Skill | Frontend Design | Anthropic | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 固定コミットから vendoring | `.claude/skills/frontend-design` |
| Skill | Web Design Guidelines | Vercel | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines) | 固定コミットから vendoring | `.claude/skills/web-design-guidelines` |
| Skill | Webapp Testing | Anthropic | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/webapp-testing) | 固定コミットから vendoring | `.claude/skills/webapp-testing` |
| Skill | Skill Creator | Anthropic | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/skill-creator) | 固定コミットから vendoring | `.claude/skills/skill-creator` |
| Skill | gh stack（stacked PR の作成・同期・マージ） | GitHub | [github/gh-stack](https://github.com/github/gh-stack/tree/main/skills/gh-stack) | 固定コミットから vendoring | `.claude/skills/gh-stack` |
| Skill | gh（エージェントから GitHub CLI を使う際の作法） | GitHub | [cli/cli](https://github.com/cli/cli/tree/trunk/skills/gh) | 固定コミットから vendoring | `.claude/skills/gh` |
| Plugin | Impeccable | Paul Bakaus | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | marketplace `pbakaus/impeccable` | `.claude/settings.json` |
| Plugin | Security Guidance | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance) | marketplace `claude-plugins-official` | `.claude/settings.json` |
| Plugin | UI/UX Pro Max | nextlevelbuilder | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | marketplace `nextlevelbuilder/ui-ux-pro-max-skill` | `.claude/settings.json` |

### 採用技術・利用サービスに応じて追加するもの

`scripts/add-stack.sh <stack>...` で、該当するプロジェクトにだけ追加します（`.mcp.json`・`.claude/skills/`・`.claude/settings.json` を更新）。

| stack | 対象 | 種別 | ツール | 提供元 | リポジトリ | 認証 |
|---|---|---|---|---|---|---|
| `typescript` | TypeScript を使う場合 | Plugin | TypeScript LSP（`typescript-language-server` を別途インストール） | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/typescript-lsp) | 不要 |
| `react-nextjs` | React / Next.js を使う場合 | Skill | React Best Practices | Vercel | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices) | 不要 |
| `react-nextjs` | 〃 | Skill | Composition Patterns | Vercel | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/composition-patterns) | 不要 |
| `react-nextjs` | 〃 | Skill | React View Transitions | Vercel | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-view-transitions) | 不要 |
| `react-nextjs` | 〃 | MCP | Next.js DevTools MCP（`next-devtools-mcp@0.4.0`。Next.js 16 以上の `next dev` 起動中に使う） | Vercel | [vercel/next-devtools-mcp](https://github.com/vercel/next-devtools-mcp) | 不要 |
| `supabase` | Supabase を使う場合 | MCP | Supabase MCP（`https://mcp.supabase.com/mcp?project_ref=${SUPABASE_PROJECT_REF}`。開発用プロジェクトに限定） | Supabase | [supabase/mcp](https://github.com/supabase/mcp) | 初回接続時に OAuth（`/mcp` から） |
| `vercel` | Vercel を使う場合 | MCP | Vercel MCP（`https://mcp.vercel.com`） | Vercel | [Vercel MCP ドキュメント](https://vercel.com/docs/agent-resources/vercel-mcp) | 初回接続時に OAuth（`/mcp` から） |
| `sentry` | Sentry を使う場合 | MCP | Sentry MCP（`https://mcp.sentry.dev/mcp`） | Sentry | [getsentry/sentry-mcp](https://github.com/getsentry/sentry-mcp) | 初回接続時に OAuth（`/mcp` から） |
| `cloudflare` | Cloudflare を使う場合 | MCP | Cloudflare API MCP（`https://mcp.cloudflare.com/mcp`） | Cloudflare | [cloudflare/mcp](https://github.com/cloudflare/mcp) | OAuth |
| `cloudflare` | 〃 | MCP | Cloudflare Docs MCP（`https://docs.mcp.cloudflare.com/mcp`） | Cloudflare | [cloudflare/mcp-server-cloudflare](https://github.com/cloudflare/mcp-server-cloudflare) | 不要 |

```bash
scripts/add-stack.sh typescript react-nextjs supabase vercel
```

**このリポジトリでは `typescript` と `react-nextjs` を適用済み**です（PoC 用アプリが TypeScript + Next.js のため）。

- TypeScript LSP を使うには、`npm install -g typescript-language-server typescript` で言語サーバーを入れておく必要があります。
- Supabase MCP を使う場合は、開発用プロジェクトの project ref を環境変数 `SUPABASE_PROJECT_REF` に設定します（`.env.example` 参照）。

Skills の固定コミットとライセンスは [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md) を参照してください。

### 初回セットアップ

1. GitHub MCP 用に、対象リポジトリだけに絞った Fine-grained PAT を発行し、シェルの環境変数に設定します（`.env.example` に推奨権限を記載。実値はコミットしない）。

   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=<your-token>
   ```

2. このディレクトリで Claude Code を起動し、プロジェクトの marketplace・プラグイン・MCP サーバーの信頼確認を承認します。
3. `/plugin` で `security-guidance` と `impeccable` が有効、`/mcp` で `github` と `playwright` が接続済みであることを確認します。
4. security-guidance の LLM レビューには Python 3.8 以上と Claude Code のサインイン（または API キー）が必要です。
5. stacked PR を使う場合は、`gh extension install github/gh-stack` で gh stack を入れ、`git config rerere.enabled true` を設定します（Git 2.36 以上が必要。リポジトリ側で Stacked PRs が有効になっている必要があります）。
6. Impeccable の設計フックやエンジンを使う場合は、必要に応じて `npx impeccable install --providers=claude --scope=project` を実行します。

### 更新

- Skills: `scripts/sync-skills.sh <anthropics/skills のコミット> <vercel-labs/agent-skills のコミット> <github/gh-stack のコミット> <cli/cli のコミット>` を実行し、差分をレビューしてからコミット
- Playwright MCP: `.mcp.json` のバージョンを上げて PR でレビュー
- Plugins: `/plugin` から更新し、動作確認後にチームへ周知

## 開発標準

AI 駆動開発の標準基盤・設計原則: [docs/standards/ai-software-factory-engineering-standard.md](docs/standards/ai-software-factory-engineering-standard.md)（v1.1 Draft、レビュー記録は [docs/standards/REVIEW.md](docs/standards/REVIEW.md)）

## Issue・PR テンプレート

各プロジェクト共通の Issue Forms（機能要望 / 不具合報告 / 技術的負債）・PR テンプレートと、AI エージェント向けの Issue・PR 記述ルールを `templates/github/` に置いています。調査結果・設計方針・記入済みサンプルは [docs/github-templates/README.md](docs/github-templates/README.md) を参照してください。

```bash
scripts/add-github-templates.sh <対象リポジトリのパス> [--with-check]
```

既存のファイルは上書きしません。`--with-check` を付けると、PR 本文の必須見出しを検証する GitHub Actions も配置します。

**このリポジトリにも `--with-check` 付きで適用済み**です（`.github/`、`docs/github-writing.md`）。

## 比較検討中ツールの PoC

計画書: [docs/poc/PLAN.md](docs/poc/PLAN.md)

| カテゴリ | 位置づけ | ツール | 提供元 | リポジトリ |
|---|---|---|---|---|
| 開発ワークフロー | 第一候補 | Superpowers | Jesse Vincent（obra） | [obra/superpowers](https://github.com/obra/superpowers) |
| 開発ワークフロー | 対抗候補 | Feature Dev | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/feature-dev) |
| 開発ワークフロー | 対抗候補 | gstack | Garry Tan | [garrytan/gstack](https://github.com/garrytan/gstack) |
| 開発ワークフロー | 対抗候補 | Compound Engineering | Every | [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) |
| 開発ワークフロー | 併用検証（§5.5） | Ponytail | Dietrich Gebert | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| セキュリティ監査 | 第一候補 | Claude Security | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/claude-security) |
| セキュリティ監査 | 対抗候補 | Cloudflare Security Audit | Cloudflare | [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) |
| PR レビュー | 第一候補 | Code Review | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review) |
| PR レビュー | 対抗候補 | PR Review Toolkit | Anthropic | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/pr-review-toolkit) |

開発ワークフローは 4 候補の得意範囲を比べるため、8 つのシナリオ（小さな変更、要件定義、大きな変更、バグ修正、UI の検証と PR 作成、学習効果、自律実行など）で全候補を試します（計画書 §5.1）。勝者を決めた後、Ponytail を併用した場合の効果も検証します（§5.5）。

候補の切り替えは `scripts/poc-profile.sh <profile>` で行います（`.claude/settings.local.json` に書き込むため、チーム共有の設定は変わりません）。

## 運用上の注意

- MCP の認証情報やトークンを Git にコミットしない（`.env*` と `.claude/settings.local.json` は `.gitignore` 済み）。
- GitHub MCP には業務上必要な最小限の権限だけを付与する。マージ・ファイル削除・リポジトリ作成は `.claude/settings.json` で毎回確認する設定にしている。
- `.claude/settings.json` の `permissions.allow` で、確認なしで実行してよい操作を決めている（git の読み取り・コミット、`agent/*` ブランチへの push、`npm ci` / `npm test` / `npm run typecheck` / `npm run build`、PoC のスクリプト、GitHub の読み取りと PR の作成・更新）。force push・`main` を含む push・削除やまとめて送る push（`--delete` / `-d` / `--mirror` / `--all` / `--tags` / `--prune`）、`git diff` などの `--output` / `--ext-diff` は `ask` で毎回確認する（`ask` は `allow` より優先される）。`cat` や `grep` などファイルを読むコマンドは、`.env` を読めてしまうため許可していない。`git push origin agent/x :other` のような「空の送り元」による削除は書式上確認に回せないため、`main` の削除・force push は GitHub の Ruleset（`docs/github-setup/rulesets/`）で防ぐ。
- Sentry MCP / Cloudflare MCP はトークンをファイルに書かず OAuth で認証する。Cloudflare API MCP は Cloudflare の API をほぼすべて操作できるため、開発用アカウントで、必要な権限だけを許可する。
- Supabase MCP は開発用プロジェクトにだけ接続する。やむを得ず本番プロジェクトにつなぐ場合は、URL に `&read_only=true` を付けて読み取り専用にする。
- Vercel MCP は OAuth で認証し、必要に応じて `https://mcp.vercel.com/<team-slug>/<project-slug>` で対象プロジェクトを限定する。
- Skills による品質チェックだけに頼らず、CI で Lint・型チェック・テスト・静的解析を実施する。
