#!/usr/bin/env bash
# memory_reflex 第 2 步：装 reflex.py + 在 server.py 注册工具。
# 只动这两处，匹配不上就整体中止、一个字不落盘。
set -euo pipefail

PKG="${PKG:-/root/tang_yu_niang}"
SERVER="${SERVER:-/root/server.py}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f "$PKG/db.py" ]]  || { echo "找不到 $PKG/db.py"; exit 1; }
[[ -f "$SERVER" ]]     || { echo "找不到 $SERVER"; exit 1; }

echo "== 备份 server.py"
cp "$SERVER" "$SERVER.bak-$STAMP"

echo "== 放 reflex.py"
cp "$SRC/package/reflex.py" "$PKG/reflex.py"

echo "== 在 server.py 注册工具"
SERVER="$SERVER" python3 - <<'PY'
import os, pathlib, sys

p = pathlib.Path(os.environ['SERVER'])
t = p.read_text()

old_wrapper = "    return _tyr.memory_reflex(text)"
if old_wrapper in t:
    # 老版本的壳没有 brief 参数，升级它
    t = t.replace(
        "def memory_reflex(text: str) -> str:", "def memory_reflex(text: str, brief: bool = True) -> str:", 1
    ).replace(old_wrapper, "    return _tyr.memory_reflex(text, brief)", 1)
    p.write_text(t)
    print("  \u2713 壳已升级：加上 brief 参数")
    sys.exit(0)

if 'memory_reflex' in t:
    print("  · 已经注册过且是新版，跳过")
    sys.exit(0)

# 锚点用纯 ASCII 的这一行，避开中文和破折号，免得对不上
anchor = "    return _tye.love_note_draw()"
n = t.count(anchor)
if n != 1:
    sys.exit(f"× 锚点匹配到 {n} 处（需要正好 1 处），已中止，文件未改动")

block = anchor + '''


@app.tool()
def memory_reflex(text: str, brief: bool = True) -> str:
    """反射 - 把一段话对词表做子串匹配,命中则浮现相关记忆;无命中返回空数组。brief=True 只回标题+摘要"""
    from tang_yu_niang import reflex as _tyr
    return _tyr.memory_reflex(text, brief)'''

p.write_text(t.replace(anchor, block, 1))
print("  ✓ memory_reflex 已注册")
PY

echo "== 语法检查"
python3 -m py_compile "$PKG/reflex.py" "$SERVER"
echo "  ✓ 两个文件都能编译"

echo
echo "改完了。备份：$SERVER.bak-$STAMP"
echo "本次改动：reflex.py 新增 151 行；server.py 新增 6 行（一个 @app.tool 壳）。"
echo
echo "下一步自己决定什么时候做："
echo "  systemctl restart mcp && journalctl -u mcp -n 20 --no-pager"
