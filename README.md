# skills-poc-20261109

AI エージェント（主に Claude Code）を使って新規開発を進めるときの標準を決め、各プロジェクトに配るためのリポジトリです。次の 4 つの問いに、PoC と調査の結果を根拠にして答えます。

| 問い | 今の答え（要約） | 状態 |
|---|---|---|
| [1. どの Skills・プラグイン・MCP を入れるか](#1-どの-skillsプラグインmcp-を入れるか) | 必須の 11 件と、採用技術ごとの追加分を固定のバージョンで入れる | 決定。追加候補は調査のみ |
| [2. どのような開発ワークフローを組むか](#2-どのような開発ワークフローを組むか実装レビュー自己改善) | 実装は既定でワークフロー用のプラグインを使わず、難しい作業だけ Compound Engineering を使う。品質を上げる手段は、Issue に運用の事情を書くこと | 暫定（PoC の途中） |
| [3. どのような GitHub の設定が必要か](#3-どのような-github-の設定が必要か) | Rulesets・Advanced Security・Actions の標準設定と、Issue・PR のテンプレートを入れる | 決定 |
| [4. AI への指示と管理をどうするか](#4-ai-への指示と管理をどうするか) | 指示ファイルと設定は雛形から始め、プロジェクト固有の罠を理由つきで書く。権限は最小にし、Skills と指示を CI で機械的に検査する | 決定 |

全体の設計原則は [開発標準](docs/standards/ai-software-factory-engineering-standard.md)（v1.1 Draft、レビュー記録は [docs/standards/REVIEW.md](docs/standards/REVIEW.md)）にまとめています。

## 1. どの Skills・プラグイン・MCP を入れるか

### 必須のもの

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

Skills の固定コミットとライセンスは [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md) を参照してください。

### 採用技術・利用サービスに応じて追加するもの

`scripts/add-stack.sh --dest <対象リポジトリのパス> <stack>...` で、該当するプロジェクトにだけ追加します（`.mcp.json`・`.claude/skills/`・`.claude/settings.json` を更新）。`--dest` を省略すると、このリポジトリ自身に追加します。

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
scripts/add-stack.sh --dest ../my-project typescript react-nextjs supabase vercel
```

- TypeScript LSP を使うには、`npm install -g typescript-language-server typescript` で言語サーバーを入れておく必要があります。
- Supabase MCP を使う場合は、開発用プロジェクトの project ref を環境変数 `SUPABASE_PROJECT_REF` に設定します（`.env.example` 参照）。

### 追加の候補と、重なりの整理（調査のみ）

- 共通ツールの候補は Context7 と Chrome DevTools MCP、採用技術別の候補は Supabase の Postgres の Skill と Python・Go などの LSP です。どれも実際には動かしていません（[docs/tool-candidates/README.md](docs/tool-candidates/README.md)）。
- UI/UX のツールは、4 つを同時に有効にすると「画面を作る」役割が 3 つ重なり、勧めが互いに逆になる箇所があります。Impeccable を作る担当、Web Design Guidelines をレビュー担当にし、UI/UX Pro Max を既定で無効にする整理案があります。まだ決定ではありません（[docs/tool-candidates/ui-ux-overlap.md](docs/tool-candidates/ui-ux-overlap.md)）。

### 更新

- Skills: `scripts/sync-skills.sh <anthropics/skills のコミット> <vercel-labs/agent-skills のコミット> <github/gh-stack のコミット> <cli/cli のコミット>` を実行し、差分をレビューしてからコミットします。指紋（`scripts/skills.lock.json`）も作り直されます。
- Playwright MCP: `.mcp.json` のバージョンを上げて、PR でレビューします。
- Plugins: `/plugin` から更新し、動作を確かめてからチームに周知します。

## 2. どのような開発ワークフローを組むか（実装・レビュー・自己改善）

ワークフロー用のプラグインの候補を、評価用のアプリ（`poc-app/`）を題材にしたシナリオで比べています。結果の一覧は [docs/poc/results/workflow/summary.md](docs/poc/results/workflow/summary.md)、計画と評価基準は [docs/poc/PLAN.md](docs/poc/PLAN.md) にあります。**ここに書く答えは暫定です。** 試行は多くが候補ごとに 2 回で、差の多くは試行のばらつきと同じくらいの大きさです。

### 実装

- **既定では、ワークフロー用のプラグインを使わない。**
  - 小さな変更、バグ修正、UI の検証、続けて行う作業、無人での実行（W1・W5〜W9）では、プラグインなしが品質で同点以上、費用は最も安かった。
  - 実在する OSS の課題（W11）でも品質の差はなく、プラグインを使うと費用が 1.8〜3.8 倍になった。
- **既存コードを横断する変更、DB の移行、テストのない古いコードの改修だけ、Compound Engineering を使う。** 人の承認つきで使う。
  - W4・W14・W15・W19 では品質が 1 位だった。
  - 一方、費用は 4〜15 倍かかった。
- **品質を上げる一番の手段は、Issue に運用の事情を書くこと。** プラグインを増やすことではない。
  - W12〜W14 で差が出た項目の多くは、聞けば分かる運用の事情（他システムが古い列を読む、など）だった。
  - 質問の数と品質は結びつかなかった。
  - Issue 駆動の流れの案は [docs/poc/notes/issue-driven-flow.md](docs/poc/notes/issue-driven-flow.md)（未決定のメモ）にあります。

### レビュー

- 不具合を見つけるレビュー（W9）では、プラグインなしを含む全試行が満点でした。
- PR レビュー用のツール（Code Review と PR Review Toolkit）の比較と、セキュリティ監査のツール（Claude Security と Cloudflare Security Audit）の比較は、**まだ実施していません**。
- Skills による品質チェックだけに頼らず、CI で Lint・型チェック・テスト・静的解析を実施します。
- 失敗を検査に反映するときの方針（案）は [docs/standards/testing-and-ci-policy.md](docs/standards/testing-and-ci-policy.md) にあります。要点は次の 3 つです。
  - 再発防止は、検出できる一番手前の段（型 → Lint → 単体テスト → 結合 → E2E）に置く。
  - 画面全体の文字やスナップショットをまとめて比べる検査は足さない。
  - PR では変更に関係する検査だけを回し、全件は main で回す。

### 自己改善

- **学習のための記憶用プラグインは入れない。**
  - 続けて作業したとき（W7）、記憶を引き継がない場合でも、決まりに沿ったコードが 1 か所あれば、同じ間違いを避けられた。
  - 記憶を引き継ぐと、かえって費用が増えた（Compound Engineering）。
- **失敗から学んだことは、指示ファイルの「罠」として、理由ときっかけになった事象の記録とセットで書き残す**（4 を参照）。
- **Skills を変えたら、機械的な検査を通す**（4 を参照）。

### 比較している候補

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

候補の切り替えは `scripts/poc-profile.sh <profile>` で行います。`.claude/settings.local.json` に書き込むため、チームで共有する設定は変わりません。

## 3. どのような GitHub の設定が必要か

- **リポジトリの設定**: 新規リポジトリの標準設定（Rulesets、Advanced Security、Actions、Environments、標準ファイル）と、AI エージェントが品質ゲートを迂回できないようにする権限設計は、[docs/github-setup/README.md](docs/github-setup/README.md) にまとめています。
- **Issue・PR のテンプレート**: 各プロジェクト共通の Issue Forms（機能要望 / 不具合報告 / 技術的負債）と PR テンプレート、AI エージェント向けの Issue・PR 記述ルールを、`templates/github/` に置いています。
  - 決めたこと・導入手順（ラベル作成を含む）・記入済みサンプル: [docs/github-templates/README.md](docs/github-templates/README.md)
  - 調査結果と出典: [docs/github-templates/research.md](docs/github-templates/research.md)

```bash
scripts/add-github-templates.sh <対象リポジトリのパス> [--with-check]
```

既存のファイルは上書きしません。`--with-check` を付けると、PR 本文の必須見出しを検証する GitHub Actions も配置します。

## 4. AI への指示と管理をどうするか

### 指示ファイルと設定

各プロジェクトに置く標準構成を、`templates/agents/` に置いています。

- 指示ファイル: `AGENTS.md`・`CLAUDE.md`
- 設定: `.claude/settings.json`（標準のプラグイン・MCP・権限）・`.mcp.json`
- Skills の検査スクリプトと、それを CI で回すワークフロー

標準の Skills は雛形に複製せず、配るときに固定コミットから取得します。

- `AGENTS.md` の「規約」の節は、どのプロジェクトにも共通の規約です。各プロジェクトが書くのは「このリポジトリについて」と「このプロジェクトの罠」の節だけです。
- 規約は言い切りの形で書き、罠は理由と、きっかけになった事象の記録とセットで書きます。書き方と根拠は [開発標準 §2.1](docs/standards/ai-software-factory-engineering-standard.md) の「規約の書き方」にあります。

```bash
scripts/add-agent-templates.sh <対象リポジトリのパス> --with-check
scripts/add-stack.sh --dest <対象リポジトリのパス> <stack>...
```

- `--with-check` を付けると、Skills の検査を CI で回すワークフロー（`.github/workflows/skills-check.yml`）も置きます。`--no-skills` を付けると、標準の Skills を置きません。
- 既存のファイルは上書きしません。設定ファイルは、雛形の中身をすべて含んでいれば（`add-stack.sh` で足しただけなら）そのままにし、雛形から外れていれば知らせます。
- ただし `AGENTS.md` に共通規約の印（`<!-- 共通規約ここから -->` 〜 `<!-- 共通規約ここまで -->`）があれば、その間だけを最新の共通規約に置き換えます。共通規約を更新したあとに再実行すると、各プロジェクトに反映できます。

### 機械的な検査

- `python3 scripts/check-skills.py` で、Skills をモデルを呼ばずに検査します（PyYAML が必要）。
  - vendored Skills: 指紋（`scripts/skills.lock.json`）と内容が一致するか（手で編集されていないか）と、`SOURCES.md` に載っているかを検査します。上流の形式の問題は警告だけにします。
  - 自作の Skills: 次の点を検査します。
    - frontmatter の形式（skill-creator の `quick_validate.py`）
    - `name` とディレクトリ名の一致
    - `SKILL.md` が 500 行以内か
    - 参照先のファイルがあるか
    - 評価ケース（`evals/evals.json`）と発火の評価（`evals/trigger.json`）の定義が正しいか
  - 評価ケースを実際のモデルで動かして採点するのは、費用がかかり結果も毎回ぶれるため、この検査には含めません。必要なときに skill-creator の手順で行います。
- このリポジトリでは、関係するファイルを変えた PR で、`agent-config-check` が上の検査と雛形の一致の検査（`scripts/check-templates.py`）を回します。失敗してもマージは止まりません。止めたい場合は Ruleset の必須チェックに加えます。

### 権限と認証情報

- MCP の認証情報やトークンを Git にコミットしない（`.env*` と `.claude/settings.local.json` は `.gitignore` 済み）。
- GitHub MCP には、業務上必要な最小限の権限だけを付与する。マージ・ファイル削除・リポジトリ作成は、`.claude/settings.json` で毎回確認する設定にしている。
- `.claude/settings.json` の `permissions.allow` で、確認なしで実行してよい操作を決めている。
  - 許可している操作:
    - git の読み取り。`git diff --stat` などよく使う決まった形だけで、引数を自由に付けられる形は許可しない（`--output` や `--no-index` などで、ファイルの書き込みや `.env` の読み取りができるため）
    - コミットと、`agent/*` ブランチへの push
    - `npm ci` / `npm test` / `npm run typecheck` / `npm run build`（このリポジトリだけ）
    - Skills の検査と雛形の一致の検査（`python3 scripts/check-skills.py`・`python3 scripts/check-templates.py`。このリポジトリだけ）。配る雛形では許可しない。エージェントが検査スクリプトを書き換えてから実行すると、任意のコードが確認なしで動くため。配布先では CI（`skills-check`）で必ず検査する。
    - PoC のスクリプト（このリポジトリだけ）
    - GitHub の読み取りと、PR の作成・更新
  - `cat` や `grep` などファイルを読むコマンドは、`.env` を読めてしまうため許可していない。
- 次の push は `ask` で毎回確認する（`ask` は `allow` より優先される）: force push、`main` を含む push、削除やまとめて送る push（`--delete` / `-d` / `--mirror` / `--all` / `--tags` / `--prune`）。
- `git push origin agent/x :other` のような「空の送り元」による削除は、書式の上で確認に回せない。そのため、`main` の削除と force push は GitHub の Ruleset（`docs/github-setup/rulesets/`）で防ぐ。
- Sentry MCP と Cloudflare MCP は、トークンをファイルに書かず OAuth で認証する。Cloudflare API MCP は Cloudflare の API をほぼすべて操作できるため、開発用アカウントで、必要な権限だけを許可する。
- Supabase MCP は、開発用プロジェクトにだけ接続する。やむを得ず本番プロジェクトにつなぐ場合は、URL に `&read_only=true` を付けて読み取り専用にする。
- Vercel MCP は OAuth で認証し、必要に応じて `https://mcp.vercel.com/<team-slug>/<project-slug>` で対象プロジェクトを限定する。

## このリポジトリ自身について

このリポジトリも、標準を使う側の 1 つです。

- **適用している設定**: `typescript` と `react-nextjs` を適用済みです（PoC 用アプリが TypeScript + Next.js のため）。Issue・PR のテンプレートも `--with-check` 付きで適用済みです（`.github/`、`docs/github-writing.md`）。
- **雛形との一致**: ルートの `AGENTS.md` の規約の節、`docs/github-writing.md`、`scripts/check-skills.py` は、雛形と同じ内容に保ちます。ルートの `.claude/settings.json`・`.mcp.json` は、雛形にこのリポジトリだけの設定を足したものにします。この 2 つは、`typescript`・`react-nextjs` の分、`poc-app` 用のフック、PoC と npm のコマンドの許可を足しています。一致しているかは `python3 scripts/check-templates.py` で確かめます。
- **クラウドのセッション**: Claude Code on the web では、開始時に `poc-app` の依存関係が自動で入ります（`.claude/hooks/session-start.sh`）。

### 初回セットアップ

1. GitHub MCP 用に、対象リポジトリだけに絞った Fine-grained PAT を発行し、シェルの環境変数に設定します（`.env.example` に推奨権限を記載。実値はコミットしない）。

   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=<your-token>
   ```

2. このディレクトリで Claude Code を起動し、プロジェクトの marketplace・プラグイン・MCP サーバーの信頼確認を承認します。
3. `/plugin` で `security-guidance` と `impeccable` が有効、`/mcp` で `github` と `playwright` が接続済みであることを確認します。
4. security-guidance の LLM レビューには、Python 3.8 以上と Claude Code のサインイン（または API キー）が必要です。
5. stacked PR を使う場合は、`gh extension install github/gh-stack` で gh stack を入れ、`git config rerere.enabled true` を設定します（Git 2.36 以上が必要。リポジトリ側で Stacked PRs が有効になっている必要があります）。
6. Impeccable の設計フックやエンジンを使う場合は、必要に応じて `npx impeccable install --providers=claude --scope=project` を実行します。
