#!/usr/bin/env python3
"""
patch_server_v4.py — 新增 /api/tang/write_memory 接口（棠予酿 Web App 写入记忆）

用法（在 VPS 上）：
    python3 /root/patch_server_v4.py
"""

import sys
import subprocess

SERVER_PATH = "/root/server.py"

NEW_ROUTE = '''

# ── 棠予酿 补充 HTTP API v4 ──────────────────────────────────────────────

@app.custom_route("/api/tang/write_memory", methods=["POST"])
async def tang_write_memory_http(request):
    """从 Web App 直接写入新记忆"""
    import sqlite3 as _sq3, json as _json, datetime as _dt
    _DB = "/root/data/tang_yu_niang.db"
    try:
        body = await request.body()
        data = _json.loads(body) if body else {}
        title   = str(data.get("title",   "")).strip()
        content = str(data.get("content", "")).strip()
        tag     = str(data.get("tag",     "diary")).strip()
        imp     = min(max(int(data.get("importance", 5)), 1), 10)
        if not title or not content:
            return JSONResponse({"ok": False, "error": "title and content are required"})
        now = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        conn = _sq3.connect(_DB)
        conn.execute(
            "INSERT INTO memories (title,content,tag,importance,created_at,activation_count) VALUES (?,?,?,?,?,0)",
            [title, content, tag, imp, now]
        )
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})

# ── / 棠予酿 补充 HTTP API v4 ────────────────────────────────────────────
'''

MAIN_MARKER = 'if __name__ == "__main__":'


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if "/api/tang/write_memory" in src:
        print("✅ /api/tang/write_memory 已存在，跳过。")
    else:
        if MAIN_MARKER not in src:
            print(f"❌ 找不到标记 {MAIN_MARKER!r}，无法插入新路由")
            sys.exit(1)
        pos = src.index(MAIN_MARKER)
        src = src[:pos] + NEW_ROUTE + src[pos:]
        with open(SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ 已添加 /api/tang/write_memory 路由")

    print("🔄 重启 mcp.service …")
    r = subprocess.run(["systemctl", "restart", "mcp"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    status = subprocess.run(["systemctl", "is-active", "mcp"], capture_output=True, text=True)
    state = status.stdout.strip()
    print(f"   状态: {state}")
    if state != "active":
        print("⚠️  服务未 active，请检查: journalctl -u mcp -n 30")
        sys.exit(1)

    import urllib.request, json, time
    BASE = "http://127.0.0.1:8890"
    time.sleep(1)

    print("\n🧪 测试 /api/tang/write_memory …")
    try:
        req = urllib.request.Request(
            BASE + "/api/tang/write_memory",
            data=json.dumps({"title":"测试记忆","content":"patch v4 测试写入","tag":"diary","importance":3}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
        print(f"   ✅ 写入结果: {body}")
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")

    print("\n🎉 patch_server_v4 完成！write_memory 接口已就绪")


if __name__ == "__main__":
    patch()
