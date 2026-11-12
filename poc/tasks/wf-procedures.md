# 候補ごとの手順（開発ワークフロー）

`poc/scripts/run-trial.sh` はこの表のとおりに、同じセッションを続けて（`--resume`）各ステップを実行する。
`<課題>` は `wf-<シナリオ>.md` の本文と定型回答（`wf-answers.md`）を連結したもの。

| シナリオ | baseline | Superpowers | Feature Dev | gstack | Compound Engineering |
|---|---|---|---|---|---|
| W1 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W2 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W3 | `<課題>` | `<課題>`（`brainstorming` の自動発火） | `/feature-dev:feature-dev <課題>`（確認質問のフェーズまで） | `/office-hours <課題>` → `/plan-ceo-review` | `/ce-brainstorm <課題>` |
| W4 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `/autoplan <課題>` → 「計画に沿って実装し、変更を git にコミットしてください。」→ `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W5 | `<課題>` | `<課題>`（`systematic-debugging` の自動発火） | `<課題>`（通常の指示） | `/qa <課題>` | `/ce-debug <課題>` |
| W6 | `<課題>` | `<課題>` → `/superpowers:finishing-a-development-branch` | `/feature-dev:feature-dev <課題>` → PR 作成の指示 | `<課題>` → `/qa` → `/ship` | `/ce-work <課題>` → `/ce-test-browser` → `/ce-commit-push-pr` |
| W7a | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` →（落とし穴の指摘の後）`/ce-compound` |
| W7b | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W7c〜W7e | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` →（落とし穴の指摘の後、最後の段階を除き）`/ce-compound` |
| W8 | `<課題>` | `/superpowers:writing-plans <課題>` → `/superpowers:subagent-driven-development` | `/feature-dev:feature-dev <課題>` | `/autoplan <課題>` → `/ship` | `/ce-brainstorm <課題>` → `/lfg` |
| W9 | `<課題>` | `/superpowers:requesting-code-review <課題>` | 「Feature Dev の code-reviewer エージェント（feature-dev:code-reviewer）でこの差分をレビューしてください。」+ `<課題>` | `/review <課題>` | `/ce-code-review <課題>` |
| W10 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W12 | `<課題>`（baseline-conventions も同じ） | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W13 | `<課題>` → `<変更依頼>` | `<課題>` → `<変更依頼>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` → `/feature-dev:feature-dev <変更依頼>` | `<課題>` → `/review` → `<変更依頼>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` → `/ce-plan <変更依頼>` → `/ce-work` → `/ce-code-review` |
| W14・W15 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |

U1（UI/UX 系ツールの組み合わせ）は候補が開発ワークフローではなく構成（`ui-none`・`ui-all`・`ui-a`・`ui-fd`・`ui-pm`）で、どの構成も `<課題>` を渡すだけ（Skill の自動発火）。詳細は [wf-U1-design.md](wf-U1-design.md)。

### W2 以降の共通の決まり

- 作業用コピーの `master`（初期状態）から作業ブランチ `poc/wf/<候補>/<シナリオ>/<回>` を切ってから始める（W1 で gstack の `/review` が `master` 上のため差分なしで止まったため）。
- 手順のステップを終えた時点でコミットが無い、または未コミットの変更が残るときは、定型の「お任せします。確認は不要なので、課題を最後まで実装し、変更を git にコミットしてください。」で続けさせる（最大 2 回、`POC_MAX_NUDGES=2`）。この回数を介入回数として記録する。
  - `next dev` が自動で書き出す `AGENTS.md` は未コミットの変更に数えない。
- 子セッションがバックグラウンドで起動した開発サーバーが残って終了待ちになるのを防ぐため、結果が出てから 30 秒たっても終わらないときは、試行用コピーで動く next のプロセスを止める（`errors.log` に記録）。
- 1 試行の費用には上限を設ける（`POC_MAX_TRIAL_USD`。各ステップに `--max-budget-usd` で残額を渡す）。上限に達した試行はそこで打ち切り、その状態で採点する。

### W3 の決まり（質問への回答）

- `<課題>` の末尾の定型文は W3 用のもの（`wf-answers.md` の「W3」）にする。課題文で「実装はしない」「要件をリポジトリ直下の `REQUIREMENTS.md` にまとめてコミットする」と指示する。
- 各ステップの後、最後のメッセージに依頼者への質問・確認があれば、回答役（`poc/scripts/answer_w3.py`）が定型回答シートから答え、その回答を次のステップとして同じセッションに送る（`--resume`）。質問が無くなるまで繰り返す（試行全体で最大 10 回、`POC_MAX_QA_ROUNDS=10`。超えたら締め切りの定型文を 1 回送る）。
- 質問用のツール（`AskUserQuestion`）は外す（`--disallowedTools AskUserQuestion`）。質問はメッセージ本文で受ける。
- 手順を終えて `REQUIREMENTS.md` がコミットされていなければ、定型の「お任せします。確認は不要なので、要件を REQUIREMENTS.md にまとめ、git にコミットしてください。」で続けさせる（最大 2 回）。
- gstack は `/office-hours` の質問がやり取りで終わってから `/plan-ceo-review` に進む（そのステップの質問にも同じように答える）。

### W5 の決まり（バグ修正）

- 仕込みバグのパッチ（正解データ `poc/answer-key/W5/bugs.patch`）を、`run-trial.sh` が作業用コピーにだけ当ててから baseline コミットを作る。バグは初期状態の一部になるので、候補からは差分として見えない。パッチファイル自体は作業用コピーに置かない（当てたパッチのハッシュを `raw/<試行ID>/injected-patch` に記録する）。W5 以外では当てない。
- 課題文は利用者からの報告 3 件（再現手順と期待する動作）だけで、原因の場所やテストの追加は指示しない（テストについては `poc/app/CLAUDE.md` の規約 5 のとおり）。
- 介入の定型文は「お任せします。確認は不要なので、報告された不具合を最後まで直し、変更を git にコミットしてください。」（最大 2 回）。
- 採点は `poc/scripts/grade_w5.py`（`poc/answer-key/W5/grading.md`）。

### W6 の決まり（UI 実装からブラウザ検証・PR 作成まで）

- 課題文で、実装後にブラウザで確認（スマートフォンの幅を含む）し、証跡をリポジトリに保存して PR から参照するよう指示する（baseline を含む全候補に同じ文面）。
- PR はローカルで完結させる。作業用コピーにはリモートが無く、`git push` と `gh` は許可リストに無いため実行できない。課題文で「作成するはずだった PR のタイトルと本文を `PR.md` に書いてコミットする」と指示する。`/ship`・`/ce-commit-push-pr`・`finishing-a-development-branch` が push や PR の作成を試みたときの挙動（拒否された操作）は記録する。
- Feature Dev の「PR 作成の指示」は「PR を作成してください（課題文の「確認と PR」のとおり、PR のタイトルと本文を PR.md に書いてコミットします）。」。
- 介入の定型文は「お任せします。確認は不要なので、課題を最後まで実装し、PR.md を含めて変更を git にコミットしてください。」（最大 2 回）。`PR.md` がコミットされていなければ未完了とみなす。
- 費用の上限は `POC_BUDGET_MODE=watch`（下の「費用の上限の守り方」）。
- 採点は `poc/scripts/grade_w6.py`（`poc/answer-key/W6/grading.md`）。

### W8 の決まり（人の介入なしでの自律実行）

- 課題文は `wf-W8.md`（タスクのタグ機能。DB + API + 画面で W2 と同程度の規模、W2 のコメント機能とは別の機能）。
- 最初の指示（課題文 + 末尾の新文言）と、上の表の手順のコマンド以外は送らない。介入（定型の「お任せします」）は行わない（`POC_MAX_NUDGES=0`。全候補で同じ）。手順を終えた時点で終わっていなければ、介入で続けさせずに「途中停止」として採点する。
- 2 ステップ目以降のコマンド（`/superpowers:subagent-driven-development`・`/ship`・`/lfg`）は引数なしで送る（同じセッションを `--resume` で続けるので、1 ステップ目の計画・要件が会話に残っている）。gstack の手順に実装のステップは無い（PLAN の W8 の行のとおり。`/autoplan` の後に実装まで進むかどうかも結果として記録する）。
- 費用の上限: 当初は watch 方式で「規模係数 × W1 の候補平均 × 5、最大 $10」としたが、2026-11-09 のユーザー指示で **W8 は上限なし**に変更した（`POC_W8_NOCAP=1 poc/scripts/run_w8_trials.sh ...`。watch 方式のまま上限を渡さない）。上限で途中停止した試行は同じ回の番号で上限なしでやり直し、上限ありの結果は `results/workflow/W8/capped/` に参考として残す。上限内で終わった試行は、watch 方式では子セッションに上限が見えないため上限なしと同じ条件とみなし、やり直さない。
- 対象は Superpowers・Compound Engineering・gstack と baseline（PLAN §5.1 のシナリオ表）。Feature Dev の 1 回は参考値（`results/workflow/W8/reference/`）。
- 子セッションの許可リストは W6 以降のもの（開発サーバーの起動・Playwright MCP・gstack の browse を含む。`SCN_NUM >= 6` で W8 にも効く）。
- リモートが無いので、`/ship`・`/lfg` の push・PR 作成は手前で止まる（W6 と同じく結果として記録する）。
- 破壊的操作と暴走の判定方法は `poc/answer-key/W8/grading.md` に試行前に固定した。採点は `poc/scripts/grade_w8.py` → `poc/scripts/score_w8.py`。

### W9 の決まり（レビューで不具合を見つける。2026-11-09 追加）

- レビュー対象の差分（正解データ `poc/answer-key/W9/review.patch`。不具合 10 件とおとり 5 件を含む PR 相当の変更）を、`run-trial.sh` が作業用コピーの作業ブランチにだけ当て、PR の説明（課題文の「# PR:」以降）をメッセージにしたコミットを 1 つ作る。候補は `master` との差分をレビューする。パッチファイルは作業用コピーに置かない（ハッシュを `raw/<試行ID>/review-patch` に記録する）。`baseline-commit` はこのレビュー対象のコミットにする（候補の成果は `REVIEW.md` などの差分だけになる）。W9 以外では当てない。
- 入口は各候補のレビュー機能: gstack は `/review`、Compound Engineering は `/ce-code-review`、Superpowers は `requesting-code-review`（コードレビューを依頼する Skill。`/superpowers:requesting-code-review` で起動）、Feature Dev はレビュー用のコマンドが無いため code-reviewer エージェントを使うよう指示する。baseline は課題文だけ（「この変更をコードレビューし…」）。
- 課題文で、指摘を `REVIEW.md` に書いてコミットし、コードは直さないよう指示する（全候補に同じ文面）。採点は `REVIEW.md` だけで行う。
- 介入の定型文は「お任せします。確認は不要なので、レビューを最後まで行い、指摘を REVIEW.md に書いて git にコミットしてください。」（最大 2 回）。`REVIEW.md` がコミットされていなければ未完了とみなす。
- 費用の上限は `POC_BUDGET_MODE=watch`、課題文の末尾は新文言（どちらもシナリオ名で決まる既定）。子セッションの許可リストは W6 以降と同じ（開発サーバーの起動・ブラウザを含む。レビューで動作を確かめる場合に使える）。
- 採点は `poc/scripts/grade_w9.py`・`blind_w9.py`・`score_w9.py`（`poc/answer-key/W9/grading.md`）。
### W7 の決まり（続けて行う作業での学習効果。2026-11-09 追加）

- W7a（完了報告）と W7b（作業記録）を、同じ候補・同じ回で続けて行う（`run-trial.sh W7a <候補> <回>` → 採点 → `run-trial.sh W7b <候補> <回>`）。W7b は新しいセッション（`--resume` しない）で始める。
- W7a は、落とし穴の決まり（日時は UTC で保存し JST で表示する、独自のエラー型を使う）への移行の途中の初期状態（正解データ `poc/answer-key/W7/base.patch`）を、W5 と同じように作業用コピーにだけ当ててから始める。
- 段階は W7c 以降に増やせる（2 段階目以降は 1 つ前の段階を引き継ぐ。足し方は `grading.md` の「段階を増やすとき」）。
- 5 段階（W7a〜W7e、回 21・22。2026-11-09 追加）: `poc/scripts/w7_chain.sh <候補> <回> 7.67 W7e` で続けて行う（`POC_W7_LAST_STAGE=W7e`。Compound Engineering の `/ce-compound` は W7a〜W7d の後）。W7c〜W7e の手順は W7b と同じ。対照は W7e だけ（`POC_W7_CONTROL=1`、回 31）。課題と採点は `grading.md` の「5 段階への延長」。
- 対照（`POC_W7_CONTROL=1`、回の番号 11）: W7b を、W7a を引き継がずに新しい作業用コピー（`base.patch` + `reference-W7a.patch`）と新しい HOME で行う。候補の記憶が無いときとの差を見る。
- W7b は新しい作業用コピーを作らず、W7a の作業用コピー（W7a の変更を含む app）と専用 HOME をそのまま使う（既定は同じ候補・同じ回の W7a。`POC_CONTINUE_FROM=<W7a の試行 ID>` で指定できる。`raw/<W7b の試行 ID>/continued-from` に記録）。W7a の終了時点を W7b の baseline コミットにし、作業ブランチ `poc/wf/<候補>/W7b/<回>` を切る。
  - 候補が残したもの（Compound Engineering の `docs/solutions/`、gstack の学習データ、候補が自分で書いた `CLAUDE.md`・メモなど）はそのまま W7b に残る。人・ハーネスは `CLAUDE.md` に追記しない。記憶の仕組みを持たない候補は、何も足されない状態で W7b を行う。
  - Claude Code 自身の自動メモリ（`~/.claude/projects/<作業用コピー>/memory/`）は候補の記憶の仕組みではないため、W7a・W7b とも全候補で止める（`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。W7 以外は既定のまま。`POC_DISABLE_AUTO_MEMORY=1|0` で明示できる）。
  - W7b が W7a の作業用コピー・HOME・試行 ID を参照するのは自分の試行の一部として扱う（`grade.py` は `continued-from` の ID を他の試行に数えない）。
- 手順のステップ（と「お任せします」の介入）を終えた後、`run-trial.sh` が `poc/scripts/check_w7.py` で落とし穴 2 件を判定し、避けられなかったものがあれば、レビューの定型の指摘を同じセッションに送って直させる（最大 2 回、`POC_MAX_FEEDBACK=2`。`feedback.log`）。1 回目の判定（`pitfalls-1.json`）が採点に使う「指摘を受ける前」の状態。判定にかかった時間は所要時間から除く（`check-seconds`）。
- Compound Engineering の `/ce-compound` は、W7a の指摘のやり取りが終わった後に行う（手順の一部で、介入に数えない）。
- 課題文の末尾は新文言（既定）。介入の定型文は W2 と同じ。採点は `poc/scripts/grade_w7.py`（`poc/answer-key/W7/grading.md`）。W7a は W7b を始める前に採点し、作業用コピーは W7b の採点が済んでから `grade.py W7a <W7a の試行 ID> --cleanup-only` で片付ける。

### W10 の決まり（仕様に書かれていない落とし穴がある機能追加。2026-11-09 追加）

- 課題文（`wf-W10.md`）は普通の仕様書として書き、隠しテストの項目（権限・入力検証・境界値・時差・同時更新・エラー時の振る舞い）は書かない。手順は W2 と同じ（`run-trial.sh` の既定の手順。W10 用の分岐は無い）。
- 介入は W2 以降の定型文（最大 2 回、`POC_MAX_NUDGES=2` を指定して実行する）。費用の上限は `POC_BUDGET_MODE=watch`、課題文の末尾は新文言（どちらもシナリオ名で決まる既定）。子セッションの許可リストは W6 以降と同じ。
- 採点は `poc/scripts/grade_w10.py`（公開の受け入れテスト・隠しテスト・ミューテーション）・`blind_w10.py`（ブラインドレビュー）・`score_w10.py`（`poc/answer-key/W10/grading.md`）。隠しテストは、時計をずらしたサーバー（`fake-clock.cjs`）に対して実行する。

### W11 の決まり（実在する OSS の解決済み課題。2026-11-09 追加）

- 設計・課題の一覧は [wf-W11-design.md](wf-W11-design.md)。課題の定義は `poc/scripts/oss/tasks.json`、課題文は `wf-W11-<課題ID>.md`（シナリオ名は `W11-<課題ID>`、試行 ID は `W11-<課題ID>-<候補>-<回>`）。
- 準備: `python3 poc/scripts/oss/oss.py prepare <課題ID>` が、本家の修正の 1 つ前のソースを履歴なしで `/tmp/poc-oss/<課題ID>/template` に取り出し（node の課題は依存も入れる）、隠しテストの F2P・P2P を `poc/answer-key/W11/<課題ID>.json` に書く。
- `run-trial.sh` は初期状態を作業用コピーへ写し（node_modules はハードリンク）、python の課題は作業領域の `venv` に環境を作って子セッションの `PATH` に入れる。本家の履歴・修正後のコード・隠しテストは作業用コピーに置かない。
- 手順: 不具合（`B*`）は W5、機能（`F*`）は W2 と同じ入口。課題文の末尾は新文言、費用の上限は付けない（2026-11-09 15:40 UTC ユーザー指示。歯止めは 1 ステップ 40 分のタイムアウトだけ。詳しくは wf-W11-design.md）、介入は最大 2 回。
- 子セッションの許可リスト: `curl` と `npx next` を外し、課題のテストと再現用のスクリプトの実行（`python`・`pytest`・`node`・`npx vitest`・`npx tsx`・`npx tsc`・`pnpm test` など）を足す（2026-11-09 ユーザー承認）。依存のインストールは許可しない。開発サーバー・ブラウザの許可は足さない。
- 採点: `python3 poc/scripts/grade_w11.py <試行ID>`（隠しテストを作業後のコードに上書きして実行し、終わったら取り除く）。外部サイト・依存のインストール・公開版のパッケージのソースへの参照は `isolation_suspects` として記録する。集計は `poc/scripts/report_w11.py`。まとめて流すときは `poc/scripts/oss/run_all.sh <試行ID>...`。

### W12 の決まり（短い要件から、運用まで考えて作る。2026-11-10 追加）

- 設計は [wf-W12-design.md](wf-W12-design.md)、採点は `poc/answer-key/W12/grading.md`。題材は計測器の校正台帳（`answer-key/W12/base.patch` を作業用コピーにだけ当てる）。課題文は `wf-W12.md` の 1 文だけ。
- 課題文の末尾は W12 用の文言（`task-suffix` が `w12`）。依頼者への質問は、作業中いつでも使える `ask-po "<質問>"`（`$WORK/bin` に置き、`PATH` に入れて `Bash(ask-po:*)` を許可）と、ステップの最後のメッセージの質問（W3 と同じ。最大 10 回）の 2 経路。依頼者役は `poc/scripts/answer_w12.py`（回答シートは `answer-key/W12/persona.md`）。`AskUserQuestion` は外す。記録は `raw/<試行ID>/po-questions.jsonl`。
- 条件に `baseline-conventions` を足す（候補なし。`CLAUDE.md` の末尾に `wf-W12-conventions.md` の開発規約を足してから baseline コミットを作る。`raw/<試行ID>/conventions` にハッシュを記録）。
- 介入は最大 2 回（`POC_MAX_NUDGES=2`）。費用の上限は付けない。まとめて流すときは `poc/scripts/run_w12_trials.sh <候補>:<回> ...`（試行のあと `grade_w12.py` で採点する）。
- 採点は `grade_w12.py`（アダプター・公開・隠し・堅牢さ・旧 DB でのマイグレーション・運用・ミューテーション）→ `blind_w12.py`（ブラインドレビュー）→ `score_w12.py`。

### W13 の決まり（途中で要件が変わる。2026-11-10 追加）

- 設計は [wf-W13-design.md](wf-W13-design.md)、採点は `poc/answer-key/W13/grading.md`。題材・初期状態・依頼者役の仕組み（`ask-po` とメッセージの 2 経路、`AskUserQuestion` は外す）・課題文の末尾（`w12`）は W12 と同じ（W12 の仕組みは `origin/agent/poc-w12` 03b1d05 から写した）。条件は 5 つ（baseline-conventions は使わない）で、全条件の作業用コピーの `CLAUDE.md` の末尾に汎用の開発標準（`poc/standards/generic-dev-standard.md` の区切りより下）を足す（`raw/<ID>/dev-standard` にハッシュ）。回答シートは `answer-key/W13/persona.md`（依頼者役は `answer_w13.py`）。
- 候補の手順・質問への回答・介入（最大 2 回）がすべて終わった時点のコミットを最初の版（`raw/<ID>/v1-commit`）とし、同じセッションに変更依頼（`wf-W13-change.md`）を送る。変更依頼にも候補の手順（上の表）を使い、その後の回答・介入（最大 2 回、v1 からのコミットで判定）も同じ。依頼者役には段階（`raw/<ID>/phase`）を渡す。
- 試行の最後に、最初の版までの差分（`diff-v1.patch`）と変更のステップの差分（`diff-change.patch`）を分けて残す。
- 費用の上限は付けない。まとめて流すときは `poc/scripts/run_w13_trials.sh <候補>:<回> ...`。採点は `grade_w13.py`（アダプターの下書き → 採点者が確定 → 採点）→ `blind_w13.py` → `score_w13.py`。

### W14 の決まり（安全な DB 移行。2026-11-10 追加）

- 設計は [wf-W14-design.md](wf-W14-design.md)、採点は `poc/answer-key/W14/grading.md`。初期状態は `answer-key/W14/base.patch`（W12 の初期状態 + ハンディ端末の API・場所の値の抽出など）を作業用コピーにだけ当てる。課題文は `wf-W14.md` の 1 文だけ。
- 依頼者への質問は W12 と同じ 2 経路（`ask-po` とメッセージ）。依頼者役は `poc/scripts/answer_persona.py W14`（回答シートは `answer-key/W14/persona.md`）。`AskUserQuestion` は外す。
- 条件は 5 つ（baseline-conventions は使わない）。全条件で、`poc/standards/generic-dev-standard.md` の汎用の開発標準を作業用コピーの `CLAUDE.md` の末尾に足す（2026-11-10 コーディネーターの連絡）。
- 介入は最大 2 回。費用の上限は付けない。まとめて流すときは `poc/scripts/run_w14_trials.sh W14 <候補>:<回> ...`。
- 採点は `grade_w14.py`（新しい DB での公開・隠し、5 万件の旧 DB での移行、表記ゆれ、前の版への戻し、運用、ミューテーション）→ `blind_w14.py` → `score_w14.py`。

## 権限

子セッションは `acceptEdits`（ファイル編集は許可）で起動し、Bash は次のコマンドだけを許可する。それ以外は自動で拒否され、拒否された操作は `permission_denials` として記録される。

- `npm run typecheck` / `npm test` / `npm run build`
- `git status` / `git diff` / `git log` / `git show` / `git add` / `git commit`
- `ls` / `cat` / `grep` などの読み取り系
- W11 は上の「W11 の決まり」のとおり（`curl` なし、テストと再現用のスクリプトの実行あり）。
- W6 以降だけ（2026-11-09 追加。W8 にも効く）: 開発サーバーの起動（`npm run dev` / `npm run start` / `npx next dev` / `npx next start`。`timeout` を付けた形も可）、Playwright MCP と Next.js DevTools MCP のツール、gstack の browse（`~/.claude/skills/gstack/browse/dist/`）。gstack のブラウザは Chrome for Testing を取得できないため、環境変数 `GSTACK_CHROMIUM_PATH` で事前インストール済みの Chromium（`/opt/pw-browsers/chromium`）を使わせる。子セッションが起動したサーバー・ブラウザは、結果が出た 30 秒後と試行の終了時に止める。W1〜W5 の許可リストは変えていない。

## gstack の導入（試行ごと）

試行ごとの専用 HOME に固定コミット（`b615592`）を置き、次のとおり入れる（2026-11-09 にユーザーの許可を得て実行）。

- `./setup --host claude --no-team --no-plan-tune-hooks --no-browser --quiet`
  - `--no-browser`: Chrome for Testing のダウンロード先（`cdn.playwright.dev`）が環境のネットワーク制限で使えないため
- `gstack-config set update_check false`、`gstack-config set codex_reviews disabled`（テレメトリーは初期値 off）
- 試行後に `gstack-egress list` で外部送信の記録を保存する

## 試行間の独立性（2026-11-09 追加。W4 の試行から適用）

候補同士が互いの成果や正解データを参照しないよう、次のとおりにする。完全な防止ではなく、防止と検出の組み合わせである（Bash の `cat`・`ls`・`find`・`grep` は参照先のパスを制限できない）。各 W の report.md に「試行間の独立性の確認結果」を 1 行書く。

- **置き場所**: 作業用コピーはリポジトリの外の `/tmp/poc-trials/<試行ID>/`（`POC_TRIAL_ROOT` で変更可）に置く。リポジトリ本体（正解データ `poc/answer-key/`、他の候補の結果 `poc/results/`）へ相対パスで辿れない。置き場所は `raw/<試行ID>/workdir` に記録し、`grade.py` と `blind_w2.py` はそこを読む（記録が無い W1〜W3 の試行は従来の `.poc-work/trials/<試行ID>/`）。
  - これに伴い、子セッションはリポジトリ本体の `CLAUDE.md`（親ディレクトリにあるもの）を読み込まなくなる。W3 までは作業用コピーがリポジトリの中にあったため、読み込まれていた可能性がある。どちらも全候補で同じ条件。
- **片付け**: 採点とブラインドレビューが済んだ試行は `python3 poc/scripts/grade.py <W> <試行ID> --cleanup-only` で作業用コピーを片付ける（成果は `raw/<試行ID>/diff.patch` などに保存済みであることを確認してから消す）。並列で走っている兄弟試行以外の作業用コピーを残さない。
- **検出**: `grade.py` は子セッションのツール入力を切り詰める前の全文で調べ、自分の作業用コピーの外への参照（リポジトリ本体の絶対パス、他の試行の作業用コピー、他の試行 ID、`../../` で外に出る相対パス、`poc`、`results/`、`answer-key`）を `transcript.isolation_suspects` に記録する。空でなければ採点者が中身を確認し、判断を report.md に書く。

## 課題文の末尾の定型文（2026-11-09 変更。W4 から適用）

`run-trial.sh` は課題文の末尾に、無人実行であることを伝える定型文を付ける（W3 は回答役を使うため別の文言）。

- 旧文言（W1・W2 の既定）: 「この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。」
- 新文言（W4 以降の既定）: 「この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことの判断はお任せしますが、ツールの手順にある工程（調査・設計・レビューなど）は省かずに進めてください。作業が終わったら、変更内容を git にコミットしてください。」
- 変更の理由: 旧文言のもとで、Feature Dev が W1〜W2 で「無人実行のため」と質問・設計案の比較・エージェントの工程を省き、候補の特長が出ていなかったため。
- 切り替え: `POC_TASK_SUFFIX=old|new` で明示できる（W1・W2 を新文言で再試行するときは `new`）。使った文言は `raw/<試行ID>/task-suffix` に記録する。

## W1・W2 の Feature Dev の補足の再試行（2026-11-09）

- 新文言（`POC_TASK_SUFFIX=new`）で Feature Dev だけを各 2 回（回の番号 3・4）やり直した。結果は `results/workflow/<W>/supplement/` に置き、元の試行の点数・順位は置き換えない（`grade.py`・`score_w1.py`・`score_w2.py`・`blind_w2.py` の `--supplement`）。
- W1 は、元の試行と同じ評価用アプリ（ログイン・SQLite の追加前、コミット `83e3877` の `poc-app/`。当時の場所）で実行する。`run-trial.sh` の `POC_APP_SRC` に、その版を取り出して `npm ci` したディレクトリを指定する（既定は現行の `poc/app/`）。

## 費用の上限の守り方（2026-11-09 追加。W6 から適用）

- 1 試行の上限は「規模係数（その W の baseline の実額 ÷ W1 baseline $0.15）× W1 の候補平均 × 5、最大 $10」（ユーザー承認済み。$10 を超える上限が要るときだけユーザーに確認する）。規模係数と上限は各 W の report.md の判断の記録に残す。
- W5 までは上限を `--max-budget-usd` で子セッションに渡していた（`POC_BUDGET_MODE=flag`、既定）。この値は子セッションのモデルに「USD budget: $0/$0.9; $0.9 remaining」のように見え、予算を意識して工程を減らした例があった（W1 の Feature Dev 再試行）。
- W6 からは `POC_BUDGET_MODE=watch` にする（`run-trial.sh` の既定はシナリオで決まり、W1〜W5 は `flag`、W6 以降（W7a・W7b・W8 を含む）は `watch`。環境変数で上書きでき、使った方式は `raw/<試行ID>/budget-mode` に記録する）。W4 は 2 回目を `watch` で行い、1 回目（`flag`）と比べる。`--max-budget-usd` を渡さず、`run-trial.sh` が実行中のトークン使用量から費用を見積もり、上限に達したら子セッションを止める（`raw/<試行ID>/budget-stopped` に見積額を記録し、`grade.py` は `budget_stopped` に転記する）。
  - 見積もりの単価（米ドル / 100 万トークン。`POC_RATE_IN`・`POC_RATE_OUT`・`POC_RATE_CACHE_READ`・`POC_RATE_CACHE_5M`・`POC_RATE_CACHE_1H`）は、2026-11-09 に claude-sonnet-5-5 の実測（result の costUSD）から求めた値を既定にしている。較正用の 2 回では、見積もりは実額の −13%〜+7% だった。
  - 見積もりは応答が 1 つ終わるごとに更新されるため、1 回の長い応答の途中では止まらない。安全のための打ち切りであり、正式な費用は従来どおり result の `total_cost_usd`。

## 2 本立ての点数（2026-11-09 追加）

各 W の総合点に加えて、同じ記録から「品質」と「効率」の 2 本の点数を並記する（定義は [PLAN.md §4.4](../PLAN.md)）。試行の手順は変わらない。採点後に `python3 poc/scripts/two_axis.py` を実行し、各 W の report の「2 本立ての点数」の節と全 W 横断の `poc/results/workflow/summary.md` を更新する。W4 以降の採点スクリプトは、品質の内訳を `two_axis.py` の `QUALITY` と同じキーで scores.json に書く（違う場合は各試行に `two_axis_quality` を書く）。
