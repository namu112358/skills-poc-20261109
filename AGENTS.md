# AGENTS.md

このリポジトリで作業する AI エージェント（Claude Code・Codex・GitHub Copilot など）に共通の規約です。Claude Code に固有の事項は `CLAUDE.md` に書きます。

## このリポジトリについて

新規開発プロジェクト向けの Claude Code 標準構成（Skills / Plugins / MCP）と、比較検討中のツールの PoC をまとめたリポジトリです。作業内容に応じて、次の資料を先に読んでください。

| 作業 | 読むもの |
|---|---|
| 標準構成・導入済みツールの確認 | [README.md](README.md) |
| 開発標準・設計原則 | [docs/standards/ai-software-factory-engineering-standard.md](docs/standards/ai-software-factory-engineering-standard.md) |
| PoC の計画・評価基準 | [docs/poc/PLAN.md](docs/poc/PLAN.md) |
| PoC の結果 | [docs/poc/results/workflow/summary.md](docs/poc/results/workflow/summary.md) |
| 標準ツールの追加候補 | [docs/tool-candidates/README.md](docs/tool-candidates/README.md) |
| GitHub リポジトリの初期設定 | [docs/github-setup/README.md](docs/github-setup/README.md) |
| Issue・PR を作る | [docs/github-writing.md](docs/github-writing.md) |

## 規約

- 応答・ドキュメントは日本語で書く。
  - 理由: 読み手のチームが日本語で判断・レビューするため。
- 設定ファイル（`.mcp.json`、`.claude/settings.json` など）に認証情報を直接書かない。トークンは環境変数（`${VAR}`）で参照する。
  - 理由: 設定ファイルはコミットされ、リポジトリを読める全員に見えるため。
- 本番環境への反映、データの削除、セキュリティ上重要な設定の変更は、実行する前に必ずユーザーの承認を得る。
  - 理由: 取り消せない、または影響が広い操作だから。
- Issue・PR を作るときは [docs/github-writing.md](docs/github-writing.md) の記述ルールに従う。
- 変更によってこのファイルや下位の `CLAUDE.md`・`AGENTS.md` の案内が古くなったら、同じ PR で直す。
  - 理由: 案内が実態とずれると、エージェントは古い案内を正しいものとして読んでしまうため。
- 警告やテストの失敗を「もとからあったもの」と決めつけない。もとからあると判断する場合は、変更前の状態で再現して確かめてから書く。
  - 理由: 確かめずに既存の問題として扱うと、自分の変更が起こした不具合を見逃すため。

## 注意が必要な場所

- `poc-app/` とその `CLAUDE.md` は、PoC の試行の初期状態です。試行のたびに `scripts/poc/run-trial.sh` がこのフォルダを作業用コピーに写し、`CLAUDE.md` の末尾に条件ごとの規約を足します。採点用のスクリプト（`scripts/poc/blind_*.py` など）も、この `CLAUDE.md` の中身を読みます。PoC の作業として依頼されたとき以外は、変更しないでください。
  - 理由: 初期状態が変わると、過去の試行の結果と比べられなくなるため。
- `docs/poc/answer-key/` は採点用の正解です。試行の作業用コピーや、候補ツールに渡す資料に含めない。
  - 理由: 正解が見えると、試行の結果が評価として使えなくなるため。
