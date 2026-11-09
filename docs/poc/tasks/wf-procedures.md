# 候補ごとの手順（開発ワークフロー）

`scripts/poc/run-trial.sh` はこの表のとおりに、同じセッションを続けて（`--resume`）各ステップを実行する。
`<課題>` は `wf-<シナリオ>.md` の本文と定型回答（`wf-answers.md`）を連結したもの。

| シナリオ | baseline | Superpowers | Feature Dev | gstack | Compound Engineering |
|---|---|---|---|---|---|
| W1 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W2 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W3 | `<課題>` | `<課題>`（`brainstorming` の自動発火） | `/feature-dev:feature-dev <課題>`（確認質問のフェーズまで） | `/office-hours <課題>` → `/plan-ceo-review` | `/ce-brainstorm <課題>` |
| W5 | `<課題>` | `<課題>`（`systematic-debugging` の自動発火） | `<課題>`（通常の指示） | `/qa <課題>` | `/ce-debug <課題>` |
| W7a | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` →（落とし穴の指摘の後）`/ce-compound` |
| W7b | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |

### W2 以降の共通の決まり

- 作業用コピーの `master`（初期状態）から作業ブランチ `poc/wf/<候補>/<シナリオ>/<回>` を切ってから始める（W1 で gstack の `/review` が `master` 上のため差分なしで止まったため）。
- 手順のステップを終えた時点でコミットが無い、または未コミットの変更が残るときは、定型の「お任せします。確認は不要なので、課題を最後まで実装し、変更を git にコミットしてください。」で続けさせる（最大 2 回、`POC_MAX_NUDGES=2`）。この回数を介入回数として記録する。
  - `next dev` が自動で書き出す `AGENTS.md` は未コミットの変更に数えない。
- 子セッションがバックグラウンドで起動した開発サーバーが残って終了待ちになるのを防ぐため、結果が出てから 30 秒たっても終わらないときは、試行用コピーで動く next のプロセスを止める（`errors.log` に記録）。
- 1 試行の費用には上限を設ける（`POC_MAX_TRIAL_USD`。各ステップに `--max-budget-usd` で残額を渡す）。上限に達した試行はそこで打ち切り、その状態で採点する。

### W3 の決まり（質問への回答）

- `<課題>` の末尾の定型文は W3 用のもの（`wf-answers.md` の「W3」）にする。課題文で「実装はしない」「要件をリポジトリ直下の `REQUIREMENTS.md` にまとめてコミットする」と指示する。
- 各ステップの後、最後のメッセージに依頼者への質問・確認があれば、回答役（`scripts/poc/answer_w3.py`）が定型回答シートから答え、その回答を次のステップとして同じセッションに送る（`--resume`）。質問が無くなるまで繰り返す（試行全体で最大 10 回、`POC_MAX_QA_ROUNDS=10`。超えたら締め切りの定型文を 1 回送る）。
- 質問用のツール（`AskUserQuestion`）は外す（`--disallowedTools AskUserQuestion`）。質問はメッセージ本文で受ける。
- 手順を終えて `REQUIREMENTS.md` がコミットされていなければ、定型の「お任せします。確認は不要なので、要件を REQUIREMENTS.md にまとめ、git にコミットしてください。」で続けさせる（最大 2 回）。
- gstack は `/office-hours` の質問がやり取りで終わってから `/plan-ceo-review` に進む（そのステップの質問にも同じように答える）。

### W5 の決まり（バグ修正）

- 仕込みバグのパッチ（正解データ `docs/poc/answer-key/W5/bugs.patch`）を、`run-trial.sh` が作業用コピーにだけ当ててから baseline コミットを作る。バグは初期状態の一部になるので、候補からは差分として見えない。パッチファイル自体は作業用コピーに置かない（当てたパッチのハッシュを `raw/<試行ID>/injected-patch` に記録する）。W5 以外では当てない。
- 課題文は利用者からの報告 3 件（再現手順と期待する動作）だけで、原因の場所やテストの追加は指示しない（テストについては `poc-app/CLAUDE.md` の規約 5 のとおり）。
- 介入の定型文は「お任せします。確認は不要なので、報告された不具合を最後まで直し、変更を git にコミットしてください。」（最大 2 回）。
- 採点は `scripts/poc/grade_w5.py`（`docs/poc/answer-key/W5/grading.md`）。

### W7 の決まり（続けて行う作業での学習効果。2026-11-09 追加）

- W7a（完了報告）と W7b（作業記録）を、同じ候補・同じ回で続けて行う（`run-trial.sh W7a <候補> <回>` → 採点 → `run-trial.sh W7b <候補> <回>`）。W7b は新しいセッション（`--resume` しない）で始める。
- W7a は、落とし穴の決まり（日時は UTC で保存し JST で表示する、独自のエラー型を使う）への移行の途中の初期状態（正解データ `docs/poc/answer-key/W7/base.patch`）を、W5 と同じように作業用コピーにだけ当ててから始める。
- 段階は W7c 以降に増やせる（2 段階目以降は 1 つ前の段階を引き継ぐ。足し方は `grading.md` の「段階を増やすとき」）。
- 対照（`POC_W7_CONTROL=1`、回の番号 11）: W7b を、W7a を引き継がずに新しい作業用コピー（`base.patch` + `reference-W7a.patch`）と新しい HOME で行う。候補の記憶が無いときとの差を見る。
- W7b は新しい作業用コピーを作らず、W7a の作業用コピー（W7a の変更を含む app）と専用 HOME をそのまま使う（既定は同じ候補・同じ回の W7a。`POC_CONTINUE_FROM=<W7a の試行 ID>` で指定できる。`raw/<W7b の試行 ID>/continued-from` に記録）。W7a の終了時点を W7b の baseline コミットにし、作業ブランチ `poc/wf/<候補>/W7b/<回>` を切る。
  - 候補が残したもの（Compound Engineering の `docs/solutions/`、gstack の学習データ、候補が自分で書いた `CLAUDE.md`・メモなど）はそのまま W7b に残る。人・ハーネスは `CLAUDE.md` に追記しない。記憶の仕組みを持たない候補は、何も足されない状態で W7b を行う。
  - Claude Code 自身の自動メモリ（`~/.claude/projects/<作業用コピー>/memory/`）は候補の記憶の仕組みではないため、W7a・W7b とも全候補で止める（`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。W7 以外は既定のまま。`POC_DISABLE_AUTO_MEMORY=1|0` で明示できる）。
  - W7b が W7a の作業用コピー・HOME・試行 ID を参照するのは自分の試行の一部として扱う（`grade.py` は `continued-from` の ID を他の試行に数えない）。
- 手順のステップ（と「お任せします」の介入）を終えた後、`run-trial.sh` が `scripts/poc/check_w7.py` で落とし穴 2 件を判定し、避けられなかったものがあれば、レビューの定型の指摘を同じセッションに送って直させる（最大 2 回、`POC_MAX_FEEDBACK=2`。`feedback.log`）。1 回目の判定（`pitfalls-1.json`）が採点に使う「指摘を受ける前」の状態。判定にかかった時間は所要時間から除く（`check-seconds`）。
- Compound Engineering の `/ce-compound` は、W7a の指摘のやり取りが終わった後に行う（手順の一部で、介入に数えない）。
- 課題文の末尾は新文言（既定）。介入の定型文は W2 と同じ。採点は `scripts/poc/grade_w7.py`（`docs/poc/answer-key/W7/grading.md`）。W7a は W7b を始める前に採点し、作業用コピーは W7b の採点が済んでから `grade.py W7a <W7a の試行 ID> --cleanup-only` で片付ける。

## 権限

子セッションは `acceptEdits`（ファイル編集は許可）で起動し、Bash は次のコマンドだけを許可する。それ以外は自動で拒否され、拒否された操作は `permission_denials` として記録される。

- `npm run typecheck` / `npm test` / `npm run build`
- `git status` / `git diff` / `git log` / `git show` / `git add` / `git commit`
- `ls` / `cat` / `grep` などの読み取り系

## gstack の導入（試行ごと）

試行ごとの専用 HOME に固定コミット（`b615592`）を置き、次のとおり入れる（2026-11-09 にユーザーの許可を得て実行）。

- `./setup --host claude --no-team --no-plan-tune-hooks --no-browser --quiet`
  - `--no-browser`: Chrome for Testing のダウンロード先（`cdn.playwright.dev`）が環境のネットワーク制限で使えないため
- `gstack-config set update_check false`、`gstack-config set codex_reviews disabled`（テレメトリーは初期値 off）
- 試行後に `gstack-egress list` で外部送信の記録を保存する

## 試行間の独立性（2026-11-09 追加。W4 の試行から適用）

候補同士が互いの成果や正解データを参照しないよう、次のとおりにする。完全な防止ではなく、防止と検出の組み合わせである（Bash の `cat`・`ls`・`find`・`grep` は参照先のパスを制限できない）。各 W の report.md に「試行間の独立性の確認結果」を 1 行書く。

- **置き場所**: 作業用コピーはリポジトリの外の `/tmp/poc-trials/<試行ID>/`（`POC_TRIAL_ROOT` で変更可）に置く。リポジトリ本体（正解データ `docs/poc/answer-key/`、他の候補の結果 `docs/poc/results/`）へ相対パスで辿れない。置き場所は `raw/<試行ID>/workdir` に記録し、`grade.py` と `blind_w2.py` はそこを読む（記録が無い W1〜W3 の試行は従来の `.poc-work/trials/<試行ID>/`）。
  - これに伴い、子セッションはリポジトリ本体の `CLAUDE.md`（親ディレクトリにあるもの）を読み込まなくなる。W3 までは作業用コピーがリポジトリの中にあったため、読み込まれていた可能性がある。どちらも全候補で同じ条件。
- **片付け**: 採点とブラインドレビューが済んだ試行は `python3 scripts/poc/grade.py <W> <試行ID> --cleanup-only` で作業用コピーを片付ける（成果は `raw/<試行ID>/diff.patch` などに保存済みであることを確認してから消す）。並列で走っている兄弟試行以外の作業用コピーを残さない。
- **検出**: `grade.py` は子セッションのツール入力を切り詰める前の全文で調べ、自分の作業用コピーの外への参照（リポジトリ本体の絶対パス、他の試行の作業用コピー、他の試行 ID、`../../` で外に出る相対パス、`docs/poc`、`results/`、`answer-key`）を `transcript.isolation_suspects` に記録する。空でなければ採点者が中身を確認し、判断を report.md に書く。

## 課題文の末尾の定型文（2026-11-09 変更。W4 から適用）

`run-trial.sh` は課題文の末尾に、無人実行であることを伝える定型文を付ける（W3 は回答役を使うため別の文言）。

- 旧文言（W1・W2 の既定）: 「この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。」
- 新文言（W4 以降の既定）: 「この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことの判断はお任せしますが、ツールの手順にある工程（調査・設計・レビューなど）は省かずに進めてください。作業が終わったら、変更内容を git にコミットしてください。」
- 変更の理由: 旧文言のもとで、Feature Dev が W1〜W2 で「無人実行のため」と質問・設計案の比較・エージェントの工程を省き、候補の特長が出ていなかったため。
- 切り替え: `POC_TASK_SUFFIX=old|new` で明示できる（W1・W2 を新文言で再試行するときは `new`）。使った文言は `raw/<試行ID>/task-suffix` に記録する。

## W1・W2 の Feature Dev の補足の再試行（2026-11-09）

- 新文言（`POC_TASK_SUFFIX=new`）で Feature Dev だけを各 2 回（回の番号 3・4）やり直した。結果は `results/workflow/<W>/supplement/` に置き、元の試行の点数・順位は置き換えない（`grade.py`・`score_w1.py`・`score_w2.py`・`blind_w2.py` の `--supplement`）。
- W1 は、元の試行と同じ評価用アプリ（ログイン・SQLite の追加前、コミット `83e3877` の `poc-app/`）で実行する。`run-trial.sh` の `POC_APP_SRC` に、その版を取り出して `npm ci` したディレクトリを指定する（既定は現行の `poc-app/`）。

## 費用の上限の守り方（2026-11-09 追加。W6 から適用）

- 1 試行の上限は「規模係数（その W の baseline の実額 ÷ W1 baseline $0.15）× W1 の候補平均 × 5、最大 $10」（ユーザー承認済み。$10 を超える上限が要るときだけユーザーに確認する）。規模係数と上限は各 W の report.md の判断の記録に残す。
- W5 までは上限を `--max-budget-usd` で子セッションに渡していた（`POC_BUDGET_MODE=flag`、既定）。この値は子セッションのモデルに「USD budget: $0/$0.9; $0.9 remaining」のように見え、予算を意識して工程を減らした例があった（W1 の Feature Dev 再試行）。
- W6 からは `POC_BUDGET_MODE=watch` にする（`run-trial.sh` の既定はシナリオで決まり、W1〜W5 は `flag`、W6 以降（W7a・W7b・W8 を含む）は `watch`。環境変数で上書きでき、使った方式は `raw/<試行ID>/budget-mode` に記録する）。W4 は 2 回目を `watch` で行い、1 回目（`flag`）と比べる。`--max-budget-usd` を渡さず、`run-trial.sh` が実行中のトークン使用量から費用を見積もり、上限に達したら子セッションを止める（`raw/<試行ID>/budget-stopped` に見積額を記録し、`grade.py` は `budget_stopped` に転記する）。
  - 見積もりの単価（米ドル / 100 万トークン。`POC_RATE_IN`・`POC_RATE_OUT`・`POC_RATE_CACHE_READ`・`POC_RATE_CACHE_5M`・`POC_RATE_CACHE_1H`）は、2026-11-09 に claude-sonnet-5-5 の実測（result の costUSD）から求めた値を既定にしている。較正用の 2 回では、見積もりは実額の −13%〜+7% だった。
  - 見積もりは応答が 1 つ終わるごとに更新されるため、1 回の長い応答の途中では止まらない。安全のための打ち切りであり、正式な費用は従来どおり result の `total_cost_usd`。

## 2 本立ての点数（2026-11-09 追加）

各 W の総合点に加えて、同じ記録から「品質」と「効率」の 2 本の点数を並記する（定義は [PLAN.md §4.4](../PLAN.md)）。試行の手順は変わらない。採点後に `python3 scripts/poc/two_axis.py` を実行し、各 W の report の「2 本立ての点数」の節と全 W 横断の `docs/poc/results/workflow/summary.md` を更新する。W4 以降の採点スクリプトは、品質の内訳を `two_axis.py` の `QUALITY` と同じキーで scores.json に書く（違う場合は各試行に `two_axis_quality` を書く）。
