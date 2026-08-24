#!/usr/bin/env bash
# A3：把 get_phone_sessions / get_sleep_gap 装进棠予酿。
# 只动两处：放一个模块 + 在 server.py 加两个 @app.tool() 壳。
# 匹配不上就整体中止、一个字不落盘。
set -euo pipefail

PKG="${PKG:-/root/tang_yu_niang}"
SERVER="${SERVER:-/root/server.py}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f "$PKG/db.py" ]] || { echo "找不到 $PKG/db.py（PKG 设对了吗）"; exit 1; }
[[ -f "$SERVER" ]]    || { echo "找不到 $SERVER"; exit 1; }

echo "== 先自检（不碰生产库，临时库跑一遍）"
python3 "$SRC/package/phone_sessions.py" --self-test

echo
echo "== 备份 server.py"
cp "$SERVER" "$SERVER.bak-$STAMP"

echo "== 放 phone_sessions.py"
cp "$SRC/package/phone_sessions.py" "$PKG/phone_sessions.py"

echo "== 在 server.py 注册两个工具"
SERVER="$SERVER" python3 - <<'PY'
import ast, os, pathlib, re, sys

p = pathlib.Path(os.environ['SERVER'])
t = p.read_text()

NEW_DOC = '"""睡眠推断(不是测量) - 由手机长时间没有活动【推断】出来的入睡/起床/夜醒。它看到的只是「有没有碰手机」:放下手机看书、起床后去洗澡上班,都会被算成睡着。讲给棠棠听的时候当趋势说,别当读数报。date_str 是醒来那天,空=今天"""'

if 'get_phone_sessions' in t:
    # 已经注册过：壳不用重插，但描述可能改了。
    # 描述是予予每次调用都会看到的那行,值不值得更新?值——
    # 08-24 那个 9.9 小时就是会被讲成「你睡了快十小时」的数字。
    #
    # 用 ast 精确定位 docstring 节点再按行列替换,不用字符串匹配:
    # 描述里有中文标点和括号,写死一份匹配串迟早对不上。
    tree = ast.parse(t)
    fn = next((n for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == 'get_sleep_gap'), None)
    if fn is None:
        sys.exit("× 找不到 def get_sleep_gap，已中止，文件未改动")
    doc = fn.body[0] if fn.body else None
    if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)
            and isinstance(doc.value.value, str)):
        sys.exit("× get_sleep_gap 没有 docstring，已中止，文件未改动")

    # 不要用 col_offset 切片！ast 的列偏移数的是 UTF-8 【字节】，不是字符。
    # 这行有中文，end_col_offset=37 而字符长度只有 22，切过头会把行尾的换行
    # 一起吃掉，下一行被粘上来，报 invalid syntax。
    # docstring 本来就独占整行，按行替换、缩进用正则取，压根不碰列偏移。
    lines = t.splitlines(keepends=True)
    a, b = doc.lineno - 1, doc.end_lineno - 1
    indent = re.match(r"[ \t]*", lines[a]).group(0)
    new_t = "".join(lines[:a]) + indent + NEW_DOC + "\n" + "".join(lines[b + 1:])

    if new_t == t:
        print("  · 已经注册过，描述也是最新的，跳过")
        sys.exit(0)
    try:
        ast.parse(new_t)
    except SyntaxError as err:
        sys.exit(f"× 改完语法不对（{err}），已中止，文件未改动")
    p.write_text(new_t)
    print("  ✓ 已注册过，更新了 get_sleep_gap 的工具描述")
    sys.exit(0)

# 不用字面锚点：server.py 已经被改过两轮，锚点这种东西一改就对不上。
# 直接找【最后一个】带 @app.tool() 的顶层函数，插在它后面——
# 这样既不会掉进 if __name__ == "__main__" 后面（那样永远不会注册），
# 也不依赖任何一行具体长什么样。
tree = ast.parse(t)
last_end = None
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for d in node.decorator_list:
            src = ast.get_source_segment(t, d) or ""
            if 'tool' in src:
                last_end = node.end_lineno
                break
if last_end is None:
    sys.exit("× 在 server.py 里没找到任何 @app.tool() 函数，已中止，文件未改动")

BLOCK = '''

@app.tool()
def get_phone_sessions(date_str: str = "", package: str = "", limit: int = 50) -> str:
    """手机使用会话 - 某天按时间顺序的每一次 app 使用(开始/结束/时长)。date_str 空=今天;package 可填包名片段模糊匹配"""
    from tang_yu_niang import phone_sessions as _ps
    import json
    return json.dumps(
        _ps.get_phone_sessions(date_str or None, package or None, limit),
        ensure_ascii=False,
    )


@app.tool()
def get_sleep_gap(date_str: str = "") -> str:
    """睡眠推断(不是测量) - 由手机长时间没有活动【推断】出来的入睡/起床/夜醒。它看到的只是「有没有碰手机」:放下手机看书、起床后去洗澡上班,都会被算成睡着。讲给棠棠听的时候当趋势说,别当读数报。date_str 是醒来那天,空=今天"""
    from tang_yu_niang import phone_sessions as _ps
    import json
    return json.dumps(_ps.get_sleep_gap(date_str or None), ensure_ascii=False)
'''

lines = t.splitlines(keepends=True)
lines.insert(last_end, BLOCK)
new = "".join(lines)

try:
    ast.parse(new)
except SyntaxError as err:
    sys.exit(f"× 改完语法不对（{err}），已中止，文件未改动")

p.write_text(new)
print(f"  ✓ 两个工具已注册（插在第 {last_end} 行之后）")
PY

echo "== 语法检查"
python3 -m py_compile "$PKG/phone_sessions.py" "$SERVER"
echo "  ✓ 两个文件都能编译"

echo
echo "改完了。备份：$SERVER.bak-$STAMP"
echo
echo "下一步："
echo "  systemctl restart mcp && sleep 10 && journalctl -u mcp -n 20 --no-pager"
echo "  重启之后 chat 端要重连一次（OAuth 客户端注册在内存里，重启就没了）"
