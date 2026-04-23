"""生活轨迹：从对话中记录生活片段，按日查询"""
import json
import uuid
from datetime import datetime, date
from tang_yu_niang.db import get_conn


def timeline_add(content, category, date_str=None, start_at=None, end_at=None,
                 subcategory=None, mood_emoji=None):
    """记录一个生活片段。
    
    category 常用：吃饭 / 睡觉 / 心情 / 事件 / 工作 / 休闲 / 关系
    subcategory 例：早餐 / 午觉 / 开心 / 看电影
    start_at / end_at 格式：'HH:MM'（可选）
    """
    today = date_str or date.today().isoformat()
    eid = str(uuid.uuid4())
    now = datetime.now().isoformat()

    conn = get_conn()
    conn.execute("""
        INSERT INTO timeline_events
        (id, date, start_at, end_at, category, subcategory, content, mood_emoji, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (eid, today, start_at, end_at, category, subcategory, content, mood_emoji, now))
    conn.commit()
    conn.close()

    return json.dumps({
        "status": "ok", "id": eid, "date": today,
        "category": category, "content": content
    }, ensure_ascii=False, indent=2)


def timeline_query(date_str=None, start_date=None, end_date=None,
                   category=None, limit=50):
    """按日期查询生活轨迹。
    
    date_str=单日；start_date+end_date=范围；category=筛选分类。
    默认查今天。
    """
    conn = get_conn()
    c = conn.cursor()

    sql = "SELECT * FROM timeline_events WHERE 1=1"
    args = []

    if date_str:
        sql += " AND date = ?"
        args.append(date_str)
    elif start_date and end_date:
        sql += " AND date BETWEEN ? AND ?"
        args.extend([start_date, end_date])
    else:
        sql += " AND date = ?"
        args.append(date.today().isoformat())

    if category:
        sql += " AND category = ?"
        args.append(category)

    sql += " ORDER BY date DESC, start_at ASC, created_at ASC LIMIT ?"
    args.append(limit)

    rows = c.execute(sql, args).fetchall()
    conn.close()

    return json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2)
