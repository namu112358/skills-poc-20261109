#!/usr/bin/env bash
# セキュリティ監査の試行で、対象のコードを隔離して動かすためのコマンド（SEC-6）。
# 使い方: sbx.sh <作業用ディレクトリ> <コマンド> [引数...]
#   作業用ディレクトリは、SBX_ROOT（試行が決める。例 /tmp/poc-trials/<ID>/out/run-1/agents）の下でなければならない。
# 中で行うこと:
#   - ネットワーク・プロセス（PID）・プロセス間通信・ホスト名の名前空間を分ける。ネットワークはループバックだけ
#   - 権限のない利用者（nobody）に切り替え、ケーパビリティを外す。対象のコードと道具は root の持ち物なので、書き換えられない
#   - 対象のコード（SBX_TARGET）は、さらに読み取り専用でマウントし直す。できなければ実行しない
#   - /home/user（このリポジトリと採点用の正解がある）と /root は空の tmpfs で隠す。/var/tmp・/dev/shm も使い捨ての tmpfs にする
#     （/tmp は隠せない。対象と作業用ディレクトリが /tmp/poc-trials の下にあるため。nobody は /tmp の他人のファイルを書き換えられない）
#   - 環境変数は空から始め、PATH・HOME・TMPDIR だけを渡す（HOME・TMPDIR は作業用ディレクトリ）
#   - CPU 時間 60 秒、仮想メモリ 16 GiB（Node.js と WebAssembly は起動時に大きな領域を予約するだけで、実際の使用量は小さい。
#     これより小さいとテストが動かない）、プロセス 64、ファイル 64 MiB、実時間 120 秒の上限
# 書き込めるのは作業用ディレクトリだけ。作業用ディレクトリは、このコマンドが新しく作ったときだけ持ち主を nobody にする
#（すでにあるものの持ち主は付け替えない。中に仕込まれたリンクを root でたどらないように）。
set -euo pipefail
[[ $# -ge 2 ]] || { echo "使い方: sbx.sh <作業用ディレクトリ> <コマンド> [引数...]" >&2; exit 2; }
: "${SBX_ROOT:?SBX_ROOT が無い}" "${SBX_TARGET:?SBX_TARGET が無い}"
ROOT_REAL="$(realpath -e "$SBX_ROOT")"
[[ "$(stat -c %u "$ROOT_REAL")" == 0 ]] || { echo "SBX_ROOT は root の持ち物でなければならない: $ROOT_REAL" >&2; exit 2; }
SCRATCH="$(realpath -m "$1")"; shift
[[ "$SCRATCH" == "$ROOT_REAL"/* ]] || { echo "作業用ディレクトリは $ROOT_REAL の下に置く: $SCRATCH" >&2; exit 2; }
if [[ -e "$SCRATCH" || -L "$SCRATCH" ]]; then
  [[ -d "$SCRATCH" && ! -L "$SCRATCH" && "$(stat -c %U "$SCRATCH")" == nobody ]] \
    || { echo "作業用ディレクトリがすでにあり、このコマンドが作ったものではない: $SCRATCH" >&2; exit 2; }
else
  mkdir -p "$(dirname "$SCRATCH")"
  mkdir -m 0700 "$SCRATCH"
  chown -h nobody:nogroup "$SCRATCH"
fi
TARGET="$(realpath -e "$SBX_TARGET")"
exec unshare --mount --net --pid --fork --ipc --uts --propagation private -- /bin/sh -c '
  set -eu
  target="$1"; scratch="$2"; shift 2
  ip link set lo up 2>/dev/null || true
  mount -t proc proc /proc
  mount --rbind "$target" "$target"
  mount -o remount,ro,bind "$target" "$target"
  findmnt -no OPTIONS "$target" | grep -qw ro || { echo "対象を読み取り専用にできない" >&2; exit 1; }
  for d in /home/user /root /var/tmp /dev/shm; do
    if [ -d "$d" ]; then mount -t tmpfs -o size=16m,mode=0755 tmpfs "$d"; fi
  done
  cd "$scratch"
  exec timeout 120 prlimit --cpu=60 --as=17179869184 --nproc=64 --fsize=67108864 -- \
    setpriv --reuid=nobody --regid=nogroup --clear-groups --inh-caps=-all --bounding-set=-all --no-new-privs -- \
    env -i PATH=/opt/node22/bin:/usr/local/bin:/usr/bin:/bin HOME="$scratch" TMPDIR="$scratch" "$@"
' sbx "$TARGET" "$SCRATCH" "$@"
