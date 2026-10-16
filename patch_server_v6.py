#!/usr/bin/env python3
"""
patch_server_v6.py — 修 /internal/diary/list 排序:改成 importance DESC 优先

老婆反馈:予予每次读到的 10 条日记全按 created_at 倒序,重要度 9-10 的老日记
根本进不了 top 10。改成 ORDER BY importance DESC, created_at DESC:重要度高
的排前面(90%~100% 的日记优先),同重要度内再按时间倒序。CodeAndPurrs 那侧
也从 20 → 10 减半,同步生效。

沿用 patch_server_v3/v4/v5 的幂等风格,只改 /root/server.py 一个文件:
- 找到 /internal/diary/list 那个函数
- 把 "ORDER BY created_at DESC LIMIT ? OFFSET ?" 换成
     "ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?"

安全:
- 只 systemctl restart mcp.service (只重启,不 kill)
- 改前自动 cp 一份 .bak-<timestamp>
- 不碰 OAuth / MCP 工具 / 其它 internal 路由 / systemd unit / nginx
- 保持 CodeAndPurrs internal 通道其它 5 条路由不变

用法(在 VPS 上):
    python3 /root/patch_server_v6.py
"""

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

SERVER_PATH = "/root/server.py"
OLD_SQL = "SELECT * FROM memories WHERE tag='diary' ORDER BY created_at DESC LIMIT ? OFFSET ?"
NEW_SQL = "SELECT * FROM memories WHERE tag='diary' ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?"


def patch():
    if not os.path.exists(SERVER_PATH):
        print(f"❌ 找不到 {SERVER_PATH}")
        sys.exit(1)

    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if NEW_SQL in src:
        print(f"✅ /internal/diary/list 已经是 importance DESC 排序,跳过。")
    elif OLD_SQL not in src:
        print(f"❌ 找不到原来的 diary/list SQL: {OLD_SQL!r}")
        print(f"   手动查一下 /root/server.py 里 /internal/diary/list 的 SQL 长什么样再说")
        sys.exit(1)
    else:
        backup_path = f"{SERVER_PATH}.bak-v6-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SERVER_PATH, backup_path)
        print(f"📦 已备份到 {backup_path}")
        src = src.replace(OLD_SQL, NEW_SQL)
        with open(SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ /internal/diary/list SQL 换成 importance DESC, created_at DESC")

    print("🔄 重启 mcp.service (只用 systemctl restart, 绝不 kill 占端口的进程)...")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    state = status.stdout.strip()
    print(f"   状态: {state}")
    if state != "active":
        print("⚠️  服务未 active, 请检查: journalctl -u mcp.service -n 30")
        sys.exit(1)

    # 等 FastMCP 完整启动 (systemctl is-active 会先于 uvicorn bind 上端口)
    time.sleep(5)

    print("\n🧪 自测 /internal/diary/list ...")
    key_line = None
    try:
        with open("/root/mcp-oauth.env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TANG_INTERNAL_KEY="):
                    key_line = line.strip().split("=", 1)[1]
                    break
    except Exception as e:
        print(f"   读 mcp-oauth.env 失败: {e}")
    if not key_line:
        print("   ⚠️  TANG_INTERNAL_KEY 没读到,跳过自测。手动:")
        print('      KEY=$(grep "^TANG_INTERNAL_KEY=" /root/mcp-oauth.env | cut -d= -f2)')
        print('      curl -sH "X-Internal-Key: $KEY" http://127.0.0.1:8890/internal/diary/list?limit=3')
        return

    req = urllib.request.Request(
        "http://127.0.0.1:8890/internal/diary/list?limit=3",
        headers={"X-Internal-Key": key_line},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
        # 简单解析: 看前 3 条的 importance 是不是从大到小
        import json as _json

        rows = _json.loads(body)
        if not isinstance(rows, list) or len(rows) == 0:
            print("   ⚠️  没拿到日记条目,可能棠予酿库里没有 tag=diary 的记录")
        else:
            imps = [r.get("importance", 0) for r in rows]
            print(f"   前 3 条 importance = {imps}")
            if imps == sorted(imps, reverse=True):
                print("   ✅ importance DESC 排序生效")
            else:
                print("   ⚠️  排序看着不对,手动查一下")
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP 错: {e.code} {e.read().decode()[:200]}")
    except Exception as e:
        print(f"   ❌ 自测失败: {e}")

    print("\n🎉 patch_server_v6 完成!")


if __name__ == "__main__":
    patch()
