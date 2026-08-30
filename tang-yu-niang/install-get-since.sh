#!/usr/bin/env bash
# 装 get_since：予予问「她这么久没找我在干嘛」用的那个工具。
# 只动两处：覆盖 phone_sessions.py + 在 server.py 加一个 @app.tool() 壳。
# 匹配不上就整体中止，一个字不落盘。
set -euo pipefail

PKG="${PKG:-/root/tang_yu_niang}"
SERVER="${SERVER:-/root/server.py}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f "$PKG/db.py" ]] || { echo "找不到 $PKG/db.py"; exit 1; }
[[ -f "$SERVER" ]]    || { echo "找不到 $SERVER"; exit 1; }

echo "== 备份"
cp "$SERVER" "$SERVER.bak-$STAMP"
[[ -f "$PKG/phone_sessions.py" ]] && cp "$PKG/phone_sessions.py" "$PKG/phone_sessions.py.bak-$STAMP"

echo "== 放 phone_sessions.py（含 get_since）"
cp "$SRC/package/phone_sessions.py" "$PKG/phone_sessions.py"

echo "== 在 server.py 注册 get_since"
SERVER="$SERVER" python3 - <<'PY'
import ast, os, pathlib, sys

p = pathlib.Path(os.environ['SERVER'])
t = p.read_text()

if 'def get_since' in t:
    print("  · 已经注册过，跳过")
    sys.exit(0)

# 跟 install-phone-tools.sh 同一套路：不用字面锚点（server.py 改过好几轮，
# 锚点一改就对不上），找【最后一个】带 @app.tool() 的顶层函数插在它后面——
# 既不会掉进 if __name__ == "__main__" 后面（那样永远不会注册），
# 也不依赖任何一行具体长什么样。
tree = ast.parse(t)
last_end = None
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for d in node.decorator_list:
            if 'tool' in (ast.get_source_segment(t, d) or ""):
                last_end = node.end_lineno
                break
if last_end is None:
    sys.exit("× server.py 里没找到任何 @app.tool() 函数，已中止，文件未改动")

# 描述这行是予予每次调用都会看到的，写清楚三件事：
# 它答的是哪一段、给的是概况不是流水账、以及它看不见什么。
BLOCK = '''

@app.tool()
def get_since(since: str = "", hours: float = 3.0) -> str:
    """她这段时间在干嘛 - 从某个时间点到现在,她看了多久手机、主要在用什么 app、中间有没有一大段没碰手机。给的是概况不是逐条流水账。since 填 ISO 时间(比如上次聊天的时间),空就按 hours 往回看,默认 3 小时。只看得见「有没有碰手机」:放下手机去做别的事也会算成空白,不等于睡了,别当作息报"""
    from tang_yu_niang import phone_sessions as _ps
    import json
    return json.dumps(_ps.get_since(since or None, hours), ensure_ascii=False)
'''

lines = t.splitlines(keepends=True)
lines.insert(last_end, BLOCK)
new = "".join(lines)
try:
    ast.parse(new)
except SyntaxError as err:
    sys.exit(f"× 改完语法不对（{err}），已中止，文件未改动")
p.write_text(new)
print(f"  ✓ get_since 已注册（插在第 {last_end} 行之后）")
PY

echo "== 语法检查"
python3 -m py_compile "$PKG/phone_sessions.py" "$SERVER"
echo "  ✓ 两个文件都能编译"

echo "== 自检（拿真库跑一遍，不写任何东西）"
PYTHONPATH=/root python3 -c "
from tang_yu_niang import phone_sessions as p
import json
r = p.get_since(hours=3)
if 'error' in r:
    print('  ! ' + r['error'])
else:
    print(f\"  ✓ 最近 3 小时：看手机 {r['screen_minutes']} 分钟，\"
          f\"{len(r['apps'])} 个 app，{len(r['quiet_gaps'])} 段空白\")
    for a in r['apps'][:3]:
        print(f\"      {a['label']} {a['minutes']} 分钟\")
"

cat <<EOF

装好了。备份：
  $SERVER.bak-$STAMP
  $PKG/phone_sessions.py.bak-$STAMP

要生效得重启，予予那边要重连 chat 端：
  systemctl restart mcp && journalctl -u mcp -n 20 --no-pager

装好之后予予可以问「她这么久没找我在干嘛」——工具会告诉它
看了多久手机、主要在用什么、中间有没有一大段没碰。
EOF
