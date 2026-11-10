# 機能追加の依頼（zod）

このリポジトリ（zod）に、次の機能要望が出ています。メンテナーと合意した仕様（下の「仕様」）のとおりに、Zod 4 の classic API（`zod/v4`）に実装してください。

---

# Support circular object validation

Hi!

I'm proposing Zod supported validating circular objects. Here's what I mean by a circular object:

```ts
const user = {
  id: 1,
  posts: [
    {
      get author() { return user }
    }
  ]
}
```

`user.posts[n].author` is a circular reference back to the root `user`. 

## Motivation

1. Circular objects are valid objects in JavaScript. You can certainly create them and they come in handy in data modeling libraries, e.g. when resolving relations between objects.
2. Zod supports _declaring_ such objects through getters, but it fails to validate them. This makes me feel like this is a bug that has to be addressed. What happens is Zod crawls circular references infinitely since `user.posts[n].author` points back to the user, which has `user.posts`, etc.

## Proposal

I'd love for this to be solved with the minimal involvement from Zod. Here's what I suggest:

```ts
function parse() {
  const visitedNodes = new Set()

  function zodCrawler(value) {
    if (isObject(value)) {
      if (visitedNodes.has(value)) {
        return
      }

      visitedNodes.add(value)

      // ...continue with the validation.
    }
  }
  
  // Once the validation is done.
  visitedNodes.clear()
}
```

Following this algorithm, the aforementioned `user` example would result in the following steps:

```
- user
  - id (validate z.number()),
  - posts (array, fall through recursively)
    - author (the same user ref, skipping)
```

---

## 仕様（合意済み）

現在は、循環参照を含む入力を再帰的なスキーマ（getter や `z.lazy`）で検証すると、`safeParse` でも捕まえられない `RangeError` になる。これを、次の振る舞いで検証できるようにする。

- 自分自身を参照する入力を検証できる。出力は入力と別のオブジェクトで、出力の中でも同じ形の循環になる（例: `out.self === out`）。入力は書き換えない。凍結（`Object.freeze`）された入力でもよい。
- 対象のコンテナ: object・array・record・tuple・Set・Map（キーと値）・union・discriminated union・`z.lazy`、何段か離れた相互再帰。JIT を使う場合と使わない場合（`jitless`）の両方。同期・非同期（`parseAsync`）の両方。`z.encode` でも同じ。
- 同じ入力ノードは、それに届いたスキーマごとに 1 回ずつ検証し、出力もスキーマごとに別に作る（相互再帰で、1 つのノードを 2 つのスキーマで検証する場合）。
- 再帰的なスキーマの中では、1 つの入力ノードに対して出力ノードを 1 つだけ作る（2 か所から参照された共有ノードは、出力でも同じオブジェクトになる）。再帰していないスキーマは従来どおり、共有の参照も別々にコピーする。
- `refine` などのチェックは、作りかけのオブジェクトに対して実行しない。チェックは参照 1 つにつき 1 回（循環が無い場合と同じ回数）実行する。循環の中で失敗したチェック・不正な値は、それ自身のパスで 1 回だけ報告する。
- 循環が `transform` を通って閉じる場合は、`reference cycle` を含むメッセージのエラーにする。循環の外にある `transform` には影響しない。
- `.readonly()` を通る循環でも、作りかけのノードを凍結しない。`z.intersection` を通る循環は、値は検証するが、出力の循環構造までは再現しない。
- 別々の `parse` の呼び出し（同時に走る非同期の呼び出しを含む）は互いに影響しない。
- `zod/mini` は対象外（mini のバンドルを増やさない）。
