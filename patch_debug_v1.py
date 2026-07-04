#!/usr/bin/env python3
"""
patch_debug_v1.py — 临时给 _internal_auth_check 的 401 响应加调试字段，
排查"env var 确认存在、curl 带了正确 key，还是 401"这个诡异现象。

只做一件事：把 patch_server_v5.py 写进去的 _internal_auth_check 函数体
原样替换成带调试信息的版本(多返回 expected/got 的长度+首尾几个字符+
Starlette 实际收到的全部 header 名单，不打印完整密钥)。

跑完之后带 key curl 一次 /internal/pulse，把 "_debug" 字段贴出来，
就知道到底是 header 没传到、key 长度不对、还是别的什么。

用法（在 VPS 上）：
    python3 /root/patch_debug_v1.py
"""

import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"

OLD_BLOCK = '''def _internal_auth_check(request):
    import os as _os
    from starlette.responses import JSONResponse as _JR
    expected = _os.environ.get("TANG_INTERNAL_KEY", "").strip()
    got = (request.headers.get("x-internal-key") or "").strip()
    if not expected or got != expected:
        return _JR({"error": "unauthorized"}, status_code=401)
    client_host = request.client.host if request.client else None
    if client_host != "127.0.0.1":
        return _JR({"error": "forbidden"}, status_code=403)
    return None'''

NEW_BLOCK = '''def _internal_auth_check(request):
    import os as _os
    from starlette.responses import JSONResponse as _JR
    expected = _os.environ.get("TANG_INTERNAL_KEY", "").strip()
    got = (request.headers.get("x-internal-key") or "").strip()
    if not expected or got != expected:
        return _JR({
            "error": "unauthorized",
            "_debug": {
                "expected_len": len(expected),
                "expected_edges": (expected[:4] + "..." + expected[-4:]) if expected else "",
                "got_len": len(got),
                "got_edges": (got[:4] + "..." + got[-4:]) if got else "",
                "header_keys_seen": list(request.headers.keys()),
            },
        }, status_code=401)
    client_host = request.client.host if request.client else None
    if client_host != "127.0.0.1":
        return _JR({"error": "forbidden", "_debug": {"client_host": client_host}}, status_code=403)
    return None'''


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if OLD_BLOCK not in src:
        if "_debug" in src and "_internal_auth_check" in src:
            print("✅ 调试版本已经在跑了，跳过写入。")
        else:
            print("❌ 没找到预期的 _internal_auth_check 原文，手动确认一下 server.py 现状再说")
            sys.exit(1)
    else:
        backup_path = f"{SERVER_PATH}.bak-debug-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SERVER_PATH, backup_path)
        print(f"📦 已备份到 {backup_path}")
        src = src.replace(OLD_BLOCK, NEW_BLOCK)
        with open(SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ 已写入带调试字段的临时版本")

    print("🔄 重启 mcp.service …")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)
    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    print(f"   状态: {status.stdout.strip()}")
    print("\n现在手动跑一次带 key 的 curl，把 _debug 字段贴给我：")
    print('   curl -s -H "X-Internal-Key: f3ZrpmWaMmo8FBd5HLPX_O6XPvGvTh7TzO6ZFWv6vQc" http://127.0.0.1:8890/internal/pulse')


if __name__ == "__main__":
    patch()
