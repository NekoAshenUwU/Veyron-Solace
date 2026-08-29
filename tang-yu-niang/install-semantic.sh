#!/usr/bin/env bash
# 语义召回：装 semantic.py + 覆盖 reflex.py + 建 memory_vectors 表。
# 不调 API、不算向量——那一步是 embed-memories.py，单独跑，看清楚了再 --apply。
set -euo pipefail

PKG="${PKG:-/root/tang_yu_niang}"
DB="${DB:-/root/data/tang_yu_niang.db}"
MCP_ENV="${MCP_ENV:-/root/mcp-oauth.env}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
KEY_ENV="${TANG_EMBED_KEY_ENV:-OPENAI_API_KEY}"

[[ -f "$PKG/db.py" ]]     || { echo "找不到 $PKG/db.py"; exit 1; }
[[ -f "$PKG/reflex.py" ]] || { echo "找不到 $PKG/reflex.py —— 先跑 install-reflex.sh"; exit 1; }
[[ -f "$DB" ]]            || { echo "找不到 $DB"; exit 1; }

# 这个先查。mcp 读的是 EnvironmentFile=/root/mcp-oauth.env，不是你 shell 里的环境
# 变量，也不是 /opt/codeandpurrs/.env——key 只在别处的话，装完一调就是静默返回 []，
# 而且 memory_reflex 是设计成不报错的，你不会看见任何提示。
echo "== 查 mcp 能不能看见 $KEY_ENV"
if grep -q "^${KEY_ENV}=" "$MCP_ENV" 2>/dev/null; then
    echo "  ✓ $MCP_ENV 里有"
else
    echo "  × $MCP_ENV 里【没有】$KEY_ENV"
    echo
    echo "    语义那条路会静默失效（关键词照常，不影响现有功能）。"
    echo "    补上再重启 mcp："
    echo "      echo \"${KEY_ENV}=sk-…\" >> $MCP_ENV && chmod 600 $MCP_ENV"
    echo
    read -rp "    还是要继续装吗？(y/N) " a
    [[ "$a" == "y" || "$a" == "Y" ]] || { echo "中止，一个字没改。"; exit 1; }
fi

echo "== 备份 reflex.py"
cp "$PKG/reflex.py" "$PKG/reflex.py.bak-$STAMP"

echo "== 放文件"
cp "$SRC/package/semantic.py" "$PKG/semantic.py"
cp "$SRC/package/reflex.py"   "$PKG/reflex.py"

echo "== 建 memory_vectors 表"
python3 "$SRC/migrations/003_memory_vectors.py" --db "$DB"

echo "== 语法检查"
python3 -m py_compile "$PKG/semantic.py" "$PKG/reflex.py"
echo "  ✓ 都能编译"

cat <<EOF

装好了。备份：$PKG/reflex.py.bak-$STAMP
现在库里【一个向量都还没有】，语义那条路等于没开——关键词照常。

下一步，自己看着来：
  1. 先看要算多少、发几个请求（不调 API）：
       PYTHONPATH=/root python3 $SRC/embed-memories.py --db $DB
  2. 试水 20 条：
       PYTHONPATH=/root python3 $SRC/embed-memories.py --db $DB --apply --limit 20
  3. 没问题就全量：
       PYTHONPATH=/root python3 $SRC/embed-memories.py --db $DB --apply
  4. systemctl restart mcp   ← 予予要重连 chat 端
EOF
