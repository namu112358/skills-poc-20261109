# 要件: 進捗画面（チームの進捗を見えやすくする）

## 背景と目的

- 依頼者はチームリーダーの佐藤。チームは佐藤・鈴木・田中の 3 人。
- 今は `/tasks` に全件が並ぶだけで、誰がどれくらい抱えているか、どれが遅れているかがひと目で分からない。毎週の定例で各自に口頭で状況を聞いて回っている。
- 目的は、定例で「遅れているタスクを早く見つけて手を打つ」こと。口頭での確認を、1 つの画面で置き換える。
- 社内向けの業務改善であり、売り物ではない。

## 作るもの

新しい「進捗」画面（`/progress`）を追加する。ヘッダーに「進捗」のリンクを置き、ログイン中ならどのページからも行けるようにする。

### 画面の構成（上から順）

1. **期限切れの未完了タスク**（いちばん目立つ位置・表示にする）
   - 項目: タイトル（タスク詳細へのリンク）・担当者名・期限・超過日数。
   - 並び順: 超過日数が大きい順。同じ日数なら ID の小さい順。
   - 見出しに件数と文言を入れる（例：「遅れ 3 件」）。背景色だけで区別しない。
   - 0 件のときは「遅れているタスクはありません」と表示する。
2. **7 日以内に期限が来る未完了タスク**（期限切れとは別枠）
   - 今日を含めて 7 日以内（今日〜6 日後）に期限が来る、完了していないタスク。
   - 項目: タイトル・担当者名・期限・期限までの残り日数。期限が近い順。
   - 0 件のときは「7 日以内に期限が来るタスクはありません」と表示する。
3. **担当者別の集計表**
   - 行: 担当者（ID ではなく名前で表示）。タスクが 0 件の担当者も行を出す。
   - 列: 未着手・進行中・完了（全期間）の件数、今週の完了。列名は「完了（全期間）」と「今週の完了」で書き分け、見間違いを防ぐ。
   - 未着手・進行中・完了の件数をクリックすると、その担当者・そのステータスで絞り込んだタスク一覧（`/tasks`）に移る。

### 用語の定義

- **今日**: 日本時間（JST）の日付。
- **遅れ（期限切れ）**: 期限日が今日より前で、ステータスが「完了」でないタスク。これ以外の基準（更新がない日数など）は使わない。
- **超過日数**: 今日 − 期限日（日数）。
- **今週**: 月曜から日曜（JST）。完了日時がこの範囲に入るタスクを「今週の完了」として担当者ごとに数える。

### タスク一覧（`/tasks`）の変更

- 絞り込みに**担当者**を追加する（URL のクエリ `assignee`）。進捗画面の件数リンクの移動先として使う。
- 今の表示とステータスの絞り込みは変えない。ステータスと担当者は同時に指定できる。
- クエリの値は検証してから使う。存在しない担当者やステータスなど不正な値は「指定なし」として扱う（既存の `status` と同じ扱い）。
- 担当者の選択肢は絞り込みフォームに追加する。

### 完了日時の記録

- ステータスを「完了」にしたとき、その日時を記録する（`tasks.completed_at`、UTC の ISO 8601）。
- 完了から「未着手」「進行中」に戻したときは、完了日時を消す。
- 完了のタスクをもう一度「完了」で保存したときは、完了日時を変えない。
- 完了のまま作成されたタスクは、作成した日時を完了日時とする。
- 導入前から完了だったタスクは完了日時が分からないので、空のままにする。今週の完了数には含めない。過去分を推測して埋めることはしない。
- 記録は `src/lib/` のタスク更新・作成の関数の中で行い、画面からでも API（`POST /api/tasks`・`PATCH /api/tasks/:id`）からでも同じ結果になるようにする。

## アクセス制御

- ログイン済みなら誰でも、全員分を見られる。未ログインでは見せない（`/progress` は `requireUser()` でログイン画面に誘導する）。
- 権限の区別（リーダーだけが見られる、など）は作らない。

## 対象外（今回やらないこと）

- 「進行中のまま何日動いていないか」の検出
- 進捗率・工数など、新しい入力項目
- 先週との比較など、過去からの推移
- 通知（メール・Slack など）
- 外部ライブラリの追加

## 実装時の制約（`app/CLAUDE.md` に沿う）

- 集計・絞り込みの処理は `src/lib/` に置き、ページには表示の処理だけを書く。
- DB の変更は `src/lib/db/migrations.ts` の末尾に新しい番号（3）のマイグレーションを追加する。既存のマイグレーションは書き換えない。SQL の値はプレースホルダを使う。
- 画面の文言は日本語にする。
- 追加・変更したロジックには `tests/` に単体テストを書く。特に次を確認する。
  - 期限切れの判定（期限が今日の場合は期限切れにしない）と超過日数
  - 7 日以内の範囲（今日と 6 日後を含み、7 日後を含まない）
  - 今週（月曜〜日曜）の境界。日曜 23:59 と月曜 0:00（JST）の扱い。
  - 完了日時の記録・消去・維持（`createTask` で完了のまま作成したとき、作成日時が完了日時になることを含む）
  - 週境界の 2 件: 日曜 23:59 JST は今週、月曜 0:00 JST は翌週に数える
  - 担当者・ステータスの絞り込みと、不正な値の扱い
  - 担当者が 0 件のときの集計表

## 初期データ（動作確認用・レビューで確定）

- 起動直後の `/progress` で、期限切れの一覧と今週の完了数を画面で確認できるようにする。そのために `src/lib/db/seed.ts` の**既存の行の値だけ**を変える。
  - 未完了タスク 2 件の期限を過去にする（期限切れが 2 件出る）。
  - 完了済みタスク 1 件に、今週の完了日時を入れる（今週の完了が 1 件出る）。
- **行は追加しない。** 既存テストが初期データの件数（7 件、追加後 8 件）を確認しているため（`tests/tasks.test.ts:16,79`）。
- 日付を固定値にすると、週が変わったときに画面が古くなる。固定にするか、起動時の日付からの相対にするかは実装時に決める。

## 受け入れ条件

1. ログイン後、ヘッダーの「進捗」から `/progress` を開ける。未ログインなら開けない。
2. 期限切れの未完了タスクが、担当者名・期限・超過日数つきで、画面の最上部に目立つ形で出る。
3. 7 日以内に期限が来る未完了タスクが、期限切れとは別枠で出る。
4. 担当者別の表に、未着手・進行中・完了の件数と今週の完了数が名前つきで出る。
5. 表の件数をクリックすると、その担当者・そのステータスで絞り込んだ `/tasks` に移る。
6. タスクを完了にすると完了日時が記録され、今週の完了数に反映される。完了から戻すと数から外れる。
7. `/tasks` のこれまでの表示とステータスの絞り込みは変わらない。
8. `npm run typecheck` と `npm test` が通る。

## 決めたこと（未指定だった点は依頼者の「お任せ」に従った）

- 0 件の担当者も集計表に出す。
- 期限切れの並びは、超過日数の大きい順にする。
- 期限切れが 0 件のときは、「遅れているタスクはありません」と表示する。
- 画面は新規の `/progress` とし、今のタスク一覧には機能を足さない。ただし、担当者の絞り込みだけは一覧に追加する。
- 初期データは既存行の値だけを変え、行は増やさない（D2）。
- 集計表の列名と期限切れの見出し、週境界などのテストを補強する（D3）。

## レビュー結果（plan-ceo-review / HOLD SCOPE）

### 判断の記録

| ID | 内容 | 状態 | 承認の根拠 |
|---|---|---|---|
| D1 | レビューモード = HOLD SCOPE | 承認 | 依頼者の回答「推奨の案（C）で進めてください」 |
| D2 | 初期データの既存行の値だけを変更（行は追加しない） | 承認 | 「推奨の案（A）で進めてください」 |
| D3 | テスト・列名・見出しの補強 4 点 | 承認 | 「推奨の案（A）で進めてください」 |

Approval readiness: PASS（D1・D2・D3 は、いずれも依頼者の実際の回答に基づく。範囲外の変更は含めていない）

### 実在確認

```
REALITY: premise-table pass unverified=0。完了への変更は createTask/updateTask のみ src/lib/tasks.ts:105-119。requireUser() src/lib/session.ts:13
REALITY: already-done pass 実装済みの形跡なし。履歴は baseline と要件書のみ
REALITY: surface-check pass /tasks /tasks/:id /api/tasks[/:id] は実在 src/app/。/progress は新規
REALITY: binding-decisions pass 過去の判断ログなし
REALITY: numbers pass 7 日・月〜日・3 人は依頼者の指定値
REALITY: deferred-asks pass 紐づく Issue なし
REALITY: pr-count pass .gstack/ship-policy.json なし。既定の 1 PR
```

`gstack-plan-reality check` は実行していない（コマンドの実行承認が得られなかったため）。

### 対象外（NOT in scope）

- 先送り（TODOS.md へ）: なし。
- 却下: 通知、推移、停滞日数の検出、進捗率・工数、外部ライブラリ（依頼者の指定による）。

### すでにあるもの（What already exists）

- 再利用: `requireUser()`、`listUsers()`、`isTaskStatus`、`STATUS_LABELS`、マイグレーションの仕組み、`now` を引数で渡す作り（`auth.ts:25,33`）。
- 新規: JST の日付計算、`src/lib/progress.ts`、`/progress` ページ、`completed_at`。

### 理想像との差（Dream state delta）

12 か月後の理想は、定例が「画面を見て手を打つ会」になることです。この計画は、その土台（遅れと負荷の可視化）を作ります。停滞の検出と推移は意図的に外しており、必要になった時点で `completed_at` を土台に追加できます。

### Error & Rescue Registry / Failure Modes

| CODEPATH | 失敗 | 対処 | テスト | ユーザーに見えるもの |
|---|---|---|---|---|
| `getProgress(now)` | DB エラー | 例外を上へ（既存と同じ） | — | Next の標準エラー |
| `/tasks?assignee=不正値` | 存在しない ID | 「指定なし」扱い | 要件にあり | 全件表示 |
| `updateTask` の完了判定 | 不正な status | `validateTaskInput` で 400 | 既存 | 400 |
| 週・日の境界 | JST と UTC のずれ | JST 固定で計算 | D3 で追加 | — |

CRITICAL GAP: 0 件。

### 実装タスク

- [ ] **T1 (P1, 人手 ~1h / CC ~10min)** — DB — マイグレーション 3 で `tasks.completed_at TEXT` を追加。Files: `src/lib/db/migrations.ts`。Verify: `npm test`（`tests/db.test.ts`）
- [ ] **T2 (P1, 人手 ~2h / CC ~15min)** — タスク — `createTask` / `updateTask` で完了日時を記録・消去・維持（`toISOString()` で保存）。Files: `src/lib/tasks.ts`、`tests/tasks.test.ts`。Verify: 該当テスト
- [ ] **T3 (P1, 人手 ~3h / CC ~20min)** — 集計 — `src/lib/progress.ts`（`now` 引数、JST 固定）。期限切れ・7 日以内・担当者別。Verify: `tests/progress.test.ts`（境界 2 件を含む）
- [ ] **T4 (P1, 人手 ~2h / CC ~20min)** — 画面 — `/progress`、ヘッダーのリンク、`/tasks` の担当者絞り込み。Files: `src/app/progress/page.tsx`、`src/app/layout.tsx`、`src/app/tasks/page.tsx`。Verify: `npm run typecheck`、`npm run build`、画面確認
- [ ] **T5 (P2, 人手 ~30min / CC ~5min)** — 初期データ — 既存行の値だけを変更（行は追加しない）。Files: `src/lib/db/seed.ts`。Verify: `npm test`（件数 7・8 が変わらない）

### 完了サマリー

```
Mode: HOLD SCOPE | Step 0: 前提・範囲は承認済みのまま固定 | 事前監査: 初期データに期限切れが無い点を発見 → D2
Section 1-10: 指摘 計3件（初期データ1、テスト補強2相当）、いずれも解決済み | Section 11: 指摘 1 件（色だけに頼らない）→ D3
Failure modes: 4 行 / CRITICAL GAP 0 | Outside voice: unavailable | Lake Score: N/A（スコア付きの質問なし）
Unresolved decisions: 0 | Reality rows: 7/7（PLAN_REALITY は未実行）
```

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR (not persisted) | mode: HOLD_SCOPE, 0 critical gaps |
| Outside Review | codex (unavailable) | Independent 2nd opinion | 0 | unavailable | no completed external review |
| Eng Review | `/autoplan` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**OUTSIDE COVERAGE:** codex, plan-review、unavailable（設定の確認コマンド `gstack-config` が実行承認を得られず、外部レビューは開始していない）。ネイティブ代替も実行していないため、クリーンの扱いにはしない。

**VERDICT:** CEO CLEARED。Eng Review は未実施のため、eng review required。

NO UNRESOLVED DECISIONS
