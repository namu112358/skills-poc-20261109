# CLAUDE.md

@AGENTS.md

@docs/github-writing.md

## Claude Code に固有の事項

- `.claude/skills/` 配下の vendored Skills は、`scripts/sync-skills.sh` だけで更新し、あわせて `.claude/skills/SOURCES.md` を更新する。同期スクリプトは指紋（`scripts/skills.lock.json`）も作り直し、手で編集すると `scripts/check-skills.py` がエラーにする。
  - 理由: Skills は公式リポジトリから無改変でコピーし、コミット SHA とライセンスを `SOURCES.md` で管理している。手で直すと出所と一致しなくなり、次の同期で上書きされて消えるため。
- PoC の候補ツールは、`scripts/poc-profile.sh` で `.claude/settings.local.json` 側に適用する（`.claude/settings.json` は標準構成だけを持つ）。
  - 理由: `.claude/settings.json` はチーム全員のセッションと標準構成の基準になる。候補を入れると、全員の作業と PoC の比較条件の両方に影響するため。
  - 例外: PoC を無人で回すための許可ルール（`scripts/poc/` のスクリプトの実行、`claude/*` ブランチへの push、進み具合を見る読み取りのコマンド、結果の確認用の Artifact の更新）は `.claude/settings.json` に置く（2026-11-11 ユーザー承認）。このリポジトリだけの設定なので、雛形（`templates/`）には入れない。
- 例外（`AGENTS.md` の「承認を得る」の例外）: PoC の試行で起動する子セッションの許可リスト（`scripts/poc/run-trial.sh` が渡す `--allowedTools`）の変更は、作業用コピーの中でしか効かないため、Skills 検証のコーディネーターが判断してよい。変更した内容と理由は、その W の `report.md` の「判断の記録」に残す。`.claude/settings*.json` の権限、ネットワーク許可の追加、データの削除、Ruleset・`.github/workflows` の変更は、この例外に含まない。
- 画面を新しく作るとき・見た目や使い勝手を変えるときは、最初に `impeccable` Skill を使う。画面の変更のレビューには、必要に応じて `web-design-guidelines` Skill を使う。
  - 理由: Skill は依頼文だけでは呼ばれないことが多く、使う Skill を書いておくと毎回呼ばれる。PoC で人が画面を比べた評価では、Impeccable で作った画面が最もよく選ばれた（docs/poc/results/workflow/U1/human-pairs.md）。
- クラウドのセッション（Claude Code on the web）では、開始時に `.claude/hooks/session-start.sh` が `poc-app` の依存関係を入れる。依存が変わっていなければ何もしない。
