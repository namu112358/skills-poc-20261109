# UI/UX 系 4 ツールの役割の重なりと整理案

いまは次の 4 つが常に同時に有効です。それぞれの中身を読んで、役割の重なりと、互いに矛盾する指示がないかを調べました（調査日: 2026-11-09）。

- Frontend Design（Anthropic の Skill）
- Web Design Guidelines（Vercel の Skill）
- Impeccable（プラグイン）
- UI/UX Pro Max（プラグイン）

読んだ版は次のとおりです。

- Impeccable: 最新版の v4.8.1。PoC で固定している版（`scripts/poc/fetch-plugins.sh`）とは、主要部分で差がありません。
- UI/UX Pro Max: v2.15.0。PoC で固定している版と同じです。

## 決定（2026-11-12。PoC U1〜U4 の結果）

**標準は Impeccable と Web Design Guidelines の 2 つにした。** Frontend Design と UI/UX Pro Max は外した。各プロジェクトの `CLAUDE.md` に「画面を作るときは `impeccable` Skill を使う」と書く（雛形に記載済み）。

| 根拠 | 結果 | 出典 |
|---|---|---|
| 人の評価（依頼者が画面を二択で 85 回比べた） | 勝率: Impeccable 79%、4 つすべて 66%、Frontend Design 40%、ツールなし 32%、UI/UX Pro Max 16%。Impeccable と Frontend Design を直接比べた組は 11 勝 1 敗（同じくらい 2）で Impeccable | [U1/human-pairs.md](../poc/results/workflow/U1/human-pairs.md) |
| Skill が呼ばれるか | 依頼文だけでは呼ばれないことが多い（4 つすべてのとき作る課題 20 回中 11 回、UI/UX Pro Max 単体で 20 回中 6 回）。`CLAUDE.md` で指定すると毎回呼ばれた | [U1](../poc/results/workflow/U1/report.md)・[U2](../poc/results/workflow/U2/report.md) |
| 作った後の仕上げの工程 | 見た目はほとんど変わらなかった。Frontend Design で作り Impeccable で仕上げる分担（勝率 50%）は、最初から Impeccable で作る構成に及ばなかった | [U3](../poc/results/workflow/U3/report.md)・[U1/human-pairs.md](../poc/results/workflow/U1/human-pairs.md) |
| UI のレビュー | 簡単な問題（9 件）も見つけにくい問題（8 件）も、道具が無くてもほとんど見つけた。Web Design Guidelines は残すが、レビューの標準の手順には入れない（任意） | [U1](../poc/results/workflow/U1/report.md)・[U4](../poc/results/workflow/U4/report.md) |
| 費用 | Impeccable は作る段階で Frontend Design の約 2 倍（1 回 $0.6〜2.0）。画面 1 つで差は 1 ドル前後 | [U1/tables.md](../poc/results/workflow/U1/tables.md) |

- 補助として使った AI の見た目の判定は、人の評価との一致が 61%（偶然なら 50%）で、人の好みの代わりにならなかった。見た目は人の評価で決めた。
- 下の「結論」「整理の案」は PoC の前（2026-11-09）に、中身を読んで書いたもの。案 A（Impeccable を作る担当、Web Design Guidelines をレビュー担当、UI/UX Pro Max は既定で無効）の向きは PoC で支持され、Frontend Design も外した。

## 結論（PoC の前の調査。2026-11-09）

- **「画面を作る」役割が 3 つ重なっています。** Frontend Design、Impeccable、UI/UX Pro Max のどれもが、画面を作る・作り直す依頼で呼び出されるように作られています。しかも、それぞれ別の手順を「必ず行う」と指示しています。
- **書体・スタイルの勧めが逆向きです。** UI/UX Pro Max が勧める書体（Inter、Open Sans、Space Grotesk など）やスタイル（すりガラス風など）を、Impeccable の自動チェックが「使い古された書体」「装飾目的の効果」として指摘します。
- **デザインの決定事項を書く場所が 3 つに分かれます。** Impeccable は `DESIGN.md`、UI/UX Pro Max は `design-system/<名前>/MASTER.md`、Frontend Design は会話の中の計画に書きます。
- **レビューの役割も 3 つ重なっています。** 指摘の内容が食い違うことはありませんが、同じ指摘が重複します。

## 各ツールの役割

| | Frontend Design | Web Design Guidelines | Impeccable | UI/UX Pro Max |
|---|---|---|---|---|
| 性格 | 作るときのデザイン方針 | レビュー専用 | 作る・評価・改善・自動チェックをすべて持つ | 書体・配色・スタイルの事例データの検索と、作る手順 |
| 呼び出される場面 | 新しい画面を作る・作り直す | 「UI をレビューして」「アクセシビリティを確認して」 | デザイン、作り直し、評価、監査、仕上げ、アニメーション | デザイン、実装、レビュー、修正 |
| 追加されるもの | なし | なし | `/impeccable` コマンド。**ファイルを編集するたびに自動でチェックする仕組み（既定で有効）** | 実際には Skill が 7 つ入る見込み（ロゴ・バナー・スライド作成などを含む。未確認） |
| 外部への依存 | なし | 実行時に GitHub からルールを取得 | 初回に GitHub から実行ファイルを取得 | Python 3。同梱の画像生成系 Skill は外部 API（Gemini など）を使う |
| AI が読み込む量の目安 | 約 2,300 トークン | 約 2,300 トークン | 新しく作るときは約 20,000 トークン | 約 4,000 トークンに、検索結果が加わる |

## 矛盾している点

| 論点 | UI/UX Pro Max | Impeccable・Frontend Design |
|---|---|---|
| 書体 | 書体の組み合わせ表で Inter を 9 か所で勧めている。例: Playfair Display + Inter、Poppins + Open Sans、Space Grotesk + DM Sans | Inter・Roboto・Open Sans・Space Grotesk などを「使い古された書体」として自動で指摘する |
| スタイル | すりガラス風・ネオン・グラデーションを選択肢として出す | 装飾目的のすりガラス効果やグラデーション文字を避けるよう指示する |
| 決め方 | 業種・製品の種類から、定番のスタイル・配色をデータで引く | 定番や既定値を避け、その依頼だけの選択をするよう指示する |

この結果、UI/UX Pro Max の勧めどおりに実装すると Impeccable が指摘する、という往復が起きる見込みです。そのたびに、直すか、例外にするか、無視するかを判断することになります（実際にどれだけ起きるかは未確認）。

Frontend Design と Impeccable は方向性が一致しています。Web Design Guidelines はデザインの好みには触れないので、ほかのツールと矛盾しません。

## 費用への影響

- **「ランディングページを作って」と頼んだ場合**: 最大で 4 つの Skill（Frontend Design、Impeccable、UI/UX Pro Max、ui-styling）が同時に読み込まれ得ます。合計で 30,000 トークンを超える見積もりで、さらにファイルを編集するたびに Impeccable のチェック結果が加わります。
- **「UI をレビューして」と頼んだ場合**: 3 つのツールが当てはまり、同じ指摘が別々の形式で出る見込みです。
- **毎回かかるもの**: どの Skill を使うかの判断材料として、毎回 7 つ以上の Skill の説明文が AI に渡されます。どの Skill が選ばれるかが、実行ごとにぶれる原因になります。

## 整理の案

### 案 A（推奨）: 作る・レビュー・参照で担当を分ける

| 役割 | 担当 | 扱い |
|---|---|---|
| 作る（デザイン方針） | Impeccable | Frontend Design は外す。方向性は Impeccable にほぼ含まれている |
| 自動チェック | Impeccable | 編集時と作業終了時のチェックをそのまま使う |
| レビュー（ルールに沿っているか） | Web Design Guidelines | PR を出す前に明示的に呼ぶ。Impeccable の監査機能とどちらを主にするかは、試行で決める |
| 書体・配色の事例の参照 | UI/UX Pro Max | 既定では無効にする。使いたい人だけ `scripts/poc-profile.sh` で個人設定に足す |

理由:

- Impeccable は、作る・評価・自動チェック・決定事項の記録（`DESIGN.md`）までを 1 つで持っています。
- UI/UX Pro Max は勧める内容が Impeccable の自動チェックと正面からぶつかります。また、プラグイン単位でしか有効・無効を切り替えられないため、使いたい Skill だけを残すこともできません。

### 案 B: UI/UX Pro Max を残す場合

- 使い道をアクセシビリティ・UX のルールと、技術ごとの指針の検索に限ります。書体・配色を決める機能（デザインシステムの生成）は使わないと、`CLAUDE.md` に明記します。
- 書体・配色の決定事項は Impeccable の `DESIGN.md` を正本にします。
- ただし、この制限は AI への指示でしかなく、強制できません。書体の衝突を避けるには、Impeccable 側で書体ごとに例外を登録する手間も残ります。

## 試行で確かめること（いずれも未確認）

1. UI/UX Pro Max を入れたとき、実際にいくつの Skill が登録されるか（`/plugin` で確認）。
2. 同じ依頼（新しいランディングページの作成、既存画面のレビュー）で、実際にどの Skill が読み込まれるか。「4 つすべて有効」と「案 A」を比べる。
3. Impeccable の自動チェックの指摘件数。特に、UI/UX Pro Max 経由で選ばれた書体が指摘され、やり直しが増えるか。
4. トークン消費と所要時間の差。
5. Security Guidance と Impeccable の作業終了時のチェックが重なったとき、作業が止まったり遅れたりしないか。
6. ネットワークが制限された環境で、ルールや実行ファイルの取得に失敗したときの動き。

## 出典

- Frontend Design: [`.claude/skills/frontend-design/SKILL.md`](../../.claude/skills/frontend-design/SKILL.md)
- Web Design Guidelines: [`.claude/skills/web-design-guidelines/SKILL.md`](../../.claude/skills/web-design-guidelines/SKILL.md)
- Impeccable: [pbakaus/impeccable](https://github.com/pbakaus/impeccable)
  - `plugin/skills/impeccable/SKILL.md`
  - `plugin/hooks/hooks.json`
  - `crates/foundation/src/constants.rs`（使い古された書体の一覧）
  - `crates/hook/src/hook_lib.rs`（自動チェックの既定値）
  - `reference/craft-floor.md`
- UI/UX Pro Max: [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
  - `.claude-plugin/plugin.json`
  - `.claude/skills/ui-ux-pro-max/SKILL.md`
  - `src/ui-ux-pro-max/data/typography.csv`
  - `styles.csv`
