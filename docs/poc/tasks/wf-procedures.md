# 候補ごとの手順（開発ワークフロー）

`scripts/poc/run-trial.sh` はこの表のとおりに、同じセッションを続けて（`--resume`）各ステップを実行する。
`<課題>` は `wf-<シナリオ>.md` の本文と定型回答（`wf-answers.md`）を連結したもの。

| シナリオ | baseline | Superpowers | Feature Dev | gstack | Compound Engineering |
|---|---|---|---|---|---|
| W1 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W2 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W3 | `<課題>` | `<課題>`（`brainstorming` の自動発火） | `/feature-dev:feature-dev <課題>`（確認質問のフェーズまで） | `/office-hours <課題>` → `/plan-ceo-review` | `/ce-brainstorm <課題>` |

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
