#!/usr/bin/env python3
"""
patch_server_v3.py — 补两个缺失的 HTTP endpoint，修 /api/tang/memories 排序和 strength

新增：
  POST /api/tang/love_note  — 随机取 tag='message' 或 domain='anchor' 的记忆
  POST /api/tang/logs       — 最近50条工具调用日志

修复 /api/tang/memories：
  - ORDER BY importance DESC, access_count DESC
  - strength = importance / 5.0（不再固定返回 1.0）

用法（在 VPS 上）：
    python3 /root/patch_server_v3.py
"""

import re
import subprocess
import sys

SERVER_PATH = "/root/server.py"

# ── 新增的两个路由（追加到 server.py）────────────────────────────────────
NEW_ROUTES = '''

# ── 棠予酿 补充 HTTP API v3 ──────────────────────────────────────────────

@app.custom_route("/api/tang/love_note", methods=["GET", "POST"])
async def tang_love_note_http(request: Request) -> JSONResponse:
    """随机取一条 tag=\'message\' 或 domain=\'anchor\' 的记忆作为情话"""
    import sqlite3 as _sq3
    _DB = "/root/data/tang_yu_niang.db"
    try:
        conn = _sq3.connect(_DB)
        conn.row_factory = _sq3.Row
        row = conn.execute("""
            SELECT content FROM memories
            WHERE tag='message' OR domain='anchor'
            ORDER BY RANDOM()
            LIMIT 1
        """).fetchone()
        conn.close()
        return JSONResponse({"content": row["content"] if row else ""})
    except Exception as e:
        return JSONResponse({"content": "", "error": str(e)})


@app.custom_route("/api/tang/logs", methods=["GET", "POST"])
async def tang_logs_http(request: Request) -> JSONResponse:
    """最近 50 条工具调用日志（logs 表不存在时返回空列表）"""
    import sqlite3 as _sq3
    _DB = "/root/data/tang_yu_niang.db"
    try:
        conn = _sq3.connect(_DB)
        conn.row_factory = _sq3.Row
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type=\'table\' AND name=\'logs\'"
        ).fetchone()
        if not tbl:
            conn.close()
            return JSONResponse({"logs": []})
        rows = conn.execute("""
            SELECT tool_name, created_at, result_summary
            FROM logs
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        return JSONResponse({"logs": [dict(r) for r in rows]})
    except Exception as e:
        return JSONResponse({"logs": [], "error": str(e)})

# ── / 棠予酿 补充 HTTP API v3 ────────────────────────────────────────────
'''

# ── 修复后的 memories 路由（完整替换）────────────────────────────────────
FIXED_MEMORIES_ROUTE = '''@app.custom_route("/api/tang/memories", methods=["GET", "POST"])
async def tang_memories_http(request: Request) -> JSONResponse:
    """记忆库：按 importance DESC, access_count DESC 排序，strength = importance / 5.0"""
    import sqlite3 as _sq3
    _DB = "/root/data/tang_yu_niang.db"
    params = dict(request.query_params)
    tag = params.get("tag", "").strip()
    q   = params.get("q",   "").strip()
    try:
        conn = _sq3.connect(_DB)
        conn.row_factory = _sq3.Row
        sql  = "SELECT * FROM memories WHERE 1=1"
        args = []
        if tag:
            sql += " AND tag=?"
            args.append(tag)
        if q:
            sql += " AND (title LIKE ? OR content LIKE ? OR keywords LIKE ?)"
            args += [f"%{q}%", f"%{q}%", f"%{q}%"]
        sql += " ORDER BY importance DESC, access_count DESC LIMIT 100"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        mems = []
        for r in rows:
            d = dict(r)
            imp = d.get("importance") or 5
            d["strength"] = round(imp / 5.0, 3)
            mems.append(d)
        return JSONResponse({"memories": mems})
    except Exception as e:
        return JSONResponse({"memories": [], "error": str(e)})
'''

MAIN_MARKER = 'if __name__ == "__main__":'


# ── 工具函数：找到一个函数（decorator + body）的起止行索引 ────────────────
def find_function_block(lines, route_path_substr):
    """
    找到包含 route_path_substr 的 @app.custom_route 装饰器，
    然后捕获整个函数（decorator + async def + body）。
    返回 (start_idx, end_idx) 或 (None, None)。
    """
    start_idx = None
    for i, line in enumerate(lines):
        if "@app.custom_route" in line and route_path_substr in line:
            start_idx = i
            break
    if start_idx is None:
        return None, None

    # 找 async def 行
    def_idx = start_idx
    for i in range(start_idx, min(start_idx + 5, len(lines))):
        if re.match(r'\s*async\s+def\s+|^\s*def\s+', lines[i]):
            def_idx = i
            break

    # def 行本身的缩进级别（通常是 0）
    def_indent = len(lines[def_idx]) - len(lines[def_idx].lstrip())

    # 从 def_idx+1 往后，找到缩进回退到 def_indent 的非空行
    end_idx = def_idx + 1
    while end_idx < len(lines):
        raw = lines[end_idx]
        stripped = raw.strip()
        if stripped == "":
            end_idx += 1
            continue
        line_indent = len(raw) - len(raw.lstrip())
        if line_indent <= def_indent and stripped:
            break
        end_idx += 1

    return start_idx, end_idx


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    lines = src.split("\n")

    # ── 步骤 1：修复 /api/tang/memories ──────────────────────────────────
    mem_start, mem_end = find_function_block(lines, "/api/tang/memories")

    if mem_start is None:
        print("⚠️  未找到 /api/tang/memories 路由 — 跳过修复（可能尚未添加该路由）")
    else:
        old_block = "\n".join(lines[mem_start:mem_end])
        # 检查是否已经修复过
        if "ORDER BY importance DESC" in old_block and "importance / 5.0" in old_block:
            print("✅ /api/tang/memories 已是最新版本，跳过。")
        else:
            # 保留 mem_start 前的装饰器（如果有多个装饰器行）
            # 我们已经从最外层 decorator 开始，直接替换
            lines = lines[:mem_start] + FIXED_MEMORIES_ROUTE.strip("\n").split("\n") + [""] + lines[mem_end:]
            print("✅ 已修复 /api/tang/memories（排序 + strength 计算）")

    src = "\n".join(lines)

    # ── 步骤 2：追加 love_note / logs 路由 ───────────────────────────────
    if "/api/tang/love_note" in src:
        print("✅ /api/tang/love_note 已存在，跳过。")
    else:
        if MAIN_MARKER not in src:
            print(f"❌ 找不到标记 {MAIN_MARKER!r}，无法插入新路由")
            sys.exit(1)
        pos = src.index(MAIN_MARKER)
        src = src[:pos] + NEW_ROUTES + src[pos:]
        print("✅ 已添加 /api/tang/love_note 路由")

    if "/api/tang/logs" in src:
        print("✅ /api/tang/logs 已存在，跳过。")
    else:
        # love_note 已插入，logs 一起插入了
        print("✅ 已添加 /api/tang/logs 路由")

    # ── 步骤 3：写回 ──────────────────────────────────────────────────────
    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(src)
    print("📝 server.py 已更新")

    # ── 步骤 4：重启服务 ──────────────────────────────────────────────────
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

    # ── 步骤 5：快速 curl 测试 ────────────────────────────────────────────
    import urllib.request, json, time
    BASE = "http://127.0.0.1:8890"
    time.sleep(1)  # 等服务启动

    def test_post(path, label):
        try:
            req = urllib.request.Request(
                BASE + path,
                data=b"",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read())
            print(f"   ✅ {label}: {list(body.keys())}")
            return body
        except Exception as e:
            print(f"   ❌ {label}: {e}")
            return None

    print("\n🧪 测试接口 …")
    test_post("/api/tang/memories", "POST /api/tang/memories")
    test_post("/api/tang/love_note", "POST /api/tang/love_note")
    test_post("/api/tang/logs",      "POST /api/tang/logs")

    print("\n🎉 patch_server_v3 完成！")
    print("   memories ✦ love_note ✦ logs 三个接口均已就绪")


if __name__ == "__main__":
    patch()
