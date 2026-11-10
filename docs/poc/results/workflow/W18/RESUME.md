# W18 の引き継ぎメモ（試行を別アカウントの担当に引き継ぐ）

2026-11-10 07:05 UTC。このアカウントの 7 日間の使用量の上限が近いため、W18 の試行は別アカウントの担当が行う（ユーザー判断、コーディネーター経由）。
準備（設計・正解データ・採点・試行前の確認）はこのブランチ `agent/poc-w18` で終わっている。**試行はまだ 1 本も行っていない。**

## まず読むもの

- 設計書: [`docs/poc/tasks/wf-W18-design.md`](../../../tasks/wf-W18-design.md)（§9 に試行前の確認の結果）
- 採点手順: [`docs/poc/answer-key/W18/grading.md`](../../../answer-key/W18/grading.md)（試行中は候補に見せない。作業用コピーには入れない）
- 手順の表: [`docs/poc/tasks/wf-procedures.md`](../../../tasks/wf-procedures.md) の「W18 の決まり」
- 全体の決まり（判断の経路・削除の運用・ask に当たる操作の回避・PR）: コーディネーターのブランチの `docs/poc/results/workflow/RESUME.md`

## 承認済みの内容（コーディネーター、2026-11-10）

- 6 回の機能の順番と依頼文、隠れ要件、配点（品質 100 = 各回の受け入れ 25 + 最終の全機能 20 + 後退の少なさ 10 + 引き継ぎ 25 + ブラインドレビュー 10 + テストの強さ 10）。
- **引き継ぎは 3 課題**（h1 副管理者、h2 使用停止・廃棄で予約が残る不具合、h3 状態「修理中」）。25 点を 3 つで分ける（各 25/3 = 通過率 × 20/3 + 後退の無さ × 5/3）。h3 は試行前の確認で差が小さかったために足した。
- 試行前の確認では、参照と最短の引き継ぎの差が小さかった（25.0 対 22.6。最短でも固定のエージェントがほぼ直せた）。**これを結果の制約として report に書く**。設計は変えずに進める。
- コードの指標は、機能の通過率と並べて、同じくらいの機能の系列どうしで読む（最短の系列は小さいため、複雑さ・重複が参照と同じか低かった）。
- **Claude Code の版は固定しない。試行ごとに記録し**（`score_w18.py` が各ステップの init の `claude_code_version` を残す）、report の制約に書く。準備の確認は 2.1.322 で行った（W12・W13 は 2.1.321）。
- 費用の見込み $370〜420、2 系列並列で 15〜20 時間。費用の上限は付けない。1 回（1 機能）が $30 を超えたらコーディネーターに報告。

## 出どころ（写したもの）

| ファイル | 出どころ |
|---|---|
| `docs/poc/answer-key/W18/base.patch` | W12 の `base.patch`（`origin/agent/poc-w12` 25b0c25〜ddde46f。sha256 a70273846daa…） |
| `docs/poc/answer-key/W18/persona-r1.md` | W12 の `persona.md`（`origin/agent/poc-w12` ddde46f） |
| `docs/poc/answer-key/W18/persona-r2.md`・`f2.cjs` | W13 の `persona.md`・`tests.cjs`（`origin/agent/poc-w13` a0617be）に K09 を足した |
| `f1.cjs`・`fake-notify.cjs`・`fake-clock.cjs` | W12 の `hidden.cjs`・`public.cjs`・`fake-notify.cjs`・`fake-clock.cjs` |
| `reference-r1.patch`・`-r2.patch`・`shortest-r1.patch`・`-r2.patch` | W12 の `reference.patch`・`shortest.patch`、W13 の `reference-v1.patch`（マイグレーションを 6 番にし K09 を足した）・`shortest-v1.patch` |
| `scripts/poc/ask-po` | `origin/agent/poc-w13` a0617be（W12 のもの） |
| `scripts/poc/answer_w18.py`・`adapt_w18.py`・`blind_w18.py` | W13 の `answer_w13.py`・`adapt_w13.py`・`blind_w13.py` を写して W18 用に変えた |
| `docs/poc/standards/generic-dev-standard.md` | `origin/claude/intelligent-mendel-hyx7aa` 8df5983（文面そのまま） |

`run-trial.sh` は main の版に W18 の分岐だけを足した（W12・W13 の分岐は入っていない）。**W12・W13 が main にマージされていたら、main を取り込んで衝突を解消してから始める**（W18 の分岐はすべて `W18` を条件にしている。`ask-po` の配置・質問の受け方・依頼者役の起動は W12・W13 と同じ形なので、取り込み後に重複しないか確かめる）。

## 新しいコンテナで最初にすること

```bash
bash scripts/poc/fetch-plugins.sh                 # .poc-cache（Git 管理外）
(cd poc-app && npm ci)                            # 作業用コピーは poc-app を node_modules ごと写す
# コードの指標の道具は grade_w18.py が初回に /tmp/poc-w18-metrics へ npm ci する（W18_METRICS_TOOLS で場所を変えられる）
# 試行前の確認をやり直すとき（試行には不要。費用はかからない）:
scripts/poc/w18_series.sh reference 1 && scripts/poc/w18_series.sh shortest 1
```

## 試行の手順

前半（系列 1）と後半（系列 2）で条件の順番を逆にする。並列は 2 系列まで。系列の中の回の順番は変えない。

```bash
# 1 系列 = 6 回（各回の後に採点。アダプターを確かめて確定してから採点し直す）
for r in 1 2 3 4 5 6; do
  scripts/poc/run-trial.sh W18r$r <候補> <系列>
  python3 scripts/poc/grade_w18.py W18r$r-<候補>-<系列>          # 初回はアダプターの下書きを作る（*.draft.json）
  # results/workflow/W18/adapters/<候補>-<系列>-r$r.draft.json をコードと見比べ、<候補>-<系列>-r$r.json として確定 → 採点し直す
done
# 引き継ぎ 3 つ（第 6 回の終わりから独立に。プラグインなしの固定のエージェント）
for h in h1 h2 h3; do
  scripts/poc/run-trial.sh W18$h <候補> <系列>
  python3 scripts/poc/grade_w18.py W18$h-<候補>-<系列> --no-mutation  # アダプターは <候補>-<系列>-$h.json（副管理者の項目名は試行ごとに違う）
done
# 全系列の後
python3 scripts/poc/blind_w18.py prepare /tmp/w18-blind <系列ID>...   # 第 6 回の終わりのコード
python3 scripts/poc/blind_w18.py review /tmp/w18-blind && python3 scripts/poc/blind_w18.py collect
python3 scripts/poc/score_w18.py --all
python3 scripts/poc/report_w18.py tables && python3 scripts/poc/report_w18.py charts /tmp/w18-charts.html
```

- 候補は `superpowers`・`feature-dev`・`gstack`・`compound-engineering`・`baseline`、系列は `1`・`2`。
- 第 2 回以降は第 1 回の作業用コピー（`/tmp/poc-trials/W18r1-<候補>-<系列>`）と HOME を引き継ぐ。**作業用コピーの片付け（`grade.py ... --cleanup-only`）は、その系列の引き継ぎ 3 つの採点まで済んでから**。
- 介入は既定で最大 2 回（`POC_MAX_NUDGES` を渡さなくてよい）。`POC_MAX_TRIAL_USD` は渡さない。

## 気をつける点（準備中に分かったこと）

- **`docs/poc/results/workflow/raw/` は `.gitignore` に入っている**（コミットされない）。採点の結果（`results/workflow/W18/*.json`・`adapters/`）はコミットする。コンテナが入れ替わると raw と `/tmp/poc-trials` が消えるので、系列の途中で消えたら第 1 回からやり直しになる。系列ごとに採点まで済ませる。
- 準備中にコンテナが 1 回入れ替わり、裏で動かしていた採点・引き継ぎが止まった（`/tmp/poc-trials` は残っていた）。止まった試行は同じ ID でやり直せる（第 2〜6 回は同じ名前の作業ブランチを作り直す）。
- アダプターの下書き（`adapt_w18.py`）は候補のコードを標準入力で `claude -p` に渡す（コードが大きいと引数に入らないため）。1 回 $0.07〜0.25。
- 引き継ぎの h1 では、固定のエージェントが副管理者の項目名を自分で決める（確認では `deputyManagerId` と `subManagerId`）。h1 のアダプターは試行ごとに下書きを作って確かめる。
- ミューテーションは 1 回 10〜30 分かかる（各回の採点で毎回行う。引き継ぎは `--no-mutation`）。2 系列並列の試行と同時に採点するとマシンが重くなる。
- 試行前の確認の結果は `results/workflow/W18/W18r*-reference-1.json`・`-shortest-1.json`・`W18h*-*.json`・`series/`。report では「確認用」として本表と分けて示す（`report_w18.py` は `reference`・`shortest` を確認用の行にする）。
- PR は docs/github-writing.md に従い draft で作り、全系列の採点と report がそろったら Ready。自動マージの条件はコーディネーターの RESUME.md のとおり。
