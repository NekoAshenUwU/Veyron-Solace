#!/usr/bin/env bash
# 第 4 步：memory_pulse 加 reflex_enabled / reflex_keyword_count
set -euo pipefail

TOOLS="${TOOLS:-/root/tang_yu_niang/tools.py}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f "$TOOLS" ]] || { echo "找不到 $TOOLS"; exit 1; }

echo "== 备份"
cp "$TOOLS" "$TOOLS.bak-$STAMP"

echo "== 打补丁"
python3 "$SRC/patch-pulse.py" "$TOOLS"

echo "== 语法检查"
python3 -m py_compile "$TOOLS"
echo "  ✓ 能编译"

echo
echo "== 改完的样子"
sed -n '/^def memory_pulse/,/^def [a-z_]*(/p' "$TOOLS" | grep -n "reflex" || true

echo
echo "备份：$TOOLS.bak-$STAMP"
echo "本次改动：tools.py 新增 10 行，全在 memory_pulse 函数体内。"
