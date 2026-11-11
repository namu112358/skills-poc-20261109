# CLAUDE.md

@AGENTS.md

@docs/github-writing.md

## Claude Code に固有の事項

- `.claude/skills/` 配下の vendored Skills は、`scripts/sync-skills.sh` だけで更新し、あわせて `.claude/skills/SOURCES.md` を更新する。同期スクリプトは指紋（`scripts/skills.lock.json`）も作り直し、手で編集すると `scripts/check-skills.py` がエラーにする。
  - 理由: Skills は公式リポジトリから無改変でコピーし、コミット SHA とライセンスを `SOURCES.md` で管理している。手で直すと出所と一致しなくなり、次の同期で上書きされて消えるため。
- PoC の候補ツールは、`scripts/poc-profile.sh` で `.claude/settings.local.json` 側に適用する（`.claude/settings.json` は標準構成だけを持つ）。
  - 理由: `.claude/settings.json` はチーム全員のセッションと標準構成の基準になる。候補を入れると、全員の作業と PoC の比較条件の両方に影響するため。
- 例外（`AGENTS.md` の「承認を得る」の例外）: PoC の試行で起動する子セッションの許可リスト（`scripts/poc/run-trial.sh` が渡す `--allowedTools`）の変更は、作業用コピーの中でしか効かないため、Skills 検証のコーディネーターが判断してよい。変更した内容と理由は、その W の `report.md` の「判断の記録」に残す。`.claude/settings*.json` の権限、ネットワーク許可の追加、データの削除、Ruleset・`.github/workflows` の変更は、この例外に含まない。
- クラウドのセッション（Claude Code on the web）では、開始時に `.claude/hooks/session-start.sh` が `poc-app` の依存関係を入れる。依存が変わっていなければ何もしない。
