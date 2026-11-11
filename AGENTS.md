# AGENTS.md

このリポジトリで作業する AI エージェント（Claude Code・Codex・GitHub Copilot など）に共通の規約です。Claude Code に固有の事項は `CLAUDE.md` に書きます。

「規約」の節は、ほかのプロジェクトに配る雛形（[templates/agents/AGENTS.md](templates/agents/AGENTS.md)）の共通規約と同じ内容です。変えるときは雛形を直してから写し、`python3 scripts/check-templates.py` で一致を確かめます。このリポジトリだけの事項は「このリポジトリの罠」に書きます。

## このリポジトリについて

AI エージェントを使った新規開発の標準（入れる Skills、開発ワークフロー、GitHub の設定、AI への指示と管理）を決め、各プロジェクトに配るリポジトリです。候補は PoC で比べ、その結果を根拠にします。作業内容に応じて、次の資料を先に読んでください。

| 作業 | 読むもの |
|---|---|
| 4 つの問いへの今の答えと、配るもの | [README.md](README.md) |
| 開発標準・設計原則 | [docs/standards/ai-software-factory-engineering-standard.md](docs/standards/ai-software-factory-engineering-standard.md) |
| PoC の計画・評価基準 | [docs/poc/PLAN.md](docs/poc/PLAN.md) |
| PoC の結果 | [docs/poc/results/workflow/summary.md](docs/poc/results/workflow/summary.md) |
| 標準ツールの追加候補 | [docs/tool-candidates/README.md](docs/tool-candidates/README.md) |
| GitHub リポジトリの初期設定 | [docs/github-setup/README.md](docs/github-setup/README.md) |
| Issue・PR を作る | [docs/github-writing.md](docs/github-writing.md) |

<!-- 共通規約ここから: 正本は skills-poc-20261109 の templates/agents/AGENTS.md。このブロックは直接編集せず、正本を直してから写す。 -->
## 規約

- 応答・ドキュメントは日本語で書く。
  - 理由: 読み手のチームが日本語で判断・レビューするため。
- 設定ファイル（`.mcp.json`、`.claude/settings.json` など）のトークンは、環境変数（`${VAR}`）で参照する。
  - 理由: 設定ファイルはコミットされ、リポジトリを読める全員に見えるため。
- 本番環境への反映、データの削除、セキュリティ上重要な設定の変更は、実行する前に必ずユーザーの承認を得る。
  - 理由: 取り消せない、または影響が広い操作だから。
- Issue・PR は [docs/github-writing.md](docs/github-writing.md) の記述ルールに沿って書く。
- ドキュメントと既存のコードが食い違うときは、既存のコードの書き方に従い、見つけた食い違いを最後の返答ですべて挙げる。
  - 理由: エージェントは、指示ファイルに書かれた古い説明を、目の前のコードより優先しやすい。この一文を足すと、コードに従う割合が 4.2% から 91.4% に上がったという報告がある（[arXiv:2610.30571](https://arxiv.org/abs/2610.30571)）。
- PR を出す前に、このファイルと下位の `CLAUDE.md`・`AGENTS.md` の案内が変更後の実態と合っているかを確かめ、ずれていれば同じ PR で直す。
  - 理由: 案内が実態とずれると、エージェントは古い案内を正しいものとして読んでしまうため。
- PR を出す前に `python3 scripts/check-skills.py` を実行し、エラーを 0 件にする。
  - 理由: Skills の形式・参照先・評価ケースの定義と、vendored Skills が手で編集されていないことを、モデルを呼ばずに確かめられるため。
- 自作の Skill には、`evals/evals.json`（評価ケース）と `evals/trigger.json`（発火すべき例・発火すべきでない例）を Skill のディレクトリに置く。形式は skill-creator（`.claude/skills/skill-creator/references/schemas.md`）に合わせる。
  - 理由: 評価の入力と合格条件を Skill の隣に置くと、Skill を変えたときに同じケースで確かめ直せるため（withastro/astro の形）。
- 警告やテストの失敗は、変更前の状態でも起きるかを再現して確かめてから、もとからあった問題として扱う。
  - 理由: 確かめずに既存の問題として扱うと、自分の変更が起こした不具合を見逃すため。
<!-- 共通規約ここまで -->

## このリポジトリの罠

- `poc-app/` とその `CLAUDE.md` は、PoC の試行の初期状態です。試行のたびに `scripts/poc/run-trial.sh` がこのフォルダを作業用コピーに写し、`CLAUDE.md` の末尾に条件ごとの規約を足します。採点用のスクリプト（`scripts/poc/blind_*.py` など）も、この `CLAUDE.md` の中身を読みます。ここは、PoC の作業として依頼された変更だけを行う。
  - 理由: 初期状態が変わると、過去の試行の結果と比べられなくなるため。
- `docs/poc/answer-key/` は採点用の正解です。採点のスクリプトだけが読み、試行の作業用コピーや候補ツールに渡す資料の外に置く。
  - 理由: 正解が見えると、試行の結果が評価として使えなくなるため。
- 配る雛形（`templates/`）を正本にし、このリポジトリで使う版をそれに合わせる。ルートの `AGENTS.md` の規約の節、`docs/github-writing.md`、`scripts/check-skills.py` は同じ内容に保ち、ルートの `.claude/settings.json`・`.mcp.json` は雛形の中身をすべて含めたうえで、このリポジトリだけの設定を足す。PR を出す前に `python3 scripts/check-templates.py` を実行し、エラーを 0 件にする。
  - 理由: このリポジトリは標準を配る側でもあり、使う側でもある。両方を別々に直すと、配った標準とこのリポジトリの運用がずれるため（`docs/github-writing.md` の写しは、下書き PR のルールが抜けたまま配られていた）。
