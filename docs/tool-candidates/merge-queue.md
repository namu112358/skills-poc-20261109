# merge queue の候補（GitHub 標準・Mergify・Trunk）

AI エージェントが並列に PR を作ると、1 件マージするたびに残りの PR が「`main` から遅れている」状態になったり、衝突したりして、ブランチの更新・CI・レビューのやり直しがくり返されます。merge queue（マージを順番待ちにし、`main` と組み合わせた状態で CI を回してからマージする仕組み）で、どこまで減らせるかを整理します（調査日: 2026-11-12）。

**まだ採用を決めていません。** どれも実際には動かしていません。Mergify・Trunk の公式の文書は、調べた環境のネットワークで読めなかったため、検索結果の要約と各社の料金ページの記載に頼っています（下の「調べ方と限界」）。

## きっかけ（PoC SF1 の測定）

GitHub のイベントで起動する Routine で Issue を並列に流した試行（[poc/results/factory/SF1/report.md](../../poc/results/factory/SF1/report.md)）で、次のことが起きました。

- PR 10 本で、衝突による draft への戻しが 12 回、レビューが 21 回（うち 9 回は衝突の解消だけのためのやり直し）。どの PR もタスク一覧の画面と DB の変更の一覧を触っていた。
- Ruleset の「`main` を取り込み済みでないとマージできない」（strict）のため、衝突していない PR も 1 件マージするたびに遅れ、ブランチの更新と CI の待ちが要った。
- 実装の途中で衝突した PR では、GitHub が CI を動かさず、実装の役が来ない CI を待ち続けた。

## merge queue で解決できること・できないこと

| 問題 | merge queue で | 理由 |
|---|---|---|
| 1 件マージするたびに、ほかの PR が遅れ、ブランチの更新と CI のやり直しが要る | **解決できる** | キューが「`main` + その PR」を組み合わせて CI を回し、通ったら順にマージする。PR ごとにブランチを更新しなくてよい。strict の代わりになる |
| CI の回数（費用・待ち時間） | **減らせる**（Mergify・Trunk のまとめての検証） | 複数の PR をまとめて 1 回の CI で確かめ、落ちたら分けて確かめ直す。GitHub 標準の merge queue には無いとされる（Mergify の FAQ。未確認） |
| 同じ行を触る PR どうしの衝突（テキストの衝突） | **解決できない** | 衝突した PR はキューから外れるだけ。直すのは人か、修正の役 |
| 実装中の衝突で CI が動かない | **関係しない** | キューに入る前の問題。手順書の直し（衝突していれば先に解消してから CI を待つ）で対応する |

テキストの衝突は、着手の前の予防（同じファイルを変える作業は待つ）で減らす必要があり、merge queue とは別に要ります。

## 候補

| | GitHub 標準 | Mergify | Trunk Merge Queue |
|---|---|---|---|
| 使えるリポジトリ | Organization の Public、または GitHub Enterprise Cloud の Organization の Private。**個人のアカウントのリポジトリは、文書に挙がっていない** | GitHub App。無料の枠あり | GitHub App。無料の枠あり |
| 無料の範囲（各社の記載・要約） | 上の条件なら追加の費用なし | Free / Open Source: 公開リポジトリと、Private は 5 人まで | Private で 5 人（committer）までは無料。merge queue の利用回数は無制限 |
| まとめての検証 | 無いとされる（未確認） | あり（失敗したら二分して確かめ直す。待ちが少ないときは小さくまとめる） | あり（まとめない指定もできる） |
| 追加の権限 | 無し（GitHub の機能） | 外部の GitHub App にリポジトリの書き込みの権限を渡す（範囲は未確認） | 同左（範囲は未確認） |
| CI の側の対応 | 必須チェックのワークフローに `merge_group` のトリガーを足す | 設定ファイル（`.mergify.yml`）でキューの条件を書く（未確認） | 未確認 |

## 今の流れとの組み合わせ（案）

- 人がマージのボタンを押す代わりに、「キューに入れる」（GitHub 標準はボタン、Mergify・Trunk はラベルやコメント）にする。マージを人が判断する決まりは変えない。
- 割り当ての役の「遅れているだけの PR を更新する」は要らなくなる。「衝突した PR を修正に回す」は残す（キューから外れた PR を draft に戻す）。
- Ruleset の strict は外し、merge queue を必須にする（GitHub 標準の場合）。

## 勧めること（案）

1. **配るプロジェクトが Organization の Public、または GitHub Enterprise Cloud なら、GitHub 標準の merge queue を使う。** 外部に権限を渡さずに済む。
2. **個人のアカウントや Team プランの Private で、並列に PR を流すなら、Mergify か Trunk の無料の枠を試す。** 外部の GitHub App に書き込みの権限を渡すことになるので、入れる前に権限の範囲とデータの扱いを確かめ、セキュリティ担当の承認を得る。
3. どれを使っても、テキストの衝突には、着手の前の予防と修正の役が要る。

## 試すなら（未実施）

- 試行の場（`namu112358/poc-software-factory-20261112`。個人のアカウント）に、Mergify か Trunk の GitHub App を入れる。**GitHub App を入れるのは、リポジトリの権限を外部に渡す設定なので、ユーザーの承認が要る。**
- タスク一覧を触る Issue を 4 件同時に流し、マージを「キューに入れる」に変えて、ブランチの更新の回数・CI の回数・全部マージされるまでの時間を、strict と割り当ての役でやっていた回と比べる。

## 調べ方と限界

- `docs.github.com`・`docs.mergify.com`・`docs.trunk.io` は、調べた環境のネットワークで許可されておらず、読めなかった。検索結果の要約と、各社の料金ページ・比較記事の記載に頼った。比較記事の多くは各社自身の記事で、競合の説明には偏りがありうる。
- 個人のアカウントで GitHub 標準の merge queue が使えないことは、文書に挙がっていないことからの推定で、確かめていない。
- 出典（検索で見つけたもの）:
  - [Pull request merge queue is now generally available（GitHub Changelog、2023-07-12）](https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/)
  - [Merging a pull request with a merge queue（GitHub Docs）](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request-with-a-merge-queue)
  - [Managing a merge queue（GitHub Enterprise Server 3.20 Docs）](https://docs.github.com/en/enterprise-server@3.20/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
  - [Mergify Pricing](https://mergify.com/pricing)、[Mergify（GitHub Marketplace）](https://github.com/marketplace/mergify)、[GitHub Pull Request Merge Queue FAQ（Mergify）](https://articles.mergify.com/github-pull-request-merge-queue-faq/)、[Mergify の batches の文書](https://docs.mergify.com/merge-queue/batches)
  - [Trunk Pricing](https://trunk.io/pricing)、[Trunk の billing の文書](https://docs.trunk.io/billing)、[Trunk の batching の文書](https://docs.trunk.io/merge-queue/optimizations/batching)
