# 機能追加の依頼（packaging）

このリポジトリ（packaging）に、次の機能要望が出ています。メンテナーと合意した仕様（下の「仕様」）のとおりに実装してください。

---

# Feature request: Method and Enum for returning subset and disjointness answers in one call

Resolver's need both containment and disjointness for the same pair of version ranges. Separate queries repeat interval walks.

I propose we add `relation(other)` to `VersionRange`, returning `SUBSET`, `DISJOINT`, `OVERLAPPING` or `EMPTY. E.g.

```python
from packaging.ranges import RangeRelation, VersionRange
from packaging.specifiers import SpecifierSet

allowed = SpecifierSet(">=1,<3").to_range()
required = SpecifierSet(">=2,<4").to_range()
relation = allowed.relation(required)
assert relation is RangeRelation.OVERLAPPING
assert not relation.is_subset and not relation.is_disjoint

empty = VersionRange.empty().relation(required)
assert empty is RangeRelation.EMPTY
assert empty.is_subset and empty.is_disjoint
```

Nab's PubGrub solver uses both flags to classify dependency terms as satisfied, contradicted or undecided. 

---

## 仕様（合意済み）

- `packaging.ranges` に列挙型 `RangeRelation`（メンバー `EMPTY`・`SUBSET`・`DISJOINT`・`OVERLAPPING`）を追加し、`__all__` から公開する。
- `RangeRelation` はプロパティ `is_subset`（`EMPTY` と `SUBSET` で真）と `is_disjoint`（`EMPTY` と `DISJOINT` で真）を持つ。`repr()` は `RangeRelation.SUBSET` のような修飾名にする。
- `VersionRange.relation(other)` は、`self` が空なら `EMPTY`、`self` が `other` に含まれれば `SUBSET`、共通部分が無ければ `DISJOINT`、それ以外は `OVERLAPPING` を返す。結果は既存の `is_subset(other)`・`is_disjoint(other)` と常に一致すること（プレリリースの扱いなどの設定も含めて）。
- 既存の `is_subset`・`is_superset`・`is_disjoint` と同じく、両方の範囲の設定（policy）が同じであることを要求する。
