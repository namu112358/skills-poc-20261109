# 失敗を検査に反映するときの方針（テスト・Lint・CI）

- 状態: 案（2026-11-11 作成）
- 対象: このリポジトリから標準を配る各プロジェクトと、このリポジトリ自身
- 関連: [開発標準](ai-software-factory-engineering-standard.md) §2.5（自動テスト）・§2.7（CI）・§2.10（継続的改善）

## 1. この方針で防ぎたいこと

失敗が起きるたびに検査を足していくと、次の 3 つが起きやすくなります。この方針は、再発防止を続けながら、これらを防ぐためのものです。

1. **不安定なテストが増える。** 例: 画面の文字を全部比べるテストは、文言を 1 つ直しただけで落ちる。
2. **落ちても、どこが悪いのか分からない。** 例: Lint で済むことを、独自のテストで大きく固める。
3. **CI が遅くなる。** 例: どの変更でも、毎回すべてのテストを回す。

## 2. 原則

### 2.1 再発防止は「検出できる一番手前の段」に置く

失敗を防ぐ検査は、次の順で、その失敗を検出できる一番手前の段に置きます。手前の段ほど、速く、安定していて、落ちたときの場所がはっきりします。

| 段 | 向いている失敗 | 例 |
|---|---|---|
| 1. 型 | 値の形・取り違え | 列挙型で取りうる値を絞る |
| 2. 既存の Lint ルール | よくある書き方の誤り | `no-floating-promises`、`.only` の検出 |
| 3. 独自の Lint ルール | プロジェクト固有の禁止・構造の決まり | 依存の向き（dependency-cruiser）、禁止 API（ESLint の独自ルール、ast-grep） |
| 4. 単体テスト | 1 つの振る舞いの誤り | 境界値、業務の決まり |
| 5. 結合テスト | 部品のつなぎ目の誤り | DB・API との組み合わせ |
| 6. E2E テスト | 利用者の主要な流れが通らない | ログインから申請の提出まで |
| 7. 指示ファイルの「罠」 | 機械では確かめられない事情 | 他システムが古い列を読む |

- 再発防止を足す PR には、どの段に置いたかと、その理由を 1 行で書く。手前の段で検出できないから後ろの段に置く、という順で考える。
- 構造や書き方の決まり（「この層からあの層を呼ばない」「この関数を使わない」）は、テストではなく Lint のルールにする。ルールにはメッセージに理由を書き、きっかけになった Issue・PR へのリンクを添える。
- 独自の Lint ルールには、ルールごとに「違反する例」と「違反しない例」のテストを付ける（ESLint の `RuleTester`、ast-grep のルールのテスト）。

### 2.2 振る舞いを、必要な所だけ確かめる

- **確かめる範囲**: 受入条件に関わる振る舞いだけを確かめる。画面全体の文字・HTML・スクリーンショットを、まとめて比べる検査は足さない。
- **画面のテスト**: 次の書き方にする。
  - 利用者から見える役割と名前で要素を探す（Playwright の `getByRole` など）。CSS のクラスや DOM の構造には依存しない。
  - 条件が満たされるまで待つ判定（Playwright の web-first assertions）を使う。固定時間の待ちは書かない。
  - 文言は、受入条件で決まっているもの（エラーの文言など）だけを確かめる。
- **スナップショット**: 安定した決まった形の出力（API のスキーマ、データ変換の結果など）にだけ使う。スナップショットだけを判定にするテストは作らない。差分は、更新する前にレビューで中身を見る。
- **単体テストの観点**: 公開された入口（API）を通して、呼んだ後の状態を確かめる。内部の関数の呼び出し順や回数は確かめない。
- **外部への依存**: テストは外部のサービスや時刻・乱数に依存させない。時刻と乱数は固定し、外部のサービスは偽物に差し替える。

### 2.3 落ちたときに、場所と理由が分かるようにする

- 1 つのテストでは 1 つの振る舞いを確かめ、テストの名前に、その振る舞いを書く。
- 再発防止のテストとルールには、きっかけになった Issue・PR へのリンクを付ける。
- 「全部を一度に調べる」大きな独自スクリプトは作らない。ルールごと、振る舞いごとに分ける。
  - 例外: 失敗の内容を項目ごとに表示できるものはよい（例: このリポジトリの `scripts/check-skills.py`）。

### 2.4 CI は、変更に関係する検査だけを PR で回す

- **PR で回すもの**: 変更されたファイルに関係する検査だけを回す。
  - 1 つのアプリのリポジトリでは、GitHub Actions の `paths` で絞る。
  - モノレポでは、依存関係を見て対象を決める道具（Nx・Turborepo の affected）を使う。`paths` だけでは、共通部分の変更が影響する先を見落とすため。
- **main と定期実行で回すもの**: すべての検査を回し、PR で絞ったことによる見落としを拾う。見落としが見つかったら、絞り込みの設定（依存関係や `paths`）を直す。
- **回す順番**: 速い検査（型・Lint）を先に回し、失敗したらそこで止める。同じ PR で新しい push があれば、古い実行は取り消す（`concurrency` の `cancel-in-progress`）。
- **目安の時間**: PR の CI は 10 分以内を目安にする。超えたら、遅いテストを見直す（段を手前に移せないか、外部への依存がないか）。
  - この値は仮置き。各プロジェクトの実測を見て決め直す。

### 2.5 不安定なテストは、記録して直すか消す

- **CI の自動の再試行**: 既定では使わない。Playwright のように「再試行で通ったテストを flaky として報告する」仕組みは、使ってよい。ただし、報告されたものは記録する。
- **見つけたとき**: 不安定なテストを見つけたら、Issue（ラベル `flaky`）に記録し、担当者を決める。
- **隔離**: 隔離（CI の必須の対象から外すこと）は人が決める。隔離するときは、Issue・担当者・期限（例: 2 週間）を決める。期限が来たら、直すか、別の手段で確かめられていることを確かめて消すかを決める。
- **AI エージェントにさせないこと**: テストの `skip`・隔離・再試行の追加と、アサーションの緩和は、AI エージェントが自分の判断で行わない（開発標準 §2.5）。

### 2.6 定期的に減らす

四半期に 1 回、次のものを見直します（開発標準 §2.10「不要な制約や複雑なワークフローを定期的に削減する」）。

- 1 年以上落ちたことがなく、Lint や型で同じことを確かめているテスト
- 実行時間の長い順に上位のテスト
- 隔離したままのテスト

消すときは、理由（どこで同じことを確かめているか）を PR に書きます。

## 3. このリポジトリでの適用

| 項目 | 今の状態 | 対応 |
|---|---|---|
| CI の対象の絞り込み | `poc-app`・`agent-config-check` は `paths` で絞っている。PR 本文の書式チェックは全 PR | 今のままでよい。main への push では、関係するファイルの変更時だけ全件を回している |
| 定期の全件実行 | なし | `poc-app` の規模では不要。テストが増えて PR で絞り込みを始めたら、加える |
| Lint | `poc-app` には ESLint がない（開発標準 §2.5 では「予定」） | 再発防止の検査は、まず Lint で書けないかを考える。そのために、先に ESLint を入れる |
| 取り消し（`cancel-in-progress`） | 未設定 | 実行時間が短いため、今は不要 |
| 不安定なテストの記録 | ラベル `flaky` がない | 最初の 1 件が出たときに作る |
| PoC の採点スクリプト | W ごとに `scripts/poc/grade_w*.py` がある | 試行の採点用で、CI の検査ではない。この方針の対象外 |

## 4. 根拠

2026-11-11 時点で確かめたものです。調べ方は Web 検索の抜粋で、原文をすべて読めてはいません。製品の提供元の記事は、その旨を書いています。

- **不安定なテストの量と原因（Google）**
  - Google の CI では、成功から失敗への変化の約 84% に、不安定なテストが関わっていた。
  - 原因は、並行処理、決まっていない振る舞いへの依存、外部のコード、基盤の問題、テストの実行順への依存。
  - テストの規模（小・中・大）が大きいほど不安定になり、外部に依存しない（hermetic な）環境ほど不安定になりにくい。
  - 出典: [Flaky Tests at Google and How We Mitigate Them](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)、[Where do our flaky tests come from?](https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html)、[Test Flakiness - One of the main challenges of automated testing](https://testing.googleblog.com/2020/12/test-flakiness-one-of-main-challenges.html)
- **壊れやすいテストを防ぐ（Google）**
  - 公開された入口を通して確かめる。
  - 呼び出しのやり取りではなく、状態を確かめる。
  - メソッドごとではなく、振る舞いごとに確かめる。
  - 出典: 『Software Engineering at Google』第 12 章 [Unit Testing](https://abseil.io/resources/swe-book/html/ch12.html)、[Prefer Testing Public APIs Over Implementation-Detail Classes](https://testing.googleblog.com/2015/01/testing-on-toilet-prefer-testing-public.html)
- **画面のテスト（Playwright の公式）**
  - 利用者から見える振る舞いを確かめる。
  - 組み込みの locator と、条件を満たすまで待つ判定を使う。
  - 1 回だけ調べる判定（`isVisible()` など）は、不安定さのもとになる。
  - 出典: [Best Practices](https://playwright.dev/docs/best-practices)
- **スナップショットの落とし穴**
  - 差分を見ずにまとめて更新してしまい、本当の不具合も一緒に承認してしまう。
  - 関係のない部分の変化で落ちる。
  - 出力が変わっていないことは分かるが、正しいことは分からない。
  - 出典: [Snapshot Testing Pitfalls](https://helpmetest.com/blog/snapshot-testing-pitfalls-best-practices/)、[snapshot testing benefits and drawbacks](https://sitepen.com/blog/snapshot-testing-benefits-and-drawbacks)（どちらもテスト関連のサービスの提供元の記事）
- **不安定なテストの隔離**
  - Fowler: まず隔離して被害を抑え、早く直す。隔離したテストが忘れられないように、長く置かない仕組みを持つ。
  - Kubernetes: 不安定なテストを許さない方針（自動の再試行を使わない）をとる。テストには `[Flaky]` の印を付け、Issue（`kind/flake`）で追い、担当の SIG が直すか消す。
  - 出典: [Eradicating Non-Determinism in Tests](https://www.martinfowler.com/articles/nonDeterminism.html)、[Kubernetes: Flaky Tests](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-testing/flaky-tests.md)、[Zero flake policy](https://groups.google.com/g/kubernetes-sig-testing/c/bvqV6I8iF28)
- **構造の決まりを Lint にする**
  - 構造の決まりを独自の Lint ルールにすると、レビューでの指摘を機械の検査に変えられる。
  - ルールには理由を書く。
  - 依存の向きは dependency-cruiser で確かめられる。
  - 出典: [Lint as architecture standards](https://visdom-maturity-matrix.virtuslab.com/guides/development/lint-as-architecture-standards-enforced-rules)、[Taking frontend architecture serious with dependency-cruiser](https://xebia.com/blog/taking-frontend-architecture-serious-with-dependency-cruiser/)
  - 有名 OSS 30 件の指示ファイルの調査では、次の事例があった。
    - vercel/ai: ガイドラインごとに、「検出したら確実に違反」と言える検証スクリプトを対で持ち、変更したファイルにだけ実行する。
    - n8n: AI レビューの設定を CI で検査する。
- **CI の絞り込みと全件実行**
  - PR では影響のある対象だけを回し、main・夜間・リリースで全件を回して、見落としを拾う。
  - `paths` は依存関係を見ないので、モノレポでは依存関係を見る道具を使う。
  - 出典: [Nx: Affected](https://nx.dev/docs/features/ci-features/affected.md)、[Turborepo: Constructing CI](https://turborepo.dev/docs/crafting-your-repository/constructing-ci)、[GitHub Actions monorepo guide](https://warpbuild.com/blog/github-actions-monorepo-guide)（CI サービスの提供元の記事）

## 5. まだ決めていないこと

- PR の CI の目安の時間（10 分は仮置き）
- 隔離の期限（2 週間は例）
- 見直しの頻度（四半期は案）
- E2E テストの対象にする「主要な流れ」の選び方。受入条件から選ぶか、利用の多い流れから選ぶか。
