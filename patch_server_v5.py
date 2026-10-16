#!/usr/bin/env python3
"""
patch_server_v5.py — 给 CodeAndPurrs 开一条只读/受限写的内部通道，读写棠予酿的记忆和日记。

新增 6 条 /internal/* 路由，全部先过 _internal_auth_check(X-Internal-Key 头 +
来源 IP=127.0.0.1)，两条有一条不过直接 401/403，不执行任何业务逻辑：

  GET  /internal/pulse                            → 复用 tang_yu_niang.tools.memory_pulse
  GET  /internal/breathe?query=&mood=&tag=&limit= → 复用 tang_yu_niang.tools.memory_breathe
  GET  /internal/diary/list?limit=&offset=        → tag='diary'，created_at 倒序(带 offset；
                                                      memory_recent 本身不支持 offset，这条是
                                                      唯一没有直接复用现成函数的路由，SQL 写法
                                                      完全照抄 memory_recent 的风格)
  GET  /internal/diary/{diary_id}                 → 单篇详情，同样限定 tag='diary'
  POST /internal/memory/hold                      → 复用 tang_yu_niang.tools.memory_hold
  POST /internal/memory/grow                      → 复用 tang_yu_niang.extras.memory_grow

安全三件套：
  a. X-Internal-Key 头校验，密钥从 /root/mcp-oauth.env 的 TANG_INTERNAL_KEY 读——
     不存在就自动生成一个写进去(只追加，不改已有内容)，脚本跑完打印出来，
     抄去 CodeAndPurrs 的 .env。全程走已有的 EnvironmentFile=/root/mcp-oauth.env
     (在 mcp.service.d/oauth.conf 里，早就配好了)，不碰任何 systemd unit 文件。
  b. 来源 IP 校验，非 127.0.0.1 一律 403——这是内层第二道防线。
  c. nginx 的 /internal/ deny all 是外层第一道防线，这个脚本不动 nginx 配置，
     照 TANG_PROTECT_DO_NOT_TOUCH.md 的规矩("改 nginx 前先备份，再 curl -I 小步
     验证")，配置片段和验证步骤打印在脚本最后，手动做。

这份脚本被批准做的事，仅限于此：
  - 只 systemctl restart mcp.service，永远不 kill 占 8890 端口的进程。
  - 改 server.py 前整份 cp 一份 .bak-<timestamp>。
  - 不碰 OAuth/GitHub 登录/JWT 那部分代码一行。
  - 不改 memory_pulse/memory_breathe/memory_hold/memory_grow 本身的函数签名和行为——
    只在外面包一层 HTTP 路由，直接 import 调用现成函数，函数体完全不动。
  - 不碰 /var/www/tang，不碰 systemd unit 文件（.env 只追加不改已有行）。

用法（在 VPS 上）：
    python3 /root/patch_server_v5.py
"""

import os
import shutil
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

SERVER_PATH = "/root/server.py"
ENV_PATH = "/root/mcp-oauth.env"
MAIN_MARKER = 'if __name__ == "__main__":'
CHECK_STRING = "/internal/pulse"

NEW_ROUTES = '''

# ── CodeAndPurrs 内部通道 v5：/internal/* ──────────────────────────────────
# 安全三件套里的 a(key)+b(来源IP) 在这个 helper 里判，6 条路由都调它，
# 以后改校验逻辑只用改这一处。c(nginx deny all)是外层，另外单独配置。
def _internal_auth_check(request):
    import os as _os
    from starlette.responses import JSONResponse as _JR
    expected = _os.environ.get("TANG_INTERNAL_KEY", "").strip()
    got = (request.headers.get("x-internal-key") or "").strip()
    if not expected or got != expected:
        return _JR({"error": "unauthorized"}, status_code=401)
    client_host = request.client.host if request.client else None
    if client_host != "127.0.0.1":
        return _JR({"error": "forbidden"}, status_code=403)
    return None


@app.custom_route("/internal/pulse", methods=["GET"])
async def internal_pulse_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import Response
    from tang_yu_niang.tools import memory_pulse
    return Response(memory_pulse(), media_type="application/json")


@app.custom_route("/internal/breathe", methods=["GET"])
async def internal_breathe_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import Response
    from tang_yu_niang.tools import memory_breathe
    params = dict(request.query_params)
    query = params.get("query") or None
    mood = params.get("mood") or None
    tag = params.get("tag") or None
    limit = int(params.get("limit", 5))
    return Response(
        memory_breathe(query=query, mood=mood, tag=tag, limit=limit),
        media_type="application/json",
    )


@app.custom_route("/internal/diary/list", methods=["GET"])
async def internal_diary_list_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import JSONResponse
    from tang_yu_niang.db import get_conn
    from tang_yu_niang.tools import _log
    params = dict(request.query_params)
    limit = int(params.get("limit", 20))
    offset = int(params.get("offset", 0))
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM memories WHERE tag='diary' ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    _log("internal_diary_list", {"limit": limit, "offset": offset}, f"返回{len(result)}条")
    return JSONResponse(result)


@app.custom_route("/internal/diary/{diary_id}", methods=["GET"])
async def internal_diary_detail_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import JSONResponse
    from tang_yu_niang.db import get_conn
    from tang_yu_niang.tools import _log
    diary_id = request.path_params["diary_id"]
    conn = get_conn()
    c = conn.cursor()
    row = c.execute(
        "SELECT * FROM memories WHERE id=? AND tag='diary'",
        (diary_id,),
    ).fetchone()
    conn.close()
    if not row:
        _log("internal_diary_detail", {"id": diary_id}, "not found")
        return JSONResponse({"error": "not found"}, status_code=404)
    _log("internal_diary_detail", {"id": diary_id}, "ok")
    return JSONResponse(dict(row))


@app.custom_route("/internal/memory/hold", methods=["POST"])
async def internal_memory_hold_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import Response, JSONResponse
    from tang_yu_niang.tools import memory_hold
    import json as _json
    try:
        body = await request.body()
        data = _json.loads(body) if body else {}
    except Exception as e:
        return JSONResponse({"error": f"bad json: {e}"}, status_code=400)
    title = str(data.get("title", "")).strip()
    content = str(data.get("content", "")).strip()
    if not title or not content:
        return JSONResponse({"error": "title and content are required"}, status_code=400)
    tag = str(data.get("tag", "diary"))
    importance = int(data.get("importance", 5))
    mood = data.get("mood")
    mood_emoji = data.get("mood_emoji")
    result = memory_hold(title, content, tag=tag, importance=importance, mood=mood, mood_emoji=mood_emoji)
    return Response(result, media_type="application/json")


@app.custom_route("/internal/memory/grow", methods=["POST"])
async def internal_memory_grow_http(request):
    _deny = _internal_auth_check(request)
    if _deny:
        return _deny
    from starlette.responses import Response, JSONResponse
    from tang_yu_niang.extras import memory_grow
    import json as _json
    try:
        body = await request.body()
        data = _json.loads(body) if body else {}
    except Exception as e:
        return JSONResponse({"error": f"bad json: {e}"}, status_code=400)
    content = str(data.get("content", "")).strip()
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)
    date_str = data.get("date_str")
    weather = data.get("weather")
    love_note = data.get("love_note")
    result = memory_grow(content, date_str, weather, love_note)
    return Response(result, media_type="application/json")

# ── / CodeAndPurrs 内部通道 v5 ──────────────────────────────────────────────
'''


def ensure_internal_key():
    """TANG_INTERNAL_KEY 不存在就生成一个追加进 /root/mcp-oauth.env(不改已有行)，返回最终值。"""
    existing = ""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("TANG_INTERNAL_KEY="):
                    existing = line.strip().split("=", 1)[1].strip()
                    break
    if existing:
        print(f"✅ TANG_INTERNAL_KEY 已存在于 {ENV_PATH}，沿用现有值。")
        return existing

    new_key = secrets.token_urlsafe(32)
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write(f"\nTANG_INTERNAL_KEY={new_key}\n")
    print(f"✅ 已生成新 TANG_INTERNAL_KEY 并追加到 {ENV_PATH}（只追加，没动已有内容）")
    return new_key


def patch():
    if not os.path.exists(SERVER_PATH):
        print(f"❌ 找不到 {SERVER_PATH}")
        sys.exit(1)

    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if CHECK_STRING in src:
        print(f"✅ {CHECK_STRING} 已存在，跳过写入 server.py（幂等，不重复插入）")
    else:
        backup_path = f"{SERVER_PATH}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SERVER_PATH, backup_path)
        print(f"📦 已备份原文件到 {backup_path}")

        if MAIN_MARKER not in src:
            print(f"❌ 找不到标记 {MAIN_MARKER!r}，无法插入新路由，未做任何修改")
            sys.exit(1)
        pos = src.index(MAIN_MARKER)
        src = src[:pos] + NEW_ROUTES + src[pos:]
        with open(SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ 已写入 6 条 /internal/* 路由")

    key = ensure_internal_key()

    print("🔄 重启 mcp.service（只用 systemctl restart，绝不 kill 占端口的进程）…")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    state = status.stdout.strip()
    print(f"   状态: {state}")
    if state != "active":
        print("⚠️  服务未 active，请检查: journalctl -u mcp.service -n 30")
        sys.exit(1)

    time.sleep(1)
    BASE = "http://127.0.0.1:8890"

    def _get(path, headers=None):
        req = urllib.request.Request(BASE + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
        except Exception as e:
            return None, str(e)

    print("\n🧪 自测 …")
    code, body = _get("/internal/pulse")
    print(f"   不带 key  GET /internal/pulse → {code}（应为 401）")

    code, body = _get("/internal/pulse", {"X-Internal-Key": key})
    print(f"   带正确key GET /internal/pulse → {code}")
    if code == 200:
        print(f"   {body[:300]}{'...' if len(body) > 300 else ''}")

    print(f"\n🔑 TANG_INTERNAL_KEY = {key}")
    print("   把这个值抄到 CodeAndPurrs 的 .env 里（变量名也叫 TANG_INTERNAL_KEY）。")
    print("\n🎉 patch_server_v5 完成！6 条 /internal/* 路由已就绪。")
    print("\n⚠️  下一步(这个脚本不会自动做，按 TANG_PROTECT_DO_NOT_TOUCH.md 的规矩手动来)：")
    print("   1. nginx 加一条 /internal/ deny all，改之前先备份对应的 /etc/nginx/sites-available/ 文件")
    print("   2. sudo nginx -t 验证语法")
    print("   3. sudo systemctl reload nginx（reload 不是 restart，不会中断现有连接）")
    print("   4. curl -I https://mcp.nekopurrs.uk/internal/pulse 确认外网拿到 403/404")
    print("\n   （/internal/diary/{diary_id} 这条带路径参数的路由没有自动跑自测，")
    print("    建议手动 curl 一下确认 Starlette 的 {param} 语法在 @app.custom_route 下正常工作）")


if __name__ == "__main__":
    patch()
