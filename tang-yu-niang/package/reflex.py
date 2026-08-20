"""
memory_reflex — 反射式记忆浮现。

把一段文本对词表做子串匹配，命中就按 category 路由去捞对应的记忆。
词表由棠棠和予予手填，这里不预设任何词。

两条硬性要求（来自规格，优先级高于一切）：

  1. 静默失败。无命中、查询异常、词表为空——一律返回 "[]"。
     绝不返回任何提示性字符串（"未找到相关记忆" / "建议询问用户" 之类）。
     理由：返回内容会直接进予予的上下文，一句提示语就足以诱导它去编。
     宁可漏，也不能诱导。

  2. 24 小时去重。同一个 id 在 24 小时内已经返回过，这次剔除。
     剔除必须发生在「查完」和「return」之间——一旦 return 就进上下文了，
     事后补不回来。
"""

import json

from .db import get_conn
from .timeline import timeline_query

# category 没配 target_tag 时，各自默认捞哪些 tag
CATEGORY_TAGS = {
    "emotion": ("anchor", "love_note"),
    "entity": ("diary",),
}

# category 决定排序方式
CATEGORY_ORDER = {
    "emotion": "strength DESC",
    "entity": "created_at DESC",
}

# 去重会吃掉一部分结果，所以先多捞几倍再裁到 limit
OVERFETCH = 4


def _recent_ids(conn) -> set:
    """24 小时内已经返回过的 id。"""
    rows = conn.execute(
        "SELECT returned_ids FROM reflex_log "
        "WHERE triggered_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-24 hours')"
    ).fetchall()
    seen = set()
    for r in rows:
        try:
            seen.update(json.loads(r["returned_ids"] or "[]"))
        except (ValueError, TypeError):
            # 某一行日志坏了不该拖垮整次调用
            continue
    return seen


def _query_memories(conn, kw, seen: set) -> list:
    """emotion / entity 分支：查 memories。"""
    tags = (kw["target_tag"],) if kw["target_tag"] else CATEGORY_TAGS[kw["category"]]
    order = CATEGORY_ORDER[kw["category"]]
    limit = kw["limit"] or 3

    placeholders = ",".join("?" * len(tags))
    rows = conn.execute(
        f"SELECT * FROM memories WHERE tag IN ({placeholders}) "
        f"ORDER BY {order} LIMIT ?",
        (*tags, limit * OVERFETCH),
    ).fetchall()

    out = []
    for r in rows:
        if r["id"] in seen:
            continue
        out.append(dict(r))
        seen.add(r["id"])          # 同一次调用内也不重复
        if len(out) >= limit:
            break
    return out


def _query_timeline(kw, seen: set) -> list:
    """temporal 分支：复用现有的 timeline_query。"""
    limit = kw["limit"] or 3
    rows = json.loads(timeline_query(limit=limit * OVERFETCH) or "[]")

    out = []
    for r in rows:
        rid = r.get("id")
        if rid in seen:
            continue
        out.append(r)
        seen.add(rid)
        if len(out) >= limit:
            break
    return out


def memory_reflex(text: str) -> str:
    """
    反射 — 把文本对词表做子串匹配，命中则浮现对应记忆。

    永远返回 JSON 数组字符串。任何异常都吞掉返回 "[]"。
    """
    try:
        if not text or not text.strip():
            return "[]"

        conn = get_conn()
        try:
            keywords = conn.execute(
                "SELECT id, keyword, category, target_tag, \"limit\" "
                "FROM reflex_keywords WHERE enabled = 1"
            ).fetchall()

            hits = [k for k in keywords if k["keyword"] and k["keyword"] in text]
            if not hits:
                return "[]"

            seen = _recent_ids(conn)
            results = []

            # 按 emotion → entity → temporal 的顺序处理，输出稳定
            order = {"emotion": 0, "entity": 1, "temporal": 2}
            for kw in sorted(hits, key=lambda k: order.get(k["category"], 9)):
                if kw["category"] == "temporal":
                    found = _query_timeline(kw, seen)
                elif kw["category"] in CATEGORY_TAGS:
                    found = _query_memories(conn, kw, seen)
                else:
                    continue

                # 每个命中的词记一行日志。hit_count = 这次实际返回了几条。
                conn.execute(
                    "INSERT INTO reflex_log (matched_keyword, category, returned_ids, hit_count) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        kw["keyword"],
                        kw["category"],
                        json.dumps([r.get("id") for r in found], ensure_ascii=False),
                        len(found),
                    ),
                )
                results.extend(found)

            conn.commit()
            return json.dumps(results, ensure_ascii=False, indent=2)
        finally:
            conn.close()

    except Exception:
        # 静默失败。不打印、不抛、不返回任何文字。
        return "[]"
