#!/usr/bin/env bash
# セキュリティ監査の試行で、対象のコードを隔離して動かすためのコマンド（SEC-6）。
# 使い方: sbx.sh <作業用ディレクトリ> <コマンド> [引数...]
#   作業用ディレクトリは、SBX_ROOT（試行が決める。例 /tmp/poc-trials/<ID>/out/run-1/agents）の下でなければならない。
# 中で行うこと:
#   - ネットワークを切る（新しいネットワークの名前空間。ループバックだけを使える）
#   - 権限のない利用者（nobody）に切り替え、ケーパビリティを外す。対象のコードと道具は root の持ち物なので、書き換えられない
#   - 対象のコード（SBX_TARGET）は、さらに読み取り専用でマウントし直す
#   - 環境変数は空から始め、PATH・HOME・TMPDIR だけを渡す（HOME・TMPDIR は作業用ディレクトリ）
#   - CPU 時間 60 秒、仮想メモリ 16 GiB（Node.js と WebAssembly は起動時に大きな領域を予約するだけで、実際の使用量は小さい。これより小さいとテストが動かない）、プロセス 64、ファイル 64 MiB、実時間 120 秒の上限
# 書き込めるのは作業用ディレクトリだけ（nobody の持ち物にする）。
set -euo pipefail
[[ $# -ge 2 ]] || { echo "使い方: sbx.sh <作業用ディレクトリ> <コマンド> [引数...]" >&2; exit 2; }
: "${SBX_ROOT:?SBX_ROOT が無い}" "${SBX_TARGET:?SBX_TARGET が無い}"
SCRATCH="$(realpath -m "$1")"; shift
ROOT_REAL="$(realpath -m "$SBX_ROOT")"
[[ "$SCRATCH" == "$ROOT_REAL"/* ]] || { echo "作業用ディレクトリは $ROOT_REAL の下に置く: $SCRATCH" >&2; exit 2; }
mkdir -p "$SCRATCH"
chown -R nobody:nogroup "$SCRATCH"
TARGET="$(realpath "$SBX_TARGET")"
exec unshare --mount --net --propagation private -- /bin/sh -c '
  ip link set lo up 2>/dev/null || true
  mount --bind "$1" "$1" && mount -o remount,ro,bind "$1" "$1"
  shift
  scratch="$1"; shift
  cd "$scratch"
  exec timeout 120 prlimit --cpu=60 --as=17179869184 --nproc=64 --fsize=67108864 -- \
    setpriv --reuid=nobody --regid=nogroup --clear-groups --inh-caps=-all --bounding-set=-all --no-new-privs -- \
    env -i PATH=/opt/node22/bin:/usr/local/bin:/usr/bin:/bin HOME="$scratch" TMPDIR="$scratch" "$@"
' sbx "$TARGET" "$SCRATCH" "$@"
