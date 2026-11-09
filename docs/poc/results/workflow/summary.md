# 開発ワークフロー PoC — 全シナリオの 2 本立て（品質・効率）一覧

> HTML 版: [summary.html](summary.html)（同じデータから `scripts/poc/two_axis.py` で生成）

各シナリオを「品質で差があるか」「同じ品質ならどれだけ安く速いか」の 2 軸で見た一覧です。従来の総合点・順位は置き換えず並記しています（定義は [PLAN.md §4.4](../../PLAN.md)）。

## 要点

- **W2 で順位が入れ替わった**: 従来の総合点の 1 位は baseline（候補なし）、品質の 1 位は Compound Engineering。ただし品質の差 3.0 点は、この W の同じ候補の 2 回の差の最大 5.4 点以下で、1 回しか試行していない側のばらつきは測れていないため、確定的な差とは言えない。
- W1（小さな変更）: 品質: 最高は Superpowers・Feature Dev・gstack・baseline（候補なし）（100.0 点）。これと差なし（差がばらつき以下）: Superpowers（100.0）、Feature Dev（100.0）、gstack（100.0）、baseline（候補なし）（100.0）。差あり: Compound Engineering（94.3、−5.7）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.1 倍・時間 1.0 倍）、Feature Dev（費用 1.1 倍・時間 1.0 倍）、baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは gstack 82.0。
- W2（仕様が明確な機能追加）: 品質: 最高は Compound Engineering（99.2 点）。これと差なし（差がばらつき以下）: Superpowers（94.2）、Compound Engineering（99.2）。差あり: Feature Dev（96.9、−2.3）、gstack（97.3、−1.9）、baseline（候補なし）（96.2、−3.0）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 63.5。
- W3（曖昧な要望から要件を固める）: 品質: 最高は Feature Dev・baseline（候補なし）（89.4 点）。これと差なし（差がばらつき以下）: Feature Dev（89.4）、Compound Engineering（82.7）、gstack（80.9）、baseline（候補なし）（89.4）。差あり: Superpowers（73.2、−16.2）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 92.0、Feature Dev 84.0、gstack 36.5。
- W4（既存コードを横断する大きな変更）: 品質: 最高は Compound Engineering（94.5 点）。これと差なし（差がばらつき以下）: Compound Engineering（94.5）、gstack（50.5）。差あり: Superpowers（81.3、−13.2）、Feature Dev（86.8、−7.7）、baseline（候補なし）（82.0、−12.5）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Compound Engineering（費用 3.9 倍・時間 2.2 倍）で効率 74.0 点。ほかは gstack 53.0。
- W5（バグ修正）: 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.4 倍・時間 1.3 倍）、Feature Dev（費用 1.7 倍・時間 1.6 倍）、baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは gstack 95.0、Compound Engineering 74.0。
- W6（UI 実装からブラウザ検証・PR 作成まで）: 品質: 最高は baseline（候補なし）（100.0 点）。これと差なし（差がばらつき以下）: Compound Engineering（99.7）、baseline（候補なし）（100.0）。差あり: Superpowers（98.2、−1.8）、Feature Dev（98.2、−1.8）、gstack（99.1、−0.9）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 95.0。
- W7（続けて行う作業での学習効果）: 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Superpowers 97.0、Feature Dev 80.0、gstack 39.0、Compound Engineering 36.5。
- W9（レビューで不具合を見つける）: 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.6 点は、同じ候補の 2 回の差の最大 1.2 点以下）。 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Feature Dev 92.0、Superpowers 90.0、gstack 90.0、Compound Engineering 74.5。
- 未完了（main に結果が無い）: W8・W10

## 品質（平均 / 100）

| 候補 | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | **100.0** | 94.2≒ | 73.2 | 81.3 | **100.0** | 98.2 | **100.0** | 未完了 | **100.0** | 未完了 |
| Feature Dev | **100.0** | 96.9 | **89.4** | 86.8 | **100.0** | 98.2 | **100.0** | 未完了 | 99.4≒ | 未完了 |
| Compound Engineering | 94.3 | **99.2** | 82.7≒ | **94.5** | **100.0** | 99.7≒ | **100.0** | 未完了 | 99.4≒ | 未完了 |
| gstack | **100.0** | 97.3 | 80.9≒ | 50.5≒ | **100.0** | 99.1 | **100.0** | 未完了 | 99.4≒ | 未完了 |
| baseline（候補なし） | **100.0** | 96.2 | **89.4** | 82.0 | **100.0** | **100.0** | **100.0** | 未完了 | **100.0** | 未完了 |

太字 = その W の品質の最高。≒ = 最高との差が試行のばらつき（2 回の差）以下で「品質に差なし」。

## 効率（平均 / 100）

| 候補 | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 100.0 | 100.0 | 84.0 | 100.0 | 100.0 | 100.0 | 97.0 | 未完了 | 90.0 | 未完了 |
| Feature Dev | 100.0 | 100.0 | 84.0 | 100.0 | 100.0 | 95.0 | 80.0 | 未完了 | 92.0 | 未完了 |
| Compound Engineering | 18.0 | 63.5 | 92.0 | 74.0 | 74.0 | 95.0 | 36.5 | 未完了 | 74.5 | 未完了 |
| gstack | 82.0 | 82.0 | 36.5 | 53.0 | 95.0 | 71.5 | 39.0 | 未完了 | 90.0 | 未完了 |
| baseline（候補なし） | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 未完了 | 100.0 | 未完了 |

## 総合点（従来、平均 / 100）

| 候補 | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Superpowers | 98.0 | 95.3 | 77.2 | 81.3 | 96.2 | 95.3 | 89.6 | 未完了 | 91.3 | 未完了 |
| Feature Dev | 97.5 | 96.2 | 89.0 | 86.8 | 94.2 | 90.4 | 96.5 | 未完了 | 91.9 | 未完了 |
| Compound Engineering | 70.0 | 87.2 | 85.2 | 94.5 | 90.5 | 91.2 | 92.0 | 未完了 | 88.2 | 未完了 |
| gstack | 85.1 | 84.6 | 81.2 | 50.5 | 96.2 | 88.0 | 81.2 | 未完了 | 90.6 | 未完了 |
| baseline（候補なし） | 99.3 | 97.1 | 91 | 82.0 | 100.0 | 100.0 | 93.8 | 未完了 | 100.0 | 未完了 |

## シナリオごとの結論

### W1 小さな変更

- 品質: 最高は Superpowers・Feature Dev・gstack・baseline（候補なし）（100.0 点）。これと差なし（差がばらつき以下）: Superpowers（100.0）、Feature Dev（100.0）、gstack（100.0）、baseline（候補なし）（100.0）。差あり: Compound Engineering（94.3、−5.7）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.1 倍・時間 1.0 倍）、Feature Dev（費用 1.1 倍・時間 1.0 倍）、baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは gstack 82.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: Superpowers・Feature Dev・gstack・baseline（候補なし））。
- 詳細: [W1/report.md](W1/report.md) の「2 本立ての点数」

- 参考（本表に含めない）: Feature Dev の補足の再試行（新文言 2 回）は品質 100.0・効率 100.0・総合点 88.4。

### W2 仕様が明確な機能追加

- 品質: 最高は Compound Engineering（99.2 点）。これと差なし（差がばらつき以下）: Superpowers（94.2）、Compound Engineering（99.2）。差あり: Feature Dev（96.9、−2.3）、gstack（97.3、−1.9）、baseline（候補なし）（96.2、−3.0）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 63.5。
- 順位の入れ替わり: あり（従来の総合点の 1 位は baseline（候補なし）、品質の 1 位は Compound Engineering）。ただし品質の差 3.0 点は、この W の同じ候補の 2 回の差の最大 5.4 点以下で、1 回しか試行していない側のばらつきは測れていないため、確定的な差とは言えない。
- 詳細: [W2/report.md](W2/report.md) の「2 本立ての点数」

- 参考（本表に含めない）: Feature Dev の補足の再試行（新文言 2 回）は品質 98.3・効率 100.0・総合点 93.4。

### W3 曖昧な要望から要件を固める

- 品質: 最高は Feature Dev・baseline（候補なし）（89.4 点）。これと差なし（差がばらつき以下）: Feature Dev（89.4）、Compound Engineering（82.7）、gstack（80.9）、baseline（候補なし）（89.4）。差あり: Superpowers（73.2、−16.2）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 92.0、Feature Dev 84.0、gstack 36.5。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: Feature Dev・baseline（候補なし））。
- 詳細: [W3/report.md](W3/report.md) の「2 本立ての点数」

### W4 既存コードを横断する大きな変更

- 品質: 最高は Compound Engineering（94.5 点）。これと差なし（差がばらつき以下）: Compound Engineering（94.5）、gstack（50.5）。差あり: Superpowers（81.3、−13.2）、Feature Dev（86.8、−7.7）、baseline（候補なし）（82.0、−12.5）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Compound Engineering（費用 3.9 倍・時間 2.2 倍）で効率 74.0 点。ほかは gstack 53.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 Compound Engineering は、品質でも 1 位（同点を含む: Compound Engineering）。
- 詳細: [W4/report.md](W4/report.md) の「2 本立ての点数」

### W5 バグ修正

- 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは Superpowers（費用 1.4 倍・時間 1.3 倍）、Feature Dev（費用 1.7 倍・時間 1.6 倍）、baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは gstack 95.0、Compound Engineering 74.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: Superpowers・Feature Dev・Compound Engineering・gstack・baseline（候補なし））。
- 詳細: [W5/report.md](W5/report.md) の「2 本立ての点数」

### W6 UI 実装からブラウザ検証・PR 作成まで

- 品質: 最高は baseline（候補なし）（100.0 点）。これと差なし（差がばらつき以下）: Compound Engineering（99.7）、baseline（候補なし）（100.0）。差あり: Superpowers（98.2、−1.8）、Feature Dev（98.2、−1.8）、gstack（99.1、−0.9）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Compound Engineering 95.0。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: baseline（候補なし））。
- 詳細: [W6/report.md](W6/report.md) の「2 本立ての点数」

### W7 続けて行う作業での学習効果

- 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.0 点は、同じ候補の 2 回の差の最大 0 点以下）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Superpowers 97.0、Feature Dev 80.0、gstack 39.0、Compound Engineering 36.5。
- 順位の入れ替わり: なし（従来の総合点の 1 位 Feature Dev は、品質でも 1 位（同点を含む: Superpowers・Feature Dev・Compound Engineering・gstack・baseline（候補なし））。
- 詳細: [W7/report.md](W7/report.md) の「2 本立ての点数」

### W8 人の介入なしでの自律実行

未完了（結果が main に入ったら下の手順で再生成する）。

### W9 レビューで不具合を見つける

- 品質: 全候補で品質に差なし（最高 100.0 点、最低との差 0.6 点は、同じ候補の 2 回の差の最大 1.2 点以下）。
- 効率（最高品質と差がない候補の中。倍率は baseline 比）: 最も安く速いのは baseline（候補なし）（費用 1.0 倍・時間 1.0 倍）で効率 100.0 点。ほかは Feature Dev 92.0、Superpowers 90.0、gstack 90.0、Compound Engineering 74.5。
- 順位の入れ替わり: なし（従来の総合点の 1 位 baseline（候補なし） は、品質でも 1 位（同点を含む: Superpowers・baseline（候補なし））。
- 詳細: [W9/report.md](W9/report.md) の「2 本立ての点数」

### W10 仕様に書かれていない落とし穴がある機能追加

未完了（結果が main に入ったら下の手順で再生成する）。

## 判断の記録

- 費用・時間の基準は各 W の baseline（1 回のみ。2 回以上あれば平均）。時間は壁時計の時間（elapsed_seconds）で、従来の採点と同じ。
- W3 の費用は候補のセッションの費用だけで、回答役（answer_w3.py）の費用は含めない（質問を効率から引かない方針に合わせるため）。
- W1 は介入の仕組み（定型の「お任せします」で続けさせる）を導入する前に実施したため、効率は 費用 60 + 時間 40 で計算した。W1 の質問回数は記録が無いため「—」。
- 「品質に差なし」の判定: 最高品質の候補との差が、両者それぞれの 2 回の差の大きい方以下なら差なし。baseline は 1 回だけなので、ばらつきは相手の候補の値を使う。
- W1・W2 の Feature Dev 補足の再試行（新文言）は参考値として各 report の別表に出し、本表の平均には混ぜない。
- W7 は W7b の費用・時間で効率を計算する（W7a 比は参考値）。W4・W6〜W8 の品質の内訳キーは採点スクリプトの作成時に `two_axis.py` の QUALITY に合わせるか、scores.json に `two_axis_quality` を書く。

## 更新のしかた

W4 以降の結果（`docs/poc/results/workflow/<W>/scores.json`）が main に入ったら、次を実行する。

```bash
python3 scripts/poc/two_axis.py
```

- 記録のある全 W の `<W>/two_axis.json` と、この `summary.md`・`summary.html` を作り直す。結果の無い W は「未完了」と表示する。
- 各 W の report.md / report.html の「2 本立ての点数」の節は、`report_w*.py` が `two_axis.md_section()` / `html_section()` を呼んで足す（W4 以降の report スクリプトでも同じように呼ぶ）。
- scores.json の品質の内訳のキーが `two_axis.py` の `QUALITY` と違う場合は、各試行に `"two_axis_quality": {"<内訳名>": [得点, 満点]}` を書く。効率には各試行の `facts.cost_usd`・`facts.elapsed_seconds`・`facts.interventions`（あれば `facts.questions`）を使う。

