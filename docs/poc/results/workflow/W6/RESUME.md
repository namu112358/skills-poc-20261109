# W6 の再開メモ（2026-11-09 中断）

usage の上限に近いため、ユーザーの指示で途中で止めた。PR はまだ作っていない（自動マージも未設定）。

## 使っている方式

- 課題文: `docs/poc/tasks/wf-W6.md`、採点手順: `docs/poc/answer-key/W6/grading.md`（試行前に固定）
- 末尾の定型文: 新文言（`raw/<ID>/task-suffix` = `new`）
- 費用の上限: `POC_BUDGET_MODE=watch`、`POC_MAX_TRIAL_USD` は 規模係数 5.85（W6 baseline $0.8769 ÷ W1 baseline $0.15）× W1 の候補平均 × 5、最大 $10
  - Superpowers $4.96、Feature Dev $5.02、gstack $10、Compound Engineering $10（baseline は規模係数を決める前に暫定 $5 で実行。実額 $0.88）
- 介入: `POC_MAX_NUDGES=2`
- 実行: `POC_BUDGET_MODE=watch POC_MAX_TRIAL_USD=<上限> POC_MAX_NUDGES=2 scripts/poc/run-trial.sh W6 <候補> <回>` → `python3 scripts/poc/grade_w6.py W6-<候補>-<回>`

## 終わった試行（採点済み。`W6/<ID>.json`）

| 試行 | E2E | 証跡 | 費用 | 時間 |
|---|---|---|---|---|
| W6-baseline-1 | 16/16 | 15 | $0.88 | 409 秒 |
| W6-superpowers-1 | 16/16 | 15 | $1.41 | 500 秒 |
| W6-superpowers-2（やり直し） | 16/16 | 15 | $0.92 | 354 秒 |
| W6-feature-dev-1 | 16/16 | 15 | $2.12 | 445 秒 |
| W6-feature-dev-2 | 16/16 | 15 | $1.73 | 450 秒 |
| W6-gstack-1 | 16/16 | 15 | $2.27 | 717 秒 |
| W6-gstack-2 | 16/16 | 15 | $7.34 | 1375 秒 |
| W6-compound-engineering-1 | 16/16 | 15 | $2.61 | 618 秒 |

作業用コピーはすべて片付け済み。

## 止めた試行（やり直し対象）

- **W6-compound-engineering-2**: 許可リストの漏れを直した後のやり直しを、1 ステップ目（`/ce-work`）の途中で止めた。`raw/W6-compound-engineering-2/` は途中の記録、作業用コピー `/tmp/poc-trials/W6-compound-engineering-2/` が残っている（どちらも次の `run-trial.sh` が作り直す）。上限 $10 でやり直す。

## 除外した試行（`W6/excluded/`。点数には使わない）

- W6-superpowers-2・W6-compound-engineering-2 の 1 回目: 許可リストに `npm start` と `PORT=3100 npm run start` などの形が無く（私の書き漏れ）、サーバーを起動できずにブラウザ確認をしないまま終わった。漏れを足して（`run-trial.sh` の W6 以降の許可）やり直した。足す前に終わったほかの 7 本には、足した形の拒否は 0 件だったので、やり直していない。

## 次にやること

1. W6-compound-engineering-2 をやり直して採点する（並列は 1 本）。
2. PR の説明のブラインドレビュー: `python3 scripts/poc/blind_w6.py prepare <スクラッチ領域>` → 独立したサブエージェント 2 名に採点させて `W6/blind/reviewer-1.json`・`reviewer-2.json` に書く → `python3 scripts/poc/blind_w6.py collect`。
3. `W6/notes.json`（所見・判断の記録・制約・独立性）を書き、`python3 scripts/poc/score_w6.py` → `python3 scripts/poc/report_w6.py` → `python3 scripts/poc/two_axis.py`。
4. PLAN.md §6 の W6 の行を更新し、main を取り込んでから PR を作る（自動マージの条件はコーディネーターの指示どおり）。

## 判断の記録に書くこと（メモ）

- 子セッションの許可（W6 以降だけ）: サーバー起動（npm run dev/start、npm start、npx next dev/start、timeout 付き、PORT= 付き）、Playwright MCP・Next.js DevTools MCP、gstack の browse。gstack は `GSTACK_CHROMIUM_PATH=/opt/pw-browsers/chromium` で事前インストール済みの Chromium を使い、browse・/qa が動いた。
- Compound Engineering の `/ce-test-browser` は「ホスト組み込みのブラウザか agent-browser だけを使う」規則のため Playwright MCP を使わず、agent-browser の確認コマンドも承認が要って止まった（CE #1）。`/ce-commit-push-pr`・gstack の `/ship`（#1）はリモートが無く止まり、PR.md で代えた。gstack #2 の `/ship` はレビュー・カバレッジ確認まで進んだ。
- PR はローカル（PR.md）で完結させる方式を課題文で全候補に指示した。push・`gh` は許可リストに無い。
