#!/usr/bin/env bash
# 採用技術・利用サービスに応じた Skills / MCP をプロジェクトに追加する（何度実行しても同じ結果になる）。
# 使い方: scripts/add-stack.sh [--dest <対象リポジトリのパス>] <stack>...
#   --dest を省略すると、このリポジトリ自身に追加する
#   react-nextjs : Vercel の React / Next.js 向け Skills + Next.js DevTools MCP
#   sentry       : Sentry MCP（リモート、OAuth）
#   cloudflare   : Cloudflare API MCP + Cloudflare Docs MCP（リモート、OAuth / 認証なし）
#   supabase     : Supabase MCP（リモート、OAuth。開発用プロジェクトに限定）
#   vercel       : Vercel MCP（リモート、OAuth）
#   typescript   : TypeScript LSP プラグイン（typescript-language-server が必要）
# 実行後は Claude Code を再起動し、/mcp で接続・認証を確認すること。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERCEL_SKILLS_REF="1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62" # vercel-labs/agent-skills
NEXT_DEVTOOLS_MCP_VERSION="0.4.0"                         # vercel/next-devtools-mcp

DEST="$ROOT"
if [[ "${1:-}" == --dest ]]; then
  DEST="$(cd "${2:?--dest にパスを指定してください}" && pwd)"
  shift 2
fi

[[ $# -gt 0 ]] || { sed -n '2,12p' "$0"; exit 1; }

# .mcp.json にサーバーを追加し、.claude/settings.json の enabledMcpjsonServers に登録する
add_mcp() { # name json
  python3 - "$DEST" "$1" "$2" <<'PY'
import json, sys, pathlib
root, name, server = pathlib.Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])
mcp = root / ".mcp.json"
d = json.loads(mcp.read_text()) if mcp.exists() else {"mcpServers": {}}
d.setdefault("mcpServers", {})[name] = server
mcp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
st = root / ".claude" / "settings.json"
s = json.loads(st.read_text())
enabled = s.setdefault("enabledMcpjsonServers", [])
if name not in enabled:
    enabled.append(name)
st.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
print(f"MCP: {name} を追加")
PY
}

# .claude/settings.json の enabledPlugins にプラグインを登録する
add_plugin() { # plugin@marketplace
  python3 - "$DEST" "$1" <<'PY2'
import json, sys, pathlib
root, plugin = pathlib.Path(sys.argv[1]), sys.argv[2]
st = root / ".claude" / "settings.json"
s = json.loads(st.read_text())
s.setdefault("enabledPlugins", {})[plugin] = True
st.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
print(f"Plugin: {plugin} を有効化")
PY2
}

vendor_vercel_skills() { # skill...
  local work; work="$(mktemp -d)"
  git init -q "$work/repo"
  git -C "$work/repo" remote add origin https://github.com/vercel-labs/agent-skills.git
  git -C "$work/repo" fetch -q --depth 1 origin "$VERCEL_SKILLS_REF"
  git -C "$work/repo" checkout -q FETCH_HEAD
  for s in "$@"; do
    mkdir -p "$DEST/.claude/skills"
    rm -rf "${DEST:?}/.claude/skills/$s"
    cp -R "$work/repo/skills/$s" "$DEST/.claude/skills/$s"
    echo "Skill: $s を配置 (vercel-labs/agent-skills@$VERCEL_SKILLS_REF)"
  done
  rm -rf "$work"
  # vendored Skills の指紋を作り直す（scripts/check-skills.py が手での編集を検出するのに使う）
  if [[ -f "$DEST/scripts/check-skills.py" ]]; then
    python3 "$DEST/scripts/check-skills.py" --update-lock
  fi
}

for stack in "$@"; do
  case "$stack" in
    react-nextjs)
      vendor_vercel_skills react-best-practices composition-patterns react-view-transitions
      # Next.js 16 以上の dev server（next dev）が起動している必要がある
      add_mcp next-devtools "{\"type\":\"stdio\",\"command\":\"npx\",\"args\":[\"-y\",\"next-devtools-mcp@$NEXT_DEVTOOLS_MCP_VERSION\"]}"
      ;;
    sentry)
      # 認証は初回接続時の OAuth（/mcp から実行）。トークンをファイルに書かない
      add_mcp sentry '{"type":"http","url":"https://mcp.sentry.dev/mcp"}'
      ;;
    cloudflare)
      # API サーバーは OAuth。開発用アカウントで、必要最小限の権限だけを許可すること
      add_mcp cloudflare '{"type":"http","url":"https://mcp.cloudflare.com/mcp"}'
      add_mcp cloudflare-docs '{"type":"http","url":"https://docs.mcp.cloudflare.com/mcp"}'
      ;;
    supabase)
      # 開発用プロジェクトだけに限定する（SUPABASE_PROJECT_REF に開発用の project ref を設定）。
      # 本番プロジェクトに接続する場合は URL に &read_only=true を付けること
      add_mcp supabase '{"type":"http","url":"https://mcp.supabase.com/mcp?project_ref=${SUPABASE_PROJECT_REF}"}'
      ;;
    vercel)
      # 認証は OAuth。特定プロジェクトに限定する場合は https://mcp.vercel.com/<team-slug>/<project-slug> に変更する
      add_mcp vercel '{"type":"http","url":"https://mcp.vercel.com"}'
      ;;
    typescript)
      add_plugin typescript-lsp@claude-plugins-official
      command -v typescript-language-server >/dev/null 2>&1 \
        || echo "注意: typescript-language-server が見つかりません。npm install -g typescript-language-server typescript を実行してください"
      ;;
    *) echo "unknown stack: $stack" >&2; exit 1 ;;
  esac
done
echo "完了。Claude Code を再起動し、/mcp で接続と認証を確認してください。"
