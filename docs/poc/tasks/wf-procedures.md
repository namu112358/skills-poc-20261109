# 候補ごとの手順（開発ワークフロー）

`scripts/poc/run-trial.sh` はこの表のとおりに、同じセッションを続けて（`--resume`）各ステップを実行する。
`<課題>` は `wf-<シナリオ>.md` の本文と定型回答（`wf-answers.md`）を連結したもの。

| シナリオ | baseline | Superpowers | Feature Dev | gstack | Compound Engineering |
|---|---|---|---|---|---|
| W1 | `<課題>` | `<課題>`（Skill の自動発火） | `/feature-dev:feature-dev <課題>` | `<課題>` → `/review` | `/ce-plan <課題>` → `/ce-work` → `/ce-code-review` |

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
