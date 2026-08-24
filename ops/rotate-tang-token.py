#!/usr/bin/env python3
"""
轮换 TANG_WEB_TOKEN —— 一条命令跑完，不用填任何东西。

为什么要脚本：这个值同时住在 nginx、env 文件、systemd drop-in 好几处，
手工一处处改极容易漏（2026-08-25 就漏过：nginx 改了、后端没改，网页当场
进不去）。而且中间夹占位符的命令串会在 bash 里报 syntax error 然后
【继续往下跑】，把 unset 也执行掉，新值就丢了。

做法：从 nginx 配置里读出【当前正在用的】那个值，拿它去搜所有该改的文件，
逐个替换。搜真值而不是搜变量名——只有真值出现的地方才需要改。

全程不打印 token，只报长度。

跑法：
    python3 rotate-tang-token.py              # 只看会改哪些文件，不落盘
    python3 rotate-tang-token.py --apply
"""

import argparse
import pathlib
import re
import secrets
import shutil
import sys
from datetime import datetime

NGINX = pathlib.Path("/etc/nginx/sites-enabled/tang")
BACKUP_DIR = pathlib.Path("/root/token-rotation-backups")

# 去这些地方找真值。刻意【不】碰 ~/.claude（那是会话日志，改了没意义）
# 和任何备份目录（改了反而毁掉回退的退路）。
SEARCH = [
    pathlib.Path("/etc/nginx/sites-enabled"),
    pathlib.Path("/etc/systemd/system"),
    pathlib.Path("/root/mcp-oauth.env"),
]
SKIP = ("backups", "nginx-backups", "token-rotation-backups", ".bak", ".save", ".claude")


def current_token() -> str | None:
    if not NGINX.exists():
        return None
    m = re.search(r'X-Tang-Token\s+"([^"]+)"', NGINX.read_text())
    return m.group(1) if m else None


def candidates(old: str) -> list:
    hits = []
    for root in SEARCH:
        if not root.exists():
            continue
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for f in files:
            if not f.is_file() or any(s in str(f) for s in SKIP):
                continue
            try:
                if old in f.read_text():
                    hits.append(f)
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    old = current_token()
    if not old:
        print(f"× 从 {NGINX} 里读不出 X-Tang-Token，已中止", file=sys.stderr)
        return 1

    files = candidates(old)
    print(f"当前 token 长度 {len(old)}，出现在 {len(files)} 个文件里：\n")
    for f in files:
        print(f"    {f}")

    if NGINX not in files:
        print(f"\n× {NGINX} 不在名单里，说明搜索逻辑有问题，已中止", file=sys.stderr)
        return 1
    if len(files) < 2:
        print("\n！只找到 nginx 一处。后端读的值不在搜索范围里——"
              "先确认后端从哪拿这个值，别改。", file=sys.stderr)
        return 1

    new = "tw_" + secrets.token_urlsafe(33).replace("-", "_")[:45]

    if not a.apply:
        print(f"\n会把这 {len(files)} 个文件里的旧值一次性换成新值（长度 {len(new)}）。")
        print("（没落盘）确认没问题就加 --apply")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for f in files:
        bak = BACKUP_DIR / f"{f.name}.{stamp}"
        shutil.copy2(f, bak)
        f.write_text(f.read_text().replace(old, new))
    print(f"\n  ✓ 改了 {len(files)} 个文件，备份在 {BACKUP_DIR}/*.{stamp}")
    print("\n下一步（顺序不能反，nginx 和后端要同时是新值）：")
    print("  nginx -t && systemctl reload nginx")
    print("  systemctl daemon-reload")
    print("  systemctl restart mcp tang-web")
    print("\n然后刷新 tang.nekopurrs.uk 确认还能进。")
    print(f"要回退：cp {BACKUP_DIR}/*.{stamp} 回原位再 reload。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
