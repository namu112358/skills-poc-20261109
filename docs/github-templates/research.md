# Issue・PR テンプレート: 調査結果

[README](README.md) の「決めたこと」の根拠です。GitHub の公式仕様と著名 OSS 5 件の運用を調べ、出典を付けています。

調査日: 2026-11-09

## 1. GitHub 公式仕様

| 論点 | 公式の記述 | 出典 |
|---|---|---|
| 個人アカウントで `.github` を使えるか | 使える。Organization・個人アカウントのどちらでも既定のコミュニティヘルスファイルを作れる | [A] |
| リポジトリの条件 | 名前は `.github`、公開設定は **public 必須**（"A repository for default files cannot be private."） | [A] |
| 適用先の公開設定 | 適用先が public か private かを問わず、同じアカウントが所有し、同じ種類のファイルを持たないリポジトリに適用される | [A] |
| 配置場所 | Issue テンプレートと `config.yml` は `.github/ISSUE_TEMPLATE/`。PR テンプレートはルート・`.github/`・`docs/` のいずれか | [A][C] |
| 優先順位 | 各リポジトリの `.github/ISSUE_TEMPLATE/` に有効なテンプレートか `config.yml` が **1 つでもあれば、既定の ISSUE_TEMPLATE は丸ごと使われない**（既定と独自を混ぜられない） | [A] |
| Git 上の扱い | 既定ファイルは各リポジトリのファイル一覧・履歴・clone に**含まれない** | [A] |
| ラベル | テンプレートで指定するラベルは、使う側の各リポジトリに作成済みである必要がある。なければ付かない | [A][D] |
| Issue Forms の状態 | **public preview**（"subject to change"） | [D] |
| Issue Forms の構文 | 必須キーは `name`・`description`・`body`。任意キーは `title`・`labels`・`assignees`・`projects`・`type`（Issue type は Organization 単位の機能）。要素は `markdown`・`textarea`・`input`・`dropdown`・`checkboxes`・`upload` | [D][E] |
| 必須項目の検証 | `validations.required` が効くのは **public リポジトリのみ**（"Only for public repositories."） | [E] |
| `config.yml` | `blank_issues_enabled` と `contact_links`。`false` にしても Write 以上の権限を持つ人には空 Issue の選択肢が残る | [B] |
| PR テンプレート | ファイル名の大文字小文字は区別されない。複数用意する場合は `PULL_REQUEST_TEMPLATE/` に置き、`?template=` で選ぶ。既定ブランチにあるものが使われる。Issue Forms は PR には使えない | [C][D] |
| Organization へ移行した場合 | 移行時の扱いについての記述はない。適用は「そのアカウントが所有するリポジトリ」なので、移行後は移行先 Organization の `.github` が使われると考えられる（推測） | [A] |
| GitHub CLI | `--body` / `--body-file` と `--template` は併用できない。対話モードではテンプレートを選んでエディタで編集する。ローカルから探すテンプレートは `.md` のみで、Issue Forms（YAML）の扱いは明記されていない | [F] |
| REST API | テンプレートを自動で適用する記述はない。`body` は渡した文字列がそのまま使われ、Issue Forms の必須項目の検証も API 経由では行われないと考えられる | [G] |

出典:
- [A] https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
- [B] https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository
- [C] https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository
- [D] https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- [E] https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema
- [F] `gh` 2.89.0 の `--help` と cli/cli のソース（[pkg/cmd/pr/shared/templates.go](https://github.com/cli/cli/blob/v2.89.0/pkg/cmd/pr/shared/templates.go)、[pkg/cmd/issue/create/create.go](https://github.com/cli/cli/blob/v2.89.0/pkg/cmd/issue/create/create.go)）。https://cli.github.com/manual/ はこの環境のネットワーク制限で取得できなかった
- [G] https://docs.github.com/en/rest/issues/issues#create-an-issue 、https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request

**この調査から導いた結論:**

1. Organization の `.github` は public でなければならないため、今回の組織では使えない。そこで、**このリポジトリに標準テンプレートを置き、各リポジトリへコピーする方式**を採る（[README](README.md) の「決めたこと」1）。コピーする方式でも GitHub の仕様の範囲内で、Organization を移っても同じものを使える。
2. CLI や API ではテンプレートが自動で適用されない。そのため、**エージェントがテンプレートのファイルを読んで本文を組み立てる**ことを前提にする（同 3）。
3. private リポジトリでは Forms の `required` が効かない。必須項目は Web UI 上の案内にとどまるため、必要に応じて CI で検証する（同 5）。

## 2. 著名 OSS の運用比較

| | Next.js | VS Code | Playwright | PowerToys | Supabase |
|---|---|---|---|---|---|
| Issue の形式 | Forms（bug / docs）。機能要望は Discussions へ | Markdown（bug / Copilot bug / feature） | Forms 7 種 | Forms 4 種 | Org の `.github` にある既定の Markdown 3 種 |
| 空 Issue | 無効 | 無効 | 無効 | 無効 | 無効 |
| PR テンプレート | What? / Why? / How?（メンテナー向け） | 見出しなし（コメントのみ） | なし | Summary / PR Checklist / Detailed Description / Validation Steps | Problem / Solution / Review instructions / Checklist |
| 実際の PR の冒頭 | 利用者から見た変化を 1 文で書く | 問題 → 変更 → テストの順の自由記述 | Summary の短い箇条書きと `Fixes #` | 利用者から見える症状から書く | 何が問題かを 1〜2 文で書く |
| 技術情報の置き場所 | Why / How と Verification | 本文中 | Summary の箇条書き（API 名） | 変更点と検証の箇条書き | Changes と Tests の節 |
| AI 向けの指示 | `AGENTS.md` と `create-pr` skill（Summary / Verification、利用者視点、diff で分かることは書かない） | `copilot-instructions.md`（公開する文面のルール） | `AGENTS.md`（`## Summary` は数行、エージェントの表記は禁止） | `AGENTS.md`（**PR 本文は人間が書く**。AI の文章は `<details>` 内に限る） | `AGENTS.md`（内部情報を書かない） |
| Issue と PR の分担 | 機能は Discussions で合意してから | PR は Issue への紐付けが前提 | **PR には Issue が必須** | Issue で合意してから PR | 新機能は Discussion を経てから |
| 遵守の担保 | Forms の required、nissuer（再現リンクの検証・ラベル付け） | ラベルによる自動コメント・自動クローズ、ML 分類 | Forms の required、Copilot によるトリアージ | Forms の required、`pr-intake.yml` による機械的なチェック | CodeRabbit による本文チェック、ラベル付け |

出典（テンプレートと AI 向け指示）:
- Next.js:
  - [bug_report.yml](https://github.com/vercel/next.js/blob/canary/.github/ISSUE_TEMPLATE/1.bug_report.yml)
  - [pull_request_template.md](https://github.com/vercel/next.js/blob/canary/.github/pull_request_template.md)
  - [AGENTS.md](https://github.com/vercel/next.js/blob/canary/AGENTS.md)
  - [create-pr skill](https://github.com/vercel/next.js/blob/canary/.agents/skills/create-pr/SKILL.md)
  - [triage.yml](https://github.com/vercel/next.js/blob/canary/.github/workflows/triage.yml)
- VS Code:
  - [bug_report.md](https://github.com/microsoft/vscode/blob/main/.github/ISSUE_TEMPLATE/bug_report.md)
  - [pull_request_template.md](https://github.com/microsoft/vscode/blob/main/.github/pull_request_template.md)
  - [copilot-instructions.md](https://github.com/microsoft/vscode/blob/main/.github/copilot-instructions.md)
  - [commands.json](https://github.com/microsoft/vscode/blob/main/.github/commands.json)
- Playwright:
  - [bug.yml](https://github.com/microsoft/playwright/blob/main/.github/ISSUE_TEMPLATE/bug.yml)
  - [AGENTS.md](https://github.com/microsoft/playwright/blob/main/AGENTS.md)
  - [CONTRIBUTING.md](https://github.com/microsoft/playwright/blob/main/CONTRIBUTING.md)
- PowerToys:
  - [ISSUE_TEMPLATE](https://github.com/microsoft/PowerToys/tree/main/.github/ISSUE_TEMPLATE)
  - [pull_request_template.md](https://github.com/microsoft/PowerToys/blob/main/.github/pull_request_template.md)
  - [AGENTS.md](https://github.com/microsoft/PowerToys/blob/main/AGENTS.md)
- Supabase:
  - [supabase/.github の ISSUE_TEMPLATE](https://github.com/supabase/.github/tree/main/.github/ISSUE_TEMPLATE)
  - [pull_request_template.md](https://github.com/supabase/supabase/blob/master/.github/pull_request_template.md)
  - [AGENTS.md](https://github.com/supabase/supabase/blob/master/AGENTS.md)

出典（実際の PR）:
- Next.js: [#101348](https://github.com/vercel/next.js/pull/101348)、[#100960](https://github.com/vercel/next.js/pull/100960)
- VS Code: [#346835](https://github.com/microsoft/vscode/pull/346835)、[#346498](https://github.com/microsoft/vscode/pull/346498)
- Playwright: [#43929](https://github.com/microsoft/playwright/pull/43929)
- PowerToys: [#48569](https://github.com/microsoft/PowerToys/pull/48569)、[#51789](https://github.com/microsoft/PowerToys/pull/51789)
- Supabase: [#52984](https://github.com/supabase/supabase/pull/52984)、[#53051](https://github.com/supabase/supabase/pull/53051)

**比較から取り入れた点:**

- 冒頭には利用者から見える変化や症状を書き、ファイル名・関数名は後ろの節に回す（5 プロジェクトすべてで共通）。
- PR テンプレートは見出しを 4〜5 個に絞る（Next.js・Supabase）。
- 検証の欄には実際に行ったことを書き、未実施ならその理由も書く（Next.js の Verification、PowerToys #48569）。
- エージェント向けの指示は `AGENTS.md` から参照する形にし、各ツール固有のファイルには同じ内容を書かない（Supabase の `CLAUDE.md` は `@AGENTS.md` の 1 行だけ）。
- 必須項目の強制は Forms の `required` を基本にし、本文の機械的なチェックは軽い CI にとどめる（PowerToys の `pr-intake.yml`）。

**取り入れなかった点:**

- 空 Issue の無効化。5 プロジェクトとも無効にしているが、どれも外部からの投稿が多い大規模 OSS である。小規模なチームでは小さなメモも Issue にしたいので、有効のままにした。
- Next.js・PowerToys の「AI は PR 本文を書かない」という方針。外部からの投稿が大量に来る OSS 向けの対策である。今回は AI に書かせる前提なので、代わりに記述ルールで品質を担保する。リポジトリ側でこの方針を定めた場合はそれに従う、と記述ルールに明記した。
