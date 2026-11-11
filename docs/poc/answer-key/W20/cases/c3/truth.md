# C3 の正解（W14-superpowers-2。2026-11-10 サブエージェントがコードと採点の記録で確かめ、担当が主な箇所をコードで確かめた）

| ID | 種類 | 場所 | 仕組み（核心） | 正しい直し方 |
|---|---|---|---|---|
| B1 | 不具合 | `src/lib/instruments.ts` の `validateLocation` の `locationId` の枝（`value.locationId = id` だけ）と `createInstrument` | 場所の ID を指定して計測器を登録すると、古い列 `location` に書く値（`locationOriginal`）が未設定のまま SQL に渡り、node:sqlite が「cannot be bound to SQLite parameter」で例外 → 500。場所を一覧から選ぶ登録がすべて失敗する | `locationId` を受けたとき、選んだ場所の名前を `locationOriginal`（古い列）にも入れる |
| B2 | 要件違反 | `src/lib/instruments.ts` の `validateLocation` の `else if ("location" in b)` の枝 | 合意した要件「登録・編集は一覧から選ぶ形にし、自由に書けるのはやめる」に反し、新しい API が自由入力の `location` を受け付けて 201（確認中）で登録する | 登録・編集の API では `location` の文字列を受け付けない（400）。文字列の照合はハンディ端末の受け付けだけに残す |
| B3 | 互換の破れ | `src/lib/instruments.ts` の `updateInstrument`（`next.locationOriginal` を書き戻す） | 新しい API で場所を変えても、古い列 `location` は変更前の文字列のまま。経理が読む列と前の版のアプリ（古い列だけを読む）が古い場所を見る（要件 7・8） | 場所を変えるときは古い列にも選んだ場所の名前を書く（両方に書く） |
| B4 | 互換の破れ | `src/lib/location-master.ts` の `updateLocation` | 場所の名前を変えても `locations.name` しか変えず、その場所の計測器の古い列 `location` は古い名前のまま（要件 5・7） | 同じトランザクションで、その場所に結び付いた計測器の `location` 列も新しい名前に更新する |

- 一致の基準: 場所（ファイルと関数）と仕組みの核心の両方を述べていれば一致。B3 と B4 を 1 件の指摘（「古い列に新しい場所・名前が入らない」）でまとめて述べたものは、両方の場所（編集と名前の変更）に触れていれば両方に一致、片方だけなら片方に一致。
- 正解に入れなかったもの: ハンディ端末の、確定済みの計測器に寄せられない文字が来たときの扱い（依頼者役が「お任せします」と答えた経緯があり、読み方が分かれる）。指摘されても誤りには数えない（正解外として担当が読む）。
