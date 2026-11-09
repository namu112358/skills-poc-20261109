# 候補ごとの手順（開発ワークフロー）

`scripts/poc/run-trial.sh` はこの表のとおりに、同じセッションを続けて（`--resume`）各ステップを実行する。
`<課題>` は `wf-<シナリオ>.md` の本文と定型回答（`wf-answers.md`）を連結したもの。

| シナリオ | baseline | Superpowers | Feature Dev | gstack | Compound Engineering |
|---|---|---|---|---|---|
| W1 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W2 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |
| W4 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `/autoplan <課題>` → 「計画に沿って実装し、変更を git にコミットしてください。」→ `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |

### W2 以降の共通の決まり

- 作業用コピーの `master`（初期状態）から作業ブランチ `poc/wf/<候補>/<シナリオ>/<回>` を切ってから始める（W1 で gstack の `/review` が `master` 上のため差分なしで止まったため）。
- 手順のステップを終えた時点でコミットが無い、または未コミットの変更が残るときは、定型の「お任せします。確認は不要なので、課題を最後まで実装し、変更を git にコミットしてください。」で続けさせる（最大 2 回、`POC_MAX_NUDGES=2`）。この回数を介入回数として記録する。
  - `next dev` が自動で書き出す `AGENTS.md` は未コミットの変更に数えない。
- 子セッションがバックグラウンドで起動した開発サーバーが残って終了待ちになるのを防ぐため、結果が出てから 30 秒たっても終わらないときは、試行用コピーで動く next のプロセスを止める（`errors.log` に記録）。
- 1 試行の費用には上限を設ける（`POC_MAX_TRIAL_USD`。各ステップに `--max-budget-usd` で残額を渡す）。上限に達した試行はそこで打ち切り、その状態で採点する。

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
