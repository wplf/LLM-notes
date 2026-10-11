#!/usr/bin/env bash
# 把仓库中的笔记（README + 各主题文件夹）复制到 _docs/，供 mkdocs 构建
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _docs && mkdir -p _docs
cp README.md _docs/index.md
for d in */; do
  d=${d%/}
  case "$d" in _docs|site|scripts|.*) continue ;; esac
  cp -R "$d" _docs/
done
