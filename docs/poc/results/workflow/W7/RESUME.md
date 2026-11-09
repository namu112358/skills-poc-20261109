# W7 の引き継ぎメモ（2026-11-09 14:45 UTC 時点）

> **2026-11-09 15:30 UTC 追記（引き継ぎ先）**: 下の「次にやること」はすべて完了した。対照の Feature Dev・Superpowers・gstack を実行・採点し、
> report.md・report.html・notes.json・PLAN.md §6 を更新した。結果は [report.md](report.md)。このメモは経緯の記録として残す。

ユーザーの指示（秘書経由）で、W7 は別アカウントに引き継ぐ。PR #25 は開いたまま、自動マージは有効にしていない。

## 終わった試行（採点済み。`W7/<試行ID>.json`、組ごとの点数は `W7/scores.json`、2 本立ては `W7/two_axis.json`）

| 組（W7a → W7b） | W7a: 指摘前の落とし穴 | W7b: 指摘前の落とし穴 | 受入 W7a / W7b | 費用 W7a → W7b | 時間 W7a → W7b | 介入 W7a → W7b | 品質 / 効率 / 総合 |
|---|---|---|---|---|---|---|---|
| baseline #1 | P1 ✅ P2 ✅ | P1 ✅ P2 ✅ | 16/16・14/14 | $0.36 → $0.36 | 101 → 96 秒 | 0 → 0 | 100 / 100 / 93.2 |
| Superpowers #1 | ✅ ✅ | ✅ ✅ | 16/16・14/14 | $0.69 → $0.63 | 172 → 152 | 0 → 0 | 100 / 100 / 94.2 |
| Superpowers #2 | ✅ ✅ | ✅ ✅ | 16/16・14/14 | $0.57 → $0.69 | 167 → 318 | 0 → 0 | 100 / 88 / 85.0 |
| Feature Dev #1 | ✅ ❌（指摘 1 回で直した） | ✅ ✅ | 16/16・14/14 | $1.52 → $1.24 | 263 → 157 | 1 → 0 | 100 / 80 / 98.5 |
| Feature Dev #2 | ✅ ✅ | ✅ ✅ | 16/16・14/14 | $1.32 → $1.36 | 237 → 207 | 0 → 0 | 100 / 74 / 94.4 |
| Compound Engineering #1 | ✅ ❌（指摘 1 回） | ✅ ✅ | 16/16・14/14 | $5.35 → $3.62 | 688 → 551 | 1 → 0 | 100 / 44 / 95.5 |
| Compound Engineering #2 | ✅ ❌（指摘 1 回） | ✅ ✅ | 16/16・14/14 | $4.58 → 約 $7.73（※） | 699 → 880 | 1 → 0 | 100 / 29 / 88.6 |
| gstack #1 | ✅ ✅ | ✅ ✅ | 16/16・14/14 | $1.81 → $2.37 | 228 → 308 | 0 → 0 | 100 / 53 / 87.2 |
| gstack #2 | ✅ ✅ | ✅ ✅ | 16/16・14/14 | $3.06 → $4.59 | 506 → 586 | 0 → 1（/review が足したテストを未コミットで確認待ち） | 100 / 19 / 75.1 |
| 対照 Compound Engineering（W7b-compound-engineering-11） | — | ✅ ✅ | —・14/14 | — → $3.96 | — → 617 | — → 0 | （対照。組の点数には入れない） |

※ Compound Engineering #2 の W7b は、watch の見積もりが上限（$7.67）に達し、`/ce-work` の途中で止めた（`budget_stopped`: step2 est=$7.7293）。`/ce-code-review` は実行されていない。止めた時点で実装とコミットは済んでおり、受け入れ 14/14・落とし穴 2 件とも回避。費用は result の $2.36 ではなく見積額で数える（`score_w7.py` の `cost()`）。

P1 = 日時は UTC で保存し JST で表示する、P2 = 新しい API は独自のエラー型（`AppError`・`withApi`）で返す。

## 止めた試行・やり直し対象（採点に使わない）

- **W7b-feature-dev-11**（対照 Feature Dev）: 実行の途中で停止。`raw/W7b-feature-dev-11/` の途中の記録は使わない。
- 前回（06:05 UTC）止めた W7a-compound-engineering-1・-2 は、13:05 UTC 以降に W7a からやり直して完了済み（上の表）。

## 次にやること（順番）

1. 対照の残り（1 本ずつ）: Feature Dev → Superpowers → gstack。
   `POC_W7_CONTROL=1 scripts/poc/w7_chain.sh <候補> 11 7.67`（W7b だけを、新しい作業用コピー = `base.patch` + `reference-W7a.patch` と新しい HOME で実行し、採点する）
   - baseline の対照・baseline の 2 回目・Haiku での比較は、ユーザー未承認のため行わない。
2. `python3 scripts/poc/score_w7.py` → `python3 scripts/poc/two_axis.py W7`（summary.md / summary.html も更新される）
3. `docs/poc/results/workflow/W7/notes.json` を書く（`report_w7.py` が読むキー: `date`・`model`・`claude_code`・`summary`・`task_html`・`observations`・`memory`・`trials`（キーは組の名前 `<候補>-<回>`）・`scoring_html`・`limitations`・`decisions`・`isolation`・`next`）。結論は 2 本立て（品質で差があるか／同じ品質ならどれだけ安く速いか）と、「2 段階で言えること・言えないこと」「5 段階に延ばす価値があるか」の見立てを含める。対照の結果（`scores.json` の `controls`）も所見に書く（`report_w7.py` はまだ対照の表を出さないので、必要なら足す）。
4. `python3 scripts/poc/report_w7.py` で report.html・report.md を生成。
5. PLAN.md §6 の W7 の行を「完了（日付。4 候補 × 2 回 + baseline）」、結果欄を `[report.md](results/workflow/W7/report.md)・[report.html](results/workflow/W7/report.html)` に更新。
6. main を取り込み（`git fetch origin main` → `git merge --no-edit origin/main`）、W1〜W6 の手順の既定が保たれていることを確かめ、PR #25 の本文を更新し、最後の push の直後に条件（poc-app/・permissions・.github/・.mcp.json・CLAUDE.md・データ削除に触れない、scripts/poc/ は後方互換）を確かめて自動マージ（SQUASH）を有効にする。
7. 作業用コピーの片付け: `python3 scripts/poc/grade.py W7a W7a-<候補>-<回> --cleanup-only`（W7b は W7a の作業用コピーを使うので、W7a の ID で片付ける）。対照は `grade.py W7b W7b-<候補>-11 --cleanup-only`。

## 使っている方式

- 初期状態: v2（`docs/poc/answer-key/W7/base.patch`。決まりへの移行の途中で、既存のコメント機能・タスクの API は古い書き方のまま、新しい決まりは `src/lib/errors.ts`・`src/lib/datetime.ts`・`withApi`・`currentApiUser`・`GET /api/me` とテストにだけ現れる）。v1 のパイロットは `W7/pilot-v1/`。
- 課題文: `docs/poc/tasks/wf-W7a.md`（完了報告）・`wf-W7b.md`（作業記録）。末尾は新文言（`raw/<ID>/task-suffix` = new）。
- 費用の上限: `POC_BUDGET_MODE=watch`（`--max-budget-usd` は渡さない。`raw/<ID>/budget-mode`）。全候補・W7a・W7b それぞれ $7.67 = v2 baseline の W7a 実額 $0.3566 ÷ W1 baseline $0.15 × W1 の候補平均 $0.6457 × 5（上限 $10 以内）。
- 介入: `POC_MAX_NUDGES=2`。落とし穴の判定（`scripts/poc/check_w7.py`）と定型の指摘は最大 2 回（`POC_MAX_FEEDBACK` の既定）。指摘の前の判定（`pitfalls-1.json`）を採点に使う。判定の時間は所要時間から除く。
- Claude Code の自動メモリは W7 の全試行で止める（`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。`raw/<ID>/auto-memory-disabled`）。
- 許可リスト: 現行（W6 の開発サーバーの許可は使わない）。モデル claude-sonnet-5-5、Claude Code 2.1.319。
- W7a → W7b の引き継ぎ: `run-trial.sh W7b <候補> <回>` は、同じ候補・同じ回の W7a の作業用コピー（`/tmp/poc-trials/W7a-<候補>-<回>/app`。W7a の変更を含む）と専用 HOME（同 `home/`）をそのまま使い、新しいセッションで始める。W7a の終了時点を W7b の baseline コミットにし、作業ブランチ `poc/wf/<候補>/W7b/<回>` を切る（`raw/<W7b の ID>/continued-from`）。W7a は W7b の前に採点する。W7c 以降も同じ仕組みで前の段階から続けられる（`docs/poc/answer-key/W7/grading.md` の「段階を増やすとき」）。Compound Engineering は W7a の指摘のやり取りの後に `/ce-compound` を行う。
- 採点: `scripts/poc/grade_w7.py`（試行ごと）→ `score_w7.py`（組ごと、品質・効率・総合、学習の記録 `learned`・`repeated`・`memory_used`、対照 `controls`）→ `two_axis.py`。手順は `docs/poc/answer-key/W7/grading.md`。
- 補助のスクリプト: `scripts/poc/w7_chain.sh`（1 組の実行と採点）。

## 判断の記録（レポートに書くこと）

- v1 の初期状態（既存のコメント機能が決まりに沿っていた）では、baseline が W7a・W7b とも既存のコードを真似るだけで 2 件とも回避し、学習の効果を測れなかったため、試行を始める前に v2 に改めた。パイロットの費用 $0.37 + $0.40。
- v2 でも baseline は最初に `api.ts`・`errors.ts`・`datetime.ts` を読み、2 件とも回避した。これ以上隠すと「作業中に気づける形」を満たさなくなるため、v2 のまま実施した。
- W6 の許可リストの変更は main に入っていなかったため、W7 は現行の許可リストで統一した。
- Claude Code の自動メモリは候補の記憶の仕組みではないため、全候補で止めた。
- 秘書経由のユーザーの要望で、段階を W7c 以降に増やせる形、前の段階の知見を読んだか・同じ間違いの繰り返し・対照の記録を足した。対照は W7a を引き継がない W7b（`base.patch` + `reference-W7a.patch`）。
- コーディネーターの指示で、品質・効率の 2 本立てを主表示にした（`two_axis.py`。効率の基準は W7b baseline の $0.3638・96 秒）。
- watch の上限で止めたステップの費用は result に入らないため、見積額で数えた（Compound Engineering #2 の W7b）。
- 1 回目の中断（06:05 UTC、usage の上限）で、W7a の途中だった Compound Engineering #1・#2 を止め、再開後に W7a からやり直した。2 回目の中断（14:45 UTC、別アカウントへの引き継ぎ）で、対照 Feature Dev を止めた。
- Feature Dev #2 の W7a の `isolation_suspects` 1 件は、作業用コピーの `src/app` から `../../tests` を読んだもの（自分の作業用コピーの中）で、他の試行への参照ではない。W7b が W7a の作業用コピー・HOME を読むのは自分の試行の一部として扱った（`grade.py` は `continued-from` の ID を他の試行に数えない）。ほかの試行の `isolation_suspects` は 0、`answer_key_access` は全試行で無し。

## ここまでで分かったこと（所見の材料）

- 品質（W7b の落とし穴 + 受け入れ）は全組 100 点で、候補の間に差は無い。
- W7a で P2 を外したのは Feature Dev #1・Compound Engineering #1・#2 の 3 組。3 組とも W7b では指摘の前に避けた（同じ間違いの繰り返し 0 件）。
- Compound Engineering は 2 回とも `/ce-compound` で `docs/solutions/conventions/new-api-routes-use-*.md` に学んだことを残し、W7b の最初の調査で読んだ（`memory_used`）。ただし対照（W7a を引き継がず、記憶なし）でも 2 件とも避けたため、W7b での回避は「W7a の直ったコード（手本）が残っていること」でも説明がつく。記憶の仕組みの寄与は、この 2 段階の設計では切り分けられていない。
- Feature Dev は記憶の仕組みを持たないが、#1 で W7a の指摘の後、W7b では避けた（直った W7a のコードを手本にしたと考えられる）。
- gstack は #2 で学習データ（`~/.gstack/projects/app/learnings.jsonl`）を 1 件残したが、内容は gstack 自身の QA の道具の使い方で、プロジェクトの決まりではない（W7a で指摘を受けていないため、学ぶ機会が無かった）。
- 効率は、同じ品質の中で baseline・Superpowers が最も安く速く、Compound Engineering・gstack が W7b でも高い（W7b の費用は baseline の 6〜21 倍）。
- 2 段階で言えないこと: 記憶の仕組みの寄与（対照でも避けられる）、段階を重ねたときの費用の下がり方。5 段階に延ばす価値の見立て: 後の段階の課題が「前の段階のコードを手本にできない」形（別の層・別の画面で同じ決まりが要る、決まりの例外を含む）であれば、記憶の仕組みの差が出る見込みがある。今の課題のまま延ばしても、コードの手本で避けられるため差は出にくい。

## 未解決の点

- 対照の Feature Dev・Superpowers・gstack が未実施（上の「次にやること」1）。
- report.md・report.html、notes.json、PLAN.md §6 の更新、PR #25 の本文の更新と自動マージが未実施。
- `report_w7.py` は対照の表を出さない（`scores.json` の `controls` を読む節を足すか、所見に書く）。
- 作業用コピー（`/tmp/poc-trials/W7a-*`、`W7b-compound-engineering-11`）は未片付け。コンテナが作り直されると消えるが、採点は済んでいるので再実行は不要。
