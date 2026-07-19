#!/usr/bin/env python3
"""
棠予酿 MCP 工具层瘦身 —— 方案二 / limit 收紧

只做:
  server.py 的 get_phone_usage_summary(): 硬编码 _neko_rows_from_codeandpurrs(40)
  改成 limit 参数,默认 5,要多少拉多少(不再默认一次性拉 40 条)。
不改其他任何函数、不改数据库。
可以安全重复运行。
"""
import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"

OLD = '''@app.tool()
def get_phone_usage_summary() -> str:
    """获取手机今日使用总结，来自 CodeAndPurrs / Neko Usage Bridge。"""
    rows = _neko_rows_from_codeandpurrs(40)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)'''

NEW = '''@app.tool()
def get_phone_usage_summary(limit: int = 5) -> str:
    """获取手机今日使用总结，来自 CodeAndPurrs / Neko Usage Bridge。默认只拉最近5条，避免一次性占用过多上下文，需要更多可传 limit。"""
    rows = _neko_rows_from_codeandpurrs(limit)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)'''


def main():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if OLD not in src:
        if NEW in src:
            print("✅ 已经打过这个补丁了,跳过。")
            return
        print("❌ 旧版文本没匹配到,结构跟预期不一样,中止,不动文件。")
        sys.exit(1)

    count = src.count(OLD)
    if count != 1:
        print(f"❌ 匹配到 {count} 处(预期1处),中止,不动文件。")
        sys.exit(1)

    backup = f"{SERVER_PATH}.bak.{int(time.time())}"
    shutil.copy(SERVER_PATH, backup)
    print(f"== 已备份 -> {backup} ==")

    src = src.replace(OLD, NEW)
    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(src)
    print("✅ 已把 get_phone_usage_summary 的 limit 收紧为默认5")

    print("== 语法检查 ==")
    r = subprocess.run([sys.executable, "-m", "py_compile", SERVER_PATH], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 语法检查失败,回滚:")
        print(r.stderr)
        shutil.copy(backup, SERVER_PATH)
        sys.exit(1)
    print("✅ 语法检查通过")

    print("== 重启 mcp.service(不 kill)==")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    time.sleep(3)
    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    print("服务状态:", status.stdout.strip())


if __name__ == "__main__":
    main()
