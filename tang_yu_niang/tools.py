"""棠予酿 MCP 工具：memory_breathe / memory_hold / memory_pulse"""
import json
import uuid
import random
from datetime import datetime, date
from tang_yu_niang.db import get_conn
from tang_yu_niang.dehydrator import extract_keywords, estimate_emotion

START_DATE = date(2025, 12, 26)

FLAVORS = ["芋泥波波","桃桃乌龙","椰子奶冻","芒果椰椰","草莓鲜奶","紫薯芋圆",
           "蜜桃四季春","荔枝玫瑰","杨枝甘露","蓝莓酸奶","焦糖布丁","樱花拿铁",
           "玫瑰荔枝","香芋珍珠"]


def _day_count():
    return (date.today() - START_DATE).days + 1


def _today_flavor():
    r = random.Random(date.today().toordinal())
    return r.choice(FLAVORS)


def _log(tool, params, summary, status="success"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (tool_name, parameters, result_summary, status, created_at) VALUES (?,?,?,?,?)",
        (tool, json.dumps(params, ensure_ascii=False), str(summary)[:200], status, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def memory_breathe(query=None, mood=None, tag=None, limit=5):
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
    return json.dumps(result, ensure_ascii=False, indent=2)


def memory_hold(title, content, tag="diary", importance=5, mood=None, mood_emoji=None):
    """存储记忆。tag: diary/treasure/anchor"""
    keywords = extract_keywords(content)
    emotion = estimate_emotion(content, mood)
    if mood_emoji:
        emotion['mood_emoji'] = mood_emoji

    now = datetime.now().isoformat()
    mid = str(uuid.uuid4())
    is_pinned = 1 if tag == 'anchor' else 0

    conn = get_conn()
    conn.execute("""
        INSERT INTO memories (id, title, content, tag, keywords, valence, arousal,
        mood_label, mood_emoji, importance, strength, is_pinned,
        created_at, updated_at, last_activated_at, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,1.0,?,?,?,?,'chat')
    """, (mid, title, content, tag, ','.join(keywords),
          emotion['valence'], emotion['arousal'], emotion['mood_label'],
          emotion['mood_emoji'], importance, is_pinned, now, now, now))
    conn.commit()
    conn.close()

    _log("memory_hold", {"title": title, "tag": tag}, f"已存储 {mid[:8]}")
    return json.dumps({"status": "ok", "id": mid, "keywords": keywords, "emotion": emotion},
                      ensure_ascii=False, indent=2)


def memory_pulse():
    """系统状态：在一起天数、今日回甘、记忆统计"""
    conn = get_conn()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    by_tag = {r[0]: r[1] for r in c.execute("SELECT tag, COUNT(*) FROM memories GROUP BY tag").fetchall()}
    pinned = c.execute("SELECT COUNT(*) FROM memories WHERE is_pinned=1").fetchone()[0]
    today = date.today().isoformat()
    today_new = c.execute("SELECT COUNT(*) FROM memories WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0]
    recent = c.execute("SELECT id, title, mood_emoji, strength FROM memories ORDER BY created_at DESC LIMIT 5").fetchall()
    conn.close()

    result = {
        "在一起第几天": _day_count(),
        "今日回甘": _today_flavor(),
        "总记忆数": total,
        "各标签": by_tag,
        "置顶锚点": pinned,
        "今日新增": today_new,
        "最近记忆": [dict(r) for r in recent],
    }
    _log("memory_pulse", {}, f"总计{total}条")
    return json.dumps(result, ensure_ascii=False, indent=2)
