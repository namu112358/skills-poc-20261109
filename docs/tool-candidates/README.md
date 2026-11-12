# 標準ツールの追加候補と UI/UX ツールの整理

README の標準ツール一覧を見直した際に、足りない領域と、役割が重なっているツールを調べた結果です（調査日: 2026-11-09）。
ここに書いたものはまだ **採用を決めていません**。採用するかどうかは、試行で確かめてから判断します。

| 文書 | 内容 |
|---|---|
| [additions.md](additions.md) | 足りない領域（最新ドキュメントの参照、パフォーマンス計測、DB 設計、TypeScript 以外の言語）を補う追加候補 |
| [ui-ux-overlap.md](ui-ux-overlap.md) | 常に同時に有効な UI/UX 系 4 ツールの役割の重なり・矛盾と、整理の案 |
| [security-audit-schedule.md](security-audit-schedule.md) | セキュリティ監査を定期的に回すときの頻度・範囲・記録の置き場の案（2026-11-11） |

## 要点

- **追加候補**
  - 共通ツールの候補: Context7（最新ドキュメントの参照）と Chrome DevTools MCP（表示速度の計測）。
  - 採用技術別の候補: Supabase の Postgres ベストプラクティス Skill と、Python・Go などの LSP プラグイン。
- **UI/UX ツール**
  - 4 つを同時に有効にすると、「画面を作る」役割が 3 つ重なります。
  - 書体やスタイルの勧めが互いに逆になっている箇所もあります。UI/UX Pro Max が勧める書体を、Impeccable の自動チェックが「使い古された書体」として指摘します。
  - PoC（U1〜U4）の結果、標準は Impeccable と Web Design Guidelines の 2 つにしました（2026-11-12）。Frontend Design と UI/UX Pro Max は外しました（[ui-ux-overlap.md](ui-ux-overlap.md) の「決定」）。
- **セキュリティ監査の定期実行**
  - PR ごとは `/security-review`、週 1 回の差分と月 1 回の全体は Claude Security（medium）、毎日は CodeQL などの LLM を使わない検査に任せる案です。
  - Cloudflare Security Audit は、`poc-app` で測ると費用が約 4 倍で、クラウドのセッションでは指摘を確かめきれなかったため、いまは使いません。

## 調べ方と限界

- 各ツールの公式リポジトリを取得し、中身（設定・説明文・ライセンス・文書）を直接読みました。最新版は npm レジストリで確認しました。
- GitHub API が使えなかったため、Star 数・Issue の状況は確認していません。
- **どのツールも、実際に Claude Code に入れて動かしてはいません。** 文中の「未確認」は、試行で確かめる必要がある点です。
