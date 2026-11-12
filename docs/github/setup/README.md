# GitHub 新規プロジェクト 初期設定手順書

AI エージェント（Claude Code など）が実装・PR 作成を行う前提で、新規リポジトリに入れる設定をまとめる。プランごとの利用条件や料金は変わるため、各節の公式ドキュメントで確認すること。

- 評価: **必須**（原則設定）／**推奨**（規模・スタックに応じて）／**任意**（特定の用途のみ）
- 目的: セキュリティ／品質保証／開発効率／AI 権限制御／運用・保守
- 個人: 1 人で開発し、AI 専用 ID を使う構成。チーム: 2 人以上。
- 設定の変更はセキュリティ上重要なため、実施前に管理者の承認を得る。

## 1. 最初に決めること: AI を動かす ID

GitHub のゲートは「誰が操作したか」で判定する。AI が人間と同じアカウント・権限で動くと、承認・Bypass・管理者権限を区別できない。

| ID | ロール | 用途 |
|---|---|---|
| 人間 | Admin | Ruleset・Secrets・Environments の管理、PR と本番デプロイの承認 |
| AI 専用 ID（GitHub App 推奨、無理ならマシンユーザー） | **Write** | push、PR 作成、Issue 操作 |

AI のトークン（Fine-grained PAT／App 権限）は対象リポジトリに限定し、次だけを付与する。

- 付与する: Contents・Pull requests・Issues（Read and write）、Metadata・Actions・Checks（Read）
- **付与しない: Workflows、Administration、Secrets、Environments、Variables、Commit statuses（Write）**

AI 専用 ID を用意できない場合（AI が本人名義の最小権限 PAT で動く）は、自分の PR を承認できないため Required approvals を 0 にするしかない。この場合「AI がマージしない」ことは Claude Code の `permissions` でしか止められない（強制力は弱い）。Auto merge は無効にする。

## 2. Settings → General

[公式](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges)

| 項目 | 推奨値 | 評価 | 目的 |
|---|---|---|---|
| Visibility | Private（公開する OSS のみ Public） | 必須 | セキュリティ |
| Default branch | `main` | 必須 | 運用・保守 |
| Squash merge | 有効のみ（Merge commit・Rebase は無効） | 必須 | 品質保証 |
| Automatically delete head branches | 有効 | 必須 | 運用・保守 |
| Allow auto-merge | 有効（承認 0 の構成では無効） | 推奨 | 開発効率 |
| Wiki | 無効（ドキュメントは `docs/` で PR レビュー） | 推奨 | 運用・保守 |
| Projects／Discussions | 無効（使う場合のみ有効） | 任意 | 運用・保守 |

## 3. Settings → Rules → Rulesets

[公式](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)。対象は `Default branch`。

| 項目 | 個人 | チーム | 評価 | 目的 |
|---|---|---|---|---|
| Bypass list | **空** | **空** | 必須 | AI 権限制御 |
| Restrict deletions／Block force pushes | 有効 | 有効 | 必須 | セキュリティ |
| Require linear history | 有効 | 有効 | 推奨 | 品質保証 |
| Require a pull request before merging | 有効 | 有効 | 必須 | 品質保証・AI 権限制御 |
| └ Required approvals | 1（AI 専用 ID がなければ 0） | 1〜2 | 必須 | AI 権限制御 |
| └ Dismiss stale approvals | 有効 | 有効 | 必須 | AI 権限制御 |
| └ Require approval of the most recent reviewable push | 有効 | 有効 | 必須 | AI 権限制御 |
| └ Require review from Code Owners | 任意 | 有効 | 推奨 | AI 権限制御 |
| └ Require conversation resolution | 有効 | 有効 | 推奨 | 品質保証 |
| Require status checks to pass | 有効（発行元を **GitHub Actions** に固定） | 同左＋up to date 必須 | 必須 | 品質保証・AI 権限制御 |
| Require code scanning results | CodeQL を使う場合 | 同左 | 推奨 | セキュリティ |
| タグ Ruleset（`v*`）: 更新・削除の禁止 | 有効 | 有効 | 推奨 | 運用・保守 |

注意:

- Bypass list に AI の ID・GitHub App・Dependabot を入れない。チームで緊急用の Bypass を置く場合も、Admin を「For pull requests only」にする。
- Status check の発行元を固定しないと、同じ名前の成功ステータスを API で送って偽装できる。
- CODEOWNERS は base ブランチ（main）のものが使われる。`.github/`、`CODEOWNERS`、`CLAUDE.md`、`AGENTS.md`、`.claude/` を人間のオーナーに割り当てる。AI 専用 ID をオーナーにしない。

## 4. Settings → Advanced Security

[公式](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security)

| 項目 | 推奨値 | 評価 | 目的 | 条件 |
|---|---|---|---|---|
| Dependency graph／Dependabot alerts／security updates | 有効 | 必須 | セキュリティ | 無料 |
| Dependabot version updates | `dependabot.yml` を置く（`github-actions` を含める） | 推奨 | 運用・保守 | 無料 |
| CodeQL default setup | 有効 | Public: 必須／Private: 推奨 | セキュリティ | Private は Code Security が必要 |
| Secret scanning＋Push protection | 有効 | Public: 必須／Private: 推奨 | セキュリティ・AI 権限制御 | Private は Secret Protection が必要 |
| Push protection の Bypass | 指定したレビュアーのみ（AI を含めない） | 推奨 | AI 権限制御 | Secret Protection が必要 |
| Dependency review | `actions/dependency-review-action` を Required check に | 推奨 | セキュリティ | Private は Code Security が必要 |
| Private vulnerability reporting | 有効 | Public: 推奨 | 運用・保守 | 無料 |
| Alerts へのアクセス | Admin とセキュリティ担当のみ | 必須 | セキュリティ | ― |

Private で Secret Protection／Code Security を使わない場合は、CI に Gitleaks（シークレット検出）と依存関係の監査（`npm audit` など）を入れる。CodeQL CLI はライセンスなしで Private のコードに使えない。

## 5. Settings → Actions → General

[公式](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)

| 項目 | 推奨値 | 評価 | 目的 |
|---|---|---|---|
| Actions permissions | GitHub 製＋許可リストの Action のみ | 必須 | セキュリティ |
| Require actions to be pinned to a full-length commit SHA | 有効 | 必須 | セキュリティ |
| Workflow permissions | Read repository contents and packages | 必須 | セキュリティ・AI 権限制御 |
| Allow GitHub Actions to create and approve pull requests | **無効** | 必須 | AI 権限制御 |
| Fork PR workflows | 外部コントリビューターは承認が必要（Public） | Public: 必須 | セキュリティ |

Workflow のルール:

- 先頭で `permissions: contents: read`、必要なジョブだけ追加する。
- `pull_request_target` で PR のコードを実行しない。
- Required check のジョブに `if:` や `paths` フィルターを付けない（スキップは成功扱い、または待機のままになる）。
- 本番クラウドの認証は OIDC（`id-token: write`）にし、クラウド側で `sub` を `environment:production` に限定する。

## 6. Environments

[公式](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)

| Environment | デプロイ対象 | 保護 | 評価 |
|---|---|---|---|
| `staging` | `main` | なし | 推奨 |
| `production` | `main` とタグ `v*` のみ | Required reviewers（人間のみ）＋Prevent self-review＋管理者の Bypass 無効 | 本番があれば必須 |

- 本番の Secrets は `production` の Environment Secrets にだけ置く（OIDC を優先）。AI の開発環境には開発用の値だけを渡す。
- Private リポジトリで Required reviewers を使えるのは Enterprise Cloud のみ。Pro／Team では、デプロイ対象を `main` に限定し（main は承認必須）、本番デプロイを `workflow_dispatch` かタグで起動する。
- ロールバック: 直前のタグを指定してデプロイを再実行し、原因の PR は Revert PR で取り消す（直接 push しない）。

## 7. リポジトリ標準ファイル

| ファイル | 評価 | 目的 | 書く内容 |
|---|---|---|---|
| `CLAUDE.md` | 必須 | AI 権限制御 | ビルド・テストのコマンド、禁止事項（main への push、CI の無効化、Secrets の読み取り、自己マージ） |
| `AGENTS.md` | 推奨 | AI 権限制御 | 複数エージェント共通の指示。`CLAUDE.md` から `@AGENTS.md` で取り込む |
| `.claude/rules/` | 任意 | 品質保証 | パス単位のルール（テスト、マイグレーションなど） |
| `.claude/settings.json` | 推奨 | AI 権限制御 | `.env` の読み取り、force push、`gh pr merge`、設定を変える `gh api` を `deny`／`ask` |
| `.github/CODEOWNERS` | チーム: 必須 | AI 権限制御 | §3 の注意を参照 |
| `.github/dependabot.yml` | 推奨 | 運用・保守 | `github-actions`＋使用するパッケージマネージャー |
| `.github/workflows/ci.yml` | 必須 | 品質保証 | Lint・型チェック・テスト・ビルド。§5 のルールに従う |
| `.github/ISSUE_TEMPLATE/`・`.github/pull_request_template.md` | 必須 | 品質保証 | [docs/github/templates/README.md](../templates/README.md) の標準テンプレートを使う |
| `SECURITY.md` | Public: 必須 | 運用・保守 | 脆弱性の報告窓口 |
| `.env.example` | 必須 | セキュリティ | 変数名だけ。`.env` は `.gitignore` に入れる |

## 8. AI 駆動開発のチェック

| 要件 | 対策 |
|---|---|
| main へ直接 push できない | PR 必須＋Bypass 空＋AI は Write |
| CI を無効化してマージできない | Required checks（発行元固定）＋AI に Workflows 権限なし＋`.github/` を CODEOWNERS で保護 |
| Ruleset を変更できない | AI を Admin にしない＋Administration 権限なし |
| 自分の PR を承認・マージしない | AI 専用 ID で PR 作成＋承認 1 以上＋最新 push の承認＋Actions による PR 承認を無効 |
| 本番 Secrets を渡さない | Environment Secrets＋OIDC＋AI に Secrets／Environments 権限なし |
| AI の PR も同じゲートを通る | Bypass に AI・Dependabot を入れない |

## 9. 複数リポジトリへの展開

- **Template Repository** でコピーされるのは**ファイルだけ**（§7）。§2〜§6 の設定は作成後に別途行う。
- Organization（Team 以上）では、**Organization Rulesets**（§3）と **Security Configurations**（§4）で一括適用する。特定の Team だけに適用する場合は、Custom Property（例: `team`）を定義し、Ruleset の対象を `props.team:<name>` で絞る。
- Organization の Public な `.github` リポジトリで、Issue／PR テンプレート・SECURITY.md を共通化できる（CODEOWNERS、dependabot.yml、Workflow は不可）。
- CI の共通化は Reusable Workflows、設定の自動化は `gh api`（[REST API](https://docs.github.com/en/rest)）、リポジトリが多い場合は [Terraform GitHub Provider](https://registry.terraform.io/providers/integrations/github/latest/docs)。

## 10. セットアップ手順

1. §1 の AI の ID と権限を決める。
2. Template Repository からリポジトリを作る（`gh repo create <owner>/<repo> --private --template <template>`）。
3. §2〜§5 を設定する（Organization の場合は Organization 側の適用を確認する）。
4. CI を一度実行し、Required status checks にジョブ名を登録して、発行元が GitHub Actions であることを確認する。
5. AI 専用 ID を Write で追加する。
6. 本番がある場合は §6 を設定する。
7. AI のトークンで、main への push、Workflow の変更、自分の PR の承認、CI 失敗時のマージがすべて拒否されることを確認する。
