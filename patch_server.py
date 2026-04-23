#!/usr/bin/env python3
"""
Run this on the VPS to add 5 tang_yu_niang tools into /root/server.py,
then restart mcp.service.

Usage:
  python3 /root/patch_server.py
"""
import subprocess
import sys

SERVER_PATH = "/root/server.py"

IMPORT_BLOCK = """
# ── 棠予酿 ─────────────────────────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, '/root')
from tang_yu_niang.db import init_db as _init_db
from tang_yu_niang import tools as _tyn
from tang_yu_niang import timeline as _tyl
_init_db()
"""

TOOL_BLOCK = """
@app.tool()
def memory_breathe(query: str = None, mood: str = None, tag: str = None, limit: int = 5) -> str:
    \"\"\"浮现记忆 — 按关键词/心情/标签检索相关记忆\"\"\"
    return _tyn.memory_breathe(query, mood, tag, limit)


@app.tool()
def memory_hold(title: str, content: str, tag: str = "diary", importance: int = 5, mood: str = None, mood_emoji: str = None) -> str:
    \"\"\"存储记忆 — 将一段经历保存进棠予酿\"\"\"
    return _tyn.memory_hold(title, content, tag, importance, mood, mood_emoji)


@app.tool()
def memory_pulse() -> str:
    \"\"\"记忆脉搏 — 查看当前记忆系统状态和今日心情\"\"\"
    return _tyn.memory_pulse()


@app.tool()
def timeline_add(content: str, category: str, date_str: str = None, start_at: str = None, end_at: str = None, subcategory: str = None, mood_emoji: str = None) -> str:
    \"\"\"记录生活轨迹 — 将一个生活片段存入时间轴（category示例：吃饭/睡觉/心情/事件/工作/休闲/关系）\"\"\"
    return _tyl.timeline_add(content, category, date_str, start_at, end_at, subcategory, mood_emoji)


@app.tool()
def timeline_query(date_str: str = None, start_date: str = None, end_date: str = None, category: str = None, limit: int = 50) -> str:
    \"\"\"查询生活轨迹 — 按日期或分类检索生活片段\"\"\"
    return _tyl.timeline_query(date_str, start_date, end_date, category, limit)

"""

MARKER = 'if __name__ == "__main__":'

def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if "memory_breathe" in src:
        print("✅ server.py already patched — tools already registered.")
        return

    if MARKER not in src:
        print(f"❌ Could not find marker: {MARKER!r}")
        print("   Please check server.py manually.")
        sys.exit(1)

    insert_pos = src.index(MARKER)

    new_src = (
        IMPORT_BLOCK
        + src[:insert_pos]
        + TOOL_BLOCK
        + src[insert_pos:]
    )

    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(new_src)

    print("✅ server.py patched — 5 tools registered.")

    print("🔄 Restarting mcp.service …")
    result = subprocess.run(
        ["systemctl", "restart", "mcp"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("❌ Restart failed:")
        print(result.stderr)
        sys.exit(1)

    print("✅ mcp.service restarted. Checking status …")
    status = subprocess.run(
        ["systemctl", "is-active", "mcp"],
        capture_output=True, text=True
    )
    print("   Status:", status.stdout.strip())
    if status.stdout.strip() != "active":
        print("⚠️  Service may not be running — check: systemctl status mcp")
    else:
        print("🎉 All done! 5 棠予酿 tools are live.")

if __name__ == "__main__":
    patch()
