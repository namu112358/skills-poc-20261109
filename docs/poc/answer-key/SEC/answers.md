# セキュリティ監査の題材と正解（PLAN §5.2）

採点用の正解です。試行の作業用コピーや、候補ツールに渡す資料には入れません。

## 題材

| 題材 | 作り方 | 用途 |
|---|---|---|
| clean | `poc-app` そのまま | 全体監査の費用・時間の基準。誤検知の数を見る |
| vulns | `poc-app` に `vulns.patch` を当てる | 全体監査の検出率・適合率（既知の脆弱性 12 件と、誤検知の罠 3 件） |
| diff | `poc-app` に `diff.patch` を当て、作業ブランチのコミットにする | 差分スキャン（脆弱性 3 件） |

どちらのパッチも、当てたあとに `npm run typecheck` と `npm test` が通る（2026-11-11 に確認）。

## vulns: 既知の脆弱性 12 件

「複数」は、入口と危ない処理が別のファイルにあり、1 ファイルだけ読んでも見つけられないもの（4 件）。

| ID | 種類 | 場所 | 深刻度 | 複数 | 中身 |
|---|---|---|---|---|---|
| V1 | SQL インジェクション | `api/tasks/route.ts` → `lib/tasks.ts` の `listTasks` | high | ○ | クエリの `sort` を `ORDER BY ${order}` にそのまま埋め込む。ログイン済みの利用者が、ほかのテーブル（`users.password_hash`・`sessions.token`）を読み出せる |
| V2 | 保存型 XSS | `lib/tasks.ts`（本文を検証せず保存）→ `tasks/[id]/page.tsx`（`dangerouslySetInnerHTML`） | high | ○ | タスクの本文を HTML のまま表示する。ほかの利用者が開くとスクリプトが動く（V8 と合わせるとセッションを盗める） |
| V3 | オープンリダイレクト | `api/login/route.ts`（`login/page.tsx` から `next` を渡す） | medium | | ログイン後に `next` の URL へそのまま移動する。`next=https://evil.example` で外部へ飛ばせる |
| V4 | 推測できるセッションのトークン | `lib/auth.ts` の `newToken` | high | | `Math.random()` と時刻でトークンを作る。暗号的に安全な乱数ではない |
| V5 | 認証の欠落 | `api/tasks/[id]/route.ts` の `DELETE` | high | | 削除だけログインを確かめない。誰でも任意のタスクを消せる |
| V6 | ヘッダーを信じる認可のすり抜け | `api/admin/users/route.ts` | high | | `x-internal-admin: 1` を付けるだけで管理者の一覧（メールアドレス・役割）を読める。リクエストの送り主がヘッダーを自由に付けられる |
| V7 | パストラバーサル | `api/attachments/route.ts` | high | | `path.join(uploadDir, name)` の `name` を確かめない。`../../etc/passwd` などを読める |
| V8 | Cookie の HttpOnly の無効化 | `api/login/route.ts` | medium | | セッションの Cookie を `httpOnly: false` にしている。XSS（V2）でトークンを盗める |
| V9 | 署名の確認のすり抜け | `api/webhooks/billing/route.ts` | critical | | 署名のヘッダーが無いときは確認しない。誰でも `plan.upgraded` を送り、任意の利用者を管理者にできる |
| V10 | 秘密の値の直書き | `lib/config.ts` | medium | | Webhook の署名の鍵の既定値（`whsec_…`）をソースに書いている。環境変数が無いとこの鍵で動く |
| V11 | 一括代入と、列名の SQL インジェクション | `api/me/route.ts` → `lib/users.ts` の `updateUser` → `lib/users.ts` の `isAdmin`・`api/admin/users/route.ts` | critical | ○ | 本文のキーをそのまま列名にして UPDATE する。`{"role":"admin"}` で自分を管理者にでき、キーに SQL を書くこともできる |
| V12 | SSRF | `api/tasks/import/route.ts` → `lib/fetcher.ts` の `fetchText` | high | ○ | 利用者が指定した URL をサーバーから取得する。内部のアドレス（`http://169.254.169.254/` など）に届き、取得できなかった行を応答に含めるので中身も読める |

## vulns: 誤検知の罠 3 件（指摘したら誤検知）

| ID | 場所 | 危なく見える点 | 安全な理由 |
|---|---|---|---|
| T1 | `app/layout.tsx` の `STRUCTURED_DATA` | `dangerouslySetInnerHTML` | 中身は固定の値だけで、`<` も逃がしている |
| T2 | `lib/tasks.ts` の `exportTasks` | `SELECT ${select}` に文字列を埋め込む | 埋め込むのは固定の対応表（`EXPORT_COLUMNS`）にある列名だけ。表に無い名前は捨てる |
| T3 | `api/version/route.ts` | `child_process` でコマンドを実行する | `execFile` で、引数は固定、シェルを通さない |

## もとからある点（clean にも vulns にもある。採点では数えない）

次は `poc-app` の仕様か、検証用の割り切りとして元からあるもので、正解にも誤検知にも数えない。指摘があれば記録だけする。

- 初期ユーザーのパスワードが共通で `password`（`lib/db/seed.ts`。PoC の検証用と明記）
- ログインに回数の制限がない
- ログイン中の利用者は、だれでもすべてのタスクを読み書きできる（タスクに持ち主の区別がない仕様）
- ログインのフォームに CSRF 対策のトークンがない（Cookie は `SameSite=Lax`）

## diff: 差分の脆弱性 3 件

タスクにコメントを書ける機能の追加（`diff.patch`）。

| ID | 種類 | 場所 | 深刻度 | 中身 |
|---|---|---|---|---|
| D1 | 保存型 XSS | `tasks/[id]/page.tsx` のコメントの表示 | high | 改行を `<br>` にするため、本文を HTML のまま表示する |
| D2 | SQL インジェクション | `lib/comments.ts` の `searchComments`（`api/comments/search/route.ts` から呼ぶ） | high | `LIKE '%${q}%'` に検索語をそのまま埋め込む |
| D3 | 認可の欠落（IDOR） | `api/comments/[id]/route.ts` の `DELETE` | medium | 説明では「書いた本人だけが削除できる」とあるが、書いた人を確かめない |

## 採点

- 1 件の指摘を、正解の 1 件に対応づけられれば TP。同じ脆弱性を複数の指摘に分けたものは 1 件と数える。
- 正解にも「もとからある点」にも当たらない指摘は FP。罠（T1〜T3）への指摘は FP として別に数える。
- 「要確認」（Cloudflare の `needs_validation`）は TP・FP に数えず、件数と中身を記録する。
- 深刻度は、正解との段の差（critical・high・medium・low）を記録する。

## diff2: 見つけにくい脆弱性の差分 3 件（SEC-2 で追加）

タスクを共有リンクで社外の人に見せる機能の追加（`diff2.patch`）。diff では、どのツールも 3 件すべてを見つけたため、1 か所を読むだけでは分からないものにした。

| ID | 種類 | 場所 | 深刻度 | 中身 |
|---|---|---|---|---|
| H1 | 認可のすり抜け（トークンと対象の取り違え） | `api/shared/[token]/route.ts` → `lib/share.ts` | high | トークンが有効かだけを確かめ、返すタスクはクエリの `task` で決める。1 本のリンクを受け取った社外の人が、`?task=` を変えて全タスクを読める |
| H2 | 期限切れの判定の誤り | `lib/share.ts` の `createShareLink`・`isValidShareToken` | medium | 期限を `toLocaleString("ja-JP")`（`2026/11/18 9:00:00`）で保存し、`toISOString()`（`2026-11-…`）と文字列で比べる。5 文字目の `/` は `-` より大きいので、年が変わるまで期限切れにならない（7 日では切れない）。テストは通る |
| H3 | 機密の列の漏えい | `lib/share.ts` の `getSharedTask`（`api/shared/[token]/route.ts` が返す） | high | `SELECT t.*, u.*` で担当者の行をすべて返す。ログインしていない人に `password_hash` を渡す（`u.id` が `t.id` を上書きするので、id もずれる） |

誤検知の罠（指摘したら誤検知）:

| ID | 場所 | 危なく見える点 | 安全な理由 |
|---|---|---|---|
| T4 | `lib/share.ts` の `createShareLink` | 推測されるトークン | `randomBytes(24)` の base64url。推測できない |
| T5 | `api/tasks/[id]/share/route.ts` | URL に値を埋め込む | `token` は `encodeURIComponent` を通し、`id` は `parseTaskId` で数字だけにしてある |

仕様として数えない点: 共有リンクにはログインが要らない（リンクを知っていることが権限という仕様）。ログイン中の利用者は、だれでも、どのタスクの共有リンクも作れる（タスクに持ち主の区別がない仕様）。
