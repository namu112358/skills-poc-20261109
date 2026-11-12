#!/usr/bin/env bash
# PoC の試行で読み込むプラグインを、固定コミットで .poc-cache/ に取得する（Git 管理外）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CACHE="${POC_CACHE:-$ROOT/.poc-cache}"
mkdir -p "$CACHE"

# name repo commit
PINS=(
  "claude-plugins-official anthropics/claude-plugins-official 0412be76f50ab4f4f8abff3753efa9269fbbca5b"
  "superpowers obra/superpowers bb92a77741419a4ab5f06e711a283343f1ada0c3"
  "compound-engineering EveryInc/compound-engineering-plugin 18c2be5e3d79024f20bce936b8cb05272621760a"
  "gstack garrytan/gstack b6155921a564ba9ec2470fd2cb3894c05e2c2d13"
  "impeccable pbakaus/impeccable b7d1a80481e4b126231dc71121bdfa8674fe8282"
  "ui-ux-pro-max nextlevelbuilder/ui-ux-pro-max-skill 4f2dbb67e64969a9a30ab00742f2d55d66ddec2b"
  "ponytail DietrichGebert/ponytail 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846"
)

for pin in "${PINS[@]}"; do
  read -r name repo commit <<<"$pin"
  dir="$CACHE/$name"
  if [[ -d "$dir/.git" ]] && [[ "$(git -C "$dir" rev-parse HEAD)" == "$commit" ]]; then
    echo "ok   $name@${commit:0:7}"; continue
  fi
  rm -rf "$dir"; git init -q "$dir"
  git -C "$dir" remote add origin "https://github.com/$repo.git"
  git -C "$dir" fetch -q --depth 1 origin "$commit"
  git -C "$dir" checkout -q FETCH_HEAD
  echo "got  $name@${commit:0:7}"
done
