#!/usr/bin/env python3
"""
棠予酿 pulse 瘦身 — server.py 打补丁
只改 3 处：
  1. memory_pulse() 工具签名 + 调用，加 mode 参数
  2. /api/tang/pulse REST 路由，透传 mode
  3. /internal/pulse REST 路由，透传 mode
不动其他任何函数/路由。
"""
import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"

PATCHES = [
    (
        '@app.tool()\n'
        'def memory_pulse() -> str:\n'
        '    """记忆脉搏 — 查看当前记忆系统状态和今日心情"""\n'
        '    return _tyn.memory_pulse()\n',
        '@app.tool()\n'
        'def memory_pulse(mode: str = "lite") -> str:\n'
        '    """记忆脉搏 — 查看当前记忆系统状态和今日心情"""\n'
        '    return _tyn.memory_pulse(mode)\n',
    ),
    (
        '@app.custom_route("/api/tang/pulse", methods=["POST"])\n'
        'async def _api_pulse(request):\n'
        '    if not _tang_api_token_ok(request):\n'
        '        return _tang_api_denied()\n'
        '    return JSONResponse(_json.loads(memory_pulse()))\n',
        '@app.custom_route("/api/tang/pulse", methods=["POST"])\n'
        'async def _api_pulse(request):\n'
        '    if not _tang_api_token_ok(request):\n'
        '        return _tang_api_denied()\n'
        '    mode = request.query_params.get("mode", "lite")\n'
        '    return JSONResponse(_json.loads(memory_pulse(mode)))\n',
    ),
    (
        '@app.custom_route("/internal/pulse", methods=["GET"])\n'
        'async def internal_pulse_http(request):\n'
        '    _deny = _internal_auth_check(request)\n'
        '    if _deny:\n'
        '        return _deny\n'
        '    from starlette.responses import Response\n'
        '    from tang_yu_niang.tools import memory_pulse\n'
        '    return Response(memory_pulse(), media_type="application/json")\n',
        '@app.custom_route("/internal/pulse", methods=["GET"])\n'
        'async def internal_pulse_http(request):\n'
        '    _deny = _internal_auth_check(request)\n'
        '    if _deny:\n'
        '        return _deny\n'
        '    from starlette.responses import Response\n'
        '    from tang_yu_niang.tools import memory_pulse\n'
        '    mode = request.query_params.get("mode", "lite")\n'
        '    return Response(memory_pulse(mode), media_type="application/json")\n',
    ),
]


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if 'def memory_pulse(mode: str = "lite")' in src:
        print("✅ server.py 已经打过这个补丁了，跳过。")
        return False

    backup = f"{SERVER_PATH}.bak.{int(time.time())}"
    shutil.copy(SERVER_PATH, backup)
    print(f"== 已备份 -> {backup} ==")

    for i, (old, new) in enumerate(PATCHES, 1):
        count = src.count(old)
        if count != 1:
            print(f"❌ 第 {i} 处补丁没匹配到（找到 {count} 处），中止，没有改任何东西。")
            print("--- 期望匹配的原文 ---")
            print(old)
            sys.exit(1)
        src = src.replace(old, new)
        print(f"✅ 第 {i} 处补丁匹配成功并替换")

    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print("== 语法检查 ==")
    r = subprocess.run([sys.executable, "-m", "py_compile", SERVER_PATH],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 语法检查失败，回滚：")
        print(r.stderr)
        shutil.copy(backup, SERVER_PATH)
        sys.exit(1)

    return True


def restart_and_test():
    print("== 重启 mcp.service（不 kill）==")
    r = subprocess.run(["systemctl", "restart", "mcp"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    time.sleep(2)
    status = subprocess.run(["systemctl", "is-active", "mcp"], capture_output=True, text=True)
    print("服务状态:", status.stdout.strip())

    print("\n== 自测：/internal/pulse 默认(lite) ==")
    subprocess.run(["curl", "-s", "http://127.0.0.1:8890/internal/pulse"])
    print("\n\n== 自测：/internal/pulse?mode=full ==")
    subprocess.run(["curl", "-s", "http://127.0.0.1:8890/internal/pulse?mode=full"])
    print()


if __name__ == "__main__":
    changed = patch()
    if changed:
        restart_and_test()
