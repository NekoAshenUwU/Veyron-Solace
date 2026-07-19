#!/usr/bin/env python3
"""
棠予酿 MCP 工具层瘦身 —— 方案一 / memory_breathe 部分
(memory_pulse 的 lite 化已经在更早的补丁里做完了)

只做:
  1) tang_yu_niang/tools.py 的 memory_breathe: 加 brief 参数,默认 True。
     brief=True(默认): 每条只回 id/title/mood_emoji/tag/created_at/summary
     (summary = content 前50字 + 省略号)。
     brief=False: 回完整记忆(含 content 全文),向后兼容。
  2) server.py 里 memory_breathe 工具签名同步加 brief 参数并透传。
不改数据库、不改其他任何函数。
每一步都单独判断是否已生效,可以安全重复运行。
"""
import shutil
import subprocess
import sys
import time

TOOLS_PATH = "/root/tang_yu_niang/tools.py"
SERVER_PATH = "/root/server.py"

TOOLS_OLD = '''def memory_breathe(query=None, mood=None, tag=None, limit=5):
    """浮现记忆：无参数返回权重最高的未解决记忆+锚点，有query按关键词匹配"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    if query:
        sql = """SELECT * FROM memories
                 WHERE (title LIKE ? OR content LIKE ? OR keywords LIKE ?)"""
        args = [f"%{query}%", f"%{query}%", f"%{query}%"]
        if tag:
            sql += " AND tag = ?"
            args.append(tag)
        if mood:
            sql += " AND mood_label = ?"
            args.append(mood)
        sql += " ORDER BY strength DESC, importance DESC LIMIT ?"
        args.append(limit)
        rows = c.execute(sql, args).fetchall()
    else:
        anchors = c.execute("SELECT * FROM memories WHERE is_pinned=1 ORDER BY created_at DESC").fetchall()
        sql = "SELECT * FROM memories WHERE is_pinned=0 AND is_resolved=0"
        args = []
        if tag:
            sql += " AND tag = ?"
            args.append(tag)
        sql += " ORDER BY strength DESC LIMIT ?"
        args.append(limit)
        regular = c.execute(sql, args).fetchall()
        rows = list(anchors) + list(regular)

    for r in rows:
        c.execute("UPDATE memories SET activation_count=activation_count+1, last_activated_at=? WHERE id=?",
                  (now, r['id']))
    conn.commit()

    result = [dict(r) for r in rows]
    conn.close()
    _log("memory_breathe", {"query": query, "mood": mood, "tag": tag}, f"{len(result)}条")
    return json.dumps(result, ensure_ascii=False, indent=2)'''

TOOLS_NEW = '''def memory_breathe(query=None, mood=None, tag=None, limit=5, brief=True):
    """浮现记忆：无参数返回权重最高的未解决记忆+锚点，有query按关键词匹配。
    brief=True(默认)：每条只回 id/title/mood_emoji/tag/created_at/summary(前50字)；
    brief=False：回完整记忆(含 content 全文)"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    if query:
        sql = """SELECT * FROM memories
                 WHERE (title LIKE ? OR content LIKE ? OR keywords LIKE ?)"""
        args = [f"%{query}%", f"%{query}%", f"%{query}%"]
        if tag:
            sql += " AND tag = ?"
            args.append(tag)
        if mood:
            sql += " AND mood_label = ?"
            args.append(mood)
        sql += " ORDER BY strength DESC, importance DESC LIMIT ?"
        args.append(limit)
        rows = c.execute(sql, args).fetchall()
    else:
        anchors = c.execute("SELECT * FROM memories WHERE is_pinned=1 ORDER BY created_at DESC").fetchall()
        sql = "SELECT * FROM memories WHERE is_pinned=0 AND is_resolved=0"
        args = []
        if tag:
            sql += " AND tag = ?"
            args.append(tag)
        sql += " ORDER BY strength DESC LIMIT ?"
        args.append(limit)
        regular = c.execute(sql, args).fetchall()
        rows = list(anchors) + list(regular)

    for r in rows:
        c.execute("UPDATE memories SET activation_count=activation_count+1, last_activated_at=? WHERE id=?",
                  (now, r['id']))
    conn.commit()

    if brief:
        result = []
        for r in rows:
            content = r['content'] or ''
            summary = content[:50] + ('…' if len(content) > 50 else '')
            result.append({
                'id': r['id'],
                'title': r['title'],
                'mood_emoji': r['mood_emoji'],
                'tag': r['tag'],
                'created_at': r['created_at'],
                'summary': summary,
            })
    else:
        result = [dict(r) for r in rows]

    conn.close()
    _log("memory_breathe", {"query": query, "mood": mood, "tag": tag, "brief": brief}, f"{len(result)}条")
    return json.dumps(result, ensure_ascii=False, indent=2)'''

SERVER_OLD = '''@app.tool()
def memory_breathe(query: str | None = None, mood: str | None = None, tag: str | None = None, limit: int = 5) -> str:
    """浮现记忆 — 按关键词/心情/标签检索相关记忆"""
    return _tyn.memory_breathe(query, mood, tag, limit)'''

SERVER_NEW = '''@app.tool()
def memory_breathe(query: str | None = None, mood: str | None = None, tag: str | None = None, limit: int = 5, brief: bool = True) -> str:
    """浮现记忆 — 按关键词/心情/标签检索相关记忆。brief=True(默认)只回标题+50字摘要，brief=False 回完整记忆含全文"""
    return _tyn.memory_breathe(query, mood, tag, limit, brief)'''


def apply_patch(path, label, old, new):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    if old not in src:
        if new in src:
            print(f"✅ [{label}] 已经是新版,跳过")
            return False
        print(f"❌ [{label}] 旧版和新版都没匹配到,结构跟预期不一样,中止,不动文件。")
        sys.exit(1)

    count = src.count(old)
    if count != 1:
        print(f"❌ [{label}] 旧版匹配到 {count} 处(预期1处),中止,不动文件。")
        sys.exit(1)

    backup = f"{path}.bak.{int(time.time())}"
    shutil.copy(path, backup)
    print(f"== [{label}] 已备份 -> {backup} ==")

    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"✅ [{label}] 匹配成功并替换")
    return True


def check_syntax(path):
    r = subprocess.run([sys.executable, "-m", "py_compile", path], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ {path} 语法检查失败:")
        print(r.stderr)
        sys.exit(1)
    print(f"✅ {path} 语法检查通过")


def main():
    changed_tools = apply_patch(TOOLS_PATH, "tools.py: memory_breathe brief", TOOLS_OLD, TOOLS_NEW)
    changed_server = apply_patch(SERVER_PATH, "server.py: memory_breathe 签名", SERVER_OLD, SERVER_NEW)

    if not (changed_tools or changed_server):
        print("== 都已经生效,无需重启 ==")
        return

    check_syntax(TOOLS_PATH)
    check_syntax(SERVER_PATH)

    print("== 重启 mcp.service(不 kill)==")
    r = subprocess.run(["systemctl", "restart", "mcp.service"], capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ 重启失败:", r.stderr)
        sys.exit(1)

    time.sleep(3)
    status = subprocess.run(["systemctl", "is-active", "mcp.service"], capture_output=True, text=True)
    print("服务状态:", status.stdout.strip())

    print("\n== 自测：/internal/breathe 默认(brief) ==")
    subprocess.run(["curl", "-s", "http://127.0.0.1:8890/internal/breathe?limit=3"])
    print()


if __name__ == "__main__":
    main()
