# GitHub 新規開発プロジェクト 初期設定標準手順書

- 版: 1.0（2026-11-09）
- 対象: GitHub.com（GitHub Enterprise Server は対象外）
- 前提: Claude Code などの AI エージェントが実装・テスト・PR 作成を行う
- 確認方法: 2026-11-09 に GitHub Docs の該当ページを確認した。GitHub の画面名・プラン条件は頻繁に変わるため、適用前に [§9 公式 URL](#9-公式-url-一覧) で最新の記述を確認すること。

この手順書は、新しいリポジトリを作るたびに上から順に実施することを想定している。設定値を反映するテンプレートとスクリプトは同じディレクトリにある。

| 置き場所 | 内容 |
|---|---|
| [`templates/`](templates/) | 新規リポジトリへコピーする標準ファイル（CODEOWNERS、CI、dependabot.yml、PR テンプレートなど） |
| [`templates/rulesets/`](templates/rulesets/) | main ブランチ用 Ruleset の JSON（個人開発用とチーム開発用） |
| [`../../scripts/github-setup/apply-repo-settings.sh`](../../scripts/github-setup/apply-repo-settings.sh) | Repository Settings を `gh api` で反映するスクリプト（既定はドライラン） |

> この手順書が扱う設定の多くは「セキュリティ上重要な設定変更」に当たる。スクリプトを `--apply` で実行する前、また Web UI で変更する前に、リポジトリ管理者の承認を得ること。

---

## 目次

1. [前提となる違い](#1-前提となる違い)
2. [AI エージェントの権限設計（最初に決めること）](#2-ai-エージェントの権限設計最初に決めること)
3. [設定項目と推奨値](#3-設定項目と推奨値)
   - A. General / B. Rulesets / C. Advanced Security / D. Actions / E. Environments / F. 標準ファイル
4. [AI 駆動開発で特に注意する事項](#4-ai-駆動開発で特に注意する事項)
5. [複数リポジトリへの展開と自動化](#5-複数リポジトリへの展開と自動化)
6. [セットアップ手順（チェックリスト）](#6-セットアップ手順チェックリスト)
7. [設定後の検証](#7-設定後の検証)
8. [ロールバック・緊急時の手順](#8-ロールバック緊急時の手順)
9. [公式 URL 一覧](#9-公式-url-一覧)
10. [未確定事項・注意](#10-未確定事項注意)

分類の凡例:

- **評価**: 必須（新規作成時に原則設定）／推奨（規模・技術スタックに応じて設定）／任意（特定の用途でのみ設定）
- **目的**: セキュリティ／品質保証／開発効率／AI 権限制御／運用・保守

---

## 1. 前提となる違い

### 1.1 Personal Account と Organization

| 観点 | Personal Account のリポジトリ | Organization のリポジトリ |
|---|---|---|
| 権限ロール | オーナー（Admin 相当）と Collaborator（Write 相当）のみ | Read / Triage / Write / Maintain / Admin、カスタムロール、Team |
| Team・CODEOWNERS | Team を使えない。CODEOWNERS はユーザー名で指定 | `@org/team` で指定できる |
| Rulesets | リポジトリ単位のみ | リポジトリ単位＋Organization Rulesets（Team 以上） |
| Bypass 対象 | Repository admin、GitHub App、Dependabot など（Team は不可） | 上記＋Team、Maintain／Write ロール、カスタムロール |
| Security Configurations | なし（リポジトリごとに設定） | Organization から一括適用できる |
| GHAS 製品（Secret Protection / Code Security） | 購入不可（Team / Enterprise の Organization が対象） | Team / Enterprise で購入可能 |
| Actions のポリシー | リポジトリごと | Organization で上限を決め、リポジトリはそれ以下に絞る |

複数人開発や本番運用があるプロジェクトは、Organization（GitHub Team 以上）で作ることを推奨する。個人アカウントの Private リポジトリでは、Secret Scanning、CodeQL、Dependency Review、本番承認ゲートを GitHub の機能だけでは用意できない（§3.C、§3.E）。

### 1.2 Public と Private

| 機能 | Public（全プラン） | Private（Free） | Private（Pro / Team） | Private（Enterprise Cloud） |
|---|---|---|---|---|
| Rulesets（ブランチ／タグ） | ○ | × | ○ | ○ |
| Push Rulesets | ―（Private / Internal 専用） | × | Organization のみ | ○ |
| Dependency Graph／Dependabot Alerts／Security Updates／Version Updates | ○（無料） | ○（無料） | ○（無料） | ○（無料） |
| CodeQL（Code Scanning） | ○（無料） | × | Code Security の購入が必要（Team） | Code Security が必要 |
| Secret Scanning／Push Protection（リポジトリ） | ○（無料） | × | Secret Protection の購入が必要（Team） | Secret Protection が必要 |
| Dependency Review Action | ○ | × | Code Security が必要 | Code Security が必要 |
| Environments・Environment Secrets・デプロイ対象ブランチ制限 | ○ | × | ○ | ○ |
| Environment の Required Reviewers・Wait Timer・カスタム保護ルール | ○ | × | **×** | ○ |

ポイント:

- **Private リポジトリで本番デプロイの承認ゲート（Required Reviewers）を使えるのは Enterprise Cloud だけ**。Pro / Team では代わりの対策が必要になる（§3.E）。
- Private リポジトリをあとで Public に変えると、それまで有料だった機能が無料で使えるようになる。逆に Public から Private に変えると、Free プランでは Environment の保護ルールとシークレットが無効になる。

### 1.3 プラン

| プラン | 対象 | 主な違い |
|---|---|---|
| GitHub Free | 個人／Organization | Private では Rulesets・Environments が使えない |
| GitHub Pro | 個人 | Private で Rulesets、CODEOWNERS 必須化、Environments（承認ゲートを除く）が使える |
| GitHub Team | Organization | Pro の内容＋Organization Rulesets、Security Configurations、GHAS 製品の購入 |
| GitHub Enterprise Cloud | Organization／Enterprise | Team の内容＋Private での Environment 承認ゲート、Enterprise 単位のポリシー、監査ログのストリーミングなど |

料金は [GitHub の料金ページ](https://github.com/pricing) で確認すること。

### 1.4 GitHub Advanced Security（GHAS）のライセンス

2025 年 4 月から、GHAS は次の 2 製品に分かれ、GitHub Team でも購入できるようになった。

| 製品 | 主な内容 | 課金 |
|---|---|---|
| **GitHub Secret Protection** | Secret Scanning、Push Protection、AI によるシークレット検出、カスタムパターン、委任バイパス（Delegated Bypass）、Security Overview | アクティブコミッター 1 人あたりの月額（発表時は 19 USD） |
| **GitHub Code Security** | Code Scanning（CodeQL）、CodeQL CLI、Copilot Autofix、Dependency Review、Dependabot のカスタム自動トリアージルール、Security Campaigns、Security Overview | アクティブコミッター 1 人あたりの月額（発表時は 30 USD） |

課金上の注意:

- **アクティブコミッター**: 有効化したリポジトリに、直近 90 日以内にコミットを push した人。Organization 全体で 1 人 1 回だけ数える。**GitHub App の bot は数えない**。マシンユーザー（AI 専用の通常アカウント）は 1 人として数えられる可能性が高い。
- Public リポジトリでは Code Scanning・Secret Scanning・Dependency Review が無料（AI Scan と Agentic Autofix は Public でも AI クレジットを消費する）。
- Security Configuration を Organization の既定にすると、新しい Private リポジトリにも自動で適用され、課金対象が増える。適用範囲は意識して決めること。
- 予算の上限設定（Limit usage when budget limit is reached）は、新しく有効化することを止めるだけで、すでに有効なリポジトリは止まらない。
- 購入前に、無料の [Secret risk assessment](https://docs.github.com/en/code-security/securing-your-organization/understanding-your-organizations-exposure-to-leaked-secrets/about-secret-risk-assessment)（Organization 向け）で漏えい状況を確認できる。

**Private リポジトリでの使い分け**:

- Secret Protection: 「認証情報を Git に入れない」ための機能。AI がコードやログ、`.env` を扱う以上、Private で AI 開発をするなら**最優先で購入を検討する**。
- Code Security: 「脆弱なコードと依存関係を入れない」ための機能。CodeQL がスタックに対応していて、外部に公開するサービスであれば推奨する。依存関係の確認は無料の Dependabot でも一部代わりになる。
- どちらも買えない／買わない場合は、CI に OSS ツール（Gitleaks などのシークレット検出、Semgrep などの静的解析、`npm audit` などの依存関係の監査）を入れる。**CodeQL CLI は、GHAS のライセンスなしに Private のコードへ使うことは利用規約で認められていない**ので注意する。

### 1.5 リポジトリ個別設定と Organization 共通設定

| 設定 | リポジトリ個別 | Organization 共通 |
|---|---|---|
| マージ方式・ブランチ自動削除 | Settings → General | なし（テンプレートやスクリプトで揃える） |
| ブランチ保護 | Repository Rulesets | Organization Rulesets（Team 以上） |
| セキュリティ機能 | Settings → Advanced Security | Security Configurations＋Global Settings |
| Actions のポリシー | Settings → Actions → General | Organization の Actions 設定が上限になる |
| Secrets | Repository／Environment Secrets | Organization Secrets（リポジトリを選んで公開） |
| Community Health Files | リポジトリ内のファイル | Organization の Public な `.github` リポジトリ |

Organization 側の設定が「上限」になり、リポジトリ側で緩めることはできない。Organization Ruleset とリポジトリ Ruleset は合算され、もっとも厳しい内容が適用される。

### 1.6 Web UI と API

| 区分 | 設定 |
|---|---|
| **API・CLI で自動化できる** | General のマージ設定、Rulesets、Dependabot、Secret Scanning、CodeQL Default Setup、Actions の権限、Environments、Secrets、Custom Properties、Security Configurations、Organization Rulesets |
| **ファイルで管理する** | CODEOWNERS、dependabot.yml、Workflow、Issue／PR テンプレート、SECURITY.md、CLAUDE.md など |
| **Web UI での確認を推奨** | Status Check の発行元（App）の選択、Alerts へのアクセス権限、GitHub App のインストール、課金・予算 |

API の一覧は [§9](#9-公式-url-一覧) を参照。

---

## 2. AI エージェントの権限設計（最初に決めること）

GitHub の品質ゲートは「誰が操作したか」で判定する。AI が人間と同じアカウント・同じ権限で動くと、Ruleset の Bypass、自己承認の禁止、管理者権限のいずれも、AI と人間を区別できない。**リポジトリを作る前に、AI をどの ID で動かすかを決める。**

### 2.1 推奨構成

| ID | ロール | 用途 |
|---|---|---|
| 人間（オーナー／メンテナー） | Admin | Ruleset・Secrets・Environments の管理、PR の承認、本番デプロイの承認 |
| **AI 専用 ID**（GitHub App を推奨。難しければマシンユーザー） | **Write**（Maintain・Admin にしない） | ブランチへの push、PR 作成、Issue 操作 |
| 他の開発者（チームの場合） | Write | 実装、レビュー |

AI 専用 ID に与える権限（Fine-grained PAT または GitHub App の権限）:

| 権限 | 値 | 理由 |
|---|---|---|
| Contents | Read and write | ブランチへの push に必要 |
| Pull requests | Read and write | PR の作成・更新 |
| Issues | Read and write（必要な場合） | Issue の起票・更新 |
| Metadata | Read | 必須 |
| Actions | Read | CI の結果確認 |
| Checks／Commit statuses | Read | CI の結果確認（Write にすると成功の偽装に使えるため付与しない） |
| **Workflows** | **付与しない** | `.github/workflows/` を変更できなくする（CI の無効化を防ぐ） |
| **Administration** | **付与しない** | Rulesets・リポジトリ設定を変更できなくする |
| **Secrets／Environments／Variables** | **付与しない** | Secrets の読み書きや Environment の保護ルール変更を防ぐ |
| Security events／Dependabot alerts | Read（脆弱性の修正を AI に任せる場合のみ） | アラートの確認 |

Fine-grained PAT は対象リポジトリだけに絞り、有効期限を設ける（最長でも 90 日を目安）。

### 2.2 AI 専用 ID を用意できない場合（個人開発の最小構成）

AI が人間のトークンで動く場合、PR の作成者は人間になる。GitHub では自分の PR を承認できないため、承認数を 1 以上にすると誰もマージできなくなる。この場合は次の構成にする。

- Ruleset の Required Approvals は 0。Required Status Checks、Force Push の禁止、ブランチ削除の禁止は有効にする。
- **Bypass List を空にする**（オーナー本人も PR 経由でしか main を変更できないようにする）。
- AI に渡すトークンは §2.1 と同じ最小権限の Fine-grained PAT にする（オーナーのログイン済み `gh` や Classic PAT を AI に使わせない）。トークンに Administration 権限がなければ、オーナー名義でも Ruleset は変更できない。
- AI がマージしないことは、GitHub 側では強制できない。Claude Code の `permissions` で `gh pr merge` や GitHub MCP のマージツールを `ask` または `deny` にする（[`templates/.claude/settings.json`](templates/.claude/settings.json)）。**これはクライアント側の制御であり、強制力は GitHub の設定より弱い**ことを理解したうえで使う。
- Auto Merge は無効にする（承認が 0 のため、AI が有効にすると CI 成功と同時にマージされる）。

---

## 3. 設定項目と推奨値

表の「個人」は 1 人で開発し AI 専用 ID を使う構成、「チーム」は 2 人以上の開発を指す。§2.2 の最小構成は注記で示す。

### A. Settings → General

| 項目 | 画面のパス | 推奨値 | 評価 | 目的 | 理由・利用条件 | API（`PATCH /repos/{owner}/{repo}`） |
|---|---|---|---|---|---|---|
| Visibility | General → Danger Zone → Change visibility | **Private**（OSS として公開する場合のみ Public） | 必須 | セキュリティ | 作成時に決める。Public にする前に Secret Scanning と履歴の確認を行う | `visibility` |
| Default branch | General → Default branch | `main` | 必須 | 運用・保守 | Ruleset の対象（`~DEFAULT_BRANCH`）になる | `default_branch` |
| Allow squash merging | General → Pull Requests | **有効**（コミットメッセージは「PR タイトルと説明」） | 必須 | 品質保証 | 1 PR = 1 コミットにし、履歴の追跡と revert を簡単にする | `allow_squash_merge`、`squash_merge_commit_title=PR_TITLE`、`squash_merge_commit_message=PR_BODY` |
| Allow merge commits | 同上 | **無効** | 必須 | 品質保証 | Linear History と両立しない | `allow_merge_commit=false` |
| Allow rebase merging | 同上 | **無効**（コミット単位の履歴を残したい場合のみ有効） | 推奨 | 品質保証 | AI は細かいコミットを多く作るため、Squash に統一したほうが履歴が読みやすい | `allow_rebase_merge=false` |
| Always suggest updating pull request branches | 同上 | 有効 | 推奨 | 開発効率 | base が進んだときに更新を促す | `allow_update_branch=true` |
| Automatically delete head branches | 同上 | **有効** | 必須 | 運用・保守 | マージ済みブランチが残らないようにする | `delete_branch_on_merge=true` |
| Allow auto-merge | 同上 | チーム: 有効／個人: 有効／§2.2 の構成: **無効** | 推奨 | 開発効率 | 承認と CI が揃った時点でマージする。承認が必須でない構成では、AI がゲートを素通りしてマージできるため無効にする | `allow_auto_merge` |
| Wiki | General → Features | **無効** | 推奨 | 運用・保守 | Wiki は PR レビューを通らない。ドキュメントはリポジトリ内の `docs/` で管理する | `has_wiki=false` |
| Projects | 同上 | 無効（リポジトリ単位の Project を使う場合のみ有効） | 任意 | 運用・保守 | Organization／ユーザーの Projects はこの設定と関係なく使える | `has_projects` |
| Discussions | 同上 | 無効（OSS でユーザーとの Q&A が必要な場合のみ有効） | 任意 | 運用・保守 | ― | `has_discussions` |
| Issues | 同上 | 有効 | 推奨 | 開発効率 | AI への作業指示を Issue で管理する場合に使う | `has_issues` |
| Require contributors to sign off on web-based commits | General | 無効（DCO を求める OSS のみ有効） | 任意 | 運用・保守 | ― | `web_commit_signoff_required` |

### B. Settings → Rules → Rulesets

画面のパス: **Settings → Rules → Rulesets → New ruleset → New branch ruleset**。旧来の Branch protection rules ではなく Rulesets を使う（複数のルールを重ねられ、Organization から一括適用でき、評価モードと Bypass の記録がある）。

利用条件: Public は全プラン、Private は Pro / Team / Enterprise Cloud。Organization Rulesets は Team 以上。

JSON: 個人用 [`templates/rulesets/main-solo.json`](templates/rulesets/main-solo.json)、チーム用 [`templates/rulesets/main-team.json`](templates/rulesets/main-team.json)。API は `POST /repos/{owner}/{repo}/rulesets`。

| 項目（UI 表記） | 個人 | チーム | 評価 | 目的 | 理由 |
|---|---|---|---|---|---|
| Ruleset name／Enforcement status | `main-protection`／**Active** | 同左 | 必須 | 品質保証 | 新しく追加するルールは、既存リポジトリでは一度 Evaluate（Enterprise のみ）で影響を見てから Active にする |
| Target branches | **Include default branch** | 同左＋必要に応じて `release/**` | 必須 | 品質保証 | ブランチ名を変えても追従する |
| Bypass list | **空** | **空**（緊急用に Repository admin を「For pull requests only」で追加するのは可） | 必須 | AI 権限制御 | AI 専用 ID・AI が使う GitHub App を**絶対に追加しない**。「Always allow」は直接 push も許可するため使わない |
| Restrict deletions | 有効 | 有効 | 必須 | セキュリティ | main の削除を防ぐ |
| Block force pushes | 有効 | 有効 | 必須 | セキュリティ | 履歴の書き換えを防ぐ |
| Require linear history | 有効 | 有効 | 推奨 | 品質保証 | Squash／Rebase のみ。revert と bisect が簡単になる |
| Require a pull request before merging | **有効** | **有効** | 必須 | 品質保証・AI 権限制御 | main への直接 push を禁止する（Bypass 以外は push できない） |
| └ Required approvals | **1**（§2.2 の構成は 0） | **1**（重要なシステムは 2） | 必須 | 品質保証・AI 権限制御 | PR 作成者は自分の PR を承認できないため、AI 専用 ID の PR は人間の承認が必要になる |
| └ Dismiss stale pull request approvals when new commits are pushed | 有効 | 有効 | 必須 | AI 権限制御 | 承認後に AI がコードを追加して、承認済みのまま通すことを防ぐ |
| └ Require review from Code Owners | 任意 | **有効** | 推奨 | AI 権限制御 | `.github/`、`CLAUDE.md`、`.claude/` などの変更に指定された人の承認を必須にする |
| └ Require approval of the most recent reviewable push | **有効** | **有効** | 必須 | AI 権限制御 | 最後に push した人以外の承認を必須にする。AI 専用 ID が他人の PR に push して自分で承認することや、人間がレビューした後に AI が差し込むことを防ぐ |
| └ Require conversation resolution before merging | 有効 | 有効 | 推奨 | 品質保証 | AI レビューや人間の指摘が未解決のままマージされることを防ぐ |
| └ Allowed merge methods | Squash | Squash | 推奨 | 品質保証 | General の設定と揃える |
| Require status checks to pass | **有効** | **有効** | 必須 | 品質保証・AI 権限制御 | CI の成功をマージ条件にする |
| └ Status checks | CI のジョブ名（テンプレートでは `ci`）。**発行元（Source）に GitHub Actions を指定する** | 同左 | 必須 | AI 権限制御 | 発行元を指定しないと、`statuses: write` を持つトークンで同じ名前の成功ステータスを送って偽装できる |
| └ Require branches to be up to date before merging | 任意 | 有効（PR が多い場合は Merge Queue を検討） | 推奨 | 品質保証 | base の最新状態でテストした結果だけを認める |
| Require code scanning results | CodeQL を使う場合に有効 | 同左 | 推奨 | セキュリティ | 重要度が高いアラートがある PR をブロックする（Code Security が必要。Public は無料） |
| Require signed commits | 無効 | 任意 | 任意 | セキュリティ | AI の署名鍵の管理が増える。GitHub App の API 経由のコミットは自動で署名される |
| Require deployments to succeed | 無効 | 任意 | 任意 | 品質保証 | Staging へのデプロイ成功をマージ条件にしたい場合 |
| Restrict updates／creations | 無効 | 無効 | ― | ― | PR 経由のマージも止まるため、通常は使わない |

追加で設定するもの:

| 項目 | 推奨値 | 評価 | 理由 |
|---|---|---|---|
| タグ Ruleset（`v*`） | Restrict updates・Restrict deletions・Block force pushes を有効 | 推奨 | リリースタグの付け替えを防ぐ（[`templates/rulesets/tags-release.json`](templates/rulesets/tags-release.json)） |
| Push Ruleset（Organization、Private／Internal） | `.github/workflows/**` の変更を制限し、Bypass に人間の管理者 Team だけを入れる | 任意 | CI 定義の変更を「PR で承認されても AI 経由では入らない」状態にしたい場合。運用が重くなるため、通常は CODEOWNERS と AI の Workflows 権限なしで十分 |
| Merge Queue | ― | 任意 | PR の多いチーム向け。Organization のリポジトリで使える |

**CODEOWNERS との連携**:

- CODEOWNERS は **PR の base ブランチ（main）にあるファイル**が使われる。PR の中で CODEOWNERS を書き換えても、その PR の判定には反映されない。CODEOWNERS 自体をコードオーナーの対象にしておけば、変更には必ずオーナーの承認が必要になる。
- コードオーナーにはリポジトリの Write 権限が必要。**AI 専用 ID をコードオーナーにしない**。
- 置き場所は `.github/CODEOWNERS`、ルート、`docs/` の順に探され、最初に見つかったものが使われる。`.github/CODEOWNERS` に統一する。

### C. Settings → Advanced Security

画面のパス: **Settings → Advanced Security**（旧「Code security」）。Organization では **Settings → Advanced Security → Configurations** から一括適用できる。

| 項目 | 推奨値 | 評価 | 目的 | 利用条件・課金 | API |
|---|---|---|---|---|---|
| Dependency graph | 有効 | 必須 | セキュリティ | 全プラン無料。Public は既定で有効、Private は有効化が必要 | `PUT /repos/{o}/{r}/vulnerability-alerts`（有効化すると依存グラフも有効になる） |
| Dependabot alerts | 有効 | 必須 | セキュリティ | 全プラン無料 | 同上 |
| Dependabot security updates | 有効 | 必須 | セキュリティ | 全プラン無料。パッチがあるアラートに対して PR を自動作成する | `PUT /repos/{o}/{r}/automated-security-fixes` |
| Grouped security updates | 有効 | 推奨 | 開発効率 | 無料。PR の数を減らす | dependabot.yml の `groups` |
| Dependabot version updates | 有効（`dependabot.yml` を置く） | 推奨 | 運用・保守 | 無料。既定で 3 日の Cooldown がある（セキュリティ更新には適用されない） | ファイル（[`templates/.github/dependabot.yml`](templates/.github/dependabot.yml)） |
| Dependabot on Actions runners | 有効（既定） | 推奨 | 運用・保守 | Actions の分数を消費する（Public は無料） | ― |
| CodeQL analysis（Default setup） | 有効（対応言語のみ） | Public: 必須／Private: 推奨 | セキュリティ | Public は無料、Private は **Code Security** が必要。Actions が有効であること。6 か月 push も PR もないと週次スキャンが止まる | `PATCH /repos/{o}/{r}/code-scanning/default-setup` |
| Copilot Autofix | 有効（既定） | 任意 | 開発効率 | Code Security に含まれる | ― |
| Secret scanning | 有効 | Public: 必須／Private: 推奨（購入できる場合は必須） | セキュリティ | Public は無料、Private は **Secret Protection** が必要 | `security_and_analysis.secret_scanning` |
| Push protection | 有効 | 同上 | セキュリティ・AI 権限制御 | 同上。リポジトリの Push Protection は既定で無効。**ユーザー単位の Push Protection**（個人設定、既定で有効）は Public リポジトリへの push のみが対象 | `security_and_analysis.secret_scanning_push_protection` |
| Push protection の Bypass 権限（Delegated bypass） | **指定したレビュアーのみ**（AI 専用 ID を含めない） | 推奨 | AI 権限制御 | Secret Protection が必要。既定では Write 権限があれば誰でも Bypass できる | Security Configuration の設定 |
| Private vulnerability reporting | 有効 | Public: 推奨／Private: 任意 | 運用・保守 | 無料 | `PUT /repos/{o}/{r}/private-vulnerability-reporting` |
| Dependency review（PR での依存関係チェック） | `actions/dependency-review-action` を CI に追加し、Required Check にする | Public: 推奨／Private: Code Security がある場合に推奨 | セキュリティ | Public は無料、Private は Code Security が必要 | Workflow |
| Access to alerts（Security Alerts へのアクセス権限） | Admin、Security manager、セキュリティ担当 Team。**AI 専用 ID は必要な場合のみ Read** | 必須 | セキュリティ | Organization では「Security manager」ロールを Team に付与する。Personal のリポジトリは、Alerts を見られる人を Settings → Advanced Security の最下部で指定する | ― |

**Code Security／Secret Protection を使わない Private リポジトリでの代替（推奨）**:

| 目的 | 代替 |
|---|---|
| シークレット検出 | Gitleaks などを CI と pre-commit で実行する（テンプレートの CI に含む） |
| 静的解析 | Semgrep CE、ESLint のセキュリティ系プラグインなど（スタックに応じて） |
| 依存関係 | Dependabot alerts／security updates（無料）＋ `npm audit --audit-level=high` などを CI で実行 |

### D. Settings → Actions → General

画面のパス: **Settings → Actions → General**。Organization では **Organization Settings → Actions → General**（こちらが上限になる）。

| 項目 | 推奨値 | 評価 | 目的 | 理由・利用条件 | API |
|---|---|---|---|---|---|
| Actions permissions | **Allow {owner}, and select non-{owner}, actions and reusable workflows** → 「Allow actions created by GitHub」を有効、Verified creators は無効、必要な Action だけ `owner/repo@*` で列挙 | 必須 | セキュリティ | 第三者 Action はサプライチェーン攻撃の入口になる。AI が見つけた Action をそのまま使わせない | `PUT /repos/{o}/{r}/actions/permissions`（`allowed_actions=selected`）、`PUT .../actions/permissions/selected-actions` |
| Require actions to be pinned to a full-length commit SHA | **有効** | 必須 | セキュリティ | タグの付け替えによる改ざんを防ぐ。Dependabot（`github-actions`）が SHA の更新 PR を作る。Reusable Workflow はタグ参照のままでも許可される | `PUT /repos/{o}/{r}/actions/permissions`（`sha_pinning_required=true`） |
| 特定 Action のブロック | 問題が出た Action を `!owner/repo@*` で列挙 | 任意 | セキュリティ | 侵害が公表された Action を即座に止める | `patterns_allowed` |
| Fork pull request workflows | 「Require approval for all external contributors」（Public の場合） | Public: 必須 | セキュリティ | 外部からの PR で Workflow が勝手に動くことを防ぐ。Private では「Run workflows from fork pull requests」を無効にしておく | `PUT .../actions/permissions/fork-pr-contributor-approval` |
| Workflow permissions | **Read repository contents and packages permissions** | 必須 | セキュリティ・AI 権限制御 | GITHUB_TOKEN の既定を読み取りのみにし、必要な権限は Workflow の `permissions:` でジョブ単位に付与する | `PUT /repos/{o}/{r}/actions/permissions/workflow`（`default_workflow_permissions=read`） |
| Allow GitHub Actions to create and approve pull requests | **無効**（既定） | 必須 | AI 権限制御 | 有効にすると Workflow（AI が変更した Workflow を含む）が PR を承認でき、Required Approvals を迂回できる | 同上（`can_approve_pull_request_reviews=false`） |
| Artifact and log retention | 既定（90 日）。Private で容量を抑えたい場合は短くする | 任意 | 運用・保守 | ― | `PUT .../actions/permissions/artifact-and-log-retention` |
| Access（Private のみ） | Not accessible（Reusable Workflow を他のリポジトリに提供する中央リポジトリだけ公開） | 推奨 | セキュリティ | ― | `PUT .../actions/permissions/access` |

**Workflow を書くときのルール**（テンプレートの CI に反映済み）:

- `permissions:` を Workflow の先頭で `contents: read` にし、必要なジョブだけ追加する。
- `uses:` は **40 桁のコミット SHA** で指定し、コメントにバージョンを書く（`actions/checkout@<sha> # v7.0.1`）。
- `pull_request_target` と `workflow_run` は、PR のコードを checkout して実行すると Secrets が漏れるため原則使わない。
- `actions/checkout` は `persist-credentials: false` にする。
- Required Check にするジョブは、Workflow 単位の `paths` フィルターでスキップさせない（Workflow 自体が起動しないとチェックが「待機中」のままになる）。ジョブの `if:` でスキップされたジョブは**成功扱い**になるため、Required Check のジョブに `if:` を付けない。

**Secrets 管理**:

| 種類 | 用途 | 評価 |
|---|---|---|
| Environment Secrets | 本番・Staging の認証情報（Environment の保護ルールを通ったジョブだけが読める） | 必須（本番の Secrets は必ずここ） |
| Repository Secrets | 環境に依存しない CI 用の値（例: テスト用 API キー） | 推奨 |
| Organization Secrets | 複数リポジトリ共通の値。**Selected repositories** で公開範囲を絞る | 任意 |
| Dependabot Secrets | Dependabot がプライベートレジストリへアクセスするための値（通常の Secrets は Dependabot の PR からは読めない） | 任意 |

**OIDC 認証**:

- 全プランで使える。ジョブに `permissions: id-token: write` を付けると、AWS、Azure、Google Cloud などへ長期間有効な鍵を保存せずに認証できる。
- **推奨**: 本番クラウドへのデプロイは OIDC にし、クラウド側の信頼条件で `sub` を `repo:{owner}/{repo}:environment:production` に限定する。こうすると、production Environment を通るジョブ以外は本番の権限を取得できない。
- 2026-07-15 以降に作成したリポジトリでは、`sub` の既定の形式に Owner と Repository の ID が含まれる。クラウド側の条件を書く前に、実際のトークンの `sub` を確認する。

### E. Environments／Deployment

画面のパス: **Settings → Environments → New environment**。API は `PUT /repos/{o}/{r}/environments/{name}`。

| Environment | デプロイ対象ブランチ | 保護ルール | Secrets | 評価 |
|---|---|---|---|---|
| `development` | 制限なし（または `feature/**` など） | なし | 開発用の値のみ | 任意（Preview 環境を使う場合） |
| `staging` | `main` のみ | なし（または Wait timer） | Staging 用の値 | 推奨 |
| `production` | **`main` とリリースタグ（`v*`）のみ** | **Required reviewers（人間のみ、AI 専用 ID を含めない）＋ Prevent self-review 有効＋ Allow administrators to bypass 無効** | 本番の値（OIDC を優先） | 本番がある場合は必須 |

プランによる制約と代替:

| 機能 | Public | Private（Pro / Team） | Private（Enterprise Cloud） |
|---|---|---|---|
| Environment・Environment Secrets・Deployment branches and tags | ○ | ○ | ○ |
| Required reviewers・Prevent self-review・Wait timer・カスタム保護ルール | ○ | **×** | ○ |

**Private かつ Pro / Team で本番の承認ゲートを作る方法**（推奨順）:

1. production Environment の Deployment branches を `main`（とリリースタグ）に限定し、main は Ruleset で承認必須にする。「main にマージされた＝人間が承認した」ことを本番デプロイの条件にする。
2. 本番デプロイのトリガーを `workflow_dispatch`（人間が手で起動）またはリリースタグの作成にし、タグ Ruleset でタグの作成を人間の管理者に限る。
3. 本番の認証は OIDC にして、クラウド側で `environment:production` からの要求だけを許可する。
4. より厳しくしたい場合は、デプロイ専用のリポジトリを分けるか、承認機能のある外部の CD サービスを使う。

**デプロイ権限**:

- 本番 Environment の Secrets を変えられるのは Admin だけにする（AI 専用 ID に Environments／Secrets の権限を付けない）。
- AI が Workflow を書き換えて別の Environment 名で本番 Secrets を読むことは、Environment Secrets と Deployment branches の制限、AI の Workflows 権限なし、CODEOWNERS の組み合わせで防ぐ。

**ロールバック手順**（リポジトリの `docs/` に記載しておく。評価: 本番がある場合は必須）:

1. 直前の正常なリリースタグ（または main のコミット）を指定して、デプロイ Workflow を `workflow_dispatch` で再実行する。
2. 原因となった PR を GitHub の「Revert」ボタンで取り消す PR を作り、通常の品質ゲートを通してマージする（main への直接 push はしない）。
3. DB マイグレーションを伴う場合は、デプロイ前に「戻し方」を PR テンプレートの項目で確認しておく。
4. Secrets の漏えいが原因の場合は、§8 の手順でローテーションする。

### F. リポジトリ標準ファイル

テンプレートは [`templates/`](templates/) にある。`.github/` 以下はこのディレクトリでは `templates/.github/` に置いている（このリポジトリで有効にならないようにするため）。

| ファイル | 評価 | 目的 | 内容・注意 | テンプレート |
|---|---|---|---|---|
| `CLAUDE.md` | 必須（Claude Code を使う場合） | AI 権限制御・品質保証 | ビルド・テストのコマンド、禁止事項（main へ直接 push しない、CI を無効化しない、Secrets を読まない）、PR の作り方。短く保ち、詳細は `.claude/rules/` に分ける | [`templates/CLAUDE.md`](templates/CLAUDE.md) |
| `AGENTS.md` | 推奨（Claude Code 以外のエージェントも使う場合） | AI 権限制御 | エージェント共通の指示。Claude Code は `CLAUDE.md` を読むため、`CLAUDE.md` から `@AGENTS.md` で取り込み、内容を二重に管理しない | [`templates/AGENTS.md`](templates/AGENTS.md) |
| `.claude/rules/*.md` | 任意 | 品質保証 | 特定のパスにだけ適用するルール（`paths:` で指定）。例: テストの書き方、DB マイグレーションのルール | [`templates/.claude/rules/testing.md`](templates/.claude/rules/testing.md) |
| `.claude/settings.json` | 推奨 | AI 権限制御 | `.env` の読み取り、`git push --force`、`gh pr merge`、Ruleset を変更する `gh api` などを `deny`／`ask` にする。認証情報は書かない | [`templates/.claude/settings.json`](templates/.claude/settings.json) |
| `.github/CODEOWNERS` | チーム: 必須／個人: 推奨 | AI 権限制御 | `.github/`、`CODEOWNERS`、`CLAUDE.md`、`AGENTS.md`、`.claude/`、依存関係のロックファイル、インフラ定義の承認者を指定する | [`templates/.github/CODEOWNERS`](templates/.github/CODEOWNERS) |
| `.github/dependabot.yml` | 推奨 | 運用・保守 | `github-actions` と使用するパッケージマネージャー。週次、グループ化、Cooldown | [`templates/.github/dependabot.yml`](templates/.github/dependabot.yml) |
| `.github/workflows/ci.yml` | 必須 | 品質保証 | Lint、型チェック、テスト、ビルド、シークレット検出。`permissions: contents: read`、SHA 固定 | [`templates/.github/workflows/ci.yml`](templates/.github/workflows/ci.yml) |
| `.github/workflows/dependency-review.yml` | Public／Code Security あり: 推奨 | セキュリティ | PR で追加される依存関係の脆弱性とライセンスを確認する | [`templates/.github/workflows/dependency-review.yml`](templates/.github/workflows/dependency-review.yml) |
| `.github/ISSUE_TEMPLATE/` | 推奨 | 開発効率 | バグ報告と機能要望のフォーム。AI に渡す前提条件（受け入れ条件）を書く欄を設ける | [`templates/.github/ISSUE_TEMPLATE/`](templates/.github/ISSUE_TEMPLATE/) |
| `.github/pull_request_template.md` | 必須 | 品質保証 | 変更内容、テスト結果、AI が作成したかどうか、影響範囲、ロールバック方法 | [`templates/.github/pull_request_template.md`](templates/.github/pull_request_template.md) |
| `SECURITY.md` | Public: 必須／Private: 推奨 | 運用・保守 | 脆弱性の報告窓口（Private vulnerability reporting）。Organization の `.github` に置けば共通化できる | [`templates/SECURITY.md`](templates/SECURITY.md) |
| `.env.example` | 必須（環境変数を使う場合） | セキュリティ | 変数名と説明だけを書き、値は空にする。`.env*`（`.env.example` を除く）を `.gitignore` に入れる | [`templates/.env.example`](templates/.env.example) |
| `.gitignore` | 必須 | セキュリティ | `.env`、`.claude/settings.local.json`、ビルド成果物 | 言語ごとの GitHub 公式テンプレートを使う |
| `LICENSE` | Public: 必須 | 運用・保守 | ― | リポジトリ作成時に選択 |

`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md` は OSS として公開する場合のみ追加する（任意）。

---

## 4. AI 駆動開発で特に注意する事項

| 要件 | GitHub 側の対策（強制力あり） | 補助的な対策（クライアント側） |
|---|---|---|
| AI が main へ直接 push できない | Ruleset「Require a pull request」＋Bypass List を空にする。AI 専用 ID を Write に留める | `CLAUDE.md` に明記。`.claude/settings.json` で `git push origin main` を `deny` |
| AI が CI の検査を無効化してマージできない | Required Status Checks（発行元を GitHub Actions に固定）。AI のトークンに **Workflows 権限を付けない**。CODEOWNERS で `.github/` の承認者を指定し、Code Owner レビューを必須化。Dismiss stale approvals。Organization では Push Ruleset で `.github/workflows/**` を制限 | Required Check のジョブに `if:` を付けない。テストのスキップ（`skip`、`only`）を Lint で禁止 |
| AI が Rulesets・Branch Protection を変更できない | AI の ID を **Admin にしない**。トークンに **Administration 権限を付けない**。Organization Rulesets は Organization オーナーしか変更できないため、重要なルールは Organization 側に置く | `.claude/settings.json` で `gh api` の `rulesets`／`branches/*/protection` を `deny`。Ruleset の変更履歴（Rule insights、監査ログ）を定期的に確認 |
| AI が自分の PR を承認してマージしない | AI 専用 ID で PR を作る（作成者は自分の PR を承認できない）。Required approvals ≥ 1。Require approval of the most recent reviewable push。「Allow GitHub Actions to create and approve pull requests」を無効 | §2.2 の構成では `gh pr merge` とマージ用 MCP ツールを `deny`／`ask` |
| 本番 Secrets を AI の開発環境に渡さない | 本番の値は production の Environment Secrets のみに置き、OIDC を優先する。AI のトークンに Secrets／Environments 権限を付けない。Deployment branches を main とタグに限定する | 開発環境の `.env` には開発用の値だけを置く。`.claude/settings.json` で `Read(./.env*)` などを `deny`。クラウドの AI 実行環境のシークレットには開発用のものだけを登録する |
| AI が作成した PR も通常の品質ゲートを通る | Bypass List に AI の GitHub App・マシンユーザーを入れない（Dependabot も入れない）。Code Scanning／Dependency Review を Required Check にする | PR テンプレートに「AI 生成」のチェック欄。AI によるレビューは人間の承認の代わりにしない |

追加の注意:

- **AI を GitHub App で動かす場合**（Claude Code GitHub Actions など）、その App の権限一覧を確認し、Administration・Workflows を外す。App のインストール先は対象リポジトリに限定する。
- **Copilot などのコーディングエージェント**の PR には、Ruleset の「Require an additional approval for unattributed Copilot pull requests」（プレビュー、既定で有効）が効く。無効にしない。
- **Dependabot を Bypass に入れない**。依存関係の更新も CI を通す。
- **Secrets を Workflow のログに出さない**。AI に CI のログを読ませる場合、ログに秘密情報が出ていないことが前提になる。
- Claude Code のローカル設定（`.claude/settings.local.json`）や MCP の設定ファイルにトークンを直接書かない。環境変数で参照する。

---

## 5. 複数リポジトリへの展開と自動化

### 5.1 手段の比較

| 手段 | できること | できないこと | 評価 |
|---|---|---|---|
| **Template Repository** | ファイル・ディレクトリ構成（既定ブランチのみ、または全ブランチ）をコピーする | Settings、Rulesets、Secrets、Environments、Webhooks、Actions の権限設定、Security 設定、ラベル（テンプレートのラベルは引き継がれない）、履歴はコピーされない | 必須 |
| **Organization の `.github` リポジトリ** | Community Health Files（Issue／PR テンプレート、SECURITY.md、CONTRIBUTING.md、SUPPORT.md など）の既定値。`workflow-templates/` で Workflow のひな形を提供 | **Public でなければならない**。CODEOWNERS、dependabot.yml、Workflow 本体、LICENSE は既定にできない。リポジトリ側に同じ種類のファイルがあれば、そちらが優先される | 推奨 |
| **Organization Rulesets** | 全リポジトリ、名前のパターン、Custom Properties で対象を選んで Ruleset を一括適用する | リポジトリ側で緩められない（変更は Organization オーナーのみ） | Team 以上: 必須 |
| **Security Configurations** | セキュリティ機能の有効化をまとめて適用する。新規リポジトリの既定にもできる | マージ方式などの General 設定 | Team 以上: 必須 |
| **Reusable Workflows** | CI の中身を中央リポジトリで管理し、各リポジトリから `uses: org/ci/.github/workflows/x.yml@<sha>` で呼ぶ | 呼び出し側の Workflow ファイルは各リポジトリに必要 | 推奨 |
| **GitHub CLI**（`gh`） | `gh repo create --template`、`gh api` で Settings を反映する。手順書のスクリプトはこれを使う | 状態の差分管理はしない | 必須 |
| **GitHub REST API** | 上記すべての設定（§1.6） | ― | ― |
| **Terraform GitHub Provider**（`integrations/github`） | リポジトリ、Rulesets、Environments、Actions の権限、Team の権限などをコードで管理し、差分を検出する | 状態ファイルと Provider の認証情報（GitHub App 推奨）の管理が必要 | 任意（リポジトリが数十を超える場合は推奨） |

**Template Repository からコピーされるもの／されないもの**:

| コピーされる（ファイル） | 作成後に別途設定が必要（Repository Settings） |
|---|---|
| `CLAUDE.md`、`AGENTS.md`、`.claude/`（`settings.local.json` を除く） | Visibility・マージ方式・ブランチ自動削除・Auto merge・Features（§3.A） |
| `.github/CODEOWNERS`、`dependabot.yml`、`workflows/`、`ISSUE_TEMPLATE/`、`pull_request_template.md` | Rulesets（§3.B） |
| `SECURITY.md`、`.env.example`、`.gitignore`、`LICENSE` | Dependency graph・Dependabot・CodeQL・Secret Scanning・Push Protection（§3.C） |
| | Actions の権限・SHA 固定・GITHUB_TOKEN の既定（§3.D） |
| | Environments・Secrets・Variables（§3.E） |
| | Collaborators・Team の権限、GitHub App のインストール、Custom Properties |

### 5.2 Team 単位で適用する方法

Organization 全体ではなく、特定の Team のリポジトリだけに適用したい場合:

1. Organization に **Custom Property**（例: `team`、値は `platform`／`web` など、必須プロパティにする）を定義し、リポジトリ作成時に設定する。
2. **Organization Ruleset** の対象を「Repositories matching a filter」にして `props.team:web` のように絞る（`visibility:private` などと組み合わせられる）。
3. **Security Configuration** をそのリポジトリ群にだけ適用する（Configurations 画面でリポジトリを絞り込んで適用）。
4. Team ごとに **Template Repository** を用意し（例: `template-web`）、Team のメンバーだけが使う。
5. Team 用の **Reusable Workflow** を Team が管理する中央リポジトリに置く。
6. Terraform を使う場合は、Team ごとのモジュールに標準値を持たせる。

Custom Property を AI が変更できると、Ruleset の対象から外れることができる。プロパティの値を変更できるのは Organization オーナー（またはプロパティ編集を許可した人）だけにする。

### 5.3 このリポジトリのスクリプト

```bash
scripts/github-setup/apply-repo-settings.sh <owner>/<repo> --profile team
```

上のコマンドは実行内容を表示するだけ（ドライラン）。承認を得てから `--apply` を付けて実行する。

```bash
scripts/github-setup/apply-repo-settings.sh <owner>/<repo> --profile team --apply
```

`--profile` は `solo`（個人、AI 専用 ID あり）、`solo-minimal`（§2.2 の構成）、`team` の 3 種類。実行には対象リポジトリの Admin 権限を持つ人間の `gh` 認証が必要（AI のトークンでは実行できないのが正しい状態）。

---

## 6. セットアップ手順（チェックリスト）

### 6.0 事前に決めること

- [ ] Personal か Organization か、プラン（§1）
- [ ] Public か Private か
- [ ] 個人（`solo`／`solo-minimal`）かチーム（`team`）か
- [ ] AI を動かす ID（GitHub App／マシンユーザー／本人の最小権限 PAT）（§2）
- [ ] Secret Protection／Code Security を使うか（Private の場合）
- [ ] 本番環境があるか、デプロイ先と認証方式（OIDC を使えるか）

### 6.1 リポジトリの作成

- [ ] Template Repository から作成する（Organization の場合は Custom Property も設定）

```bash
gh repo create <owner>/<repo> --private --template <owner>/<template-repo> --clone
```

- [ ] テンプレートを使わない場合は、[`templates/`](templates/) の内容をコピーし、`CODEOWNERS` のユーザー名・Team 名、CI のコマンド、`dependabot.yml` のエコシステムを書き換えて、最初の PR（または初回コミット）で入れる

### 6.2 Repository Settings の反映

- [ ] スクリプトをドライランで実行し、内容を確認する
- [ ] 承認を得て `--apply` で実行する（General、Actions、Advanced Security、Rulesets）
- [ ] CI を一度実行してから、Ruleset の Required Status Checks に CI のジョブ名を登録し、発行元が GitHub Actions になっていることを Web UI で確認する（チェックが一度も実行されていないと選択できない）
- [ ] Organization の場合は Organization Rulesets・Security Configuration が適用されていることを確認する

### 6.3 権限の設定

- [ ] AI 専用 ID を Write で追加する（GitHub App の場合はインストール先を対象リポジトリに限定）
- [ ] AI 用の Fine-grained PAT／App 権限が §2.1 のとおりであることを確認する
- [ ] Bypass List が空（または管理者の「For pull requests only」のみ）であることを確認する
- [ ] Alerts へのアクセス権限を設定する

### 6.4 Environments（本番がある場合）

- [ ] `staging`、`production` を作成し、Deployment branches を設定する
- [ ] Required reviewers（使えるプランの場合）と Prevent self-review を設定する
- [ ] 本番の認証を OIDC にし、クラウド側の信頼条件を `environment:production` に限定する
- [ ] Environment Secrets を登録する（AI には値を渡さない）
- [ ] ロールバック手順を `docs/` に書く

### 6.5 AI エージェントの設定

- [ ] `CLAUDE.md`（と `AGENTS.md`）のコマンドと禁止事項をプロジェクトに合わせる
- [ ] `.claude/settings.json` の `deny` 設定を確認する
- [ ] AI の実行環境（ローカル／クラウド）に開発用の認証情報だけを設定する

---

## 7. 設定後の検証

AI 専用 ID（または AI が使うトークン）で次を試し、**すべて拒否される**ことを確認する。

| # | 操作 | 期待する結果 |
|---|---|---|
| 1 | `git push origin HEAD:main` | Ruleset により拒否される |
| 2 | `git push --force` で main を書き換える | 拒否される |
| 3 | `.github/workflows/ci.yml` を変更したコミットを push する | Workflows 権限がないため拒否される |
| 4 | CI が失敗している PR をマージする | Required Status Checks によりマージできない |
| 5 | 自分が作った PR を承認する | 作成者は承認できない |
| 6 | `gh api -X POST repos/<owner>/<repo>/rulesets ...` | 権限不足で拒否される（403／404） |
| 7 | ダミーのシークレット（Secret Scanning のテスト用文字列）を含むコミットを push する | Push Protection（または CI の Gitleaks）で止まる |
| 8 | 承認後に追加のコミットを push する | 承認が取り消され、再承認が必要になる |
| 9 | `feature/*` ブランチから production へデプロイする | Deployment branches の制限で拒否される |

---

## 8. ロールバック・緊急時の手順

| 状況 | 手順 |
|---|---|
| Ruleset の設定ミスで誰もマージできない | Admin が Web UI で該当 Ruleset を一時的に Disabled にし、修正後すぐに Active に戻す。変更した理由を Issue に残す |
| 緊急の修正を main に入れたい | Bypass を使わず、通常の PR で承認を得る。チームで「For pull requests only」の管理者 Bypass を設定している場合でも、使ったら事後に Issue で記録する |
| Secrets が漏えいした | 1) 発行元で該当の認証情報を失効・再発行する、2) GitHub の Secrets を更新する、3) Secret Scanning のアラートを閉じる、4) 履歴からの削除は失効後に判断する（失効しない限り、履歴を消しても安全にならない） |
| AI のトークンが漏えいした | Fine-grained PAT を失効させる／GitHub App の秘密鍵を再発行する。監査ログで操作を確認する |
| 誤ったデプロイ | §3.E のロールバック手順 |

---

## 9. 公式 URL 一覧

**プラン・ライセンス**

- GitHub のプラン: https://docs.github.com/en/get-started/learning-about-github/githubs-plans
- GitHub Advanced Security について: https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security
- GHAS の課金: https://docs.github.com/en/billing/concepts/product-billing/github-advanced-security
- 料金: https://github.com/pricing ／ https://github.com/security/advanced-security

**General**

- マージ方式: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github
- ブランチの自動削除: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches
- Auto merge: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-auto-merge-for-pull-requests-in-your-repository
- REST API（リポジトリの更新）: https://docs.github.com/en/rest/repos/repos#update-a-repository

**Rulesets・CODEOWNERS**

- Rulesets について: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- 利用できるルール: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- リポジトリの Ruleset の作成（Bypass）: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- Organization の Ruleset の作成（対象の指定）: https://docs.github.com/en/organizations/managing-organization-settings/creating-rulesets-for-repositories-in-your-organization
- REST API（Rulesets）: https://docs.github.com/en/rest/repos/rules
- CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

**Advanced Security**

- Dependency graph の有効化: https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/enable-dependency-graph
- Dependabot alerts: https://docs.github.com/en/code-security/dependabot/dependabot-alerts/about-dependabot-alerts
- Dependabot security updates: https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates
- Dependabot version updates: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/about-dependabot-version-updates
- dependabot.yml のオプション: https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
- CodeQL Default setup: https://docs.github.com/en/code-security/code-scanning/enabling-code-scanning/configuring-default-setup-for-code-scanning
- Push protection: https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection
- Dependency review: https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review
- Security Configurations: https://docs.github.com/en/code-security/securing-your-organization/introduction-to-securing-your-organization-at-scale/about-enabling-security-features-at-scale

**Actions**

- リポジトリの Actions 設定: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- GITHUB_TOKEN の権限: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
- Actions のセキュリティ（SHA 固定など）: https://docs.github.com/en/actions/reference/security/secure-use
- Secrets: https://docs.github.com/en/actions/concepts/security/secrets
- OIDC: https://docs.github.com/en/actions/concepts/security/openid-connect ／ https://docs.github.com/en/actions/reference/security/oidc
- Reusable Workflows: https://docs.github.com/en/actions/how-tos/sharing-automations/reuse-workflows
- REST API（Actions の権限）: https://docs.github.com/en/rest/actions/permissions

**Environments**

- Environment の管理: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- Deployments と Environments（プランの制約）: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- REST API（Environments）: https://docs.github.com/en/rest/deployments/environments

**展開・自動化**

- Template Repository からの作成: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template
- 既定の Community Health Files: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
- Custom Properties: https://docs.github.com/en/organizations/managing-organization-settings/managing-custom-properties-for-repositories-in-your-organization
- GitHub CLI: https://cli.github.com/manual/
- Terraform GitHub Provider: https://registry.terraform.io/providers/integrations/github/latest/docs

**AI エージェント**

- Claude Code の設定（permissions）: https://code.claude.com/docs/en/settings
- Claude Code のメモリ（CLAUDE.md、`.claude/rules/`）: https://code.claude.com/docs/en/memory
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions

---

## 10. 未確定事項・注意

確認時点（2026-11-09）で、公式ドキュメントの記述が食い違っていた、または明記されていなかった点。適用前に再確認すること。

| 項目 | 内容 | この手順書での扱い |
|---|---|---|
| Organization Rulesets のプラン | 「About rulesets」に「Enterprise プランの Organization では組織レベルで設定できる」という記述と、「Team と Enterprise」という記述が混在している | 作成手順のページの記述（Team 以上）に従う |
| GHAS 製品の Team での購入方法 | GHAS のページは Team で購入できると書いているが、課金のページは従量課金を Enterprise Cloud 向けとしている | Team で購入できる前提。購入画面で確認する |
| Dependency review の Public での扱い | GHAS の比較表と、Dependency review のページの記述が食い違っている | Public は無料（Dependency review のページの記述）に従う |
| Prevent self-review の Private での可否 | Required reviewers の節に含まれ、Private（Pro / Team）では Required reviewers 自体が使えない | Private では Enterprise Cloud のみと判断 |
| Personal Account の Bypass List | 個人のリポジトリでの対象が明記されていない | Repository admin、GitHub App、Dependabot を対象と判断（Team は不可） |
| API の `sha_pinning_required` | Web UI の設定は確認済み。API のフィールド名はスクリプトで確認のうえ使う | スクリプトの実行結果でエラーが出た場合は Web UI で設定する |
| 価格 | 2025 年 4 月の発表時の価格を記載 | 公式の料金ページで確認する |
