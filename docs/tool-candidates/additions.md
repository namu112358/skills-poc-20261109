# 足りない領域を補う追加候補

いまの標準ツールでカバーできていない 4 つの領域について、候補を調べました（調査日: 2026-11-09）。
版・最終更新日は調査日時点のものです。

| 領域 | 分類 | 候補 | 結論 |
|---|---|---|---|
| 最新ドキュメントの参照 | 共通 | Context7（Upstash） | 試行する価値あり。無料枠と外部送信の確認が必要 |
| パフォーマンス計測 | 共通（テスト・動作確認） | Chrome DevTools MCP（Google） | 試行する価値あり。既定で Google に利用統計を送るため、止める設定で入れる |
| DB 設計・SQL | 採用技術別 | Supabase Postgres Best Practices Skill | 追加してよい。静的な文書だけで、認証・外部送信なし |
| TypeScript 以外の言語 | 採用技術別 | claude-plugins-official の LSP プラグイン | 該当する言語を使う案件が出たときに stack として追加 |

---

## 1. 最新ドキュメントの参照: Context7

**何が良くなるか**: AI は学習した時点より古い書き方をしがちです。Context7 を使うと、ライブラリの最新ドキュメントを取り込んでから実装できます。Next.js 以外の技術（Supabase、Tailwind など）にも効きます。

| 項目 | 内容 |
|---|---|
| 提供元 | Upstash |
| リポジトリ | [upstash/context7](https://github.com/upstash/context7)（2026-11-09 にもコミットあり） |
| ライセンス | MIT |
| 版 | `@upstash/context7-mcp@4.6.0`（2026-11-09 公開。出たばかりなので、固定するなら 1 つ前の 4.5.1 も候補） |
| 入れ方 | ① 公式 marketplace のプラグイン `context7@claude-plugins-official`（中身はリモート MCP `https://mcp.context7.com/mcp`）<br>② `.mcp.json` にリモート MCP を書く（API キーを `Authorization: Bearer ${CONTEXT7_API_KEY}` で渡す） |
| 認証 | API キーなしでも使えるが、呼び出し回数の制限が低い。プラグインは `/mcp` から OAuth でサインインできる |
| 料金 | 無料は月 1,000 回まで（使い切ると翌月まで止まり、1 日 20 回だけ追加で使える）。Pro は 1 人あたり月 $10 で 2,000 回 |

**注意点**

- **外部に送られるもの**
  - AI が組み立てた検索文・ライブラリ名・IP アドレスが Context7 に送られます。プロンプト全文やコードは送らない、とされています。
  - ただし、検索文に機密情報を入れない仕組みは、ツールの説明文による指示だけです。
  - 検索文は匿名化したうえで保存されます（Enterprise は保存しない）。
  - 出典: [docs/security/data-privacy.mdx](https://github.com/upstash/context7/blob/master/docs/security/data-privacy.mdx)
- **ローカル版でも外部と通信する**: npx で動かすローカル版も `context7.com` の API を呼ぶため、外部に出さない運用にはできません。
- **API キーの扱いが文書ごとに食い違う**: プラグインが環境変数 `CONTEXT7_API_KEY` を読むかどうかについて、Upstash の文書と公式 marketplace の README で書いていることが違います（未確認）。キーを使うなら、`.mcp.json` で環境変数を参照するのが確実です。
- **月 1,000 回では足りないかもしれない**: チーム全体で使うと超えるおそれがあります。試行で 1 人・1 日あたりの呼び出し回数を測る必要があります。

**すでにあるものとの関係**: Next.js DevTools MCP の `nextjs_docs`、Cloudflare Docs MCP は、それぞれ自社製品のドキュメントだけを扱います。Context7 はそれ以外の技術を補う位置づけです。

## 2. パフォーマンス計測: Chrome DevTools MCP

**何が良くなるか**: Playwright MCP は画面の操作が中心で、表示の速さは測れません。Chrome DevTools MCP を使うと、AI が表示速度（LCP・INP・CLS などの Core Web Vitals）を計測し、遅い原因まで調べられます。

| 項目 | 内容 |
|---|---|
| 提供元 | Google（Chrome DevTools チーム） |
| リポジトリ | [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)（活発に開発中） |
| ライセンス | Apache-2.0 |
| 版 | `chrome-devtools-mcp@1.12.0`（2026-10-22 公開） |
| 入れ方 | `.mcp.json` に `npx -y chrome-devtools-mcp@1.12.0` と書く（README は `@latest` を勧めているが、このリポジトリの方針で版を固定する） |
| 認証 | 不要 |
| 主な機能 | パフォーマンスの計測と原因の分析、ネットワークの調査、Lighthouse（アクセシビリティ・SEO）、CPU・回線速度を遅くした状態の再現、メモリの解析 |

**注意点**

- **Google への利用統計の送信が既定で有効**: `--no-usage-statistics` で止めます。
- **計測したページの URL を Google の CrUX API に送ることがある**: 社内の URL を外に出さないため、`--no-performance-crux` を付けます。
- **前回のブラウザの状態が残る**: 既定ではブラウザのプロファイルを使い続けます。`--isolated` を付けると、毎回使い捨てのプロファイルで動きます。
- **Playwright MCP と機能が一部重なる**: 画面操作・スクリーンショット・コンソールの確認は両方にあります。両方入れると AI が使うツールの数が増えるため、使い分けを試行で確かめます。
- **使えるブラウザ**: 対象は Chrome / Chrome for Testing だけです。

推奨する設定の例:

```json
"chrome-devtools": {
  "command": "npx",
  "args": ["-y", "chrome-devtools-mcp@1.12.0", "--no-usage-statistics", "--no-performance-crux", "--isolated"]
}
```

## 3. DB 設計・SQL: Supabase Postgres Best Practices

**何が良くなるか**: Supabase MCP は DB を操作するための道具で、スキーマ設計やクエリの良し悪しを判断する知識は持っていません。この Skill を入れると、インデックス、RLS（行単位のアクセス制御）、ロック、接続管理などの定石に沿って設計・レビューできます。Supabase 以外の Postgres にも使えます。

| 項目 | 内容 |
|---|---|
| 提供元 | Supabase |
| リポジトリ | [supabase/agent-skills](https://github.com/supabase/agent-skills)（最終コミット 2026-10-02、最新リリース v0.1.9） |
| ライセンス | MIT |
| 中身 | `skills/supabase-postgres-best-practices`。Markdown の参照文書 約 30 件で、スクリプトは含まない。8 分野: クエリ性能、接続管理、スキーマ設計、ロック、セキュリティ・RLS、データアクセス、監視、高度な機能 |
| 入れ方 | このリポジトリの方針に合わせ、固定コミットから vendoring する |
| 認証・外部送信 | なし |

- 同じリポジトリには Supabase 全般を扱う `skills/supabase` もあります。こちらは Supabase MCP と役割が重なるかを確かめてから判断します。
- 追加先は、既存の `supabase` stack に足すか、`postgres` stack を新しく作るかのどちらかです。Supabase 以外の Postgres を使う案件があるなら後者が向いています。
- ほかの候補として Neon の [neondatabase/agent-skills](https://github.com/neondatabase/agent-skills) もありますが、Neon 専用です。汎用の Postgres 設計の知識としては Supabase のものが最有力です。

## 4. TypeScript 以外の言語: LSP プラグイン

**何が良くなるか**: LSP を入れると、AI がコードを編集したときに型エラーや参照先をすぐ確かめられます。TypeScript では導入済みです。

公式 marketplace（[anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)）に、Anthropic 製の LSP プラグインが言語ごとにあります。どれも認証は不要で、言語サーバー本体を別に入れる必要があります。

| プラグイン | 言語 | 別に入れる言語サーバー |
|---|---|---|
| `pyright-lsp` | Python | `pyright`（`npm i -g pyright` など） |
| `gopls-lsp` | Go | `gopls` |
| `rust-analyzer-lsp` | Rust | `rust-analyzer` |
| `jdtls-lsp` | Java | `jdtls` |
| `kotlin-lsp` | Kotlin | `kotlin-lsp` |
| `csharp-lsp` | C# | `csharp-ls` |
| `php-lsp` | PHP | `intelephense` |
| `ruby-lsp` | Ruby | `ruby-lsp` |
| `swift-lsp` | Swift | `sourcekit-lsp` |
| `clangd-lsp` | C / C++ | `clangd` |
| `lua-lsp` | Lua | `lua-language-server` |

- 全部を先に用意する必要はありません。その言語を使う案件が出たときに、`scripts/add-stack.sh` に stack（例: `python`、`go`）を足します。足し方は `typescript` と同じです。

## 次にやること

1. Context7 と Chrome DevTools MCP を `scripts/poc-profile.sh` で一時的に有効にして試し、次を記録する。
   - 効果（古い書き方が減るか、遅いページを見つけられるか）
   - 費用（呼び出し回数）
   - Playwright MCP との使い分け
2. Supabase Postgres Best Practices は試行の負担が小さいので、`supabase` stack に足す PR を作る。
3. LSP は、該当する言語の案件が出た時点で追加する。
