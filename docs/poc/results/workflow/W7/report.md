# 開発ワークフロー PoC — W7 続けて行う作業での学習効果

実施日 2026-11-09 ・ モデル claude-sonnet-5-5 ・ Claude Code 2.1.319 ・ 計画書 docs/poc/PLAN.md §5.1

> HTML 版: [report.html](report.html)（同じデータから `scripts/poc/report_w7.py` で生成）

**W7（続けて行う作業での学習効果）では、品質に差は出ませんでした。**4 候補 × 2 組と baseline の全 9 組が、W7b（作業記録）で 2 件の落とし穴（日時は UTC で保存し JST で表示する、新しい API は独自のエラー型で返す）をレビューの指摘の前に避け、受け入れテストも 14/14 でした（品質は全組 100 点）。

W7a（完了報告）で落とし穴を外したのは Feature Dev #1・Compound Engineering #1・#2 の 3 組（いずれも P2 のエラー型）で、3 組とも W7b では指摘の前に避けました（**同じ間違いの繰り返しは 0 件**）。Compound Engineering は `/ce-compound` で決まりを `docs/solutions/` に残し、#2 は W7b の最初の調査でそれを読みました。

ただし、**前の段階の知見が無い対照（W7a を引き継がず、W7a の参照実装だけがある状態で W7b を実行）でも 4 候補すべてが 2 件とも避けた**ため、W7b での回避は「W7a で直ったコードが手本として残っていること」で説明でき、記憶の仕組みの効き目はこの 2 段階の設計では切り分けられません。

効率（同じ品質での費用・時間。基準は W7b baseline の $0.36・96 秒）は baseline（100 点）と Superpowers（94 点）が最も良く、Feature Dev 77 点、Compound Engineering 36.5 点、gstack 36 点です。続けて行った W7b の費用は対照と比べても下がっておらず（Compound Engineering $5.67 対 $3.96、gstack $3.48 対 $3.02）、記憶を引き継ぐことによる費用・時間の削減は見られませんでした。

## 2 本立ての点数（品質・効率）

- 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Superpowers 94.0、Feature Dev 77.0、Compound Engineering 36.5、gstack 36.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 Feature Dev は、品質でも 1 位（同点を含む: Superpowers・Feature Dev・Compound Engineering・gstack・baseline（候補なし））。

### 候補ごとの平均

| 候補 | 回数 | 品質 / 100 | 2 回の差 | 効率 / 100 | 総合点（従来） | 費用（baseline 比） | 時間（baseline 比） | 介入 | 質問（参考） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 100.0（最高） | 0.0 | 94.0 | 89.6 | $0.66（1.8 倍） | 3.9 分（2.4 倍） | 0 回 | 0 回 |
| Feature Dev | 2 | 100.0（最高） | 0.0 | 77.0 | 96.5 | $1.30（3.6 倍） | 3.0 分（1.9 倍） | 0 回 | 0 回 |
| Compound Engineering | 2 | 100.0（最高） | 0.0 | 36.5 | 92.0 | $5.67（15.6 倍） | 11.9 分（7.5 倍） | 0 回 | 0 回 |
| gstack | 2 | 100.0（最高） | 0.0 | 36.0 | 81.2 | $3.48（9.6 倍） | 7.5 分（4.7 倍） | 1 回 | 0 回 |
| baseline（候補なし） | 1 | 100.0（最高） | — | 100.0 | 93.2 | $0.36（1.0 倍） | 1.6 分（1.0 倍） | 0 回 | 0 回 |

### 試行ごとの内訳

| 試行 | W7b で落とし穴を避けた数 / 50 | W7b の受け入れ / 20 | 品質 / 100 | 費用 / 50 | 時間 / 30 | 介入 / 20 | 効率 / 100 | 総合点（従来） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers #1 | 50 | 20 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 94.2 |
| Superpowers #2 | 50 | 20 | 100.0 | 50.0 | 18.0 | 20 | 88.0 | 85.0 |
| Feature Dev #1 | 50 | 20 | 100.0 | 30.0 | 30.0 | 20 | 80.0 | 98.5 |
| Feature Dev #2 | 50 | 20 | 100.0 | 30.0 | 24.0 | 20 | 74.0 | 94.4 |
| Compound Engineering #1 | 50 | 20 | 100.0 | 15.0 | 9.0 | 20 | 44.0 | 95.5 |
| Compound Engineering #2 | 50 | 20 | 100.0 | 0.0 | 9.0 | 20 | 29.0 | 88.6 |
| gstack #1 | 50 | 20 | 100.0 | 15.0 | 18.0 | 20 | 53.0 | 87.2 |
| gstack #2 | 50 | 20 | 100.0 | 0.0 | 9.0 | 10 | 19.0 | 75.1 |
| baseline（候補なし） #1 | 50 | 20 | 100.0 | 50.0 | 30.0 | 20 | 100.0 | 93.2 |

### 計算方法と判断の記録

- 品質 = （W7b で落とし穴を避けた数 50 + W7b の受け入れ 20）の得点 ÷ 70 × 100。
- 効率 = 費用 50 + 時間 30 + 介入 20。費用・時間は baseline（$0.3638・96 秒）に対する倍率で、2 倍以下 = 満点、3 倍以下 = 80%、5 倍以下 = 60%、10 倍以下 = 30%、10 倍超 = 0。介入は 0 回 = 20、1 回 = 10、2 回以上 = 0。
- 質問の回数は効率から引かない（参考値）。品質の差が、比べる 2 候補の 2 回の差（ばらつき）の大きい方以下なら「差なし」とする。
- 定義は docs/poc/PLAN.md §4.4。計算は scripts/poc/two_axis.py。従来の総合点・順位はこの節では変えない。


## 課題

同じ評価用アプリで、W7a「タスクの完了報告」（API 3 本と詳細画面の表示。課題文 `docs/poc/tasks/wf-W7a.md`）を行い、続けて新しいセッションで W7b「タスクの作業記録」（API 3 本と詳細画面の一覧・合計。`wf-W7b.md`）を行わせた。W7b は W7a の作業用コピーと専用 HOME をそのまま引き継ぐ。初期状態は v2（決まりへの移行の途中。既存のコメント・タスクの API は古い書き方のまま、新しい決まりは `src/lib/errors.ts`・`src/lib/datetime.ts`・`withApi`・`GET /api/me` とテストにだけ現れる）。どちらの課題文にも決まりは書かず、W7a・W7b の両方に同じ 2 件の落とし穴を含めた。手順を終えた後に落とし穴を判定し、外していればレビューの定型の指摘を送って直させた（最大 2 回）。採点は W7b の指摘前の判定で行う。

## 結果の概要（平均点。W7a → W7b の 1 組ごとに採点）

| 候補 | 組 | 合計 / 100 | 落とし穴（W7b）/ 50 | 所要時間の比 / 15 | 介入回数の比 / 15 | 受け入れテスト（W7b）/ 20 | 指摘前に避けた落とし穴 W7a → W7b | 平均費用 W7a → W7b | 平均時間（分）W7a → W7b |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 2 | 89.6 | 50 | 4.6 | 15.0 | 20.0 | 4 / 4 → 4 / 4 | $0.63 → $0.66 | 2.8 → 3.9 |
| **Feature Dev** | 2 | 96.5 | 50 | 11.4 | 15.0 | 20.0 | 3 / 4 → 4 / 4 | $1.42 → $1.30 | 4.2 → 3.0 |
| Compound Engineering | 2 | 92.0 | 50 | 7.0 | 15.0 | 20.0 | 2 / 4 → 4 / 4 | $4.97 → $5.67 | 11.6 → 11.9 |
| gstack | 2 | 81.2 | 50 | 3.6 | 7.5 | 20.0 | 4 / 4 → 4 / 4 | $2.43 → $3.48 | 6.1 → 7.5 |
| baseline（候補なし） | 1 | 93.2 | 50 | 8.2 | 15.0 | 20.0 | 2 / 2 → 2 / 2 | $0.36 → $0.36 | 1.7 → 1.6 |

## 落とし穴を指摘の前に避けられた組の数

| 候補 | W7a P1 日時（UTC 保存・JST 表示） | W7a P2 独自のエラー型 | W7b P1 日時（UTC 保存・JST 表示） | W7b P2 独自のエラー型 |
|---|---:|---:|---:|---:|
| Superpowers | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| Feature Dev | 2 / 2 | 1 / 2 | 2 / 2 | 2 / 2 |
| Compound Engineering | 2 / 2 | 0 / 2 | 2 / 2 | 2 / 2 |
| gstack | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| baseline（候補なし） | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |

## 組ごとの結果

落とし穴: 「指摘前」は手順を終えた時点（レビューの指摘を受ける前）、「最終」は指摘のやり取りの後。

| 組 | 点数 | W7a 指摘前 | W7a 最終 | W7b 指摘前 | W7b 最終 | 受入 W7a | 受入 W7b | 時間（分）W7a → W7b（比） | 介入 W7a → W7b | 費用 W7a → W7b | ターン | 使われた Skill |
|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Superpowers #1 | 94.2 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 2.9 → 2.5（0.88） | 0 → 0 | $0.69 → $0.63 | 8 → 2 | superpowers:brainstorming, superpowers:requesting-code-review |
| Superpowers #2 | 85.0 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 2.8 → 5.3（1.9） | 0 → 0 | $0.57 → $0.69 | 2 → 2 | superpowers:brainstorming, superpowers:requesting-code-review, superpowers:test-driven-development |
| Feature Dev #1 | 98.5 | P1✅ P2❌ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 4.4 → 2.6（0.6） | 1 → 0 | $1.52 → $1.24 | 13 → 2 | — |
| Feature Dev #2 | 94.4 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 4.0 → 3.5（0.87） | 0 → 0 | $1.32 → $1.36 | 1 → 3 | — |
| Compound Engineering #1 | 95.5 | P1✅ P2❌ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 11.5 → 9.2（0.8） | 1 → 0 | $5.35 → $3.62 | 49 → 104 | compound-engineering:ce-code-review, compound-engineering:ce-commit, compound-engineering:ce-doc-review, compound-engineering:ce-simplify-code, compound-engineering:ce-work |
| Compound Engineering #2 | 88.6 | P1✅ P2❌ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 11.7 → 14.7（1.26） | 1 → 0 | $4.58 → $7.73 | 137 → 23 | compound-engineering:ce-code-review, compound-engineering:ce-doc-review, compound-engineering:ce-simplify-code, compound-engineering:ce-work |
| gstack #1 | 87.2 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 3.8 → 5.1（1.35） | 0 → 0 | $1.81 → $2.37 | 40 → 58 | review, verify |
| gstack #2 | 75.1 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 8.4 → 9.8（1.16） | 0 → 1 | $3.06 → $4.59 | 55 → 88 | code-review, review |
| baseline（候補なし） #1 | 93.2 | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | P1✅ P2✅ | 16/16 | 14/14 | 1.7 → 1.6（0.95） | 0 → 0 | $0.36 → $0.36 | 19 → 21 | — |

## 前の段階の知見を読んだか・同じ間違いを繰り返したか

「W7a で指摘を受けた」は W7a で指摘の前に避けられなかった落とし穴（学ぶ機会があったもの）。「W7b で繰り返した」はそのうち W7b でも指摘の前に避けられなかったもの。

| 組 | W7a で指摘を受けた | W7b で繰り返した | W7b で読んだ前の段階の知見（W7a が残したファイル） |
|---|---|---|---|
| Superpowers #1 | なし | — | なし |
| Superpowers #2 | なし | — | なし |
| Feature Dev #1 | P2 | なし | なし |
| Feature Dev #2 | なし | — | なし |
| Compound Engineering #1 | P2 | なし | `docs/plans/2026-11-09-1200-feat-task-completion-report-plan.md` |
| Compound Engineering #2 | P2 | なし | `docs/plans/2026-11-09-1330-feat-task-completion-report-plan.md`<br>`docs/solutions/conventions/new-api-routes-use-withapi-and-apperror.md` |
| gstack #1 | なし | — | なし |
| gstack #2 | なし | — | なし |
| baseline（候補なし） #1 | なし | — | なし |

## 対照（W7a を引き継がない W7b）との比較

対照は、同じ候補で W7b だけを、新しい作業用コピー（初期状態 + W7a の参照実装）と新しい HOME で行ったもの（各候補 1 回）。候補の記憶も、候補自身が書いた W7a のコードも無い。「続けて」は続けて行った W7b（2 組の平均）。

| 候補 | 対照: 指摘前 | 続けて: 指摘前に避けた数 | 対照: 受入 | 費用 対照 / 続けて | 時間（分）対照 / 続けて | ターン 対照 / 続けて | 品質 対照 / 続けて | 効率 対照 / 続けて |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | P1✅ P2✅ | 4 / 4 | 14/14 | $0.75 / $0.66 | 3.4 / 3.9 | 4 / 2.0 | 100.0 / 100.0 | 84.0 / 94.0 |
| Feature Dev | P1✅ P2✅ | 4 / 4 | 14/14 | $1.36 / $1.30 | 4.3 / 3.0 | 3 / 2.5 | 100.0 / 100.0 | 74.0 / 77.0 |
| Compound Engineering | P1✅ P2✅ | 4 / 4 | 14/14 | $3.96 / $5.67 | 10.3 / 11.9 | 19 / 63.5 | 100.0 / 100.0 | 29.0 / 36.5 |
| gstack | P1✅ P2✅ | 4 / 4 | 14/14 | $3.02 / $3.48 | 7.2 / 7.5 | 71 / 73.0 | 100.0 / 100.0 | 53.0 / 36.0 |

## 所見

- 品質（W7b の落とし穴 + 受け入れ）は 9 組すべて 100 点で、候補の間に差はありません。W7a の受け入れテストも全組 16/16 でした。
- W7a で落とし穴を外したのは 3 組で、すべて P2（新しい API で `AppError`・`withApi` を使わず、既存のタスク API と同じ `jsonError` で返した）。P1（日時）は全組が W7a から避けました。既存コードに `toUtcIso`・`formatJst` とテストがあり、日時は気づきやすかったと考えられます。
- W7a で指摘を受けた 3 組（Feature Dev #1、Compound Engineering #1・#2）は、W7b で 3 組とも指摘の前に避けました（同じ間違いの繰り返し 0 件）。ほかの 6 組は W7a でも避けていたため、学ぶ機会自体がありませんでした。
- 前の段階の知見を読んだ形跡: Compound Engineering #2 は W7b の 1 ステップ目で `docs/solutions/conventions/new-api-routes-use-withapi-and-apperror.md` を直接読みました。#1 は記録上、W7a の計画書（`docs/plans/`）を読んだ形跡だけが残り、`docs/solutions/` を読んだかはサブエージェントの中で読んだ可能性も含めて確認できませんでした。Feature Dev #1 は記憶の仕組みを持たず、W7a で直したコード（同じ作業用コピーに残る）を手本にしたと考えられます。
- 対照（W7a を引き継がない W7b、各候補 1 回）: Superpowers・Feature Dev・Compound Engineering・gstack の 4 本とも、指摘の前に 2 件とも避け、受け入れ 14/14 でした。対照の作業用コピーには W7a の参照実装（決まりに沿ったコード）があるので、続けて行った W7b と同じく「手本」はあり、違いは候補の記憶と候補自身の W7a のコードの有無だけです。この差で回避の結果は変わりませんでした。
- 費用・時間の対照との比較（続けて行った W7b の 2 組平均 / 対照）: Superpowers $0.66・3.9 分 / $0.75・3.4 分、Feature Dev $1.30・3.0 分 / $1.36・4.3 分、Compound Engineering $5.67・11.9 分 / $3.96・10.3 分、gstack $3.48・7.5 分 / $3.02・7.2 分。続けて行うことで安く速くなったとは言えず、Compound Engineering は記憶を引き継いだ側の方が高くつきました（#2 は上限 $7.67 で止めた）。
- W7a → W7b の費用の変化は、baseline $0.36 → $0.36、Superpowers $0.63 → $0.66（平均）、Feature Dev $1.42 → $1.30、Compound Engineering $4.97 → $5.67、gstack $2.43 → $3.48。W7b は W7a と別の機能なので、この変化は学習だけでなく課題の違いも含みます。
- gstack #2 の W7b は、`/review` が足したテストを未コミットのまま確認待ちで止まり、「お任せします」の介入を 1 回受けました（効率の介入 0 点）。Compound Engineering #2 の W7b は watch の見積もりが上限（$7.67）に達し、`/ce-work` の途中で止めました（実装とコミットは済んでおり、品質は 100 点）。

## 各候補が W7a → W7b に残したもの

- **Compound Engineering**: 2 組とも W7a の指摘の後の `/ce-compound` で、決まり（新しい API は `withApi` と `AppError` を使う）を `docs/solutions/conventions/` に 1 件残しました。W7a の計画書（`docs/plans/`）も作業用コピーに残ります。
- **gstack**: 専用 HOME の `~/.gstack/` に設定・状態が残りました。#2 は学習データ（`learnings.jsonl`）を 1 件残しましたが、内容は gstack 自身の QA の道具の使い方で、プロジェクトの決まりではありません（W7a で指摘を受けておらず、学ぶ機会がなかった）。
- **Superpowers・Feature Dev・baseline**: 記憶の仕組みを持たないため、残ったのは W7a で書いたコードとコミットだけです（Claude Code の自動メモリは全試行で止めた）。
- 候補が `CLAUDE.md` の API の一覧を更新した組がある（baseline・Feature Dev #2・gstack #1 の W7b など）が、内容は API の追加の記載で、落とし穴の決まりを書き足した組はありませんでした。

## 組の詳細

### Superpowers #1 — 94.2 点

2 段階とも `brainstorming` が発火。W7a は `requesting-code-review` でレビューもさせた。2 件とも W7a から避けた。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Agent: `{"description": "Review worklogs feature", "subagent_type": "general-purpose", "prompt": "Review the uncommitted changes in /tmp/poc-trials/W7a-superpowers-1/ap`

### Superpowers #2 — 85.0 点

2 件とも W7a から避けた。W7b は `test-driven-development`・`requesting-code-review` まで進み、時間が W7a の 1.9 倍になった（総合点の時間の比は 0 点）。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Agent: `{"description": "作業記録機能のコードレビュー", "subagent_type": "general-purpose", "prompt": "Review the git diff 1c46db715f175b5f21dbbdcc51ffb2549cbfb07e..197dcec60a5bd8be9`

### Feature Dev #1 — 98.5 点

W7a で P2 を外し、指摘 1 回で直した。W7b は 2 件とも指摘の前に避けた。記憶の仕組みは無く、W7a で直したコードを手本にしたと考えられる。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Agent: `{"subagent_type": "feature-dev:code-architect", "description": "最小変更案の設計", "prompt": "/tmp/poc-trials/W7a-feature-dev-1/app に「作業記録(worklog)」を追加する設計を、最小変更・最大再利用の`
- Agent: `{"subagent_type": "feature-dev:code-reviewer", "description": "規約・簡潔さのレビュー", "prompt": "/tmp/poc-trials/W7a-feature-dev-1/app の CLAUDE.md の規約（1〜9）と既存コードの流儀（src/`

### Feature Dev #2 — 94.4 点

2 件とも W7a から避けた。W7a の `isolation_suspects` 1 件は自分の作業用コピーの中の参照（下の「試行間の独立性」）。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Agent: `{"subagent_type": "feature-dev:code-architect", "description": "Minimal worklog design", "prompt": "/tmp/poc-trials/W7a-feature-dev-2/app（CLAUDE.md を先に読むこと）に「作業`
- Agent: `{"subagent_type": "feature-dev:code-architect", "description": "Clean worklog design", "prompt": "/tmp/poc-trials/W7a-feature-dev-2/app（CLAUDE.md を先に読むこと）に「作業記録`
- Agent: `{"subagent_type": "feature-dev:code-reviewer", "description": "Review conventions/simplicity", "prompt": "/tmp/poc-trials/W7a-feature-dev-2/app の未コミットの変更（git st`

### Compound Engineering #1 — 95.5 点

W7a で P2 を外し、指摘 1 回で直した後、`/ce-compound` で決まりを `docs/solutions/` に残した。W7b は 2 件とも指摘の前に避けた。W7b で読んだ形跡として記録に残ったのは W7a の計画書。

W7a から W7b に残ったもの（作業用コピー）:

- `docs/plans/2026-11-09-1200-feat-task-completion-report-plan.md`
- `docs/solutions/conventions/new-api-routes-use-apperror-and-withapi.md`

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/output-mode.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/resume.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/intake.md"}`
- Bash: `{"command": "git rev-parse --show-toplevel && git status --short \| head && ls -a && cat .compound-engineering/config.yaml 2>/dev/null; ls docs docs/plans 2>/dev`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/synthesis-summary.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/research.md"}`
- Bash: `{"command": "git log --oneline \| head -20 && cat docs/plans/*.md \| head -150 && ls docs/solutions && cat \"src/app/tasks/[id]/page.tsx\" \"src/app/tasks/[id]/co`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/structure.md"}`
- Bash: `{"command": "find docs/solutions -type f \| head; ls .compound-engineering 2>&1 \| head -3; cd ../plugins/compound-engineering/skills/ce-plan && ls references ref`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-1/plugins/compound-engineering/skills/ce-plan/references/plan-sections.md"}`

### Compound Engineering #2 — 88.6 点

W7a で P2 を外し、指摘 1 回で直した後、`/ce-compound` で決まりを残した。W7b の最初の調査でその `docs/solutions/` を読み、2 件とも避けた。W7b は watch の上限（$7.67）で `/ce-work` の途中で止めた（費用は見積額 $7.73 で数える。`/ce-code-review` は未実行）。

W7a から W7b に残ったもの（作業用コピー）:

- `docs/plans/2026-11-09-1330-feat-task-completion-report-plan.md`
- `docs/solutions/conventions/new-api-routes-use-withapi-and-apperror.md`

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/plugins/compound-engineering/skills/ce-plan/references/output-mode.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/plugins/compound-engineering/skills/ce-plan/references/resume.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/plugins/compound-engineering/skills/ce-plan/references/intake.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/plugins/compound-engineering/skills/ce-plan/references/synthesis-summary.md"}`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/plugins/compound-engineering/skills/ce-plan/references/research.md"}`
- Bash: `{"command": "git status --short \| head; git log --oneline \| head -5; find . -path ./node_modules -prune -o -path ./.next -prune -o -path ./.git -prune -o -type `
- Bash: `{"command": "git status --short; for f in docs/solutions/conventions/new-api-routes-use-withapi-and-apperror.md src/lib/api.ts src/lib/errors.ts src/lib/complet`
- Bash: `{"command": "git status --short; cat docs/solutions/conventions/new-api-routes-use-withapi-and-apperror.md src/lib/api.ts src/lib/errors.ts src/lib/completions.`
- Bash: `{"command": "cat 'src/app/tasks/[id]/page.tsx' src/lib/session.ts src/lib/db/index.ts src/lib/users.ts; sed -n 1,60p tests/completions.test.ts; cat package.json`
- Read: `{"file_path": "/tmp/poc-trials/W7a-compound-engineering-2/app/src/app/tasks/[id]/page.tsx"}`

### gstack #1 — 87.2 点

2 件とも W7a から避けた。W7b の `/review` は専門家別のサブエージェントでレビューした。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- `.gstack/.gbrain-local-status-cache.json`
- `.gstack/.last-setup-version`
- `.gstack/.welcome-seen`
- `.gstack/config.yaml`
- `.gstack/gbrain-detection.json`
- `.gstack/installs.tsv`
- `.gstack/sessions/26024`
- `.gstack/slug-cache/_tmp_poc-trials_W7a-gstack-1_app`
- `.gstack/slug-cache/_tmp_poc-trials_W7a-gstack-1_app_.git`

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Bash: `{"command": "git add CLAUDE.md src tests && git status --short && git commit -q -m \"タスクの作業記録（API・詳細画面表示）を追加\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthr`
- Bash: `{"command": "git rev-parse --short master poc/wf/gstack/W7a/1 HEAD; git fetch origin master --quiet 2>&1 \| head -2; ls TODOS.md 2>&1 \| head -1; touch /tmp/poc-t`
- Bash: `{"command": "B=HEAD~1; git diff $B --stat \| tail -12; ~/.claude/skills/gstack/bin/gstack-review-log --start review 2>&1 \| head -3; echo ---GATE; ~/.claude/skill`
- Bash: `{"command": "~/.claude/skills/gstack/bin/gstack-state-matrix outfile 2>&1 \| head -3; ~/.claude/skills/gstack/bin/gstack-review-log --start adversarial-review 2>`
- Agent: `{"description": "Testing specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer. Work`
- Agent: `{"description": "Maintainability specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code review`
- Agent: `{"description": "Security specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "This is an authorized defensive-securit`
- Agent: `{"description": "Performance specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer. `
- Agent: `{"description": "API contract specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer.`
- Agent: `{"description": "Design specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist design/frontend code`

### gstack #2 — 75.1 点

2 件とも W7a から避けた。W7b で `/review` が足したテストを未コミットのまま確認待ちで止まり、介入 1 回。費用は W7b で $4.59。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- `.gstack/.activated`
- `.gstack/.gbrain-local-status-cache.json`
- `.gstack/.last-setup-version`
- `.gstack/.welcome-seen`
- `.gstack/config.yaml`
- `.gstack/gbrain-detection.json`
- `.gstack/installs.tsv`
- `.gstack/sessions/23275`
- `.gstack/slug-cache/_tmp_poc-trials_W7a-gstack-2_app`
- `.gstack/slug-cache/_tmp_poc-trials_W7a-gstack-2_app_.git`

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- Bash: `{"command": "touch /tmp/poc-trials/W7a-gstack-2/home/.gstack/.feature-prompted-model-overlay /tmp/poc-trials/W7a-gstack-2/home/.gstack/.completeness-intro-seen;`
- Agent: `{"description": "Testing specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer. Read`
- Agent: `{"description": "Maintainability specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code review`
- Agent: `{"description": "Security specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "This is an authorized defensive-securit`
- Agent: `{"description": "Performance specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer. `
- Agent: `{"description": "API contract specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewer.`
- Agent: `{"description": "Data migration specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewe`
- Agent: `{"description": "Design specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist design reviewer. Rea`
- Agent: `{"description": "Simplification specialist review", "subagent_type": "general-purpose", "run_in_background": false, "prompt": "You are a specialist code reviewe`
- Bash: `{"command": "D=~/.claude/skills/gstack/bin/gstack-qa-deadline; E=~/.claude/skills/gstack/bin/gstack-qa-evidence; P=/tmp/poc-trials/W7a-gstack-2/app/.gstack/tmp/`

### baseline（候補なし） #1 — 93.2 点

W7a・W7b とも最初に `api.ts`・`errors.ts`・`datetime.ts` を読み、2 件とも避けた。費用・時間は W7a・W7b ともほぼ同じ（$0.36・約 1.6 分）。

W7a から W7b に残ったもの（作業用コピー）:

- なし

W7a から W7b に残ったもの（専用 HOME。セッションの記録を除く）:

- なし

W7b で記憶になりうるものを読んだ形跡（最初の 10 件）:

- なし

## 採点方法

手順は `docs/poc/answer-key/W7/grading.md`（試行前に固定）。試行ごとに `scripts/poc/grade_w7.py`（受け入れテスト、落とし穴の判定 `pitfalls.cjs`、W7a が残したもの、W7b でそれを読んだ形跡）、組ごとに `score_w7.py`、2 本立てを `two_axis.py` で計算した。


- **品質**（主表示）=（W7b で指摘の前に避けた落とし穴 50 + W7b の受け入れテスト 20）/ 70 × 100。
- **効率**（主表示）= 費用 50 + 時間 30 + 介入 20。W7b の費用・時間を W7b baseline（$0.3638・96 秒）に対する倍率で段階評価する。上限で止めたステップの費用は見積額で数える。
- **総合**（並記。PLAN.md §5.1）= W7b の落とし穴 50 + W7b の所要時間の W7a 比 15 + 介入回数の W7a 比 15 + W7b の受け入れ 20。
- 学習の記録（点数に入れない）: 前の段階の知見を読んだか（`memory_used`）、同じ間違いを繰り返したか（`learned`・`repeated`）、対照との差（`controls`）。

## この結果の制約

- 各候補 2 組、baseline 1 組、対照は各候補 1 回（baseline の対照なし）。全組が品質 100 点で、落とし穴の回避に差が出なかったため、学習の効き目の大きさは測れていない。
- W7a で落とし穴を外して学ぶ機会があったのは 3 組だけ（すべて P2）。P1 は全組が W7a から避けたため、P1 での学習は観察できない。
- 続けて行った W7b と対照の差は、候補の記憶と、候補自身が書いた W7a のコードの両方を含む。対照にも W7a の参照実装（決まりに沿ったコード）があるので、「コードの手本」による回避と「記憶」による回避を区別できない。
- W7b は W7a と別の機能なので、W7a → W7b の費用・時間の変化は課題の違いを含む。
- 対照 Feature Dev・Superpowers・gstack は、ほかの組と別の日時・別のコンテナで実行した（モデル・Claude Code・プラグインの固定コミット・許可リストは同じ）。
- 引き継ぎ後に実行した対照 3 本（Feature Dev・Superpowers・gstack）以外の試行のトランスクリプト（`raw/`、Git 管理外）はコンテナの入れ替えで残っておらず、採点結果の JSON に残った記録だけで判断した箇所がある（Compound Engineering #1 が `docs/solutions/` を読んだか、など）。

## 判断の記録

- v1 の初期状態（既存のコメント機能が決まりに沿っていた）では、baseline が W7a・W7b とも既存のコードを真似るだけで 2 件とも避け、学習の効果を測れなかったため、試行を始める前に v2 に改めた（パイロットの費用 $0.37 + $0.40。`W7/pilot-v1/`）。
- v2 でも baseline は最初に `api.ts`・`errors.ts`・`datetime.ts` を読み 2 件とも避けた。これ以上隠すと「作業中に気づける形」（PLAN.md §5.1）を満たさなくなるため、v2 のまま実施した。
- W6 の許可リストの変更（開発サーバーの起動・ブラウザ）は W7 の試行の開始時点で main に入っていなかったため、W7 は従来の許可リストで統一した。引き継ぎ後に main を取り込んだところ、`run-trial.sh` がシナリオ番号 6 以上に開発サーバー等を許可する形になっていたため、**W7 だけをその追加から外した**（子セッションの許可リストの変更。CLAUDE.md の例外としてコーディネーターが判断）。理由: 採点済みの 18 試行と対照 Compound Engineering が従来の許可リストで行われており、残りの対照 3 本も同じ条件にするため。W6・W9 以降の許可は変えていない。
- Claude Code の自動メモリは候補の記憶の仕組みではなく、W7b が W7a の HOME を引き継ぐと全候補に同じ記憶が残るため、W7 の全試行で止めた（`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`）。
- ユーザーの要望で、段階を W7c 以降に増やせる形（`run-trial.sh` は 1 つ前の段階を引き継ぐ。`POC_W7_LAST_STAGE`）、前の段階の知見を読んだか・同じ間違いの繰り返し・対照の記録を足した。対照は W7a を引き継がない W7b（`base.patch` + `reference-W7a.patch`、回の番号 11）。baseline の対照・baseline の 2 回目は、ユーザー未承認のため行っていない。
- 品質・効率の 2 本立てを主表示にし、総合点を並記した（効率の基準は W7b baseline の $0.3638・96 秒）。
- watch の上限で止めたステップの費用は result に入らないため、見積額で数えた（Compound Engineering #2 の W7b、$7.73）。
- 上限はすべて $7.67（v2 baseline の W7a 実額 $0.3566 ÷ W1 baseline $0.15 × W1 の候補平均 $0.6457 × 5）。$10 を超える上限は不要だった。
- 中断とやり直し: 1 回目の中断（06:05 UTC、usage の上限）で W7a の途中だった Compound Engineering #1・#2 を止め、再開後に W7a からやり直した。2 回目の中断（14:45 UTC、別アカウントへの引き継ぎ）で対照 Feature Dev を途中で止め、その記録は使わずに引き継ぎ後に最初からやり直した。
- 引き継ぎ後の新しいコンテナでは、前任の作業用コピー（`/tmp/poc-trials/`）とトランスクリプト（`raw/`、Git 管理外）が残っていなかった。採点は済んでいたため再実行はせず、対照 3 本だけを新しく実行した。作業用コピーの片付け（`grade.py --cleanup-only`）は、前任の分はコンテナとともに消えているため不要。
- `report_w7.py` の HOME に残ったものの一覧は、Claude Code のセッションの記録（`.claude/projects/` の `memory/` 以外）を除いて表示する（`grade_w7.py` が除くようになる前に採点した試行の分も同じに揃えるため）。

## 試行間の独立性の確認結果

`grade.py` の検出で、対照 4 本を含む全 22 試行の `answer_key_access`（正解データを読んだ形跡）は無し、`isolation_suspects`（作業用コピーの外への参照）は Feature Dev #2 の W7a の 1 件を除いて 0。その 1 件は作業用コピーの `src/app` から `../../tests` を読んだもので、自分の作業用コピーの中の参照。W7b が W7a の作業用コピー・HOME を読むのは自分の試行の一部として扱った（`continued-from` の ID は他の試行に数えない）。

## 次の対応

- **2 段階で言えること**: 決まりに沿ったコードが作業用コピーに 1 か所でもあれば、記憶の仕組みの有無にかかわらず、4 候補と baseline のすべてが次の作業で同じ落とし穴を避けた。W7a で指摘を受けた 3 組も W7b で繰り返さなかった。続けて行うことで費用・時間が下がる効果は見られず、Compound Engineering・gstack は記憶を引き継いでも高いままだった。
- **2 段階で言えないこと**: 記憶の仕組み（Compound Engineering の `docs/solutions/`、gstack の学習データ）の寄与。対照でも避けられたため、コードの手本の効果と切り分けられない。段階を重ねたときに費用が下がるか・記憶が古くなって害になるか。
- **5 段階に延ばす価値の見立て**: 今の課題の形（同じ層・同じ書き方の API を足す）のまま延ばしても、コードの手本で避けられるため差は出にくく、費用に見合わない。延ばすなら、後の段階を「前の段階のコードを手本にできない」形にする（別の層・別の画面で同じ決まりが要る、決まりに例外がある、決まりがコードに現れない運用上の約束など）。その場合は記憶の仕組みの差が出る見込みがあり、価値がある。W7c〜W7e の課題文・受け入れテスト・参照実装を足せば、今の `run-trial.sh` のまま実行できる（`grading.md` の「段階を増やすとき」）。
- 延長するかどうかは、費用（1 組あたり最大 $7.67 × 段階数）とあわせてユーザーの判断を仰ぐ。
