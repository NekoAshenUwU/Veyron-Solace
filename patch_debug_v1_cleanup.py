#!/usr/bin/env python3
"""
patch_debug_v1_cleanup.py — 撤掉 patch_debug_v1.py 加的调试字段，
换回 patch_server_v5.py 原本干净的 _internal_auth_check。

诊断已经结束：确认是手机键盘/剪贴板在手动重打 key 时把中间某个字符
换成了看起来一样、编码不同的字符，不是代码逻辑的问题。以后校验 key
一律用 `KEY=$(grep '^TANG_INTERNAL_KEY=' /root/mcp-oauth.env | cut -d= -f2)`
从文件里读，不再手动复制粘贴到 curl 命令里。

用法（在 VPS 上）：
    python3 /root/patch_debug_v1_cleanup.py
"""

import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"

DEBUG_BLOCK = '''def _internal_auth_check(request):
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

CLEAN_BLOCK = '''def _internal_auth_check(request):
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


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if DEBUG_BLOCK not in src:
        if CLEAN_BLOCK in src:
            print("✅ 已经是干净版本，跳过。")
        else:
            print("❌ 没找到调试版本的原文，手动确认一下 server.py 现状再说")
            sys.exit(1)
    else:
        backup_path = f"{SERVER_PATH}.bak-cleanup-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SERVER_PATH, backup_path)
        print(f"📦 已备份到 {backup_path}")
        src = src.replace(DEBUG_BLOCK, CLEAN_BLOCK)
        with open(SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ 已撤掉调试字段，换回干净版本")

    print("🔄 重启 mcp.service …")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)
    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    print(f"   状态: {status.stdout.strip()}")

    print("\n验证一下（从文件读 key，不要手打）：")
    print("   KEY=$(grep '^TANG_INTERNAL_KEY=' /root/mcp-oauth.env | cut -d= -f2)")
    print('   curl -s -o /dev/null -w "%{http_code}\\n" -H "X-Internal-Key: $KEY" http://127.0.0.1:8890/internal/pulse')
    print("   应该是 200，且响应体里不再有 _debug 字段。")


if __name__ == "__main__":
    patch()
