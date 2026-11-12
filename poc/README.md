# PoC（候補ツールの比較）

標準に入れるツールや進め方を、同じ条件で試して比べるための一式です。PoC に関わるものは、すべてこのディレクトリの下に置きます。結果から決めた標準は、ルートの [README.md](../README.md) にまとめています。

## どこに何があるか

| 場所 | 中身 | 注意 |
|---|---|---|
| [PLAN.md](PLAN.md) | 計画と評価基準 | |
| [app/](app/) | 評価用のアプリ（`poc-app`。Next.js + TypeScript + SQLite のタスク管理アプリ） | 試行の初期状態。PoC の作業として依頼された変更だけを行う |
| [tasks/](tasks/) | 試行で渡す課題文（`wf-<シナリオ>.md`）、シナリオごとの設計（`wf-<シナリオ>-design.md`）、手順（[wf-procedures.md](tasks/wf-procedures.md)） | 課題文は、試行が始まった後は変えない |
| [profiles/](profiles/) | 候補ツールごとの設定。`scripts/poc-profile.sh` が `.claude/settings.local.json` に適用する | |
| [standards/](standards/)・[proxy/](proxy/) | 試行の条件として使う文書（汎用の開発標準、人の代わりに判断するときの原則） | 試行が始まった後は変えない |
| [answer-key/](answer-key/) | 採点用の正解（受け入れテスト、参照実装、仕込んだ不具合の一覧） | 採点のスクリプトだけが読む。試行の作業用コピーや候補ツールに渡さない |
| [scripts/](scripts/) | 試行を回す・採点する・レポートを作るスクリプト | |
| [results/](results/) | 結果。試行ごとの記録と、シナリオごとのレポート | |
| [notes/](notes/) | 結果から考えた案のメモ（未決定） | |

## 結果を読む

- 開発ワークフローの一覧: [results/workflow/summary.md](results/workflow/summary.md)。シナリオごとのレポートは `results/workflow/<シナリオ>/report.md`
- レビュー用 Skill の比較のまとめ: [results/review-skills.md](results/review-skills.md)
- セキュリティ監査のツールの比較: [results/security/README.md](results/security/README.md)

シナリオの番号は、W が開発ワークフローとレビュー、U が UI/UX、SEC がセキュリティ監査です。

## スクリプトの名前

`scripts/` のスクリプトは、名前の先頭で役割が分かります。どれもリポジトリのルートから実行します。

| 名前 | 役割 |
|---|---|
| `run-trial.sh`・`run-security-*.sh` | 試行を 1 本回す。`app/` を作業用コピー（既定は `/tmp/poc-trials/<試行ID>/`）に写し、子セッションを起動する |
| `run_<シナリオ>_trials.sh`・`*_driver.sh` など | 試行をまとめて回す |
| `grade*.py` | 試行の成果物を、正解と突き合わせて採点する |
| `blind_*.py`・`judge_*.py` | 候補の名前を隠したレビューと、指摘の判定 |
| `score_*.py`・`two_axis.py` | 採点の結果から点数を出す |
| `report_*.py` | 点数と所見（`results/workflow/<シナリオ>/notes.json`）からレポートを作る |
| `poc-profile.sh` | 候補ツールを切り替える（`poc/scripts/poc-profile.sh <profile>`） |
| `fetch-plugins.sh` | 候補のプラグインを、固定の版で取得する |
