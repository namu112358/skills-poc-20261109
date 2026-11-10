#!/usr/bin/env bash
# 開発ワークフローの試行を 1 回実行する。
# 使い方: scripts/poc/run-trial.sh <シナリオ> <候補> <回>
#   候補: baseline | superpowers | feature-dev | compound-engineering | gstack
#         | baseline-conventions（W12 で追加。候補なしで、作業用コピーの CLAUDE.md の末尾に開発規約だけを足す）
#   （gstack の setup 実行は 2026-11-09 にユーザーの許可を得た。専用 HOME の中だけで実行する）
# 作業用コピー（既定は /tmp/poc-trials/<ID>。POC_TRIAL_ROOT で変更可）で、専用の HOME を使って Claude Code をヘッドレスで起動する。
# 作業用コピーをリポジトリの外に置くのは、正解データ（docs/poc/answer-key/）や他の試行の結果へ相対パスで辿れないようにするため。
# 置き場所は raw/<ID>/workdir に記録し、grade.py はそこを読む（記録がなければ旧来の .poc-work/trials/<ID>）。
# W7 の 2 段階目以降（W7b、後から足す W7c〜W7e など）は新しい作業用コピーを作らず、1 つ前の段階の作業用コピー
#（それまでの変更を含む app）と専用 HOME をそのまま使う（既定は同じ候補・同じ回の 1 つ前の段階。W7b なら W7a。
# POC_CONTINUE_FROM=<試行 ID> で指定できる）。docs/poc/tasks/wf-procedures.md の「W7 の決まり」。
# 対照（POC_W7_CONTROL=1）: 前の段階を引き継がず、新しい作業用コピーに、前の段階までの参照実装を当てた状態から始める
#（候補の記憶が無いときとの差を見るため）。
# 子セッションの権限は docs/poc/tasks/wf-procedures.md の「権限」のとおり（全許可にはしない）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCENARIO="$1"; CAND="$2"; RUN="$3"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
MODEL="${POC_MODEL:-claude-sonnet-5-5}"
ID="$SCENARIO-$CAND-$RUN"
TRIALS="${POC_TRIAL_ROOT:-/tmp/poc-trials}"
WORK="$TRIALS/$ID"
CONTINUE_FROM=""
W7_CONTROL=""
if [[ "$SCENARIO" =~ ^W7([b-z])$ ]]; then
  if [[ "${POC_W7_CONTROL:-}" == 1 ]]; then
    W7_CONTROL=1
  else
    PREV_STAGE="W7$(printf "\\$(printf '%03o' $(( $(printf '%d' "'${BASH_REMATCH[1]}") - 1 )))")"
    CONTINUE_FROM="${POC_CONTINUE_FROM:-$PREV_STAGE-$CAND-$RUN}"
    WORK="$TRIALS/$CONTINUE_FROM"
    [[ -d "$WORK/app/.git" && -d "$WORK/home" ]] || { echo "$SCENARIO: 引き継ぐ前の段階の作業用コピーがない: $WORK" >&2; exit 1; }
  fi
fi
APP="$WORK/app"
HOME_DIR="$WORK/home"
OUT="$ROOT/docs/poc/results/workflow/raw/$ID"

if [[ -n "$CONTINUE_FROM" ]]; then
  rm -rf "$OUT"; mkdir -p "$OUT"
  echo "$CONTINUE_FROM" > "$OUT/continued-from"
else
  rm -rf "$WORK" "$OUT"; mkdir -p "$APP" "$HOME_DIR" "$OUT"
fi
echo "$WORK" > "$OUT/workdir"
[[ -n "$W7_CONTROL" ]] && echo 1 > "$OUT/control"

# 1) 評価用アプリのコピー（node_modules を含む）と、常時有効な Skills・MCP
# POC_APP_SRC: コピー元の評価用アプリ（既定は $ROOT/poc-app）。W1 を当時の poc-app（ログイン・SQLite の追加前）で
# 再試行するときなどに、その版を取り出したディレクトリを指定する。使ったコピー元は raw/<ID>/app-src に記録する。
APP_SRC="${POC_APP_SRC:-$ROOT/poc-app}"
[[ -n "${POC_APP_SRC:-}" ]] && echo "$APP_SRC" > "$OUT/app-src"
if [[ -n "$CONTINUE_FROM" ]]; then
  # W7b: W7a の終了時点（コミット済み）を baseline にし、W7b の作業ブランチを切る。アプリのコピー・パッチ・Skills の配置はしない
  git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
  git -C "$APP" switch -q -c "poc/wf/$CAND/$SCENARIO/$RUN"
else
if [[ "$SCENARIO" == W11-* ]]; then
  # W11（実在する OSS の解決済み課題）: scripts/poc/oss/oss.py prepare で作った初期状態（修正の 1 つ前のソース。履歴なし）を写す。
  # node_modules はハードリンク、python の課題は $WORK/venv に環境を作る（app の外なので git に入らない）。
  # 本家の履歴・修正後のコード・隠しテストは作業用コピーに置かない（docs/poc/tasks/wf-W11-design.md）。
  OSS_TASK="${SCENARIO#W11-}"
  python3 "$ROOT/scripts/poc/oss/oss.py" copy-app "$OSS_TASK" "$APP" "$WORK" > "$OUT/oss-setup.log" 2>&1
else
cp -a "$APP_SRC/." "$APP/"
rm -rf "$APP/.next" "$APP"/*.tsbuildinfo
fi
mkdir -p "$APP/.claude/skills"
cp -a "$ROOT/.claude/skills/." "$APP/.claude/skills/"
rm -f "$APP/.claude/skills/SOURCES.md"
cat > "$APP/.mcp.json" <<'JSON'
{"mcpServers":{
  "playwright":{"type":"stdio","command":"npx","args":["-y","@playwright/mcp@0.0.84"]},
  "next-devtools":{"type":"stdio","command":"npx","args":["-y","next-devtools-mcp@0.4.0"]}}}
JSON
# W5（バグ修正）: 仕込みバグのパッチ（正解データ）を作業用コピーにだけ当ててから baseline コミットを作る。
# バグは baseline の一部になるので、候補からは差分として見えない。パッチファイル自体は作業用コピーに置かない。
# W7a: 落とし穴の決まり（日時・エラー型）を含む既存機能の初期状態（answer-key/W7/base.patch）を同じように当てる。
# W5・W7a 以外は既定で当てない（POC_INJECT_PATCH で明示したときだけ当てる）。
INJECT="${POC_INJECT_PATCH:-}"
[[ -z "$INJECT" && "$SCENARIO" == W5 ]] && INJECT="$ROOT/docs/poc/answer-key/W5/bugs.patch"
[[ -z "$INJECT" && "$SCENARIO" == W7a ]] && INJECT="$ROOT/docs/poc/answer-key/W7/base.patch"
# W12: 題材（計測器の校正台帳）の初期状態を当てる（docs/poc/tasks/wf-W12-design.md）
[[ -z "$INJECT" && "$SCENARIO" == W12 ]] && INJECT="$ROOT/docs/poc/answer-key/W12/base.patch"
# W13: 同じ題材の初期状態（W12 の base.patch の写し。docs/poc/tasks/wf-W13-design.md）
[[ -z "$INJECT" && "$SCENARIO" == W13 ]] && INJECT="$ROOT/docs/poc/answer-key/W13/base.patch"
# W14・W15: 同じ題材に、その W に必要なものを足した初期状態（docs/poc/tasks/wf-W14-design.md・wf-W15-design.md）
[[ -z "$INJECT" && ( "$SCENARIO" == W14 || "$SCENARIO" == W15 ) ]] && INJECT="$ROOT/docs/poc/answer-key/$SCENARIO/base.patch"
# W7 の対照: 初期状態 + 前の段階までの参照実装（例: W7b なら base.patch:reference-W7a.patch）。POC_INJECT_PATCH は : 区切りで複数書ける
if [[ -z "$INJECT" && -n "$W7_CONTROL" ]]; then
  INJECT="$ROOT/docs/poc/answer-key/W7/base.patch"
  for s in a b c d e f g h; do
    [[ "W7$s" == "$SCENARIO" ]] && break
    INJECT="$INJECT:$ROOT/docs/poc/answer-key/W7/reference-W7$s.patch"
  done
fi
( cd "$APP" && git init -q )
if [[ -n "$INJECT" ]]; then
  IFS=: read -r -a INJECTS <<< "$INJECT"
  : > "$OUT/injected-patch"
  for pf in "${INJECTS[@]}"; do
    git -C "$APP" apply "$pf"
    sha256sum "$pf" | sed "s#$ROOT/##" >> "$OUT/injected-patch"
  done
fi
# baseline-conventions（W12 で追加した条件）: 候補のプラグインなしで、CLAUDE.md の末尾に開発規約（固定の文言）だけを足す。
# 規約は初期状態の一部になるので、候補からは差分として見えない。
if [[ "$CAND" == baseline-conventions ]]; then
  cat "$ROOT/docs/poc/tasks/wf-$SCENARIO-conventions.md" >> "$APP/CLAUDE.md"
  sha256sum "$ROOT/docs/poc/tasks/wf-$SCENARIO-conventions.md" | sed "s#$ROOT/##" > "$OUT/conventions"
fi
# W14・W15: W13 と同じく、全条件の作業用コピーで、アプリの CLAUDE.md の末尾に汎用の開発標準を足す
# （2026-11-10 コーディネーターの連絡・ユーザー承認。W13 の分岐とぶつからないよう別に足した）
if [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]]; then
  STD="$ROOT/docs/poc/standards/generic-dev-standard.md"
  { echo; sed '1,/^-->$/d' "$STD"; } >> "$APP/CLAUDE.md"
  sha256sum "$STD" | sed "s#$ROOT/##" > "$OUT/dev-standard"
fi
( cd "$APP" && git add -A && git -c user.name=poc -c user.email=poc@example.invalid commit -qm baseline )
git -C "$APP" config user.name poc
git -C "$APP" config user.email poc@example.invalid
git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
# 試行は作業ブランチの上で始める（W2 以降。W1 で gstack の /review が master 直コミットのため差分なしで止まったため）
#（W1 は master のまま。W1 の手順を同じ条件で再実行できるようにするため）
[[ "$SCENARIO" != W1 ]] && git -C "$APP" switch -q -c "poc/wf/$CAND/$SCENARIO/$RUN"
# W9（レビューで不具合を見つける）: レビュー対象の差分（正解データ docs/poc/answer-key/W9/review.patch）を
# 作業ブランチにだけ当て、PR の説明（課題文の「# PR:」以降）をメッセージにしたコミットを作る。候補は master との差分をレビューする。
# パッチファイル自体は作業用コピーに置かない。baseline-commit はレビュー対象のコミットにする（候補が書いた REVIEW.md などだけが成果の差分になる）。
# W9 以外では何もしない。
if [[ "$SCENARIO" == W9 ]]; then
  REVIEW_PATCH="${POC_REVIEW_PATCH:-$ROOT/docs/poc/answer-key/W9/review.patch}"
  git -C "$APP" apply "$REVIEW_PATCH"
  sha256sum "$REVIEW_PATCH" | sed "s#$ROOT/##" > "$OUT/review-patch"
  git -C "$APP" rev-parse HEAD > "$OUT/review-base-commit"
  sed -n '/^# PR:/,$p' "$ROOT/docs/poc/tasks/wf-W9.md" | sed '1s/^# PR: //' > "$WORK/review-commit-msg"
  ( cd "$APP" && git add -A && git commit -q -F "$WORK/review-commit-msg" )
  rm -f "$WORK/review-commit-msg"
  git -C "$APP" rev-parse HEAD > "$OUT/baseline-commit"
fi
fi

# 2) 必須プラグイン + 候補プラグイン（すべて固定コミット。scripts/poc/fetch-plugins.sh で取得）
#    Skill が自分の参照ファイル（references/*.md など）を読めるよう、試行ごとの作業領域にコピーして
#    --add-dir で読み取りを許可する（コピーなので、書き換えられても他の試行には影響しない）。
PLUG="$WORK/plugins"; mkdir -p "$PLUG"
PLUG_EXTRA=()
CPO="$CACHE/claude-plugins-official/plugins"
copy_plugin() {  # W7b は W7a でコピーしたものをそのまま使う
  [[ -n "$CONTINUE_FROM" && -d "$PLUG/$2" ]] || { cp -a "$1" "$PLUG/$2"; rm -rf "$PLUG/$2/.git"; }
  PLUGINS+=(--plugin-dir "$PLUG/$2")
}
PLUGINS=()
copy_plugin "$CPO/security-guidance" security-guidance
copy_plugin "$CPO/typescript-lsp" typescript-lsp
copy_plugin "$CACHE/impeccable/plugin" impeccable
copy_plugin "$CACHE/ui-ux-pro-max" ui-ux-pro-max
case "$CAND" in
  baseline|baseline-conventions) ;;
  superpowers) copy_plugin "$CACHE/superpowers" superpowers ;;
  feature-dev) copy_plugin "$CPO/feature-dev" feature-dev ;;
  compound-engineering) copy_plugin "$CACHE/compound-engineering" compound-engineering ;;
  gstack)
    # gstack は marketplace 配布ではないため、試行ごとの専用 HOME の ~/.claude/skills/gstack に固定コミットを置き、
    # setup を実行する（チーム用の自動更新フックなし・plan-tune フックなし）。
    # ブラウザ（Chrome for Testing）は環境のネットワーク制限で取得できないため --no-browser。
    GSTACK="$HOME_DIR/.claude/skills/gstack"
    if [[ -n "$CONTINUE_FROM" ]]; then
      # W7b: W7a で入れた gstack と、その状態・学習データ（専用 HOME）をそのまま使う
      [[ -x "$GSTACK/bin/gstack-config" ]] || { echo "W7b: W7a の gstack がない: $GSTACK" >&2; exit 1; }
      PLUG_EXTRA=(--add-dir "$GSTACK")
    else
    mkdir -p "$HOME_DIR/.claude/skills"
    cp -a "$CACHE/gstack" "$GSTACK"
    ( cd "$GSTACK" && HOME="$HOME_DIR" ./setup --host claude --no-team --no-plan-tune-hooks --no-browser --quiet ) > "$OUT/gstack-setup.log" 2>&1
    # 外部送信を止める（更新確認、Codex への外部レビュー）。テレメトリーは初期値 off のまま
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" set update_check false >> "$OUT/gstack-setup.log" 2>&1
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" set codex_reviews disabled >> "$OUT/gstack-setup.log" 2>&1
    HOME="$HOME_DIR" "$GSTACK/bin/gstack-config" get telemetry >> "$OUT/gstack-setup.log" 2>&1
    PLUG_EXTRA=(--add-dir "$GSTACK")
    fi
    ;;
  *) echo "unknown candidate: $CAND" >&2; exit 1 ;;
esac

# 3) 権限（全許可にはしない）
ALLOWED=(
  "Bash(npm run typecheck)" "Bash(npm test)" "Bash(npm run test)" "Bash(npm run build)"
  "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git branch:*)" "Bash(git rev-parse:*)"
  "Bash(git switch:*)" "Bash(git checkout:*)" "Bash(git -C:*)" "Bash(git check-ignore:*)"
  "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(find:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
  "Bash(cd:*)" "Bash(mkdir:*)" "Bash(sleep:*)"
  # 候補プラグイン自身のスクリプト（試行ごとのコピー）
  "Bash(python3 $PLUG/:*)" "Bash(bash $PLUG/:*)" "Bash(node $PLUG/:*)"
)
if [[ "$SCENARIO" != W11-* ]]; then
  # W11 は外部への接続（本家の修正の参照）を避けるため curl を許可しない。next は W11 では使わない
  ALLOWED+=("Bash(curl -s:*)" "Bash(npx next:*)")
fi
CHILD_ENV=()
if [[ "$SCENARIO" == W11-* ]]; then
  # W11: 課題のテストと、再現用のスクリプトの実行を許可する（2026-11-09 ユーザー承認）。依存のインストールは許可しない。
  ALLOWED+=(
    "Bash(python:*)" "Bash(python3:*)" "Bash(pytest:*)" "Bash(timeout * python*)"
    "Bash(node:*)" "Bash(npx vitest:*)" "Bash(npx tsx:*)" "Bash(npx tsc:*)" "Bash(timeout * node*)" "Bash(timeout * npx*)"
    "Bash(pnpm test:*)" "Bash(pnpm vitest:*)" "Bash(pnpm exec vitest:*)" "Bash(pnpm exec tsx:*)" "Bash(pnpm exec tsc:*)"
  )
  # python の課題: 試行ごとの環境（$WORK/venv）の python・pytest を使わせる
  [[ -x "$WORK/venv/bin/python" ]] && CHILD_ENV=(PATH="$WORK/venv/bin:$PATH" VIRTUAL_ENV="$WORK/venv")
  # zod の課題（B3・F1）: CLAUDE.md が指示する nub の代替（scripts/poc/oss/nub-shim）を PATH に入れ、nub の実行を許可する。
  # 代替は事前に入れた依存だけで動き、依存の変更と知らないサブコマンドは拒否する（2026-11-09 コーディネーター承認）
  if [[ -x "$WORK/bin/nub" ]]; then
    CHILD_ENV=(PATH="$WORK/bin:$PATH")
    ALLOWED+=("Bash(nub:*)" "Bash(timeout * nub*)")
  fi
fi
if [[ "$CAND" == gstack ]]; then
  # gstack 自身のコマンド（~/.claude/skills/gstack/bin/*）
  ALLOWED+=("Bash($GSTACK/bin/:*)" "Bash(~/.claude/skills/gstack/bin/:*)" "Bash(bun $GSTACK/:*)")
fi
# W6 以降（UI 実装からブラウザ検証まで）: 開発サーバーの起動とブラウザ操作を許可する（2026-11-09 追加）。
# W1〜W5 は比較の条件を揃えるため従来の許可リストのまま。サーバーは試行後に reap_servers が止める。
SCN_NUM="${SCENARIO#W}"; SCN_NUM="${SCN_NUM%%[a-z-]*}"
# W7 は除く: W7 の試行は、この許可の追加が main に入る前に現行の許可リストで始めたため、
# 対照も含めて同じ許可リストのまま行う（W7 の report.md「判断の記録」）。
# W11 は OSS のライブラリが対象なので、開発サーバー・ブラウザの許可は足さない
if [[ "$SCN_NUM" -ge 6 && "$SCN_NUM" != 7 && "$SCN_NUM" != 11 ]]; then
  ALLOWED+=(
    "Bash(npm run dev)" "Bash(npm run dev:*)" "Bash(npm run start)" "Bash(npm run start:*)"
    "Bash(timeout * npm run dev*)" "Bash(timeout * npm run start*)" "Bash(timeout * npx next *)"
    # npm start（npm run start の別名）と、ポートを環境変数で渡す形（PORT=3100 npm run start など）。
    # 2026-11-09 の最初の試行でこの形が漏れていて、2 試行がサーバーを起動できなかったため追加した
    "Bash(npm start)" "Bash(npm start:*)" "Bash(PORT=* npm start*)" "Bash(PORT=* npm run start*)"
    "Bash(PORT=* npm run dev*)" "Bash(PORT=* npx next *)"
    # ブラウザ: Playwright MCP（全候補共通。事前インストール済みの Chromium を使う）と Next.js DevTools MCP
    "mcp__playwright" "mcp__next-devtools"
  )
  if [[ "$CAND" == gstack ]]; then
    # gstack のブラウザ（browse）。Chrome for Testing は取得できないので、事前インストール済みの Chromium を使わせる
    ALLOWED+=("Bash($GSTACK/browse/dist/:*)" "Bash(~/.claude/skills/gstack/browse/dist/:*)")
  fi
  CHILD_ENV+=(GSTACK_CHROMIUM_PATH=/opt/pw-browsers/chromium)
  # 子セッションが起動したサーバー・ブラウザが試行後に残らないよう、終了時にも止める（reap_servers は下で定義）
  trap 'declare -F reap_servers >/dev/null && reap_servers end' EXIT
fi
# W12: 依頼者への質問コマンド ask-po を作業用コピーの外（$WORK/bin）に置き、子セッションの PATH に入れて実行を許可する
#（2026-11-10 コーディネーター承認。CLAUDE.md の例外: 子セッションの許可リストの変更）。依頼者役は下で裏に起動する。
if [[ "$SCENARIO" == W12 ]]; then
  mkdir -p "$WORK/bin"
  cp "$ROOT/scripts/poc/ask-po" "$WORK/bin/ask-po"
  chmod +x "$WORK/bin/ask-po"
  ALLOWED+=("Bash(ask-po:*)" "Bash(ask-po *)")
  CHILD_ENV+=(PATH="$WORK/bin:$PATH")
fi
# W13: W12 と同じ ask-po（依頼者役は answer_w13.py）。許可リストへの追加は ask-po だけ（2026-11-10 コーディネーター承認）
if [[ "$SCENARIO" == W13 ]]; then
  mkdir -p "$WORK/bin"
  cp "$ROOT/scripts/poc/ask-po" "$WORK/bin/ask-po"
  chmod +x "$WORK/bin/ask-po"
  ALLOWED+=("Bash(ask-po:*)" "Bash(ask-po *)")
  CHILD_ENV+=(PATH="$WORK/bin:$PATH")
fi
# W14・W15: W12 と同じ ask-po（依頼者役は answer_persona.py。回答シートは answer-key/<W>/persona.md）。
# 許可リストへの追加は ask-po だけ（2026-11-10 コーディネーター承認）
if [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]]; then
  mkdir -p "$WORK/bin"
  cp "$ROOT/scripts/poc/ask-po" "$WORK/bin/ask-po"
  chmod +x "$WORK/bin/ask-po"
  ALLOWED+=("Bash(ask-po:*)" "Bash(ask-po *)")
  CHILD_ENV+=(PATH="$WORK/bin:$PATH")
fi

# 4) 手順（docs/poc/tasks/wf-procedures.md）
if [[ "$SCENARIO" == W3 ]]; then
  # W3 は質問に定型回答シートで答える（docs/poc/tasks/wf-answers.md の「W3」）。末尾の定型文もそれに合わせる。
  TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

この作業は無人で実行しています。質問には、依頼者の代わりに定型の回答シートから答えます（シートに無いことは「お任せします」と答えます）。"
else
  # 末尾の定型文（2026-11-09 変更）。旧文言では Feature Dev が「無人のため」と調査・設計・レビューの工程を省いたため、
  # W4 以降は工程を省かないよう明記した新文言にする。W1・W2 は再現性のため旧文言が既定。
  # POC_TASK_SUFFIX=old|new で明示的に切り替えられる（W1・W2 の新文言での再試行など）。
  SUFFIX_MODE="${POC_TASK_SUFFIX:-}"
  if [[ -z "$SUFFIX_MODE" ]]; then
    case "$SCENARIO" in W1|W2) SUFFIX_MODE=old ;; W12) SUFFIX_MODE=w12 ;; *) SUFFIX_MODE=new ;; esac
    # W13 も依頼者に質問できるので W12 と同じ文言
    [[ "$SCENARIO" == W13 ]] && SUFFIX_MODE=w12
    # W14・W15 も依頼者（品質保証部の担当者）に質問できるので同じ文言
    [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]] && SUFFIX_MODE=w12
  fi
  case "$SUFFIX_MODE" in
    # W12: 依頼者に質問できることを伝える（ask-po と、メッセージでの質問の両方）。工程を省かないことは新文言と同じ
    w12) SUFFIX="この作業は無人で実行しています。依頼者（品質保証部の担当者）に確認したいことがあれば、作業中いつでも ask-po \"<質問>\" コマンドで質問できます（依頼者が答えます。決まっていないことは「お任せします」と返ります）。作業の区切りで、最後のメッセージに依頼者への質問を書いても答えます。ツールの手順にある工程（調査・設計・レビューなど）は省かずに進めてください。作業が終わったら、変更内容を git にコミットしてください。" ;;
    old) SUFFIX="この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことはお任せします。作業が終わったら、変更内容を git にコミットしてください。" ;;
    new) SUFFIX="この作業は無人で実行しています。確認の質問には答えられないので、課題文に書かれていないことの判断はお任せしますが、ツールの手順にある工程（調査・設計・レビューなど）は省かずに進めてください。作業が終わったら、変更内容を git にコミットしてください。" ;;
    *) echo "POC_TASK_SUFFIX は old・new・w12 のいずれか: $SUFFIX_MODE" >&2; exit 1 ;;
  esac
  echo "$SUFFIX_MODE" > "$OUT/task-suffix"
  TASK="$(cat "$ROOT/docs/poc/tasks/wf-$SCENARIO.md")

$SUFFIX"
fi
EXTRA=()
if [[ "$SCENARIO" == W3 ]]; then
  # 質問はメッセージ本文で受け、回答役（answer_w3.py）が次のステップで返す。質問ツールは無人では答えられないので外す。
  EXTRA=(--disallowedTools AskUserQuestion)
  case "$CAND" in
    baseline|superpowers) STEPS=("$TASK") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
    compound-engineering) STEPS=("/ce-brainstorm $TASK") ;;
    gstack) STEPS=("/office-hours $TASK" "/plan-ceo-review") ;;
  esac
else
  case "$CAND" in
    baseline|baseline-conventions|superpowers) STEPS=("$TASK") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
    compound-engineering) STEPS=("/ce-plan $TASK" "/ce-work" "/ce-code-review") ;;
    gstack) STEPS=("$TASK" "/review") ;;
  esac
  # W12: 質問はメッセージ本文か ask-po で受ける。質問ツールは無人では答えられないので外す（W3 と同じ）
  [[ "$SCENARIO" == W12 ]] && EXTRA=(--disallowedTools AskUserQuestion)
  [[ "$SCENARIO" == W13 ]] && EXTRA=(--disallowedTools AskUserQuestion)
  [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]] && EXTRA=(--disallowedTools AskUserQuestion)
fi
# W7a の後の手順（Compound Engineering は学んだことを残す /ce-compound。落とし穴の指摘のやり取りが終わってから行う）
POST_STEPS=()
# 後から段階を足すときは、最後の段階を除く各段階の後に行う（POC_W7_LAST_STAGE。既定は W7b）
[[ "$SCENARIO" =~ ^W7[a-z]$ && "$SCENARIO" < "${POC_W7_LAST_STAGE:-W7b}" && "$CAND" == compound-engineering ]] && POST_STEPS=("/ce-compound")
# W4 の gstack は /autoplan → 実装 → /review（PLAN.md §5.1。ほかのシナリオの手順は変えない）
if [[ "$SCENARIO" == W4 && "$CAND" == gstack ]]; then
  STEPS=("/autoplan $TASK" "計画に沿って実装し、変更を git にコミットしてください。" "/review")
fi
if [[ "$SCENARIO" == W6 ]]; then
  # W6 の手順（docs/poc/tasks/wf-procedures.md）。PR はリモートが無いので PR.md に書かせる（課題文に明記）。
  PR_STEP="PR を作成してください（課題文の「確認と PR」のとおり、PR のタイトルと本文を PR.md に書いてコミットします）。"
  case "$CAND" in
    baseline) STEPS=("$TASK") ;;
    superpowers) STEPS=("$TASK" "/superpowers:finishing-a-development-branch") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK" "$PR_STEP") ;;
    compound-engineering) STEPS=("/ce-work $TASK" "/ce-test-browser" "/ce-commit-push-pr") ;;
    gstack) STEPS=("$TASK" "/qa" "/ship") ;;
  esac
fi
if [[ "$SCENARIO" == W8 ]]; then
  # W8（人の介入なしでの自律実行）の手順（docs/poc/tasks/wf-procedures.md・PLAN.md §5.1 の W8 の行）。
  # 介入（「お任せします」）は既定 0 回（POC_MAX_NUDGES の既定どおり）。最初の指示と手順のコマンド以外は送らない。
  case "$CAND" in
    baseline) STEPS=("$TASK") ;;
    superpowers) STEPS=("/superpowers:writing-plans $TASK" "/superpowers:subagent-driven-development") ;;
    feature-dev) STEPS=("/feature-dev:feature-dev $TASK") ;;
    compound-engineering) STEPS=("/ce-brainstorm $TASK" "/lfg") ;;
    gstack) STEPS=("/autoplan $TASK" "/ship") ;;
  esac
fi
if [[ "$SCENARIO" == W5 || "$SCENARIO" == W11-B* ]]; then
  # W5 の手順（W11 の不具合の課題も同じ）（docs/poc/tasks/wf-procedures.md）。gstack は /qa、Compound Engineering は /ce-debug に課題を渡す。
  case "$CAND" in
    baseline|superpowers|feature-dev) STEPS=("$TASK") ;;
    compound-engineering) STEPS=("/ce-debug $TASK") ;;
    gstack) STEPS=("/qa $TASK") ;;
  esac
fi
if [[ "$SCENARIO" == W9 ]]; then
  # W9 の手順（docs/poc/tasks/wf-procedures.md）。各候補のレビューの入口に課題を渡す。Feature Dev はレビュー用のコマンドが
  # 無いため、code-reviewer エージェントを使うよう指示する。指摘は REVIEW.md に書かせる（課題文に明記）。
  case "$CAND" in
    baseline) STEPS=("$TASK") ;;
    superpowers) STEPS=("/superpowers:requesting-code-review $TASK") ;;
    feature-dev) STEPS=("Feature Dev の code-reviewer エージェント（feature-dev:code-reviewer）でこの差分をレビューしてください。

$TASK") ;;
    compound-engineering) STEPS=("/ce-code-review $TASK") ;;
    gstack) STEPS=("/review $TASK") ;;
  esac
fi

# 1 試行の費用の上限（米ドル。空なら上限なし）。
MAX_USD="${POC_MAX_TRIAL_USD:-}"
# 上限の守り方（POC_BUDGET_MODE）:
#   flag（W1〜W5 の既定）: 各ステップに、それまでの累計を引いた残りを --max-budget-usd で渡す。
#     この値は子セッションのモデルに「USD budget: $0/$0.9; $0.9 remaining」のように見えるため、
#     予算を意識して工程を減らすことがある（W1 の Feature Dev 再試行で確認）。
#   watch（W6 以降の既定）: --max-budget-usd を渡さず、run-trial.sh が途中のトークン使用量から費用を見積もり、
#     上限に達したら子セッションを止める。見積もりの単価は POC_RATE_*（米ドル / 100 万トークン）で変えられる。
#     正式な費用は従来どおり result の total_cost_usd。止めたときは budget-stopped に見積額を記録する。
# 既定はシナリオで決める（W1〜W5 は再現のため flag、W6 以降は watch）。POC_BUDGET_MODE で上書きできる。
BUDGET_MODE="${POC_BUDGET_MODE:-}"
if [[ -z "$BUDGET_MODE" ]]; then
  case "$SCENARIO" in W1|W2|W3|W4|W5) BUDGET_MODE=flag ;; *) BUDGET_MODE=watch ;; esac
fi
echo "$BUDGET_MODE" > "$OUT/budget-mode"
case "$BUDGET_MODE" in flag|watch) ;; *) echo "POC_BUDGET_MODE は flag か watch: $BUDGET_MODE" >&2; exit 1 ;; esac
# 介入（定型の「お任せします」で続けさせる）の上限回数。0 なら介入しない（W1 の手順）。
MAX_NUDGES="${POC_MAX_NUDGES:-0}"
NUDGE="お任せします。確認は不要なので、課題を最後まで実装し、変更を git にコミットしてください。"
# W3: 回答のやり取りの上限（試行全体の回数）と、締め切り・完了の定型文
MAX_QA="${POC_MAX_QA_ROUNDS:-10}"
QA_CLOSE="質問はここまでで締め切ります。残りはお任せします。ここまでの回答をもとに要件を REQUIREMENTS.md にまとめ、git にコミットしてください。"
[[ "$SCENARIO" == W3 ]] && NUDGE="お任せします。確認は不要なので、要件を REQUIREMENTS.md にまとめ、git にコミットしてください。"
[[ "$SCENARIO" == W5 || "$SCENARIO" == W11-B* ]] && NUDGE="お任せします。確認は不要なので、報告された不具合を最後まで直し、変更を git にコミットしてください。"
# W7: 手順を終えた後、落とし穴 2 件を判定し（scripts/poc/check_w7.py）、避けられなかったものをレビューの定型の指摘で直させる回数の上限。
# 判定にかかった時間は所要時間から除く（check-seconds）。W7 以外は 0（判定しない）。
MAX_FEEDBACK="${POC_MAX_FEEDBACK:-0}"
[[ "$SCENARIO" =~ ^W7[a-z]$ ]] && MAX_FEEDBACK="${POC_MAX_FEEDBACK:-2}"
# Claude Code 自身の自動メモリ（~/.claude/projects/<作業用コピー>/memory/）は候補の記憶の仕組みではないため、
# W7 では W7a・W7b とも全候補で止める（W7b は W7a の HOME を引き継ぐので、止めないと全候補に同じ記憶が残る）。W7 以外は既定のまま。
AUTO_MEMORY_ENV=()
if [[ "${POC_DISABLE_AUTO_MEMORY:-}" == 1 ]] || [[ -z "${POC_DISABLE_AUTO_MEMORY:-}" && "$SCENARIO" =~ ^W7[a-z]$ ]]; then
  AUTO_MEMORY_ENV=(CLAUDE_CODE_DISABLE_AUTO_MEMORY=1)
  echo 1 > "$OUT/auto-memory-disabled"
fi
[[ "$SCENARIO" == W6 ]] && NUDGE="お任せします。確認は不要なので、課題を最後まで実装し、PR.md を含めて変更を git にコミットしてください。"
[[ "$SCENARIO" == W9 ]] && NUDGE="お任せします。確認は不要なので、レビューを最後まで行い、指摘を REVIEW.md に書いて git にコミットしてください。"

session_cost() {  # これまでの全ステップの最後の result の total_cost_usd（--resume では累計）
  python3 -c '
import json, sys, glob, re
cost = 0.0
for f in sorted(glob.glob(sys.argv[1] + "/step*.jsonl"), key=lambda p: int(re.search(r"step(\d+)", p).group(1))):
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result" and d.get("total_cost_usd") is not None:
            cost = d["total_cost_usd"]
print(cost)' "$OUT"
}
over_budget() {
  [[ -s "$OUT/budget-stopped" ]] && return 0
  [[ -n "$MAX_USD" ]] && python3 -c "import sys; sys.exit(0 if $(session_cost) >= $MAX_USD * 0.98 else 1)"
}
step_estimate() {  # watch 用: 実行中のステップの費用の見積もり（それまでの result の累計 + このステップのトークン × 単価）
  python3 -c '
import json, os, sys
rate = {k: float(os.environ.get("POC_RATE_" + k.upper(), d)) / 1e6 for k, d in
        {"in": 1.87, "out": 9.96, "cache_read": 0.187, "cache_5m": 2.34, "cache_1h": 3.74}.items()}
# 途中のメッセージの usage.output_tokens は書き始め時点の値なので、出力は本文の文字数 / 3 との大きい方で見積もる
msgs = {}
for line in open(sys.argv[2]):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    m = d.get("message") or {}
    if d.get("type") != "assistant" or not m.get("usage"):
        continue
    e = msgs.setdefault(m.get("id"), {"usage": m["usage"], "chars": 0})
    e["chars"] += len(json.dumps(m.get("content") or [], ensure_ascii=False))
est = 0.0
for e in msgs.values():
    u = e["usage"]; cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0)
    w5m = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - w1h)
    out = max(u.get("output_tokens", 0), e["chars"] / 3)
    est += (u.get("input_tokens", 0) * rate["in"] + out * rate["out"]
            + u.get("cache_read_input_tokens", 0) * rate["cache_read"] + w5m * rate["cache_5m"] + w1h * rate["cache_1h"])
print(round(float(sys.argv[1]) + est, 4))' "$1" "$2"
}
first_session_id() {
  python3 -c '
import json, sys
for line in open(sys.argv[1]):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("session_id"):
        print(d["session_id"]); break' "$1"
}
reap_servers() {  # 作業用コピーを cwd にして動く next のプロセス（子セッションが起動したサーバー）を止める
  local p pid cwd cmd
  for p in /proc/[0-9]*; do
    pid="${p#/proc/}"
    cwd="$(readlink "$p/cwd" 2>/dev/null)" || continue
    [[ "$cwd" == "$APP"* ]] || continue
    cmd="$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)" || continue
    case "$cmd" in claude*|timeout*|*run-trial.sh*|*playwright-mcp*|*next-devtools-mcp*) continue ;; esac
    # next（開発サーバー）に加え、W6 以降の gstack の browse デーモンと、そのブラウザ（chrome）も止める
    if [[ "$cmd" == *next* || "$cmd" == *browse/dist/* || "$cmd" == *chrom* ]]; then
      kill "$pid" 2>/dev/null && echo "step$1 killed leftover: ${cmd:0:120}" >> "$OUT/errors.log"
    fi
  done
}
run_step() {  # run_step <番号> <プロンプト>
  local n="$1" prompt="$2" RESUME=() BUDGET=()
  [[ -n "$SESSION" ]] && RESUME=(--resume "$SESSION")
  local before; before="$(session_cost)"
  if [[ -n "$MAX_USD" && "$BUDGET_MODE" == flag ]]; then
    BUDGET=(--max-budget-usd "$(python3 -c "print(max(0.01, round($MAX_USD - $(session_cost), 2)))")")
  fi
  ( cd "$APP" && env HOME="$HOME_DIR" "${CHILD_ENV[@]}" "${AUTO_MEMORY_ENV[@]}" timeout "${POC_STEP_TIMEOUT:-2400}" claude -p "$prompt" \
      --model "$MODEL" --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" \
      --mcp-config "$APP/.mcp.json" --strict-mcp-config --add-dir "$PLUG" "${PLUG_EXTRA[@]}" \
      "${PLUGINS[@]}" "${RESUME[@]}" "${BUDGET[@]}" \
      "${EXTRA[@]}" --output-format stream-json --verbose < /dev/null ) > "$OUT/step$n.jsonl" 2> "$OUT/step$n.stderr" &
  local pid=$! waited=0
  # 子セッションがバックグラウンドで起動した開発サーバー（npx next dev など）が残ると、結果を出した後も
  # claude -p が終了待ちになる。結果が出てから 30 秒たっても終わらなければ、作業用コピーで動く next のプロセスを止める。
  while kill -0 "$pid" 2>/dev/null; do
    sleep 5
    if [[ -n "$MAX_USD" && "$BUDGET_MODE" == watch ]] && ! grep -q '"type":"result"' "$OUT/step$n.jsonl" 2>/dev/null; then
      local est; est="$(step_estimate "$before" "$OUT/step$n.jsonl")"
      if python3 -c "import sys; sys.exit(0 if $est >= $MAX_USD else 1)"; then
        echo "step$n est=\$$est limit=\$$MAX_USD" > "$OUT/budget-stopped"
        echo "step$n stopped: estimated \$$est reached budget \$$MAX_USD" >> "$OUT/errors.log"
        pkill -TERM -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null
        break
      fi
    fi
    if grep -q '"type":"result"' "$OUT/step$n.jsonl" 2>/dev/null; then
      waited=$((waited + 5))
      if [[ "$waited" -ge 30 ]]; then reap_servers "$n"; waited=-60; fi
    fi
  done
  wait "$pid" || echo "step$n exit=$?" >> "$OUT/errors.log"
  [[ -z "$SESSION" ]] && SESSION="$(first_session_id "$OUT/step$n.jsonl")"
  return 0
}

qa_answer() {  # qa_answer <ステップ> <通し番号>: 回答役に答えさせ、回答文を出す（質問が無ければ何も出さない）
  if [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]]; then
    POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_persona.py" "$SCENARIO" message "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$1" "$2"
  elif [[ "$SCENARIO" == W13 ]]; then
    POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w13.py" message "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$1" "$2"
  elif [[ "$SCENARIO" == W12 ]]; then
    POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w12.py" message "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$1" "$2"
  else
    POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w3.py" "$OUT" "$1" "$2"
  fi
}
qa_loop() {  # W3・W12: 直前のステップの最後のメッセージに質問があれば、回答役の回答で続ける（上限 MAX_QA 回）
  [[ "$SCENARIO" == W3 || "$SCENARIO" == W12 || "$SCENARIO" == W13 || "$SCENARIO" == W14 || "$SCENARIO" == W15 ]] || return 0
  local reply
  while :; do
    # W12 は上限に達したら答えるのをやめる（締め切りの定型文は送らない。続きは介入の定型文で進める）
    [[ ( "$SCENARIO" == W12 || "$SCENARIO" == W13 || "$SCENARIO" == W14 || "$SCENARIO" == W15 ) && "$QA" -ge "$MAX_QA" ]] && { echo "qa limit $MAX_QA reached" >> "$OUT/errors.log"; return 0; }
    if [[ "$QA" -ge "$MAX_QA" ]]; then
      # 上限に達した後も質問が続くときは、締め切りの定型文を 1 回だけ送る（qa-closed.log に記録）
      if [[ ! -s "$OUT/qa-closed.log" ]] && ! over_budget; then
        reply="$(POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w3.py" "$OUT" "$i" "$((QA+1))")"
        mv "$OUT/qa-$((QA+1)).json" "$OUT/qa-unanswered.json"
        if [[ -n "$reply" ]]; then
          i=$((i+1)); echo "step$i" > "$OUT/qa-closed.log"; run_step "$i" "$QA_CLOSE"
        fi
      fi
      return 0
    fi
    over_budget && { echo "qa skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; return 0; }
    QA=$((QA+1))
    reply="$(qa_answer "$i" "$QA")"
    [[ -z "$reply" ]] && return 0
    i=$((i+1)); run_step "$i" "$reply"
  done
}

# W12: 依頼者役（ask-po の受け口）を裏で起動する。試行の終わりに止める
PO_PID=""
if [[ "$SCENARIO" == W12 ]]; then
  mkdir -p "$WORK/answerer-home"
  POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w12.py" serve "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$WORK/po.sock" \
    >> "$OUT/persona.log" 2>&1 &
  PO_PID=$!
  trap 'declare -F reap_servers >/dev/null && reap_servers end; [[ -n "$PO_PID" ]] && kill "$PO_PID" 2>/dev/null' EXIT
  for _ in $(seq 1 20); do [[ -S "$WORK/po.sock" ]] && break; sleep 0.5; done
fi
# W13: 依頼者役（answer_w13.py）。変更依頼の前（v1）と後（v2）で答えが変わるので、段階を $OUT/phase に書いて渡す
if [[ "$SCENARIO" == W13 ]]; then
  mkdir -p "$WORK/answerer-home"
  echo v1 > "$OUT/phase"
  POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_w13.py" serve "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$WORK/po.sock" \
    >> "$OUT/persona.log" 2>&1 &
  PO_PID=$!
  trap 'declare -F reap_servers >/dev/null && reap_servers end; [[ -n "$PO_PID" ]] && kill "$PO_PID" 2>/dev/null' EXIT
  for _ in $(seq 1 20); do [[ -S "$WORK/po.sock" ]] && break; sleep 0.5; done
fi
# W14・W15: 依頼者役（answer_persona.py）を W12 と同じく裏で起動する
if [[ "$SCENARIO" == W14 || "$SCENARIO" == W15 ]]; then
  mkdir -p "$WORK/answerer-home"
  POC_ANSWER_HOME="$WORK/answerer-home" python3 "$ROOT/scripts/poc/answer_persona.py" "$SCENARIO" serve "$OUT" "$APP" "$(cat "$OUT/baseline-commit")" "$WORK/po.sock" \
    >> "$OUT/persona.log" 2>&1 &
  PO_PID=$!
  trap 'declare -F reap_servers >/dev/null && reap_servers end; [[ -n "$PO_PID" ]] && kill "$PO_PID" 2>/dev/null' EXIT
  for _ in $(seq 1 20); do [[ -S "$WORK/po.sock" ]] && break; sleep 0.5; done
fi
START=$(date +%s); SESSION=""; i=0; QA=0
for step in "${STEPS[@]}"; do
  i=$((i+1))
  if over_budget; then echo "step$i skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
  run_step "$i" "$step"
  qa_loop
done

# 介入: 手順を終えてもコミットが無い、または未コミットの変更が残る（確認待ちで止まった）ときは、
# 定型の「お任せします」で続けさせ、その回数を interventions.log に記録する（PLAN.md §5.1 実行手順 3）。
: > "$OUT/interventions.log"
for _ in $(seq 1 "$MAX_NUDGES"); do
  commits="$(git -C "$APP" rev-list --count "$(cat "$OUT/baseline-commit")"..HEAD)"
  # AGENTS.md は next dev が自動で書き出すファイルなので、未コミットの変更に数えない
  # W6 以降の Playwright MCP が自動で書き出すページの記録（.playwright-mcp/）も数えない（W5 までは出ない）
  dirty="$(git -C "$APP" status --porcelain -- . ':!AGENTS.md' ':!.playwright-mcp' | head -1)"
  # W3 は要件文書（REQUIREMENTS.md）がコミットされていることも完了の条件にする
  if [[ "$SCENARIO" == W3 ]] && ! git -C "$APP" cat-file -e HEAD:REQUIREMENTS.md 2>/dev/null; then commits=0; fi
  # W6 は PR の本文（PR.md）がコミットされていることも完了の条件にする
  if [[ "$SCENARIO" == W6 ]] && ! git -C "$APP" cat-file -e HEAD:PR.md 2>/dev/null; then commits=0; fi
  # W9 はレビューの指摘（REVIEW.md）がコミットされていることも完了の条件にする
  if [[ "$SCENARIO" == W9 ]] && ! git -C "$APP" cat-file -e HEAD:REVIEW.md 2>/dev/null; then commits=0; fi
  [[ "$commits" -gt 0 && -z "$dirty" ]] && break
  if over_budget; then echo "nudge skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
  i=$((i+1))
  echo "step$i commits=$commits dirty=${dirty:+yes}" >> "$OUT/interventions.log"
  run_step "$i" "$NUDGE"
  qa_loop
done

# W7: 落とし穴の判定と、避けられなかったときのレビューの定型の指摘（最大 MAX_FEEDBACK 回）。
# 判定の結果は pitfalls-<回>.json（1 回目が「指摘を受ける前」の状態）。指摘した回は feedback.log に記録する。
CHECK_SECONDS=0
if [[ "$MAX_FEEDBACK" -gt 0 ]]; then
  : > "$OUT/feedback.log"
  for r in $(seq 1 $((MAX_FEEDBACK + 1))); do
    c0=$(date +%s)
    fb="$(python3 "$ROOT/scripts/poc/check_w7.py" "$SCENARIO" "$APP" "$OUT/pitfalls-$r.json" --feedback 2>> "$OUT/errors.log")" || true
    CHECK_SECONDS=$((CHECK_SECONDS + $(date +%s) - c0))
    [[ -z "$fb" || "$r" -gt "$MAX_FEEDBACK" ]] && break
    if over_budget; then echo "feedback skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
    i=$((i+1))
    echo "step$i round=$r" >> "$OUT/feedback.log"
    run_step "$i" "$fb"
  done
fi
echo "$CHECK_SECONDS" > "$OUT/check-seconds"

# W13（途中で要件が変わる）: 候補の手順・質問への回答・介入がすべて終わった時点を「最初の版（v1）」として記録し、
# 同じセッションに変更依頼（wf-W13-change.md の固定の文言）を送る。変更依頼にも候補の手順を同じように使う
#（Feature Dev は /feature-dev:feature-dev、gstack は → /review、Compound Engineering は /ce-plan → /ce-work → /ce-code-review）。
# その後の介入は v1 からのコミットの有無で判定する（最大 POC_MAX_NUDGES 回。定型文は変更依頼用）。docs/poc/tasks/wf-W13-design.md。
if [[ "$SCENARIO" == W13 ]]; then
  if [[ -n "$(git -C "$APP" status --porcelain -- . ':!AGENTS.md' ':!.playwright-mcp' | head -1)" ]]; then
    # 未コミットのまま残った変更は、最初の版に含める（記録して残す）
    ( cd "$APP" && git add -A && git commit -qm "poc: v1 leftovers" ) && echo yes > "$OUT/v1-leftovers"
  fi
  git -C "$APP" rev-parse HEAD > "$OUT/v1-commit"
  echo "$i" > "$OUT/v1-last-step"
  echo $(( $(date +%s) - START - CHECK_SECONDS )) > "$OUT/v1-seconds"
  session_cost > "$OUT/v1-cost"
  cp "$OUT/v1-commit" "$OUT/phase-base"
  echo v2 > "$OUT/phase"
  CHANGE="$(cat "$ROOT/docs/poc/tasks/wf-W13-change.md")"
  case "$CAND" in
    baseline|baseline-conventions|superpowers) CHANGE_STEPS=("$CHANGE") ;;
    feature-dev) CHANGE_STEPS=("/feature-dev:feature-dev $CHANGE") ;;
    compound-engineering) CHANGE_STEPS=("/ce-plan $CHANGE" "/ce-work" "/ce-code-review") ;;
    gstack) CHANGE_STEPS=("$CHANGE" "/review") ;;
  esac
  for step in "${CHANGE_STEPS[@]}"; do
    i=$((i+1))
    run_step "$i" "$step"
    qa_loop
  done
  NUDGE="お任せします。確認は不要なので、変更依頼を最後まで実装し、変更を git にコミットしてください。"
  for _ in $(seq 1 "$MAX_NUDGES"); do
    commits="$(git -C "$APP" rev-list --count "$(cat "$OUT/v1-commit")"..HEAD)"
    dirty="$(git -C "$APP" status --porcelain -- . ':!AGENTS.md' ':!.playwright-mcp' | head -1)"
    [[ "$commits" -gt 0 && -z "$dirty" ]] && break
    i=$((i+1))
    echo "step$i commits=$commits dirty=${dirty:+yes} phase=v2" >> "$OUT/interventions.log"
    run_step "$i" "$NUDGE"
    qa_loop
  done
fi
for step in "${POST_STEPS[@]}"; do
  if over_budget; then echo "post step skipped: budget \$$MAX_USD reached" >> "$OUT/errors.log"; break; fi
  i=$((i+1)); run_step "$i" "$step"
done
echo $(( $(date +%s) - START - CHECK_SECONDS )) > "$OUT/elapsed-seconds"
[[ -n "$PO_PID" ]] && { kill "$PO_PID" 2>/dev/null || true; }

# 5) 成果物の保存（コミット済み・未コミットの両方を含む差分）
( cd "$APP" && git add -A && git commit -qm "poc: uncommitted leftovers" ) || true
git -C "$APP" diff "$(cat "$OUT/baseline-commit")" HEAD -- . ':!package-lock.json' > "$OUT/diff.patch"
git -C "$APP" log --oneline "$(cat "$OUT/baseline-commit")"..HEAD > "$OUT/commits.txt"
# W13: 最初の版までの差分と、変更のステップ（v1 → 最後）の差分を分けて残す（ブラインドレビューと手戻りの集計に使う）
if [[ "$SCENARIO" == W13 && -s "$OUT/v1-commit" ]]; then
  git -C "$APP" diff "$(cat "$OUT/baseline-commit")" "$(cat "$OUT/v1-commit")" -- . ':!package-lock.json' > "$OUT/diff-v1.patch"
  git -C "$APP" diff "$(cat "$OUT/v1-commit")" HEAD -- . ':!package-lock.json' > "$OUT/diff-change.patch"
  git -C "$APP" log --format='%h %s%n%b' "$(cat "$OUT/baseline-commit")".."$(cat "$OUT/v1-commit")" > "$OUT/commits-v1.txt"
  git -C "$APP" log --format='%h %s%n%b' "$(cat "$OUT/v1-commit")"..HEAD > "$OUT/commits-change.txt"
fi
if [[ "$CAND" == gstack ]]; then
  # 外部送信の記録（G2 の確認用）
  HOME="$HOME_DIR" "$GSTACK/bin/gstack-egress" list > "$OUT/gstack-egress.txt" 2>&1 || true
fi
echo "done $ID ($(cat "$OUT/elapsed-seconds")s)"
