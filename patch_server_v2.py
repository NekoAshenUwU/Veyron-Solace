#!/usr/bin/env python3
"""
棠予酿 v2 — 把剩下 4 个工具注册进 server.py
 - memory_tidal   记忆潮汐
 - memory_trace   溯源/改删
 - memory_grow    日记归档（长文拆分）
 - love_note_draw 抽情话

前置：extras.py 必须已经在 /root/tang_yu_niang/extras.py

用法：
    python3 /root/patch_server_v2.py
"""
import subprocess
import sys
import urllib.request

SERVER_PATH = "/root/server.py"
EXTRAS_PATH = "/root/tang_yu_niang/extras.py"

EXTRAS_URL = (
    "https://api.github.com/repos/nekoashenuwu/veyron-solace/contents/"
    "tang_yu_niang/extras.py?ref=claude/read-claude-md-d5C3m"
)

NEW_TOOL_BLOCK = '''

@app.tool()
def memory_tidal(limit: int = 20, direction: str = "all") -> str:
    """记忆潮汐 — 按strength从高到低排列所有记忆，标注涨/退潮方向（direction: all/rising/falling/deep_falling/pinned）"""
    from tang_yu_niang import extras as _tye
    return _tye.memory_tidal(limit, direction)


@app.tool()
def memory_trace(memory_id: str, action: str, updates: dict = None) -> str:
    """溯源 — 修改记忆元数据（action: resolve 标记已解决 / pin 置顶 / unpin / delete / update）"""
    from tang_yu_niang import extras as _tye
    return _tye.memory_trace(memory_id, action, updates)


@app.tool()
def memory_grow(content: str, date_str: str = None, weather: str = None, love_note: str = None) -> str:
    """生长 — 把一段长日记自动按段落拆分为多条记忆条目"""
    from tang_yu_niang import extras as _tye
    return _tye.memory_grow(content, date_str, weather, love_note)


@app.tool()
def love_note_draw() -> str:
    """抽情话 — 从情话库随机抽一条给棠棠"""
    from tang_yu_niang import extras as _tye
    return _tye.love_note_draw()

'''

MARKER = 'if __name__ == "__main__":'


def ensure_extras():
    import os
    if os.path.exists(EXTRAS_PATH):
        print(f"✅ extras.py 已存在: {EXTRAS_PATH}")
        return
    print(f"📥 下载 extras.py → {EXTRAS_PATH}")
    req = urllib.request.Request(
        EXTRAS_URL,
        headers={"Accept": "application/vnd.github.v3.raw"},
    )
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(EXTRAS_PATH), exist_ok=True)
    with open(EXTRAS_PATH, "wb") as f:
        f.write(data)
    print(f"   ✅ {len(data)} bytes 写入")


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if "memory_tidal" in src:
        print("✅ server.py 已有 memory_tidal — 4 个工具都已注册，跳过。")
        return

    if MARKER not in src:
        print(f"❌ 找不到标记: {MARKER!r}")
        sys.exit(1)

    pos = src.index(MARKER)
    new_src = src[:pos] + NEW_TOOL_BLOCK + src[pos:]

    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(new_src)

    print("✅ server.py 已打补丁 — 4 个新工具注册（累计 9 个棠予酿工具）")

    print("🔄 重启 mcp.service …")
    r = subprocess.run(
        ["systemctl", "restart", "mcp"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    status = subprocess.run(
        ["systemctl", "is-active", "mcp"],
        capture_output=True, text=True,
    )
    print("   Status:", status.stdout.strip())
    if status.stdout.strip() == "active":
        print("\n🎉 全部 9 个棠予酿工具现在都活着了：")
        print("   ┌─ 原有 5 个 ─┐")
        print("   │ memory_breathe   浮现")
        print("   │ memory_hold      存储")
        print("   │ memory_pulse     脉搏")
        print("   │ timeline_add     记录轨迹")
        print("   │ timeline_query   查询轨迹")
        print("   ├─ 新增 4 个 ─┤")
        print("   │ memory_tidal     潮汐 🌊")
        print("   │ memory_trace     溯源 🕰")
        print("   │ memory_grow      生长 🌱")
        print("   │ love_note_draw   抽情话 💌")
        print("   └─────────────┘")
    else:
        print("⚠️  mcp.service 未 active，检查: systemctl status mcp")


if __name__ == "__main__":
    ensure_extras()
    patch()
