# C2 の正解（W19-superpowers-1。2026-11-10 担当がコードと本番の起動で確かめた）

| ID | 種類 | 場所 | 仕組み（核心） | 正しい直し方 |
|---|---|---|---|---|
| B1 | 不具合 | `src/app/instruments/[id]/page.tsx` の `<InspectionForms users={planChoices} …>`（`planChoices` は `src/lib/users.ts` の `listActiveUsers()` が返す DB の行） | node:sqlite の行（素のオブジェクトではない）を、サーバーの部品からクライアントの部品（`inspection-forms.tsx`）にそのまま渡している。本番の起動（next start）では「Only plain objects … can be passed to Client Components」で、すべての計測器の詳細の画面が 500 になる（担当者・点検の記録・未点検の表示も見られない） | 渡す前に `{ id, name }` の素のオブジェクトに写す（`map((u) => ({ id: u.id, name: u.name }))`）。`listActiveUsers` で写してもよい |
| G1 | 要件の抜け | 計測器の一覧（`src/app/api/instruments/route.ts`・`src/app/instruments/page.tsx`・`src/lib/instruments.ts` の `listInstruments`） | 合意した要件「担当者で絞り込み・並べ替えができる」が無い。一覧の API・画面とも、担当者での絞り込み・並べ替えを受けない | 一覧に担当者の絞り込み（`?inspector=`）と並べ替えを足す |
| G2 | 要件の抜け | 担当者ごとの集計が無い（API・画面・毎朝の仕事のどれにも無い） | 合意した要件「担当者ごとに、点検が遅れている台数を毎朝知りたい」が無い。計測器ごとの「期限切れ」の表示だけ | 担当者ごとの遅れの台数を返す集計（画面・API・毎朝の仕事のいずれか）を足す |

- 一致の基準: B1 は「サーバーの部品からクライアントの部品に、DB の行（null プロトタイプ・クラスのインスタンス）を渡している／詳細の画面が本番で落ちる」ことを述べていれば一致（場所は page.tsx か users.ts か inspection-forms.tsx の受け渡し）。G1・G2 は、それぞれの要件が実装されていないことを述べていれば一致。
- おとり（指摘したら誤り）は置いていない。B1・G1・G2 以外の指摘は、判定役が「正解外（本当の問題か要確認）」に分け、担当が読んで本当の問題かを決める。
