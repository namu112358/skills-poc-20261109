# main ブランチの Ruleset（このリポジトリ用）

`skills-poc-main.json` を読み込むと、main を変更する手段が PR だけになります。さらに、main の最新の内容を取り込み、PR 本文のチェックに合格した PR だけがマージできるようになります。

PR #6 の新規プロジェクト用テンプレート（`templates/rulesets/main-solo-minimal.json`）と同じ方針にしたうえで、このリポジトリに合わせて次の 3 点を変えています。

- 必須チェックを、このリポジトリにあるワークフローに合わせた
- 「main を取り込んでからでないとマージできない（strict）」を有効にした
- ルールの名前を変えた

## 各ルールの意味

| ルール（JSON の `type`） | 設定値 | 意味 |
|---|---|---|
| `deletion` | 有効 | main ブランチを削除できなくする |
| `non_fast_forward` | 有効 | force push（履歴の書き換え）を禁止する |
| `required_linear_history` | 有効 | main の履歴を一直線に保つ（merge commit を入れない） |
| `pull_request` | 承認 0 人、squash のみ | main への直接 push を禁止し、PR 経由に限る。未解決のレビューコメントがあるとマージできない |
| `required_status_checks` | `check`（GitHub Actions）、strict 有効 | 「PR body check」ワークフローの成功を必須にする。strict を有効にすると、main を取り込み済みのブランチでなければマージできない（「Require branches to be up to date before merging」と同じ） |
| `bypass_actors` | なし | 例外にするユーザーはいない。オーナー本人も PR 経由でしか main を変更できない |

補足:

- 必須チェックの名前は、ワークフロー `.github/workflows/pr-body-check.yml` のジョブ ID `check` です。`integration_id: 15368` は GitHub Actions を指します。ワークフローのジョブ名を変えたら、この Ruleset も合わせて変えてください。
- Draft の PR では、このチェックはスキップされます。Draft の PR はもともとマージできないので問題ありません。Ready for review にするとチェックが再実行されます。

## 判断が必要な点

### 必須レビュー人数（既定: 0）

- GitHub では、PR の作成者は自分の PR を承認できません。このリポジトリで承認できるのはユーザー 1 人なので、1 以上にするとユーザー自身が作った PR はマージできなくなります。
- AI が同じアカウントで PR を作る場合も、作成者は本人と同じ扱いになります。
- 1 以上にするには、別の承認者を用意するか、ユーザーを `bypass_actors` に入れる必要があります。ただし bypass に入れるとルールを素通りできるようになり、保護が弱まります。
- 承認人数を 0 にしても、PR 経由に限ること、必須チェック、main の取り込み必須はそのまま有効です。

### マージ方法（既定: squash のみ）

| 選択肢 | 今回の問題（マージ済みのブランチに続きを積むと、古い変更が diff に出る）との関係 |
|---|---|
| **squash のみ**（既定） | main 側に元のコミットが残らないので、古いブランチに続きを積むと、マージ済みの内容が再び diff に出ます。そのため、**マージ後は main からブランチを作り直す**運用とセットで使います。履歴は 1 PR = 1 コミットで読みやすくなります |
| merge commit も許可 | 元のコミットが main に残るので、続きを積んでも diff は新しい分だけになり、問題は起きにくくなります。ただし履歴が分岐して読みにくくなります。`required_linear_history` とは両立しないため、このルールを外し、`allowed_merge_methods` に `"merge"` を追加する必要があります |

strict（main の取り込み必須）だけでは、古い変更が diff に出ることは防げません。strict の効果は、取り込みを忘れたまま古い main を前提にマージしてしまうことを防ぐことです。

## インポート手順

1. リポジトリの **Settings → Rules → Rulesets** を開く
2. **New ruleset → Import a ruleset** を選び、`skills-poc-main.json` を選択する
3. 表示された内容を確認する。特に **Require status checks to pass** の `check` の発行元が GitHub Actions になっているか見る
4. **Create** を押す
5. 確認: main に直接 push すると拒否されること、テスト用の PR で `check` が必須と表示されることを確かめる

あわせて **Settings → General → Pull Requests** で「Allow squash merging」だけを有効にし、「Automatically delete head branches」も有効にしておくと、Ruleset の設定と矛盾しません。

ルールを外したいとき（ロールバック）は、Rulesets の一覧からこの Ruleset を開き、Enforcement を **Disabled** にするか削除してください。
