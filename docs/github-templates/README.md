# Issue・PR テンプレート

各プロジェクトで共通に使う Issue Forms・PR テンプレートと、AI エージェント向けの記述ルールです。
狙いは、AI が書いた Issue・PR でも、人が冒頭を読めば目的と影響が分かるようにすることです。

調査の詳細と出典は [research.md](research.md) にあります。

## 決めたこと

| # | 決めたこと | 理由 |
|---|---|---|
| 1 | テンプレートは**このリポジトリの `templates/github/` に置き、各リポジトリへコピーする**。`.github` リポジトリ方式（既定ファイル）は使わない | `.github` リポジトリは public 必須で、組織では使えない。また既定ファイルは clone に含まれないため、AI がローカルで読めない |
| 2 | Issue は「何を実現するか」、PR は「何が変わり、どう検証したか」を書く。**受入条件の正本は Issue** に置く | Issue と PR の役割を分け、同じ内容を二重に管理しないため |
| 3 | AI は**テンプレートのファイルを読んで本文を組み立てる** | CLI や API で作成すると、テンプレートは自動では適用されないため |
| 4 | 冒頭は利用者・業務の振る舞いを主語にし、ファイル名・関数名は後ろに回す（技術的負債の Issue は例外） | 調べた OSS 5 件すべてで共通の書き方 |
| 5 | PR 本文の必須見出しは、必要なリポジトリだけ GitHub Actions でチェックする | private リポジトリでは Issue Forms の必須チェックが効かないため |
| 6 | 空の Issue は許可する。Issue・PR 作成用の Skill は作らない | 小規模チームではメモ程度の Issue も作りたいため。Skill は記述ルールで足りないと分かってから検討する |

## 導入手順

1. テンプレートを配置する。PR 本文のチェックも使う場合は `--with-check` を付ける。

   ```bash
   scripts/add-github-templates.sh ../my-project --with-check
   ```

2. 既存のファイルは上書きせず、「スキップ」として一覧表示する。表示されたファイルは、中身を見比べて手で統合する。
3. `tech-debt` ラベルを作る（`enhancement` と `bug` は GitHub が最初から用意している）。

   ```bash
   gh label create tech-debt --color BFD4F2 --description "技術的負債・リファクタリング" -R <owner>/<repo>
   ```

4. 既定ブランチにマージする。
5. 表示を確認する。
   - `https://github.com/<owner>/<repo>/issues/new/choose` に 3 種類のフォームが出るか。YAML に構文エラーがあると、そのフォームは表示されない。
   - PR を作成する画面で、本文にテンプレートが入るか。

導入後に、AI に Issue か PR を 1 件作らせ、[記入済みサンプル](examples/)と同じ水準になっているか確かめてください。特に次の 2 点を見ます。

- 冒頭が関数名で始まっていないか
- 実施していないテストを「実施済み」と書いていないか

## 配置されるもの

| ファイル | 内容 |
|---|---|
| `.github/ISSUE_TEMPLATE/feature.yml` | 機能要望（ラベル `enhancement`）。必須: 概要 / 背景・課題 / 期待する動作 / 受入条件 |
| `.github/ISSUE_TEMPLATE/bug.yml` | 不具合報告（ラベル `bug`）。必須: 発生している問題 / 期待する動作 / 実際の動作 / 再現手順 |
| `.github/ISSUE_TEMPLATE/tech-debt.yml` | 技術的負債（ラベル `tech-debt`）。必須: 現状の問題 / 改善する理由 / 期待する改善 / 既存動作への影響 / 完了条件 |
| `.github/ISSUE_TEMPLATE/config.yml` | 空の Issue を許可する設定 |
| `.github/pull_request_template.md` | 見出しは 概要 / 背景・目的 / 変更内容（変更前 / 変更後）/ 検証結果 / 注意事項・残課題 / 関連 Issue。検証結果には、テストの削除や `skip` の有無を書く欄がある（[開発標準](../standards/ai-software-factory-engineering-standard.md) §2.5） |
| `.github/workflows/pr-body-check.yml` | `--with-check` を付けたときだけ配置する。必須見出し（概要 / 背景・目的 / 変更内容 / 検証結果 / 関連 Issue）が欠けているか空なら失敗する。マージを止めたいときは、ブランチ保護で必須チェックに設定する |
| `docs/github-writing.md` | AI と人の共通の記述ルール（正本）。スクリプトが `AGENTS.md` から参照する 1 行を追記する。`AGENTS.md` がなければ `CLAUDE.md` に `@docs/github-writing.md` を追記する |

記入済みサンプル: [機能要望](examples/feature-issue.md) / [不具合報告](examples/bug-issue.md) / [PR](examples/pull-request.md)

## 更新と運用

- テンプレートの正本はこのリポジトリの `templates/github/` です。変更は PR で行い、そのとき `examples/` のサンプルも合わせて直してください。
- 更新を各リポジトリに反映するときは、スクリプトを再実行します。各リポジトリで独自に変えた部分を消さないよう、スクリプトは既存ファイルを上書きしません。差分は「スキップ」として表示されるので、手で取り込みます。
- PR の必須見出しを変えるときは、`pull_request_template.md` と `pr-body-check.yml` の `required` を同時に変えます。
- 共通の 3 種類で足りないリポジトリは、そのリポジトリの `.github/ISSUE_TEMPLATE/` にフォームを追加します。共通のフォームは消さずに残します。
- 将来、public の `.github` リポジトリを使えるようになったら、`templates/github/.github/` の中身をそこへ移せば、既定ファイル方式に切り替えられます。記述ルールは AI がローカルで読めるよう、各リポジトリに残してください。
