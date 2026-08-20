#!/usr/bin/env python3
"""
第 4 步：memory_pulse 返回值加 reflex_enabled / reflex_keyword_count。

只动 tools.py 里 memory_pulse 这一个函数，改动限定在函数体切片内，
不会波及同名的其它代码。匹配不上就中止，不落盘。
"""

import pathlib
import sys

TOOLS = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/root/tang_yu_niang/tools.py")

QUERY = '''    # memory_reflex 的状态。表还没建也不能让 pulse 挂掉——它是开窗第一个调的。
    try:
        _reflex_count = c.execute(
            "SELECT COUNT(*) FROM reflex_keywords WHERE enabled=1"
        ).fetchone()[0]
        _reflex_ok = True
    except Exception:
        _reflex_count, _reflex_ok = 0, False

'''

FIELDS = '''        "reflex_enabled": _reflex_ok,
        "reflex_keyword_count": _reflex_count,
'''


def main() -> int:
    text = TOOLS.read_text()
    if "reflex_keyword_count" in text:
        print("  · 已经打过补丁，跳过")
        return 0

    lines = text.split("\n")

    # 圈出 memory_pulse 的函数体，改动只在这一段里做
    start = next((i for i, l in enumerate(lines) if l.startswith("def memory_pulse(")), None)
    if start is None:
        print("× 找不到 def memory_pulse(，已中止", file=sys.stderr)
        return 1
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(("def ", "@", "class "))),
        len(lines),
    )
    body = lines[start:end]

    # 1) 查询插在 conn.close() 之前（函数体内第一个）
    close_at = next((i for i, l in enumerate(body) if l.strip() == "conn.close()"), None)
    if close_at is None:
        print("× memory_pulse 里找不到 conn.close()，已中止", file=sys.stderr)
        return 1

    # 2) 两个字段插在 recent 那一行之后（纯 ASCII 锚点，不受中文影响）
    anchor = "[dict(r) for r in recent],"
    recent_at = next((i for i, l in enumerate(body) if anchor in l), None)
    if recent_at is None:
        print(f"× memory_pulse 里找不到 {anchor}，已中止", file=sys.stderr)
        return 1

    # 从后往前插，免得前面的插入把后面的行号顶掉
    body.insert(recent_at + 1, FIELDS.rstrip("\n"))
    body.insert(close_at, QUERY.rstrip("\n"))

    lines[start:end] = body
    TOOLS.write_text("\n".join(lines))
    print("  ✓ reflex_enabled / reflex_keyword_count 已加进 memory_pulse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
