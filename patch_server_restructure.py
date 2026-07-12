#!/usr/bin/env python3
"""
棠予酿 MCP 服务端重构 + phone-sync 空数据防线
只做:
  1) 删除 __main__ 之后的死代码(从未执行过的重复/Override 定义),
     把其中"最终措辞"合并进真正生效的版本里
  2) receive_phone_data: apps 为空时返回 422,不再假装成功
  3) memory_hold/timeline_add/timeline_query/memory_grow/memory_trace
     的 `x: str = None` 类型注解改成 `x: str | None = None`(dict 同理)
不改数据库、不改其他任何逻辑。
"""
import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"

STRING_PATCHES = [
    # 1) _fmt_neko_usage_rows 措辞采用死代码里的"最终版"
    (
        '''def _fmt_neko_usage_rows(rows):
    if not rows:
        return {
            "ok": False,
            "error": "No app_usage data found in /root/data/dream_events.db for local today"
        }
    return {
        "ok": True,
        "source": "/root/data/dream_events.db",
        "count": len(rows),
        "events": rows,
    }''',
        '''def _fmt_neko_usage_rows(rows):
    if not rows:
        return {
            "ok": False,
            "error": "No app_usage data found in CodeAndPurrs dream_events.db"
        }
    return {
        "ok": True,
        "source": "CodeAndPurrs dream_events.db",
        "count": len(rows),
        "events": rows,
    }''',
    ),
    # 2) 三个 phone usage 工具 docstring 采用死代码里的"最终版"措辞
    (
        '''@app.tool()
def get_phone_app_usage() -> str:
    """获取手机今日 App 使用时长完整记录，来自 Neko Usage Bridge 共享 DB。"""
    rows = _neko_rows_from_codeandpurrs(80)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)

@app.tool()
def get_today_platform_usage() -> str:
    """获取今日常用平台统计，来自 Neko Usage Bridge 共享 DB。"""
    rows = _neko_rows_from_codeandpurrs(80)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)

@app.tool()
def get_phone_usage_summary() -> str:
    """获取手机今日使用总结，来自 Neko Usage Bridge 共享 DB。"""
    rows = _neko_rows_from_codeandpurrs(40)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)''',
        '''@app.tool()
def get_phone_app_usage() -> str:
    """获取手机今日 App 使用时长完整记录，来自 CodeAndPurrs / Neko Usage Bridge。"""
    rows = _neko_rows_from_codeandpurrs(80)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)

@app.tool()
def get_today_platform_usage() -> str:
    """获取今日常用平台统计，来自 CodeAndPurrs / Neko Usage Bridge。"""
    rows = _neko_rows_from_codeandpurrs(80)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)

@app.tool()
def get_phone_usage_summary() -> str:
    """获取手机今日使用总结，来自 CodeAndPurrs / Neko Usage Bridge。"""
    rows = _neko_rows_from_codeandpurrs(40)
    return json.dumps(_fmt_neko_usage_rows(rows), ensure_ascii=False, indent=2)''',
    ),
    # 3) phone-sync 空 apps 422 防线
    (
        '''            if isinstance(app_usage, dict):
                for k in ["apps", "records", "items"]:
                    if isinstance(app_usage.get(k), list):
                        app_usage = app_usage[k]
                        debug["unwrapped_from"] = f"app_usage.{k}"
                        break
            if isinstance(app_usage, list):
                created_at = body.get("synced_at") or body.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")

                for item in app_usage:''',
        '''            if isinstance(app_usage, dict):
                for k in ["apps", "records", "items"]:
                    if isinstance(app_usage.get(k), list):
                        app_usage = app_usage[k]
                        debug["unwrapped_from"] = f"app_usage.{k}"
                        break

            if not app_usage:
                print("phone-sync: empty apps list, nothing written. debug=", debug)
                return JSONResponse({
                    "status": "empty",
                    "reason": "apps list is empty, nothing written",
                    "debug": debug
                }, status_code=422)

            if isinstance(app_usage, list):
                created_at = body.get("synced_at") or body.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")

                for item in app_usage:''',
    ),
    # 4) memory_hold 类型注解
    (
        'def memory_hold(title: str, content: str, tag: str = "diary", importance: int = 5, mood: str = None, mood_emoji: str = None) -> str:',
        'def memory_hold(title: str, content: str, tag: str = "diary", importance: int = 5, mood: str | None = None, mood_emoji: str | None = None) -> str:',
    ),
    # 5) timeline_add 类型注解
    (
        'def timeline_add(content: str, category: str, date_str: str = None, start_at: str = None, end_at: str = None, subcategory: str = None, mood_emoji: str = None) -> str:',
        'def timeline_add(content: str, category: str, date_str: str | None = None, start_at: str | None = None, end_at: str | None = None, subcategory: str | None = None, mood_emoji: str | None = None) -> str:',
    ),
    # 6) timeline_query 类型注解
    (
        'def timeline_query(date_str: str = None, start_date: str = None, end_date: str = None, category: str = None, limit: int = 50) -> str:',
        'def timeline_query(date_str: str | None = None, start_date: str | None = None, end_date: str | None = None, category: str | None = None, limit: int = 50) -> str:',
    ),
    # 7) memory_trace 类型注解
    (
        'def memory_trace(memory_id: str, action: str, updates: dict = None) -> str:',
        'def memory_trace(memory_id: str, action: str, updates: dict | None = None) -> str:',
    ),
    # 8) memory_grow 类型注解
    (
        'def memory_grow(content: str, date_str: str = None, weather: str = None, love_note: str = None) -> str:',
        'def memory_grow(content: str, date_str: str | None = None, weather: str | None = None, love_note: str | None = None) -> str:',
    ),
]

# __main__ 之后的一切都是从未执行过的死代码,截断即可
MAIN_MARKER = 'if __name__ == "__main__":\n    app.run(transport="streamable-http", host="0.0.0.0", port=8890)\n'


def patch():
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if 'mood: str | None = None' in src and '# ===== Override old Tang phone usage tools' not in src:
        print("✅ server.py 已经打过这个补丁了,跳过。")
        return False

    backup = f"{SERVER_PATH}.bak.{int(time.time())}"
    shutil.copy(SERVER_PATH, backup)
    print(f"== 已备份 -> {backup} ==")

    for i, (old, new) in enumerate(STRING_PATCHES, 1):
        count = src.count(old)
        if count != 1:
            print(f"❌ 第 {i} 处补丁没匹配到(找到 {count} 处),中止,没有改任何东西。")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"✅ 第 {i} 处补丁匹配成功并替换")

    marker_count = src.count(MAIN_MARKER)
    if marker_count != 1:
        print(f"❌ __main__ 标记没匹配到(找到 {marker_count} 处),中止。")
        sys.exit(1)
    idx = src.index(MAIN_MARKER) + len(MAIN_MARKER)
    tail_len = len(src) - idx
    src = src[:idx]
    print(f"✅ 已截断 __main__ 之后的死代码(删除了 {tail_len} 字节的从未执行过的重复定义)")

    with open(SERVER_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print("== 语法检查 ==")
    r = subprocess.run([sys.executable, "-m", "py_compile", SERVER_PATH],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 语法检查失败,回滚:")
        print(r.stderr)
        shutil.copy(backup, SERVER_PATH)
        sys.exit(1)
    print("✅ 语法检查通过")

    return True


def restart_and_test():
    print("== 重启 mcp.service(不 kill)==")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    time.sleep(2)
    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    print("服务状态:", status.stdout.strip())

    print("\n== 自测 1: 空 apps 列表,期望 422 ==")
    r1 = subprocess.run([
        "curl", "-s", "-w", "\\nHTTP_STATUS:%{http_code}\\n",
        "-X", "POST", "http://127.0.0.1:8890/api/phone-sync",
        "-H", "Content-Type: application/json",
        "-H", "X-Auth-Token: nekopurrs-secret-2026",
        "-d", '{"apps": []}',
    ], capture_output=True, text=True)
    print(r1.stdout)

    print("\n== 自测 2: 正常 apps 列表,期望 200 ==")
    r2 = subprocess.run([
        "curl", "-s", "-w", "\\nHTTP_STATUS:%{http_code}\\n",
        "-X", "POST", "http://127.0.0.1:8890/api/phone-sync",
        "-H", "Content-Type: application/json",
        "-H", "X-Auth-Token: nekopurrs-secret-2026",
        "-d", '{"apps": [{"label": "TestApp", "minutes": 5}]}',
    ], capture_output=True, text=True)
    print(r2.stdout)


if __name__ == "__main__":
    changed = patch()
    if changed:
        restart_and_test()
