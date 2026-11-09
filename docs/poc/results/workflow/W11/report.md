# PoC W11 実在する OSS の解決済み課題 — 結果レポート

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w11.py` で生成）

実在する OSS（pytest・zod・packaging・click）で、2026 年 7〜11 月に本家が解決した課題 6 件（不具合 3・機能 3）を、解決前の状態から各候補に解かせた。採点は本家の修正で追加されたテスト（隠しテスト）で行った。設計は [wf-W11-design.md](../../../tasks/wf-W11-design.md)。

## 候補ごとのまとめ

| 候補 | 解決（全 6） | 不具合 3 の解決 | 機能 3 の解決 | 品質の平均 | 費用の合計 | 時間の合計 | 効率の平均 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 4/5 | 2/3 | 2/2 | 93.0 | $2.55 | 26 分 | 85.4 |
| Feature Dev | 4/4 | 2/2 | 2/2 | 100.0 | $2.67 | 14 分 | 82.0 |
| Compound Engineering | 4/4 | 2/2 | 2/2 | 100.0 | $8.33 | 25 分 | 51.5 |
| gstack | 4/5 | 2/3 | 2/2 | 93.0 | $4.48 | 22 分 | 78.0 |
| baseline（候補なし） | 4/5 | 2/3 | 2/2 | 93.0 | $1.29 | 11 分 | 100.0 |

- 解決 = 本家のテストのうち、修正前に失敗し修正後に通るもの（F2P）がすべて通り、もともと通るもの（P2P）を 1 つも壊していない。
- 品質（100 点）= 新しいテストの通過率 × 70 + 既存テストの維持率 × 30。
- 効率（100 点）= 費用 50 + 時間 30 + 介入 20。その課題の baseline に対する倍率で段階を付ける（2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、それ超 = 0）。

## 課題 × 候補の結果

各セル: 解決（✅ / ❌）と品質、（新しいテストの通過数 / 総数・壊した既存テストの数）。

| 課題 | Superpowers | Feature Dev | Compound Engineering | gstack | baseline（候補なし） |
|---|---|---|---|---|---|
| **B1**（不具合）pytest: 同じ親ディレクトリが引数に複数回出ると、フィクスチャが見つからない | ✅ 100（新 1/1） | ✅ 100（新 1/1） | ✅ 100（新 1/1） | ✅ 100（新 1/1） | ✅ 100（新 1/1） |
| **B2**（不具合）pytest: assert の中の代入式（:=）が 2 回評価される | ✅ 100（新 13/13） | ✅ 100（新 13/13） | ✅ 100（新 13/13） | ✅ 100（新 13/13） | ✅ 100（新 13/13） |
| **B3**（不具合）zod: 共通の再帰スキーマを持つ union の非同期検証が不正な入力を通す | ❌ 65（新 5/10） | — | — | ❌ 65（新 5/10） | ❌ 65（新 5/10） |
| **F1**（機能）zod: 循環参照を含む入力を検証できるようにする | — | — | — | — | — |
| **F2**（機能）packaging: 範囲の包含関係と重なりを 1 回で返す API | ✅ 100（新 54/54） | ✅ 100（新 54/54） | ✅ 100（新 54/54） | ✅ 100（新 54/54） | ✅ 100（新 54/54） |
| **F3**（機能）click: テスト実行器 invoke() に Context の設定を渡せるようにする | ✅ 100（新 22/22） | ✅ 100（新 22/22） | ✅ 100（新 22/22） | ✅ 100（新 22/22） | ✅ 100（新 22/22） |

## 費用と時間

| 課題 | Superpowers | Feature Dev | Compound Engineering | gstack | baseline（候補なし） |
|---|---|---|---|---|---|
| B1 | $0.48・5.7 分 | $0.58・5.8 分 | $0.50・2.2 分 | $0.59・2.6 分 | $0.45・3.6 分 |
| B2 | $0.66・7.8 分 | $0.58・3.7 分 | $0.62・5.3 分 | $0.46・2.7 分 | $0.17・1.4 分 |
| B3 | $0.29・6.4 分 | —・— | —・— | $0.31・7.2 分 | $0.21・3.4 分 |
| F1 | —・— | —・— | —・— | —・— | —・— |
| F2 | $0.65・3.3 分 | $0.80・2.7 分 | $3.76・8.6 分 | $1.38・4.6 分 | $0.24・1.2 分 |
| F3 | $0.47・2.4 分 | $0.72・1.9 分 | $3.46・8.4 分 | $1.74・4.9 分 | $0.21・1.2 分 |

## 変更の規模と、候補が書いたテスト

ソースの変更行数（追加 + 削除。テスト・文書・候補の管理用ファイルを除く）と、候補が追加したテストの行数。括弧内は本家の修正の行数。

| 課題（本家） | Superpowers | Feature Dev | Compound Engineering | gstack | baseline（候補なし） |
|---|---|---|---|---|---|
| B1（25） | ソース 6・テスト +35 | ソース 11・テスト +47 | ソース 15・テスト +31 | ソース 18・テスト +40 | ソース 7・テスト +31 |
| B2（161） | ソース 104・テスト +94 | ソース 83・テスト +38 | ソース 105・テスト +61 | ソース 101・テスト +41 | ソース 67・テスト +28 |
| B3（94） | ソース 11・テスト +13 | — | — | ソース 12・テスト +19 | ソース 17・テスト +11 |
| F1（?） | — | — | — | — | — |
| F2（137） | ソース 83・テスト +84 | ソース 76・テスト +67 | ソース 89・テスト +194 | ソース 76・テスト +73 | ソース 70・テスト +64 |
| F3（52） | ソース 35・テスト +77 | ソース 31・テスト +32 | ソース 26・テスト +120 | ソース 27・テスト +45 | ソース 29・テスト +43 |

## 試行の独立性と拒否された操作

| 試行 | 外部参照などの形跡 | 拒否された操作 | 使った Skill | サブエージェント | 介入 | 費用上限で停止 |
|---|---|---:|---|---:|---:|---|
| W11-B1-baseline-1 | なし | 6 | — | 0 | 0 | — |
| W11-B1-compound-engineering-1 | なし | 5 | — | 0 | 0 | — |
| W11-B1-feature-dev-1 | なし | 8 | feature-dev:feature-dev | 1 | 0 | — |
| W11-B1-gstack-1 | なし | 0 | — | 0 | 0 | — |
| W11-B1-superpowers-1 | なし | 6 | superpowers:systematic-debugging | 0 | 0 | — |
| W11-B2-baseline-1 | なし | 0 | — | 0 | 0 | — |
| W11-B2-compound-engineering-1 | なし | 8 | compound-engineering:ce-commit | 0 | 0 | — |
| W11-B2-feature-dev-1 | なし | 3 | feature-dev:feature-dev | 3 | 0 | — |
| W11-B2-gstack-1 | なし | 0 | — | 0 | 0 | — |
| W11-B2-superpowers-1 | なし | 3 | superpowers:requesting-code-review, superpowers:systematic-debugging | 1 | 0 | — |
| W11-B3-baseline-1 | なし | 2 | — | 0 | 0 | — |
| W11-B3-gstack-1 | なし | 0 | — | 0 | 0 | — |
| W11-B3-superpowers-1 | なし | 3 | superpowers:systematic-debugging | 0 | 0 | — |
| W11-F2-baseline-1 | なし | 1 | — | 0 | 0 | — |
| W11-F2-compound-engineering-1 | なし | 22 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-work | 3 | 0 | — |
| W11-F2-feature-dev-1 | なし | 5 | — | 3 | 0 | — |
| W11-F2-gstack-1 | なし | 10 | code-review | 3 | 0 | — |
| W11-F2-superpowers-1 | なし | 5 | superpowers:brainstorming, superpowers:requesting-code-review | 1 | 0 | — |
| W11-F3-baseline-1 | なし | 2 | — | 0 | 0 | — |
| W11-F3-compound-engineering-1 | なし | 20 | compound-engineering:ce-code-review, compound-engineering:ce-commit, compound-engineering:ce-doc-review, compound-engineering:ce-work | 3 | 2 | — |
| W11-F3-feature-dev-1 | なし | 4 | — | 4 | 0 | — |
| W11-F3-gstack-1 | なし | 8 | review, verify | 5 | 0 | — |
| W11-F3-superpowers-1 | なし | 6 | superpowers:brainstorming, superpowers:requesting-code-review | 1 | 0 | — |

