# 開発ワークフロー PoC — W4 既存コードを横断する大きな変更

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 docs/poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w4.py` で生成）

<strong>W4（既存コードを横断する大きな変更）では、品質に差が出ました。</strong>完走した 8 試行はすべて受け入れテスト 26 件のほぼ全部と認可プローブ 9 件を通過し、影響箇所 16 項目もほぼ網羅しました。差が付いたのは「設計案の比較」で、Compound Engineering（品質 平均 94.5 点）は 2 回とも、データの持ち方・認可の置き場所など複数の論点で案を比べていました。

Feature Dev（86.8 点）は複数の設計案をサブエージェントに出させましたが、比較の中身が記録に残らず（2 回目は「最小変更案を採用、クリーン案は過剰」の 1 論点だけ）、設計案の比較は 5〜11 / 20 点でした。Superpowers（81.3 点）と baseline（82.0 点）は比較をせず、仕様をそのまま設計として進めました。

効率（費用・時間）は、Superpowers・Feature Dev が baseline の 2 倍以内（効率 100 点）、Compound Engineering は費用 3.9 倍・時間 2.2 倍（74 点）、gstack は費用 7.1 倍・時間 3.7 倍（53 点）でした。<strong>同じ品質帯で比べると、品質最高の Compound Engineering は baseline の約 4 倍の費用がかかります。費用を抑えるなら Feature Dev（1.9 倍）が品質 2 位です。</strong>

gstack は 1 回目（打ち切り額が見える方式）では $8.36 で完走し品質 87.5 点でしたが、2 回目（見えない方式）では上限 $10 に計画段階（/autoplan）で達し、実装に至りませんでした（13.4 点）。打ち切り額の見せ方が工程に影響した直接の例です。

## 2 本立ての点数（品質・効率）

- 品質: 最高は Compound Engineering（94.5 点）。これと差なし（差がばらつき以下）: Compound Engineering（94.5）、gstack（50.5）。差あり: Superpowers（81.3、−13.2）、Feature Dev（86.8、−7.7）、baseline（候補なし）（82.0、−12.5）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Compound Engineering（費用 3.9 倍・時間 2.2 倍）で効率 74.0 点。ほかは gstack 53.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 Compound Engineering は、品質でも 1 位（同点を含む: Compound Engineering）。

### 候補ごとの平均

| 候補 | 回数 | 品質 / 100 | 2 回の差 | 効率 / 100 | 総合点（従来） | 費用（baseline 比） | 時間（baseline 比） | 介入 | 質問（参考） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 81.3 | 1.4 | 100.0 | 81.3 | $1.64（1.3 倍） | 7.8 分（1.3 倍） | 0 回 | 0 回 |
| Feature Dev | 2 | 86.8 | 4.5 | 100.0 | 86.8 | $2.39（1.9 倍） | 7.9 分（1.3 倍） | 0 回 | 0 回 |
| Compound Engineering | 2 | 94.5（最高） | 4.0 | 74.0 | 94.5 | $4.99（3.9 倍） | 13.3 分（2.2 倍） | 0 回 | 0 回 |
| gstack | 2 | 50.5（差なし） | 74.1 | 53.0 | 50.5 | $9.20（7.1 倍） | 22.3 分（3.7 倍） | 0 回 | 0 回 |
| baseline（候補なし） | 1 | 82.0 | — | 100.0 | 82.0 | $1.29（1.0 倍） | 6.0 分（1.0 倍） | 0 回 | 0 回 |

### 試行ごとの内訳

| 試行 | 影響箇所の網羅率 / 30 | 受け入れ / 30 | 認可の正しさ / 20 | 設計案の比較 / 20 | 品質 / 100 | 費用 / 50 | 時間 / 30 | 介入 / 20 | 効率 / 100 | 総合点（従来） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers #1 | 30 | 30 | 19.5 | 2.5 | 82.0 | 50.0 | 30.0 | 20 | 100.0 | 82.0 |
| Superpowers #2 | 29.1 | 30 | 19.5 | 2 | 80.6 | 50.0 | 30.0 | 20 | 100.0 | 80.6 |
| Feature Dev #1 | 30 | 30 | 19.5 | 5 | 84.5 | 50.0 | 30.0 | 20 | 100.0 | 84.5 |
| Feature Dev #2 | 30 | 30 | 18 | 11 | 89.0 | 50.0 | 30.0 | 20 | 100.0 | 89.0 |
| Compound Engineering #1 | 28.6 | 27.4 | 20 | 16.5 | 92.5 | 30.0 | 24.0 | 20 | 74.0 | 92.5 |
| Compound Engineering #2 | 30 | 30 | 20 | 16.5 | 96.5 | 30.0 | 24.0 | 20 | 74.0 | 96.5 |
| gstack #1 | 30 | 30 | 19.5 | 8 | 87.5 | 15.0 | 18.0 | 20 | 53.0 | 87.5 |
| gstack #2 | 0 | 8.4 | 0 | 5 | 13.4 | 15.0 | 18.0 | 20 | 53.0 | 13.4 |
| baseline（候補なし） #1 | 30 | 30 | 20 | 2 | 82.0 | 50.0 | 30.0 | 20 | 100.0 | 82.0 |

### 計算方法と判断の記録

- 品質 = （影響箇所の網羅率 30 + 受け入れ 30 + 認可の正しさ 20 + 設計案の比較 20）の得点 ÷ 100 × 100。
- 効率 = 費用 50 + 時間 30 + 介入 20。費用・時間は baseline（$1.2901・361 秒）に対する倍率で、2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。介入は 0 回 = 20、1 回 = 10、2 回以上 = 0。
- 質問の回数は効率から引かない（参考値）。品質の差が、比べる 2 候補の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする。
- 定義は docs/poc/PLAN.md §4.4。計算は scripts/poc/two_axis.py。従来の総合点・順位はこの節では変えない。

## 1 回目（打ち切り額が見える）と 2 回目（見えない）の比較

1 回目は 1 試行の打ち切り額を --max-budget-usd で子セッションに渡す方式（flag。子セッションのモデルに残額が見える）、2 回目は見せずに外側で見積もって止める方式（watch）で行った（ユーザーの決定）。上限額は同じ。どの候補も各方式で 1 回ずつなので、候補間の公平は保たれる。親セッションの文章で打ち切り額・予算に触れた発言は、両方式とも全試行で 0 件だった。gstack は、上限 $10・watch 方式では計画段階（/autoplan）で上限に達し実装に至らなかった。flag 方式（上限が見える）の #1 は $8.36 で完走しており、打ち切り額の可視性が工程に影響した直接の例である。

| 候補 | 費用（1 回目 → 2 回目） | 時間（分） | ターン（参考） | サブエージェント | 点数 | 打ち切り額・予算への言及 |
|---|---|---|---|---|---|---|
| Compound Engineering | $4.30 → $5.69 | 14.2 → 12.5 | 130 → 72 | 4 → 8 | 92.5 → 96.5 | 0 → 0 |
| Feature Dev | $2.26 → $2.53 | 7.3 → 8.5 | 7 → 85 | 5 → 7 | 84.5 → 89.0 | 0 → 0 |
| gstack | $8.36 → $10.04 | 21.3 → 23.4 | 117 → 0 | 16 → 7 | 87.5 → 13.4 | 0 → 0 |
| Superpowers | $1.78 → $1.50 | 7.4 → 8.3 | 5 → 3 | 1 → 1 | 82.0 → 80.6 | 0 → 0 |

試行間の独立性の確認結果: 全 9 試行で、他の試行の作業用コピー・docs/poc/・正解データへの参照（grade.py の isolation_suspects と answer_key_access）は 0 件だった。

## 課題

タスクをチームで共有できるようにする（権限モデルの変更）。これまで全員が全タスクを閲覧・編集できたのを、「自分の個人タスク」と「所属チームのタスク」だけに限る。チーム・役割（管理者／メンバー）・既存データの移行・既存のタスク API 4 本の変更・チームの API 5 本・タスク一覧／詳細の変更・チーム画面 2 つ。仕様書は `docs/poc/tasks/wf-W4.md`。

## 結果の概要（平均点）

| 候補 | 回数 | 合計 / 100 | 影響箇所 / 30 | 受け入れ / 30 | 認可 / 20 | 設計案の比較 / 20 | 平均費用 | 平均時間（分） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 81.3 | 29.6 | 30.0 | 19.5 | 2.2 | $1.64 | 7.8 |
| Feature Dev | 2 | 86.8 | 30.0 | 30.0 | 18.8 | 8 | $2.39 | 7.9 |
| **Compound Engineering** | 2 | 94.5 | 29.3 | 28.7 | 20.0 | 16.5 | $4.99 | 13.3 |
| gstack | 2 | 50.5 | 15.0 | 19.2 | 9.8 | 6.5 | $9.20 | 22.3 |
| baseline（候補なし） | 1 | 82.0 | 30.0 | 30.0 | 20.0 | 2 | $1.29 | 6.0 |

## 試行ごとの結果

| 試行 | 点数 | E2E | チェック | 認可プローブ | 影響箇所 | 設計案 | 介入 / 質問 | コード追加行 | テスト追加行 | 費用 | 時間（分） | ターン | サブエージェント | 拒否された操作 | 使われた Skill |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 82.0 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 2.5 | 0 / 0 | 579 | 271 | $1.78 | 7.4 | 5 | 1 | 11 | superpowers:brainstorming, superpowers:executing-plans, superpowers:writing-plans |
| Superpowers #2 | 80.6 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 29.1 | 2 | 0 / 0 | 569 | 317 | $1.50 | 8.3 | 3 | 1 | 11 | superpowers:brainstorming, superpowers:test-driven-development, superpowers:writing-plans |
| Feature Dev #1 | 84.5 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 5 | 0 / 0 | 624 | 359 | $2.26 | 7.3 | 7 | 5 | 12 | — |
| Feature Dev #2 | 89.0 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 11 | 0 / 0 | 645 | 307 | $2.53 | 8.5 | 85 | 7 | 9 | — |
| Compound Engineering #1 | 92.5 | 23/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 28.6 | 16.5 | 0 / 0 | 614 | 427 | $4.30 | 14.2 | 130 | 4 | 26 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-simplify-code, compound-engineering:ce-work |
| Compound Engineering #2 | 96.5 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 16.5 | 0 / 0 | 653 | 394 | $5.69 | 12.5 | 72 | 8 | 17 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-work |
| gstack #1 | 87.5 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 8 | 0 / 0 | 660 | 456 | $8.36 | 21.3 | 117 | 16 | 3 | — |
| gstack #2 | 13.4 | 1/26 | typecheck ✅ test ✅ build ✅ | 0/9 | 0.0 | 5 | 0 / 0 | 0 | 0 | $10.04 | 23.4 | 0 | 7 | 0 | — |
| baseline（候補なし） #1 | 82.0 | 26/26 | typecheck ✅ test ✅ build ✅ | 9/9 | 30.0 | 2 | 0 / 0 | 576 | 319 | $1.29 | 6.0 | 57 | 0 | 12 | code-review |

## 影響箇所ごとの対応（0〜1、採点者 2 名・2 回の平均）

| 影響箇所 | Superpowers | Feature Dev | Compound Engineering | gstack | baseline（候補なし） |
|---|---:|---:|---:|---:|---:|
| 1. マイグレーション | 1 | 1 | 1 | 0.5 | 1 |
| 2. 既存データの移行 | 1 | 1 | 1 | 0.5 | 1 |
| 3. 初期データ | 1 | 1 | 1 | 0.5 | 1 |
| 4. 型と読み出し | 1 | 1 | 1 | 0.5 | 1 |
| 5. 一覧の閲覧範囲 | 1 | 1 | 1 | 0.5 | 1 |
| 6. 1 件の閲覧範囲 | 1 | 1 | 1 | 0.5 | 1 |
| 7. 作成時の所属・作成者 | 1 | 1 | 1 | 0.5 | 1 |
| 8. 担当者の規則 | 1 | 1 | 1 | 0.5 | 1 |
| 9. 所属変更の権限 | 1 | 1 | 1 | 0.5 | 1 |
| 10. チームの処理 | 1 | 1 | 1 | 0.5 | 1 |
| 11. チームの API | 1 | 1 | 1 | 0.5 | 1 |
| 12. 一覧画面 | 1 | 1 | 1 | 0.5 | 1 |
| 13. 詳細画面 | 1 | 1 | 1 | 0.5 | 1 |
| 14. チーム画面・ヘッダー | 1 | 1 | 0.88 | 0.5 | 1 |
| 15. 既存テストの更新 | 1 | 1 | 1 | 0.5 | 1 |
| 16. 新しいテストと文書 | 0.75 | 1 | 0.75 | 0.5 | 1 |

## 認可・設計のレビューの項目別平均（0〜5）

| 候補 | 認可: 一貫性 | 認可: 入力と境界 | 設計: 比較の有無 | 設計: 選択肢 | 設計: トレードオフ | 設計: 決定と実装 |
|---|---:|---:|---:|---:|---:|---:|
| Superpowers | 4.8 | 4.8 | 0 | 0 | 0 | 2.2 |
| Feature Dev | 4.5 | 4.2 | 2.2 | 2 | 1.2 | 2.5 |
| Compound Engineering | 5 | 5 | 4.2 | 4 | 3.2 | 5 |
| gstack | 2.5 | 2.2 | 1.5 | 1.5 | 1.5 | 2.0 |
| baseline（候補なし） | 5 | 5 | 0 | 0 | 0 | 2 |

採点者 2 名の差が大きい項目（影響箇所は 1、ほかは 3 点以上）はありませんでした。

## 所見

- <strong>受け入れテスト・認可・影響箇所の網羅では、完走した試行の間にほとんど差がありませんでした。</strong>baseline も含め、閲覧範囲の SQL を 1 か所にまとめ、関数の署名に閲覧者を必須で渡す設計に自然に行き着いています。権限モデルの変更でも、仕様が明確なら候補なしで十分に対応できる範囲でした。
- <strong>差が付いたのは設計案の比較です。</strong>Compound Engineering は 2 回とも計画書の「Alternatives Considered」で複数の論点を比べ、採用理由（Key Technical Decisions）が実装と一致していました。Feature Dev はアーキテクトのサブエージェントで 2 案を出させましたが、比較の記述が薄く、1 回目は案の到着を待たずに実装を始めていました。gstack の /autoplan は判断の記録は多いものの、主に仕様の解釈の判断で、設計の代替案の比較ではありませんでした。Superpowers と baseline は比較していません。
- Compound Engineering #1 だけが画面の不具合（DB の行をそのままクライアント部品に渡し、管理者用のメンバー管理画面が表示されない）を残しました。参照実装を作ったときにも同じ問題が出た、このコードベース特有の落とし穴です。他の試行は回避していました。
- <strong>同じ品質なら、どれだけ安く速いか</strong>: 品質最高の Compound Engineering は baseline の 3.9 倍の費用・2.2 倍の時間です。品質 2 位の Feature Dev は 1.9 倍・1.3 倍で、設計案の比較を除けば Compound Engineering とほぼ同じ成果でした。Superpowers は baseline とほぼ同じ費用・品質で、候補を使う効果は見えませんでした。
- gstack は品質の 2 回の差（74.1 点）が打ち切りによるもので、2 本立ての自動判定が「最高品質と差なし」としているのはこのばらつきのためです。完走した #1 だけを見ると品質 87.5 点（Feature Dev と同程度）で、費用は baseline の 6.5 倍でした。
- security-guidance の試行中の指摘（バックグラウンドのレビュー）は、全試行で 0 件でした。子セッションに LLM レビュー用の認証情報が渡らず、パターンによる警告だけが動いていた可能性があります。認可の確認は、認可プローブとブラインドのコードレビューで行いました。

## 試行の詳細

### Superpowers #1 — 82.0 点

brainstorming → writing-plans → executing-plans の Skill が発火したが、「仕様をそのまま承認済みの設計とする」として設計案は比べなかった。計画書（docs/superpowers/plans/）に採用構成はある。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 4.5）:

- 閲覧範囲を tasks.ts の VISIBLE_TO_VIEWER に一本化し、getTask/listTasks/updateTask がどれも閲覧者 ID を必須で取るため、一覧・1 件取得・更新・画面の判定が揃っている。requireTeamMember で 404→403→400 の順に確認し、teamId の型違い（文字列 "1" など）も validateTaskInput で 400 にしている。減点に当たる指摘は無い。
- viewer を必須にした getTask・listTasks・updateTask と、Route 共通の requireTeamMember（404）→ 役割（403）の順で、権限の確認は一貫している。軽微な点が 2 つある。メンバー追加の本文（userId・role）の検証が lib ではなく Route（members/route.ts）に直接書かれている。また validateTaskInput の担当者・所属の分岐（unchanged・teamValid）が込み入っていて読みにくく、PATCH の検証と更新も 1 つのトランザクションにまとまっていない。

設計のレビュー（設計: 比較の有無 0 ・ 設計: 選択肢 0 ・ 設計: トレードオフ 0 ・ 設計: 決定と実装 2.5）:

- 仕様をそのまま承認済みの設計とみなして計画に進んでおり、設計案の比較は一切ない。計画書の Architecture に『可視性は tasks.ts の SQL（viewer 引数）に集約、チーム操作は teams.ts、Route と画面は薄く』と採用方針と短い理由があり、差分の VISIBLE_TO_VIEWER と一致するため D4 のみ加点。
- 「仕様をそのまま承認済みの設計とする」として、設計案の比較はしていない。計画書には採用した構成（可視性を viewer 引数つきの SQL に集める、team-roles.ts の分離）があり、owner を NULL 可にした理由（SQLite の制約）も書かれていて、実装と一致しているので D4 だけ点を付けた。

変更ファイル:

- `CLAUDE.md` +2 −1（doc）
- `docs/superpowers/plans/2026-11-09-team-sharing.md` +50 −0（tool-artifact）
- `src/app/api/tasks/[id]/route.ts` +11 −5（code）
- `src/app/api/tasks/route.ts` +11 −6（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +23 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +43 −0（code）
- `src/app/api/teams/route.ts` +19 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +6 −2（code）
- `src/app/tasks/page.tsx` +22 −4（code）
- `src/app/teams/[id]/members.tsx` +110 −0（code）
- `src/app/teams/[id]/page.tsx` +27 −0（code）
- `src/app/teams/page.tsx` +23 −0（code）
- `src/lib/api.ts` +12 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +23 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/tasks.ts` +119 −26（code）
- `src/lib/team-roles.ts` +13 −0（code）
- `src/lib/teams.ts` +87 −0（code）
- `tests/schema.test.ts` +45 −0（test）
- `tests/tasks.test.ts` +145 −25（test）
- `tests/teams.test.ts` +81 −0（test）

コミット:

- `dd0d5ec fix: PATCH でタスクの読み込みを本文の読み取り後に行い、更新できなかったときは 404 を返す`
- `496c60a feat: タスクをチームで共有できるようにする（チーム・役割・閲覧権限、チーム API と画面）`

### Superpowers #2 — 80.6 点

brainstorming・writing-plans・test-driven-development が発火。設計の比較は無し。poc-app/CLAUDE.md の API 一覧・権限の説明を更新しておらず（影響箇所 16 が 0.5）、権限を確認しない getTask が export のまま残る点で軽く減点。

コードのレビュー（影響箇所 29.1 / 30、認可: 一貫性 4.5 ・ 認可: 入力と境界 5）:

- poc-app/CLAUDE.md の API 一覧・権限の説明が更新されていないので、16 を 0.5 にした（単体テストは tests/teams.test.ts と tests/tasks.test.ts に十分ある）。認可は VISIBLE_TO_USER と getVisibleTask にまとまっていて、一覧・1 件取得・PATCH・画面のどれも同じ規則を使っている。権限を確認しない getTask を内部用として残しているが、ルートや画面からは呼ばれていないので減点していない。
- 機能はほぼ網羅しているが、poc-app/CLAUDE.md の API 一覧・権限の説明を更新していない（16 は 0.5）。権限確認なしの getTask が getVisibleTask と並んで export されたまま残り、updateTask も内部で getTask を使う。そのため認可は API Route 側の事前確認だけが頼りで、管理者かどうかの確認も route に分散している（A は軽微な指摘で 4）。

設計のレビュー（設計: 比較の有無 0 ・ 設計: 選択肢 0 ・ 設計: トレードオフ 0 ・ 設計: 決定と実装 2）:

- brainstorming を使うと宣言したが、設計案の比較は見当たらず、計画書は 1 案の構成（migration 3、権限判定を tasks.ts と teams.ts に置く）を述べるだけ。採用した構成と仕様外の判断（担当者の再検証の条件、同値 teamId の扱い）は理由付きで書かれ、差分とも一致するので D4 は中程度。
- ブレインストーミングを宣言しているが、設計案の比較は資料に無い。計画書には採用した構成（マイグレーション 3、判定を src/lib に置く）が書かれているものの理由が無いので、D4 は低くした。実装はその構成に沿っている。

変更ファイル:

- `docs/superpowers/plans/2026-11-09-team-tasks.md` +45 −0（tool-artifact）
- `src/app/api/tasks/[id]/route.ts` +11 −5（code）
- `src/app/api/tasks/route.ts` +13 −6（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +24 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +29 −0（code）
- `src/app/api/teams/route.ts` +18 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +7 −3（code）
- `src/app/tasks/page.tsx` +22 −4（code）
- `src/app/teams/[id]/member-manager.tsx` +91 −0（code）
- `src/app/teams/[id]/page.tsx` +26 −0（code）
- `src/app/teams/page.tsx` +21 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +22 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/tasks.ts` +117 −19（code）
- `src/lib/teams.ts` +138 −0（code）
- `tests/db.test.ts` +38 −0（test）
- `tests/tasks.test.ts` +154 −28（test）
- `tests/teams.test.ts` +125 −0（test）

コミット:

- `b8bf62e feat: チームでタスクを共有できるようにする`

### Feature Dev #1 — 84.5 点

コードの探索とアーキテクト（最小変更案・クリーン案）のサブエージェント 5 つを起動し、報告で「2 案を比較した」と書いたが、比較の中身が記録に無く、案の到着前に実装を始めていた（設計 5 / 20）。認可はほぼ満点。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 4.5）:

- 減点はない。getTask と updateTask に viewer を必須の引数として渡す形に変え、閲覧の判定を VISIBLE の 1 か所にまとめたので、権限を確認しない経路が残っていない。所属の変更は isForbiddenTeamChange（403）と validateTaskInput（所属先・変更後の担当者の確認）で扱っている。normalizeTeamName が文字数を UTF-16 の長さで数えている点は細かい違いで、点数には影響させていない。
- getTask・listTasks・updateTask の署名を変えて viewer を必須にしたので、閲覧範囲の抜け道は無い。軽微な点が 2 つある。PATCH の権限確認（isForbiddenTeamChange）・検証・updateTask が 1 つのトランザクションにまとまっていない。また validateTaskInput は、現在と同じ teamId を送っただけでも今の担当者を検証し直すため、担当者がチームを外れたままのタスクでは不要な 400 になる。

設計のレビュー（設計: 比較の有無 1.5 ・ 設計: 選択肢 1 ・ 設計: トレードオフ 0.5 ・ 設計: 決定と実装 2）:

- アーキテクト 2 名（最小変更・クリーン）を起動し、最終報告で『設計は 2 案を比較し』と述べるが、どの論点でどちらを採ったか、長所短所は資料に一切無い。差分は tasks テーブルを作り直す方式で、その選択の理由は設計の記述に無い（コード中のコメントのみ）ため、決定と理由の明示が不十分。
- 最小変更案とクリーン設計案のサブエージェントを起動し、報告で「設計は 2 案を比較した」と書いているが、どの論点でどう比べたかが資料に一切無い。サブエージェントの結果を待たずにマイグレーションと lib を書き始めている。採用した設計（閲覧者 ID を必須にする、テーブルの作り直し）は実装から読み取れるが、理由はほとんど書かれていない。

変更ファイル:

- `CLAUDE.md` +7 −1（doc）
- `src/app/api/tasks/[id]/route.ts` +13 −5（code）
- `src/app/api/tasks/route.ts` +10 −5（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +24 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +29 −0（code）
- `src/app/api/teams/route.ts` +21 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +7 −2（code）
- `src/app/tasks/page.tsx` +23 −4（code）
- `src/app/teams/[id]/member-list.tsx` +97 −0（code）
- `src/app/teams/[id]/page.tsx` +32 −0（code）
- `src/app/teams/page.tsx` +21 −0（code）
- `src/lib/db/index.ts` +11 −3（code）
- `src/lib/db/migrations.ts` +36 −0（code）
- `src/lib/db/seed.ts` +27 −7（code）
- `src/lib/ids.ts` +5 −0（code）
- `src/lib/tasks.ts` +132 −30（code）
- `src/lib/teams.ts` +130 −0（code）
- `src/lib/users.ts` +5 −1（code）
- `tests/db.test.ts` +36 −3（test）
- `tests/tasks.test.ts` +192 −23（test）
- `tests/teams.test.ts` +131 −0（test）

コミット:

- `6f3498c タスクをチームで共有できるようにする`

### Feature Dev #2 — 89.0 点

アーキテクトに 2 案を出させ、最小変更案を採用して「Result 型・テーブル再構築は今回の規模には過剰」と見送った（設計 11 / 20）。権限を確認しない getTask・updateTask が export のまま残り、Route 側の事前確認に頼る形で認可のレビューは 8 / 10。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 4 ・ 認可: 入力と境界 4）:

- 権限を見ない getTask が export されたまま残り、updateTask もその getTask を使うので、閲覧範囲の確認は API Route が先に getVisibleTask を呼ぶことに頼っている（今の経路に抜けは無いが、二重定義で抜け道になりうる）。requestsTeamChange はキーがあるだけで真になるため、作成者でないメンバーが今と同じ teamId を送っても 403 になる。validateTeamInput は文字数を .length（UTF-16 の単位）で数えている。
- 閲覧の確認が無い getTask・updateTask が export されたまま残っており、PATCH が通るかは Route 側で先に getVisibleTask を呼ぶことに頼っている（確認の二重化・抜け道になりうる。updateTask はトランザクションでもない）。requestsTeamChange は teamId という項目があるだけで所属変更とみなすため、作成者でないメンバーが現在と同じ teamId を送っても 403 になる。ほかの要件（validateTaskPlacement、requireAdmin、最後の管理者の保護）は正しい。

設計のレビュー（設計: 比較の有無 3 ・ 設計: 選択肢 3 ・ 設計: トレードオフ 2 ・ 設計: 決定と実装 3）:

- 『最小変更案』と『クリーン案』の 2 案をアーキテクトに出させ、最小変更案を採用し、クリーン案の Result 型導入と tasks テーブル再構築を『今回の規模には過剰』として見送った。比較は全体方針の 1 論点に限られ、トレードオフは『過剰』の一言で具体性に欠ける（案の到着前に実装を始めてもいる）。差分は ALTER TABLE・Result 型なしで採用案と一致。
- 最小変更案とクリーン案を比べ、Result 型の導入と tasks テーブルの再構築を見送って最小変更案を採ったと書いている。ただ比べた中身は「今回の規模には過剰」の一言だけで、影響する関数やテスト、権限の抜けの危険に基づくトレードオフは書かれていない。実装は採用した方針（NULL 可の ADD COLUMN、既存の ValidationResult を流用）に沿っている。

変更ファイル:

- `CLAUDE.md` +2 −1（doc）
- `src/app/api/tasks/[id]/route.ts` +21 −4（code）
- `src/app/api/tasks/route.ts` +22 −5（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +16 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +39 −0（code）
- `src/app/api/teams/route.ts` +18 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +7 −3（code）
- `src/app/tasks/page.tsx` +23 −4（code）
- `src/app/teams/[id]/member-list.tsx` +102 −0（code）
- `src/app/teams/[id]/page.tsx` +32 −0（code）
- `src/app/teams/page.tsx` +21 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +24 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/tasks.ts` +119 −13（code）
- `src/lib/team-roles.ts` +13 −0（code）
- `src/lib/teams.ts` +158 −0（code）
- `tests/db.test.ts` +40 −0（test）
- `tests/tasks.test.ts` +131 −9（test）
- `tests/teams.test.ts` +136 −0（test）

コミット:

- `355806a タスクをチームで共有できるようにする（個人/チームのタスクと権限）`

### Compound Engineering #1 — 92.5 点

計画書の Alternatives Considered で 3 論点（中間テーブルか列か、アプリ側の絞り込みか SQL の条件か、Server Action か API か）を比較（設計 16.5 / 20）。ただし管理者のチーム詳細で DB の行（null プロトタイプ）をそのままクライアント部品に渡したため、メンバーの追加・外す画面が表示されず受け入れ 23/26。

コードのレビュー（影響箇所 28.6 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 5）:

- createTaskFor/updateTaskFor と teams.ts の getTeamFor に、権限の判定と 404→403→400 の順序をまとめており、認可には抜けが無い。差分に poc-app/CLAUDE.md の更新（API 一覧・権限の説明）が無いので、16 は単体テストの分だけの 0.5 にした。
- teams.ts の listMembers が node:sqlite の行（null プロトタイプ）をそのまま返しており、teams/[id]/page.tsx はそれをクライアントコンポーネント MemberManager に渡している。このため管理者がチーム詳細を開くと、React の「null prototypes are not supported」エラーで追加・外す画面が表示されない（14 は 0.5）。poc-app/CLAUDE.md も更新していない（16 は 0.5）。認可は createTaskFor/updateTaskFor・addMember/removeMember に集約され、判定の順序も入力の検証も適切。

設計のレビュー（設計: 比較の有無 4.5 ・ 設計: 選択肢 4 ・ 設計: トレードオフ 3 ・ 設計: 決定と実装 5）:

- Alternatives Considered で、task_teams 結合表と tasks.team_id 列、取得後のアプリ側での絞り込みと SQL 述語、Server Action と既存 API 経由という 3 つの論点を比べ、いずれもこのコードベースで現実的な案。ただし各案の理由は 1 行で、短所の掘り下げ（影響する関数・テスト）は薄い。KTD1〜7 で採用理由が明示され、差分（VISIBLE_TO_VIEWER、Outcome 型、member-manager の fetch＋refresh）と一致する。
- 「Alternatives Considered」で、task_teams の中間テーブルと tasks.team_id の列（データの持ち方）、取得後にアプリ側で絞る方式と SQL の条件 1 か所（呼び出し箇所を 1 つ漏らせば漏えいする）、Server Action と API 経由（認可の経路が 2 つになる）を比べている。DB 側の NOT NULL も SQLite の制約に基づいて見送った。複数の論点を現実的な案で比べているが、各論点は 1 文の却下理由にとどまるので D3 は 3 とした。KTD と実装（VISIBLE_TO_VIEWER、Outcome 型、クライアントからの fetch）は一致している。

不合格の受け入れテスト:

- 画面: 所属していないチームの詳細は 404 ページ、管理者には追加フォームと各メンバーの「外す」ボタン: `sato: forms=0 input=0 buttons=0`
- 画面: 管理者がフォームでメンバーを追加し、「外す」で一覧から消せる: `locator.evaluate: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('form[aria-label="メンバーの追加"] [name="userId"]')[22m `
- 画面: 最後の管理者を外そうとすると role=alert のエラーが出て、一覧は変わらない: `locator.click: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('[data-testid="member"]').filter({ hasText: '佐藤' }).getByRole('button', { name: '`

変更ファイル:

- `docs/plans/2026-11-09-0447-feat-team-shared-tasks-plan.md` +301 −0（tool-artifact）
- `src/app/api/tasks/[id]/route.ts` +6 −7（code）
- `src/app/api/tasks/route.ts` +10 −8（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +14 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +20 −0（code）
- `src/app/api/teams/route.ts` +20 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +7 −2（code）
- `src/app/tasks/page.tsx` +24 −4（code）
- `src/app/teams/[id]/member-manager.tsx` +91 −0（code）
- `src/app/teams/[id]/page.tsx` +40 −0（code）
- `src/app/teams/page.tsx` +23 −0（code）
- `src/lib/api.ts` +7 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +24 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/outcome.ts` +8 −0（code）
- `src/lib/tasks.ts` +141 −36（code）
- `src/lib/teams.ts` +137 −0（code）
- `src/lib/util.ts` +12 −0（code）
- `tests/db.test.ts` +68 −0（test）
- `tests/tasks.test.ts` +210 −20（test）
- `tests/teams.test.ts` +149 −0（test）

コミット:

- `379d31b fix: チーム画面のレビュー指摘を反映する`
- `d1ba41d feat: タスクをチームで共有できるようにする`

### Compound Engineering #2 — 96.5 点

owner の持たせ方（テーブル再作成か NULL 可の列か）、トランザクションの方式、Server Action か API かを SQLite の制約に基づいて比較（設計 16.5 / 20）。受け入れ・認可・影響箇所は満点で、品質は全試行で最高の 96.5 点。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 5）:

- 減点はない。createTaskFor と updateTaskFor（トランザクション内）が、閲覧の 404 → 型の 400 → 作成者以外の所属変更の 403 → 変更先と担当者の 400 の順で確かめ、本文の owner は使わない。権限を確認しない getTask は lib の内部用として残っているが、ルートと画面は getViewableTask だけを使い、CLAUDE.md にもその取り決めを書いている。
- 閲覧範囲を tasks.ts の VISIBLE_TO_VIEWER と getViewableTask に集め、一覧・1 件取得・更新（updateTaskFor）・画面のすべてで同じ規則を使っており、減点する箇所は見当たらない。updateTaskFor は閲覧の確認から更新までを transaction で行い、teamId の型（文字列・小数・真偽値）、作成者以外による所属変更（403）、変更後の担当者、最後の管理者も lib で検証している。単体テストは移行・閲覧範囲・役割の境界まで網羅しており、CLAUDE.md も更新されている。

設計のレビュー（設計: 比較の有無 4 ・ 設計: 選択肢 4 ・ 設計: トレードオフ 3.5 ・ 設計: 決定と実装 5）:

- データの形は一択と判断して比較を省いた理由を明記したうえで、owner を NOT NULL にするテーブル再作成と NULL 可の ADD COLUMN（SQLite の制約、NULL 行は誰にも見えず安全側）、BEGIN IMMEDIATE・楽観ロックと単一トランザクション（node:sqlite は同期単一プロセス）、Server Action と API 経由のクライアント部品を、このコードの事実に基づいて比べている。各論点は 1 段落程度で厚くはない。KTD1〜8 と PATCH の検査順の図で決定と理由が明示され、差分（kind 付き結果型、ALTER TABLE、member-manager）と一致する。
- owner を NOT NULL にするテーブル再作成と NULL 可の列の追加（SQLite の ADD COLUMN の制約が根拠）、Server Action とクライアントから API を呼ぶ方式（認可の判定が二重になる）、BEGIN IMMEDIATE とトランザクションだけで済ませる方式を比べている。データの持ち方は「一択」として比べておらず、各論点も短い却下理由にとどまるため減点した。採用した KTD（可視性の SQL 条件を 1 か所に置く、結果型、NULL 可の列）はそのまま実装されている。

変更ファイル:

- `CLAUDE.md` +8 −1（doc）
- `docs/plans/2026-11-09-0531-feat-team-task-sharing-plan.md` +311 −0（tool-artifact）
- `src/app/api/tasks/[id]/route.ts` +11 −8（code）
- `src/app/api/tasks/route.ts` +13 −8（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +17 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +29 −0（code）
- `src/app/api/teams/route.ts` +18 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +8 −3（code）
- `src/app/tasks/page.tsx` +22 −4（code）
- `src/app/teams/[id]/member-manager.tsx` +75 −0（code）
- `src/app/teams/[id]/page.tsx` +39 −0（code）
- `src/app/teams/page.tsx` +21 −0（code）
- `src/lib/api.ts` +15 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +24 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/result.ts` +13 −0（code）
- `src/lib/tasks.ts` +159 −31（code）
- `src/lib/teams.ts` +159 −0（code）
- `tests/db.test.ts` +51 −5（test）
- `tests/tasks.test.ts` +186 −24（test）
- `tests/teams.test.ts` +157 −0（test）

コミット:

- `7e605bd feat: タスクをチームで共有できるようにする`

### gstack #1 — 87.5 点

/autoplan で多数のレビュー（サブエージェント 16）を回し、判断 D1〜D9 を CLAUDE.md に表で残した。ただし判断は主に仕様の解釈で、データの持ち方・認可の置き場所の代替案は比べていない（設計 8 / 20）。実装は受け入れ・認可・影響箇所とも満点。費用は全完走試行で最高の $8.36。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 4.5）:

- VISIBLE_TASK_SQL に閲覧条件を集め、updateTask/addMember/removeMember を BEGIN IMMEDIATE のトランザクションで包んで、確認から書き込みまでを 1 つにまとめている。teamChangeForbidden で 403 を入力の 400 より先に返しており、所属の変更後の担当者も確認している。単体テストと CLAUDE.md の権限の説明も十分にある。減点に当たる指摘は無い。
- VISIBLE_TASK_SQL 1 か所で閲覧範囲を決めている。updateTask・addMember・removeMember はトランザクションの中で 404→403→400→409 の順に確認し、CLAUDE.md とテストも充実している。軽微な点として、validateTaskInput や addMember のエラーの details が受け取った値を JSON.stringify でそのまま返し、403 の文言に作成者の ID を含めている（B は 4）。

設計のレビュー（設計: 比較の有無 1.5 ・ 設計: 選択肢 1.5 ・ 設計: トレードオフ 1.5 ・ 設計: 決定と実装 3.5）:

- 多数のレビューを回したが、比べたのは範囲の採否（エラーの code 欄、索引、非管理者の自己離脱を 403 にするか等）の二択の判断で、データの持ち方や認可の置き場所の代替案は検討されていない（レビュアー自身が『visibility 列との比較が無い』と指摘）。採用方針（VISIBLE_TASK_SQL 一本化・ServiceError 結果型）と判断は明示され CLAUDE.md にも表で残り、差分と一致する。
- 判断 D1〜D9 は主に仕様の解釈（同じ teamId は変更なし、管理者でないメンバーは自分を外せないなど）で、設計案の比較ではない。レビュアー自身が「visibility 列との比較が無い」と指摘している。比較に近いのは、エラー本文に code を足すかどうか（仕様で本文が決まっているので見送り）と、ACL の汎用基盤を作らないことくらいである。採用した設計（VISIBLE_TASK_SQL、ServiceError と respondError、500 のラッパー）は理由とともに書かれており、実装と一致している。

変更ファイル:

- `CLAUDE.md` +21 −1（doc）
- `TODOS.md` +15 −0（doc）
- `src/app/api/tasks/[id]/route.ts` +16 −10（code）
- `src/app/api/tasks/route.ts` +14 −10（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +16 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +26 −0（code）
- `src/app/api/teams/route.ts` +19 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +7 −2（code）
- `src/app/tasks/page.tsx` +22 −4（code）
- `src/app/teams/[id]/member-manager.tsx` +112 −0（code）
- `src/app/teams/[id]/page.tsx` +29 −0（code）
- `src/app/teams/page.tsx` +24 −0（code）
- `src/lib/api.ts` +22 −0（code）
- `src/lib/db/index.ts` +14 −5（code）
- `src/lib/db/migrations.ts` +23 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/result.ts` +23 −0（code）
- `src/lib/tasks.ts` +145 −30（code）
- `src/lib/teams.ts` +127 −0（code）
- `tests/db.test.ts` +52 −0（test）
- `tests/tasks.test.ts` +227 −19（test）
- `tests/teams.test.ts` +177 −0（test）

コミット:

- `446dedc レビュー指摘の修正: PATCH の確認順序とトランザクション`
- `fff239a タスクをチームで共有できるようにする`

### gstack #2 — 13.4 点

打ち切り額を見せない方式で、/autoplan（3 ステップ中の 1 つ目、計画とレビュー）の途中で見積額 $10.04 が上限 $10 に達し打ち切り。コードの変更は無く（TODOS.md のみ）、受け入れは既存の動作の 1/26 だけ。ユーザーの判断で、打ち切りのまま採点した。

コードのレビュー（影響箇所 0.0 / 30、認可: 一貫性 0 ・ 認可: 入力と境界 0）:

- patch が空で、コードの変更が無い。影響箇所はすべて未対応、認可も 0 とした。
- patch が空で、コードの変更が無い。影響箇所はどれも対応されておらず、変更前と同じく全員が全タスクを閲覧・編集できる。

設計のレビュー（設計: 比較の有無 1.5 ・ 設計: 選択肢 1.5 ・ 設計: トレードオフ 1.5 ・ 設計: 決定と実装 0.5）:

- レビュアーが text input と select、内部関数の非公開化と import 走査など代替を挙げたが、候補自身が案を並べて比べた記述は無く、TODOS.md の Pros/Cons も見送った機能についてのもの。VISIBLE_SQL への集約や *For 関数などの方針は読み取れるが、差分が空で実装との一致を確かめられないため D4 も低い。
- 比較らしいものは、レビュアーが出した代案（select とテキスト入力、権限確認の無い関数を別モジュールに分ける、先に確かめてから挿入する方式と挿入して制約違反を捕まえる方式）だけで、候補自身が案を並べて選んだ記述は無い。TODOS.md に見送った項目の長所・短所はある。差分が空で実装が無いため、D4 は 0 とした。

不合格の認可プローブ:

- 所属外のチームの ID を文字列で送っても、そのチームのタスクは作れない
- 所属外のチームで絞り込んでも、そのチームのタスクは返らない（API）
- 所属外のチームで絞り込んでも、そのチームのタスクは表示されない（画面）
- 閲覧できないタスクの詳細画面に、タイトルなどの内容が出ない
- 作成者でないメンバーは、別の所属チームへの付け替えもできない（403、所属は変わらない）
- 管理者でないメンバーは、自分を管理者にできない（403。409 などで存在を漏らさない）
- 管理者でないメンバーは、管理者を外せない
- ほかのチームの管理者でも、所属していないチームのメンバーは外せない（404）
- 外された管理者は、そのチームのメンバーを操作できなくなる

不合格の受け入れテスト:

- API: 未ログインは 401（チームの API すべて）: `got 404,404,404,404,404`
- API: タスク一覧は自分の個人タスクと所属チームのタスクだけ（teamId・owner 付き）: `sato=1,2,3,4,5,6,7 suzuki=1,2,3,4,5,6,7 tanaka=1,2,3,4,5,6,7`
- API: teamId での絞り込み（チーム・personal・所属外・不正な値・status との併用）: `{"team1":[1,2,3,4,5,6,7],"personal":[1,2,3,4,5,6,7],"team2":[1,2,3,4,5,6,7],"bad":[1,2,3,4,5,6,7],"both":[4,5,6]}`
- API: 閲覧できないタスクの取得は 404（エラーは { error } の JSON）: `{"tanaka1":200,"sato7":200,"sato4":200}`
- API: 所属チームの一覧（自分の役割付き、ID 順）: `{"s":[],"z":[],"t":[]}`
- API: メンバー一覧（ユーザー ID 順）。所属していない・存在しない・不正な ID のチームは 404: `404 []`
- 画面: タスク一覧は閲覧できるタスクだけを、所属（チーム名・個人）付きで表示する: `["要件定義書のレビュー完了sato2026-11-02","ログイン画面のデザイン進行中suzuki2026-11-12","API 設計進行中sato2026-11-14","DB スキーマ作成未着手tanaka2026-11-18","CI の整備未着手suzuki2026-11-20","E2E テストの追加未`
- 画面: 一覧の所属の絞り込み（select name=teamId で チーム・個人）: `options=[]`
- 画面: 閲覧できないタスクの詳細は 404 ページ、閲覧できるタスクは所属を表示する: `page.textContent: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('[data-testid="task-team"]')[22m `
- 画面: ヘッダーの「チーム」リンクと、チーム一覧（チーム名・役割・詳細へのリンク）: `page.waitForURL: Timeout 10000ms exceeded. =========================== logs =========================== waiting for navigation until "load" ====================`
- 画面: チーム詳細はメンバーと役割を表示し、管理者でなければ追加フォーム・「外す」ボタンを出さない: `[]`
- 画面: 所属していないチームの詳細は 404 ページ、管理者には追加フォームと各メンバーの「外す」ボタン: `sato: forms=0 input=0 buttons=0`
- API: 閲覧できないタスクの更新は 404 で、内容は変わらない: `r1=200 r6=200 t1=乗っ取り t6=done`
- API: teamId なしで作ると作成者の個人タスク（本文の owner は無視、ほかの人からは 404）: `[{"id":8,"title":"W4 確認用 1","status":"todo","assignee":"sato","dueDate":"2026-12-01"},{"id":9,"title":"W4 確認用 2","status":"todo","assignee":"sato","dueDate":"20`
- API: 個人タスクの担当者を作成者以外にすると 400（作成・更新）: `create=201 patch=200 assignee=suzuki`
- API: チームのタスクを作る（所属外・存在しないチームは 400、担当者はチームのメンバーだけ）: `{"id":12,"title":"W4 確認用 4","status":"todo","assignee":"tanaka","dueDate":"2026-12-01"} tanaka=200 sato=200`
- API: チームのタスクの担当者はそのチームのメンバーにだけ変えられる（外は 400）: `bad=200 ok=200 {"task":{"id":13,"title":"W4 確認用 5","status":"todo","assignee":"suzuki","dueDate":"2026-12-01"}}`
- API: 所属の変更は作成者だけ（作成者以外は 403、変更先は所属チームか null、担当者の規則も確かめる）: `byOther=200 toForeign=200 assigneeBreaks=200 teamId=undefined`
- API: owner は更新できない（送っても作成者のまま）: `200 {"id":15,"title":"題名の変更","status":"todo","assignee":"sato","dueDate":"2026-12-01"}`
- API: チームを作ると作成者が管理者になる（名前は前後の空白を除いて 1〜50 文字）: `404 undefined`
- API: メンバーの追加は管理者だけ（メンバーは 403、所属外は 404、不正な入力は 400、重複は 409）: `チーム作成に失敗 404 undefined`
- API: メンバーを外すのは管理者だけ（メンバーは 403、非所属は 404、最後の管理者は 400、ほかに管理者がいれば自分も外せる）: `チーム作成に失敗 404 undefined`
- API: チームに加わるとそのチームのタスクが見え、外されると担当者のタスクでも見えなくなる: `チーム作成に失敗 404 undefined`
- 画面: 管理者がフォームでメンバーを追加し、「外す」で一覧から消せる: `チーム作成に失敗 404 undefined`
- 画面: 最後の管理者を外そうとすると role=alert のエラーが出て、一覧は変わらない: `チーム作成に失敗 404 undefined`

変更ファイル:

- `TODOS.md` +52 −0（doc）

コミット:

- `0475e38 poc: uncommitted leftovers`

### baseline（候補なし） #1 — 82.0 点

候補なし。設計の比較はせず、owner を NOT NULL にするため tasks テーブルを作り直す方式で一気に実装した。受け入れ・認可・影響箇所は満点。設計案の比較の点（2 / 20）だけが低い。

コードのレビュー（影響箇所 30.0 / 30、認可: 一貫性 5 ・ 認可: 入力と境界 5）:

- 減点はない。createTask と updateTask が actorId を受け取り、所属・作成者・担当者の規則を src/lib 側で確かめて Outcome を返す。addMember と removeMember も 404→403→400→409 の順で lib の中で判定している。PATCH は validateTaskInput の 400 を作成者かどうかの 403 より先に返すが、閲覧できないタスクは先に 404 にしているので情報の漏れはない。
- 閲覧範囲を VISIBLE 条件 1 か所に集約し、getTask(id, viewerId) の署名変更で一覧・1件・更新・画面のすべてを同じ規則にしている。createTask/updateTask・addMember/removeMember が Outcome で 404→403→400 を返し、teamId の型検査・最後の管理者・所属変更後の担当者の再検証もそろっている。PATCH で入力検証（400）が所属変更の 403 より先に来る点はあるが、仕様上の問題とはいえず減点しない。

設計のレビュー（設計: 比較の有無 0 ・ 設計: 選択肢 0 ・ 設計: トレードオフ 0 ・ 設計: 決定と実装 2）:

- 設計の記述は最終報告の変更内容だけで、比較は無い。『owner を NOT NULL にするため tasks を作り直す』『listTasks・getTask に閲覧者 ID を追加』という採用方針と短い理由はあり、差分（tasks_new の作成と RENAME）と一致するが、根拠はごく薄い。
- 設計案の比較は無く、実装の報告だけである。owner を NOT NULL にするためにテーブルを作り直したことと、listTasks / getTask の署名を変えたことは理由とともに書かれており、実装（tasks_new への作り直し）とも合っているので D4 だけに点を付けた。

変更ファイル:

- `CLAUDE.md` +7 −1（doc）
- `src/app/api/tasks/[id]/route.ts` +6 −4（code）
- `src/app/api/tasks/route.ts` +12 −6（code）
- `src/app/api/teams/[id]/members/[userId]/route.ts` +16 −0（code）
- `src/app/api/teams/[id]/members/route.ts` +23 −0（code）
- `src/app/api/teams/route.ts` +18 −0（code）
- `src/app/layout.tsx` +1 −0（code）
- `src/app/tasks/[id]/page.tsx` +6 −2（code）
- `src/app/tasks/page.tsx` +22 −4（code）
- `src/app/teams/[id]/member-manager.tsx` +83 −0（code）
- `src/app/teams/[id]/page.tsx` +26 −0（code）
- `src/app/teams/page.tsx` +21 −0（code）
- `src/lib/api.ts` +6 −0（code）
- `src/lib/db/index.ts` +9 −3（code）
- `src/lib/db/migrations.ts` +36 −0（code）
- `src/lib/db/seed.ts` +20 −7（code）
- `src/lib/result.ts` +13 −0（code）
- `src/lib/tasks.ts` +120 −22（code）
- `src/lib/teams.ts` +138 −0（code）
- `tests/db.test.ts` +20 −0（test）
- `tests/tasks.test.ts` +165 −17（test）
- `tests/teams.test.ts` +134 −0（test）

コミット:

- `e4cc2dd タスクをチームで共有できるようにする`

## 採点方法

試行前に固定した手順（`docs/poc/answer-key/W4/grading.md`）で採点した。品質（100 点）は PLAN.md §5.1 の W4 の配点そのもの。


- <strong>影響箇所の網羅率 30</strong>: 正解の影響箇所 16 項目を、差分で正しく対応できたか（1 / 0.5 / 0）。ブラインドの採点者 2 名の平均 ÷ 16 × 30。
- <strong>受け入れテスト 30</strong>: 隠しの E2E 26 件 × 22.5/26 + 型チェック・単体テスト・ビルド 各 2.5。
- <strong>認可の正しさ 20</strong>: 認可プローブ 9 件 × 10/9 + ブラインドの採点者 2 名による認可のコードレビュー（一貫性・入力と境界、各 0〜5）の平均。
- <strong>設計案の比較 20</strong>: 候補が書いた文章・サブエージェントの報告・計画書から、ブラインドの採点者 2 名が 4 項目 × 0〜5 点。

効率（100 点）は PLAN.md §4.4 の共通の定義（`scripts/poc/two_axis.py`）: 費用 50 + 時間 30 + 介入 20。費用・時間は W4 baseline（$1.29・6.0 分）に対する倍率の段階。

## この結果の制約

- 各候補 2 回（baseline 1 回）で、2 回は打ち切り額の見せ方が違う（1 回目 flag・2 回目 watch）。候補間の条件は揃っているが、同じ候補の 2 回の差には方式の違いが含まれる。
- 無人の実行なので、確認・承認を前提にした工程（Feature Dev の設計案の選択、gstack の /autoplan の判断の確認）は人の判断なしで進んでいる。
- ブラインドレビューの採点者は人ではなくサブエージェント（同じモデル系統）。コードの採点者 1 名あたりの資料が多いため、9 試行を 2 つの組に分けて読ませた（組み方と順番は採点者ごとに変えた）。採点者 2 名の差が大きい項目（影響箇所は 1、ほかは 3 点以上）は無かった。
- 記録上のターン数（result の num_turns）は、Superpowers・Feature Dev #1 で 3〜7 と実際の操作数より少なく、比較には使っていない。
- 子セッションの許可リストでは実サーバーの起動ができないため、画面の動作確認はどの候補もできていない（Compound Engineering #1 の画面の不具合はこのために見逃された可能性がある）。

## 判断の記録

- <strong>費用の上限</strong>: W2 と同じ規模係数の考え方で決めた。規模係数 8.6（W4 baseline の実額 $1.29 ÷ W1 baseline $0.15）× 5 × 各候補の W1 平均、最大 $10。Superpowers・Feature Dev は $7.3、gstack・Compound Engineering は $10。「W1 の 5 倍（W1 全試行平均 $0.59 × 5 ≒ $2.96）を超える上限」はユーザー承認が必要とのコーディネーターの指摘を受け、一時的に $2.96 で進める指示があったが、その間に $2.96 で走らせた試行は無く、04:39 にユーザーの承認（コーディネーター経由）を得て上記の上限で行った。Superpowers #1・Feature Dev #1 は承認前に $7.3 で開始していたが、実費は $2.96 以内だった。
- <strong>旧文言で始めた baseline の破棄</strong>: 最初の baseline は旧文言（「課題文に書かれていないことはお任せします」）で始めたが、W4 から新文言（工程を省かないよう明記）に変える指示で、結果が出る前に止めた。費用はトークンからの推定で約 $0.35。採点に使っていない。
- <strong>2 回目を watch 方式にした経緯</strong>: 2 回目の途中で、打ち切り額を子セッションに見せない方式（watch）に変えるユーザーの決定があった。flag 方式で既に走っていた Compound Engineering #2（26/26・9/9・$7.97・16.1 分・サブエージェント 13）は記録を `W4/flag-run/` に移して採点から外し、watch で同じ上限でやり直した。flag 方式の gstack #2 はステップ 1 の途中で止めた（result なし、トークンからの推定で約 $0.5）。各試行の方式は `raw/<試行>/budget-mode` に記録した。
- <strong>gstack #2 の打ち切り</strong>: watch 方式・上限 $10 で、/autoplan の途中に見積額 $10.04 で打ち切られ、実装に至らなかった。完走させるには $10 超の上限が必要なため、コーディネーター経由でユーザーに確認し、回答（A）どおり打ち切りのまま採点した（やり直しなし）。費用は result が無いため run-trial.sh の見積額を使った。
- <strong>usage 上限による中断と再開</strong>: 途中で usage の上限が近いため中断し（再開メモ `W4/RESUME.md`）、再開後に止めた gstack #2 を同じ方式・同じ上限で最初からやり直した。中断で止めた分は結果が出ておらず、採点に使っていない。
- <strong>影響箇所の判定</strong>: 候補が報告で「影響箇所」として挙げた一覧ではなく、実際の差分で正しく対応できたかで判定した（PLAN の「使った機能ではなく成果で採点」に合わせるため。試行前に固定）。
- <strong>認可の正しさの測り方</strong>: PLAN の「security-guidance と採点者確認」を、受け入れテストとは別の認可プローブ 9 件（自動）と、ブラインドの採点者による認可のコードレビューの合計にした。security-guidance の試行中の指摘は記録だけにした（全試行で 0 件）。
- <strong>採点スクリプトの修正</strong>: grade.py の検査スクリプトの実行（W4 で追加した run_key）が出力の末尾 3000 字しか読まず、不合格が多いと結果の JSON が切れていた（gstack #2 で発覚）。標準出力全体を読むよう直した。W1〜W3・W5 の結果にこの症状が出た試行は無く、過去の点数は変わらない。
- <strong>W4 の gstack の手順</strong>: PLAN.md §5.1 の「/autoplan → 実装 → /review」に合わせ、実装のステップは定型の「計画に沿って実装し、変更を git にコミットしてください。」にした（run-trial.sh の W4 だけの分岐。ほかのシナリオの手順は変えない）。

## 次の対応

- W4 の結論（設計案の比較で差が出る）が、仕様の曖昧さが大きい課題でも同じか、W8（自律実行）などの結果と合わせて確かめる。
- 打ち切り額の見せ方（flag / watch）の影響は gstack で大きく出た。以降の W は watch で行い、gstack のような多段の計画工程を持つ候補では上限の決め方（規模係数）を見直すか検討する。
- 子セッションでの実サーバー起動（画面の確認）の可否は、W6 の結果と合わせて判断する。
