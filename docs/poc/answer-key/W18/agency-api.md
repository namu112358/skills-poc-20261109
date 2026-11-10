# 校正機関 受付システム API（抜粋）

外部の校正機関（東日本計測サービス）が提供する、校正の発注を受け付けるシステム。
発注を受け付けると、校正機関が計測器を引き取りに来て、校正の後に返却する。

## 接続先と認証

- URL と API キーは環境変数で渡す: `AGENCY_API_URL`（例: `https://order.ej-keisoku.example`）、`AGENCY_API_KEY`（情報システム課が校正機関から受け取って管理する）。
- すべての要求に `X-Api-Key: <AGENCY_API_KEY>` を付ける。

## 発注する

`POST {AGENCY_API_URL}/v1/orders`

```json
{
  "clientReference": "（発注側の番号。発注ごとに一意。64 文字まで）",
  "item": { "managementNo": "MI-0001", "name": "デジタルマルチメータ", "model": "DMM-7510" },
  "requestedBy": "sato",
  "note": "（任意。500 文字まで）"
}
```

| ヘッダー | 内容 |
|---|---|
| `X-Api-Key` | API キー（必須） |
| `Content-Type` | `application/json`（必須） |
| `Idempotency-Key` | 任意の文字列（255 文字まで、任意）。同じキーの要求は 24 時間、最初の 1 回だけ処理され、2 回目以降は最初の結果が返る |

### 応答

| ステータス | 意味 |
|---|---|
| `201` | 受け付けた。本文 `{ "orderId": "AG-...", "status": "accepted", "estimatedReturnOn": "YYYY-MM-DD" }`（`estimatedReturnOn` は返却予定日） |
| `400` | 要求の誤り（項目の欠落・長すぎる など）。本文 `{ "error": "..." }` |
| `401` | API キーが無い・誤り |
| `409` | 同じ `clientReference` の発注がすでにある。本文 `{ "error": "duplicate", "orderId": "AG-..." }` |
| `429` | 要求が多すぎる。`Retry-After` ヘッダー（秒）が付く |
| `503` | 一時的に利用できない（夜間のメンテナンス・高負荷） |

- 応答が返るまでに時間がかかることがある（混雑時は数十秒）。
- 夜間（日本時間 0:00〜6:00）は止まっていることが多い。
