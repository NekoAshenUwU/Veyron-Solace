"""
棠予酿 — 扩展工具
包含: memory_tidal / memory_trace / memory_grow / love_note_draw
"""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

DB_PATH = "/root/data/tang_yu_niang.db"

LAMBDA_DECAY = 0.05
AROUSAL_BOOST = 0.3
START_DATE = datetime(2025, 12, 26)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _extract_keywords_simple(text: str, max_n: int = 5) -> str:
    import re
    tokens = re.findall(r"[一-鿿A-Za-z]{2,4}", text)
    seen, out = set(), []
    for t in tokens:
        if t not in seen and len(out) < max_n:
            seen.add(t)
            out.append(t)
    return ",".join(out)


# ── 遗忘曲线 ──────────────────────────────────────────────────────────────
def _calc_strength(row: sqlite3.Row, now: datetime) -> float:
    if row["is_pinned"]:
        return 1.0
    try:
        last_act = datetime.fromisoformat(
            row["last_activated_at"] or row["created_at"]
        )
    except Exception:
        last_act = now
    days = max((now - last_act).total_seconds() / 86400, 0.0)
    base_mult = 0.05 if row["is_resolved"] else 1.0
    act_count = max(row["activation_count"], 1)
    s = (
        (row["importance"] / 10.0)
        * (act_count ** 0.3)
        * math.exp(-LAMBDA_DECAY * days)
        * (0.7 + (row["arousal"] or 0.5) * AROUSAL_BOOST)
        * base_mult
    )
    return round(min(max(s, 0.0), 1.0), 3)


def _tidal_direction(row: sqlite3.Row, now: datetime) -> str:
    if row["is_pinned"]:
        return "pinned"
    try:
        last_act = datetime.fromisoformat(
            row["last_activated_at"] or row["created_at"]
        )
    except Exception:
        return "stable"
    days = (now - last_act).days
    if days < 3:
        return "rising"
    if days > 30:
        return "deep_falling"
    return "falling"


# ── 1) memory_tidal ───────────────────────────────────────────────────────
def memory_tidal(limit: int = 20, direction: str = "all") -> str:
    """按strength排序返回记忆的潮汐状态"""
    conn = _conn()
    try:
        rows = conn.execute("""
            SELECT id, title, tag, mood_emoji, importance, arousal,
                   is_pinned, is_resolved, activation_count,
                   created_at, last_activated_at
            FROM memories
        """).fetchall()

        now = datetime.now()
        items = []
        for r in rows:
            s = _calc_strength(r, now)
            d = _tidal_direction(r, now)
            if direction != "all" and direction != d:
                continue
            items.append({
                "id": r["id"],
                "title": r["title"],
                "tag": r["tag"],
                "mood_emoji": r["mood_emoji"],
                "strength": s,
                "strength_pct": f"{int(s*100)}%",
                "direction": d,
            })
        items.sort(key=lambda x: x["strength"], reverse=True)

        return json.dumps({
            "total": len(items),
            "items": items[:limit],
        }, ensure_ascii=False, indent=2)
    finally:
        conn.close()


# ── 2) memory_trace ───────────────────────────────────────────────────────
def memory_trace(memory_id: str, action: str,
                 updates: Optional[dict] = None) -> str:
    """修改记忆元数据"""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT id, title FROM memories WHERE id=?", (memory_id,)
        ).fetchone()
        if not row:
            return json.dumps(
                {"ok": False, "error": f"memory {memory_id} not found"},
                ensure_ascii=False,
            )

        title = row["title"]
        ts = _now_iso()

        if action == "resolve":
            conn.execute(
                "UPDATE memories SET is_resolved=1, updated_at=? WHERE id=?",
                (ts, memory_id),
            )
            msg = f"✅ 已解决: {title}"
        elif action == "pin":
            conn.execute(
                "UPDATE memories SET is_pinned=1, updated_at=? WHERE id=?",
                (ts, memory_id),
            )
            msg = f"📌 已置顶: {title}"
        elif action == "unpin":
            conn.execute(
                "UPDATE memories SET is_pinned=0, updated_at=? WHERE id=?",
                (ts, memory_id),
            )
            msg = f"📍 已取消置顶: {title}"
        elif action == "delete":
            conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            msg = f"🗑️  已删除: {title}"
        elif action == "update":
            if not updates:
                return json.dumps(
                    {"ok": False, "error": "update action requires 'updates'"},
                    ensure_ascii=False,
                )
            allowed = {
                "title", "content", "tag", "importance",
                "mood_label", "mood_emoji", "keywords",
            }
            fields, values = [], []
            for k, v in updates.items():
                if k in allowed:
                    fields.append(f"{k}=?")
                    values.append(v)
            if not fields:
                return json.dumps(
                    {"ok": False, "error": "no valid fields"},
                    ensure_ascii=False,
                )
            values.extend([ts, memory_id])
            conn.execute(
                f"UPDATE memories SET {','.join(fields)}, updated_at=? WHERE id=?",
                values,
            )
            msg = f"✏️  更新了 {len(fields)} 个字段: {title}"
        else:
            return json.dumps(
                {"ok": False, "error": f"unknown action: {action}"},
                ensure_ascii=False,
            )

        conn.commit()
        return json.dumps({"ok": True, "message": msg}, ensure_ascii=False)
    finally:
        conn.close()


# ── 3) memory_grow ────────────────────────────────────────────────────────
def memory_grow(content: str, date_str: Optional[str] = None,
                weather: Optional[str] = None,
                love_note: Optional[str] = None) -> str:
    """把长日记拆分为多条记忆"""
    if not content.strip():
        return json.dumps(
            {"ok": False, "error": "empty content"}, ensure_ascii=False
        )

    today_str = date_str or datetime.now().strftime("%Y-%m-%d")

    # 段落切分（双/单换行），至少10字才算一段
    raw_parts = content.replace("\n\n", "\n").split("\n")
    chunks = [p.strip() for p in raw_parts if len(p.strip()) >= 10]
    if not chunks:
        chunks = [content.strip()]

    conn = _conn()
    try:
        created = []
        for i, chunk in enumerate(chunks):
            mid = str(uuid.uuid4())
            ts = f"{today_str}T12:00:00"
            snippet = chunk[:14].replace("\n", " ")
            title = f"{today_str} {snippet}…"
            conn.execute("""
                INSERT INTO memories (
                    id, title, content, tag, keywords,
                    valence, arousal, mood_label, mood_emoji,
                    importance, strength, activation_count,
                    is_resolved, is_pinned,
                    created_at, updated_at, last_activated_at, source
                ) VALUES (?, ?, ?, 'diary', ?, 0.0, 0.5, NULL, NULL,
                          5, 1.0, 0, 0, 0, ?, ?, ?, 'memory_grow')
            """, (
                mid, title, chunk,
                _extract_keywords_simple(chunk),
                ts, ts, ts,
            ))
            created.append({"id": mid, "title": title})

        if love_note:
            ln_id = str(uuid.uuid4())
            ts = _now_iso()
            conn.execute("""
                INSERT INTO memories (
                    id, title, content, tag, keywords,
                    valence, arousal, mood_label, mood_emoji,
                    importance, strength, activation_count,
                    is_resolved, is_pinned,
                    created_at, updated_at, last_activated_at, source
                ) VALUES (?, ?, ?, 'love_note', ?, 0.8, 0.4, '甜', '💗',
                          3, 1.0, 0, 0, 0, ?, ?, ?, 'memory_grow')
            """, (
                ln_id, love_note[:14], love_note,
                _extract_keywords_simple(love_note),
                ts, ts, ts,
            ))

        conn.commit()

        # 在一起第几天
        today_dt = datetime.fromisoformat(today_str)
        day_count = (today_dt - START_DATE).days + 1

        return json.dumps({
            "ok": True,
            "date": today_str,
            "day_count": day_count,
            "weather": weather,
            "created_count": len(created),
            "created": created,
            "love_note_saved": bool(love_note),
            "message": f"📖 {today_str} (第{day_count}天) 归档 {len(created)} 条",
        }, ensure_ascii=False, indent=2)
    finally:
        conn.close()


# ── 4) love_note_draw ─────────────────────────────────────────────────────
def love_note_draw() -> str:
    """从情话库随机抽一条"""
    conn = _conn()
    try:
        row = conn.execute("""
            SELECT id, content FROM memories
            WHERE tag='love_note'
            ORDER BY RANDOM()
            LIMIT 1
        """).fetchone()
        if not row:
            return json.dumps(
                {"ok": False, "error": "情话库是空的 🌸"},
                ensure_ascii=False,
            )
        ts = _now_iso()
        conn.execute("""
            UPDATE memories
            SET activation_count = activation_count + 1,
                last_activated_at=?
            WHERE id=?
        """, (ts, row["id"]))
        conn.commit()
        return json.dumps(
            {"ok": True, "content": row["content"]},
            ensure_ascii=False,
        )
    finally:
        conn.close()
