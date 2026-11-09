# W9（レビューで不具合を見つける）— 再開メモ

> **2026-11-09 追記（引き継ぎ後）: W9 は完了した。** 残りの 4 試行（Feature Dev #2 のやり直し・CE #2・Superpowers #2・gstack #2）を新しいコンテナで実行し、ブラインド判定・採点・レポート（`report.md`・`report.html`）・PLAN.md §6 の更新まで行った。以下は引き継ぎ時点の記録として残す。

2026-11-09 14:15 ごろ、コーディネーターの指示（ユーザー指示: 別アカウントのセッションに引き継ぐ）で作業を止めた。ブランチは `agent/poc-w9`。PR はまだ作っていない（自動マージもなし）。

## 終わったこと

- 準備（コミット済み）
  - レビュー対象の差分 `docs/poc/answer-key/W9/review.patch`（検索・削除・一括ステータス変更・期限切れ一覧・同時編集の検知。9 ファイル +254 / −18。型チェック・単体テスト 26 件・ビルドは通る）。不具合 10 件（B1〜B10）とおとり 5 件（D1〜D5）を含む。
  - 正解リスト・配点・突き合わせの基準・具体性・ブラインド判定の手順: `docs/poc/answer-key/W9/grading.md`（試行前に固定）。
  - 課題文 `docs/poc/tasks/wf-W9.md`（PR の説明を含む。指摘は `REVIEW.md` に書いてコミット、コードは直さない）。
  - `scripts/poc/run-trial.sh` の W9 分岐（W9 のときだけ、作業ブランチの上にパッチを当てて PR の説明をメッセージにしたコミットを作る。`baseline-commit` はそのコミット。W9 の手順・介入の定型文・`REVIEW.md` の完了条件）。W1〜W8 の手順は変えていない。
  - `scripts/poc/grade.py`: 隠しの E2E（`acceptance.cjs`）が無い W では E2E を実行しない（後方互換）。
  - 採点スクリプト: `grade_w9.py`（REVIEW.md の本文などを試行の JSON に足す）、`blind_w9.py`（prepare / collect）、`score_w9.py`、`report_w9.py`（report_w6.py と同じ構成。`W9/notes.json` が必要。未実行）。
  - `scripts/poc/two_axis.py`: `SCENARIOS`・`TITLES`・`QUALITY` に W9（recall 40 / precision 25 / specificity 20）と W10（acceptance 25 / hidden 40 / test_strength 20 / review 15）を追加。
  - `docs/poc/tasks/wf-procedures.md` の W9 の行と「W9 の決まり」。`docs/poc/PLAN.md` の §3.2・§4.3（W9・W10 は重みを変えず、判定会で扱いを決める注記）・§4.4・§5.1（シナリオ表・手順の表・試行数 90 回）・§6（W9「実施中」、W10「未着手」）・§8。
- 試行（採点用の記録 `W9/W9-<候補>-<回>.json` はコミット済み。作業用コピーは片付け済み。ブラインド判定は未実施）

| 試行 | 費用 | 時間 | 介入 | 上限で停止 | isolation_suspects |
|---|---:|---:|---:|---|---:|
| W9-baseline-1 | $0.1755 | 60 秒 | 0 | なし | 0 |
| W9-gstack-1 | $0.3824 | 70 秒 | 0 | なし | 0 |
| W9-superpowers-1 | $0.4386 | 111 秒 | 0 | なし | 0 |
| W9-compound-engineering-1 | $0.5177 | 111 秒 | 0 | なし | 0 |
| W9-feature-dev-1 | $0.3239 | 116 秒 | 0 | なし | 0 |

すべて `REVIEW.md` をコミットし、コードは変えていない。`raw/<ID>/task-suffix` は new、`budget-mode` は watch を確認済み（raw/ は Git 管理外なので、このコンテナが消えると raw は失われる。点数に必要な事実は試行の JSON に入っている）。

## 止めた試行（やり直し対象）

- **W9-feature-dev-2**: 開始直後（14:12:59 開始、約 1 分後）に止めた。採点していない。`raw/W9-feature-dev-2` と作業用コピー `/tmp/poc-trials/W9-feature-dev-2` が残っている（diff.patch が無いため `grade.py --cleanup-only` では消えない。コンテナが入れ替われば消える）。最初からやり直す。

## 決めたこと（判断の記録。report.md の「判断の記録」に転記する）

- **費用の上限**: baseline を暫定上限 $10 で先に実行。規模係数 = W9 baseline の実額 $0.1755 ÷ W1 baseline $0.15 = 1.17。上限 = 1.17 × W1 の候補平均 × 5（最大 $10）で、Superpowers $0.99、Feature Dev $1.00、gstack $2.68、Compound Engineering $10（計算値 $10.44）。ここまでに上限で止まった試行は無い。
- **介入**: 全候補で `POC_MAX_NUDGES=2`（W2 以降の決まりと同じ）。ここまで介入 0 回。
- **課題文の末尾・費用の守り方**: 既定（新文言・watch）。W9 はシナリオ名で自動的にそうなる。
- **入口**: gstack `/review <課題>`、Compound Engineering `/ce-code-review <課題>`、Superpowers `/superpowers:requesting-code-review <課題>`、Feature Dev はレビュー用コマンドが無いため「Feature Dev の code-reviewer エージェント（feature-dev:code-reviewer）でこの差分をレビューしてください。」+ 課題、baseline は課題だけ。
- **レビュー対象の置き方**: 作業用コピーの `master`（初期状態）から作業ブランチを切り、その上にレビュー対象のコミットを 1 つ積む。リモート（origin）は置かない（W1〜W8 と同じ。gstack の `/review` は `origin/<base>` が無くても `master...HEAD` で差分を取れた）。課題文に `git diff master...HEAD` を明記した。
- **許可リスト**: 変更していない。W9 は SCN_NUM ≥ 6 なので W6 以降の許可リスト（開発サーバー・ブラウザを含む）がそのまま効く。
- **配点**: 総合点 = 再現率 40 + 適合率 25 + 具体性 20 + 費用 15。2 本立ての品質 = 前の 3 つ（85 点）を 100 点に正規化。
- **実行順**: baseline → gstack#1 → Superpowers#1 → CE#1 → Feature Dev#1 → Feature Dev#2 → CE#2 → Superpowers#2 → gstack#2（1 本ずつ。後半は前半の逆順）。

## 次にやること

1. `bash scripts/poc/fetch-plugins.sh` と `poc-app` の `npm ci`（新しいコンテナの場合）。
2. 残りの試行を 1 本ずつ: Feature Dev#2（やり直し）→ CE#2 → Superpowers#2 → gstack#2。各試行は `POC_MAX_TRIAL_USD=<上の上限> POC_MAX_NUDGES=2 scripts/poc/run-trial.sh W9 <候補> <回>` → `python3 scripts/poc/grade_w9.py W9-<候補>-<回>` → `python3 scripts/poc/grade.py W9 W9-<候補>-<回> --cleanup-only`。前に使ったスクリプト（スクラッチ）はコンテナと一緒に消えるので、同じ内容をスクリプトファイルにして実行する（rm -rf は使わない）。
3. 全 9 試行がそろったら `python3 scripts/poc/blind_w9.py prepare <スクラッチ>` → 判定者 2 名（独立した新しいサブエージェント、順番を変えて渡す）が `W9/blind/reviewer-1.json`・`reviewer-2.json` を書く → `blind_w9.py collect` → `score_w9.py`。
4. `W9/notes.json`（date・model・claude_code・summary・task_html・observations・trials・scoring_html・limitations・decisions・isolation・next。形式は `W6/notes.json` と同じ）を書いて `python3 scripts/poc/report_w9.py` → `python3 scripts/poc/two_axis.py`（summary を更新）。
5. PLAN.md §6 の W9 を「完了（日付。4 候補 × 2 回 + baseline）」にし、結果欄に report.md・report.html のリンク。main を取り込み（`git fetch origin main` → `git merge --no-edit origin/main`、衝突は両方残す）、two_axis.py を再実行してから PR（`.github/pull_request_template.md` と `docs/github-writing.md` に従う）→ 自動マージの条件確認 → 有効化。

## 未解決の点

- baseline が 60 秒・$0.18 で 10 件すべてに触れる指摘を書いた（ブラインド判定前の目視）。再現率は全員高い可能性があり、差は適合率・具体性に出るかもしれない。設計は試行前に固定したので変えない。結果の制約としてレポートに書く。
- 候補ごとの所要時間がどれも 1〜2 分と短い。gstack#1 は `/review` の手順（gstack の bin を使った準備）を始めたが、Review Army などの専門エージェントは起動せずに差分を読んで `REVIEW.md` を書いた。Compound Engineering#1 は `ce-code-review` の references を読み、general-purpose のサブエージェントを使った。各ツールが手順をどこまで踏んだか（省略の有無）は、レポートの所見で確かめて書く。
- `grade.py` の `skills_used` は、スラッシュコマンドで起動した Skill を数えない（Skill ツールの呼び出しだけを数える）ため、W9 では全試行で空になる。所見ではトランスクリプトから入口の手順が読み込まれたこと（参照ファイルの読み込み、gstack の bin の呼び出し、サブエージェントの種類）で確かめる。
