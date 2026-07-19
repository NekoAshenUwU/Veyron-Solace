#!/usr/bin/env python3
"""
棠予酿前端"点开看全文" —— 按 id 单取全文修复

背景: memory_pulse 默认 lite 之后,首页"最近记忆"列表条目不再带 content。
之前前端点击直接用 pulse 返回的对象 setDetail(m),现在 m 没有 content,
点开日记类条目就是空的。

只做:
  1) server.py 的 /api/tang/memories 路由: 加 id 参数支持,传 id 时精确查询单条
     (含 content 全文),不传 id 行为不变(向后兼容)。
  2) /var/www/tang/index.html 的 HomeTab: "最近记忆"点击时,如果 m.content
     是 undefined(说明是 lite 数据),先按 id 查一次全文再打开详情弹窗；
     如果已经有 content(比如以后某处已经是全量数据)直接打开,不多打一次请求。
不改数据库、不改其他任何路由/组件。
每一步都单独判断是否已生效,可以安全重复运行。
"""
import shutil
import subprocess
import sys
import time

SERVER_PATH = "/root/server.py"
HTML_PATH = "/var/www/tang/index.html"

SERVER_OLD = '''@app.custom_route("/api/tang/memories", methods=["GET", "POST"])
async def tang_memories_http(request):
    """记忆库：按 importance DESC, access_count DESC 排序，strength = importance / 5.0"""
    if not _tang_api_token_ok(request):
        return _tang_api_denied()
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
        sql += " ORDER BY importance DESC, activation_count DESC LIMIT 100"
        rows = conn.execute(sql, args).fetchall()
        conn.close()
        mems = []
        for r in rows:
            d = dict(r)
            imp = d.get("importance") or 5
            d["strength"] = round(min(imp / 5.0, 1.0), 3)
            mems.append(d)
        return JSONResponse({"memories": mems})
    except Exception as e:
        return JSONResponse({"memories": [], "error": str(e)})'''

SERVER_NEW = '''@app.custom_route("/api/tang/memories", methods=["GET", "POST"])
async def tang_memories_http(request):
    """记忆库：按 importance DESC, access_count DESC 排序，strength = importance / 5.0。
    传 id 时精确查询单条(含 content 全文),用于前端按需拉全文。"""
    if not _tang_api_token_ok(request):
        return _tang_api_denied()
    import sqlite3 as _sq3
    _DB = "/root/data/tang_yu_niang.db"
    params = dict(request.query_params)
    tag = params.get("tag", "").strip()
    q   = params.get("q",   "").strip()
    mem_id = params.get("id", "").strip()
    try:
        conn = _sq3.connect(_DB)
        conn.row_factory = _sq3.Row
        if mem_id:
            rows = conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchall()
        else:
            sql  = "SELECT * FROM memories WHERE 1=1"
            args = []
            if tag:
                sql += " AND tag=?"
                args.append(tag)
            if q:
                sql += " AND (title LIKE ? OR content LIKE ? OR keywords LIKE ?)"
                args += [f"%{q}%", f"%{q}%", f"%{q}%"]
            sql += " ORDER BY importance DESC, activation_count DESC LIMIT 100"
            rows = conn.execute(sql, args).fetchall()
        conn.close()
        mems = []
        for r in rows:
            d = dict(r)
            imp = d.get("importance") or 5
            d["strength"] = round(min(imp / 5.0, 1.0), 3)
            mems.append(d)
        return JSONResponse({"memories": mems})
    except Exception as e:
        return JSONResponse({"memories": [], "error": str(e)})'''

HTML_OLD_1 = '''  const [calDate, setCalDate] = useState(null);
  const [clicked, setClicked] = useState(null);
  const [detail,  setDetail]  = useState(null);
  const tap = (item, idx) => {
    setClicked(idx);
    setTimeout(() => setClicked(null), 320);
    item.fn();
  };'''

HTML_NEW_1 = '''  const [calDate, setCalDate] = useState(null);
  const [clicked, setClicked] = useState(null);
  const [detail,  setDetail]  = useState(null);
  const tap = (item, idx) => {
    setClicked(idx);
    setTimeout(() => setClicked(null), 320);
    item.fn();
  };
  const openDetail = async (m) => {
    if (m.content !== undefined) { setDetail(m); return; }
    const res = await api('/memories?id=' + m.id);
    const full = res && res.memories && res.memories[0];
    setDetail(full || m);
  };'''

HTML_OLD_2 = '''          {recent.slice(0,3).map((m,i) => (
            <G key={i} onClick={() => setDetail(m)} style={{padding:'15px 18px',marginBottom:'10px',cursor:'pointer',animation:`slideUp 0.42s ease-out ${i*0.09}s both`}}>'''

HTML_NEW_2 = '''          {recent.slice(0,3).map((m,i) => (
            <G key={i} onClick={() => openDetail(m)} style={{padding:'15px 18px',marginBottom:'10px',cursor:'pointer',animation:`slideUp 0.42s ease-out ${i*0.09}s both`}}>'''


def patch_file(path, patches):
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    src = original
    any_changed = False
    for label, old, new in patches:
        if old not in src:
            if new in src:
                print(f"✅ [{label}] 已经是新版,跳过")
                continue
            print(f"❌ [{label}] 旧版和新版都没匹配到,结构跟预期不一样,中止,不动文件。")
            sys.exit(1)
        count = src.count(old)
        if count != 1:
            print(f"❌ [{label}] 旧版匹配到 {count} 处(预期1处),中止,不动文件。")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"✅ [{label}] 匹配成功并替换")
        any_changed = True

    if not any_changed:
        return False

    backup = f"{path}.bak.{int(time.time())}"
    shutil.copy(path, backup)
    print(f"== 已备份 {path} -> {backup} ==")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return True


def main():
    server_changed = patch_file(SERVER_PATH, [("server.py: /api/tang/memories 加 id 支持", SERVER_OLD, SERVER_NEW)])
    html_changed = patch_file(HTML_PATH, [
        ("index.html: openDetail 函数", HTML_OLD_1, HTML_NEW_1),
        ("index.html: 最近记忆点击改用 openDetail", HTML_OLD_2, HTML_NEW_2),
    ])

    if server_changed:
        print("== server.py 语法检查 ==")
        r = subprocess.run([sys.executable, "-m", "py_compile", SERVER_PATH], capture_output=True, text=True)
        if r.returncode != 0:
            print("❌ 语法检查失败:")
            print(r.stderr)
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

    if html_changed:
        print("== index.html 是静态文件,nginx 直接 serve,不需要重启任何服务,浏览器刷新即可生效 ==")

    if not server_changed and not html_changed:
        print("== 两边都已经是新版,什么都没做 ==")


if __name__ == "__main__":
    main()
