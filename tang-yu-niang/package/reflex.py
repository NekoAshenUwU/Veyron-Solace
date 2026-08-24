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
from datetime import datetime, timezone

from . import strength
from .db import get_conn
from .timeline import timeline_query

# category 没配 target_tag 时，各自默认捞哪些 tag
CATEGORY_TAGS = {
    "emotion": ("anchor", "love_note"),
    "entity": ("diary",),
}

# category 决定排序方式
# 排序必须带一个唯一的 tiebreak，否则同输入不同输出。
#
# 2026-08-23 查库发现：memories.strength 全库都是 1.0（anchor 11 条、
# love_note 29、diary 71，min=avg=max 全是 1.0）。也就是说
# "ORDER BY strength DESC" 所有行并列，SQLite 按内部顺序随便给——
# 予予实测同一句话两次撞出完全不重叠的结果，一半是这个原因
# （另一半是 24 小时去重）。
#
# created_at 同理：日记常常一整批同一天写的，8 月 4 号那批就是。
#
# 加 id DESC 兜底：id 唯一，排序就唯一了。
CATEGORY_ORDER = {
    "emotion": "strength DESC, id DESC",
    "entity": "created_at DESC, id DESC",
}

# 去重会吃掉一部分结果，所以先多捞几倍再裁到 limit。
#
# 光乘 limit 不够：配额把 limit 压到 2 之后窗口只有 8 条，24 小时去重
# 吃掉前 7 条强锚点就只剩 1 条能返回，名额白给了。配额越小越容易饿死。
# 池子本来就小（anchor 11 / love_note 29 / diary 71），给个下限一次多捞点，
# 代价可以忽略。
OVERFETCH = 4
MIN_FETCH = 80

# 一次调用【总共】最多回几条，不管命中了几个词。
# 没有这个上限的话是每个词各拿 limit 条然后累加：
# 「今天好累，弟弟又来找我，CC 那边代码还没跑完」命中 累/弟弟/CC/代码 四个词，
# 一次灌回 12 条。那不是反射，是把抽屉整个翻倒。
MAX_TOTAL_RESULTS = 5

# 这个 category 要不要拿关键词去比对正文。
#
#   entity  = True —— 说「弟弟」就该捞【提到弟弟的】日记。原来只按 tag='diary'
#             加 created_at DESC，捞回来的是「最近的日记」，跟弟弟没关系；
#             予予实测撞出 8 月 4 号那一整批碎片，就是这么来的。
#   emotion = False —— 这个是【故意】不比对正文的：说「累」的时候要浮上来的
#             不是「写过累字的记忆」，而是最强的那几条锚点。按情绪给安慰，
#             不是按字面检索。改这条之前先想清楚要的是哪种。
CATEGORY_MATCH_CONTENT = {"emotion": False, "entity": True}

# 按 tag 分配名额，而不是把几个 tag 混在一起取 top-N。
#
# 混着取的问题不在第一次，在【去重之后】。
# love_note 基线 0.80，锚点里有 7 条在 0.80 以上，所以头几次撞出来的
# 确实是锚点。但 24 小时去重把这 7 条吃掉之后，29 条并列 0.80 的情话
# 就全部排在剩下 4 条锚点（0.75/0.70/0.65/0.30）前面——那 4 条一整天
# 都不可能浮上来，而后半天说「累」拿到的会是清一色情话。
# 配额把这条路堵死：anchor 永远有 2 个名额。
#
# 配额是【硬的】：anchor 那 2 个名额没取满也不给 love_note 补。
# 补了就等于又回到数量说了算。
CATEGORY_QUOTA = {
    "emotion": (("anchor", 2), ("love_note", 1)),
}


# brief 模式下正文截断到多少字
BRIEF_CHARS = 50


def _slim(row: dict) -> dict:
    """brief 模式：只留标题和摘要，别把全文灌进上下文。"""
    content = (row.get("content") or "").strip()
    if len(content) > BRIEF_CHARS:
        content = content[:BRIEF_CHARS] + "…"
    return {
        k: v for k, v in (
            ("id", row.get("id")),
            ("title", row.get("title")),
            ("tag", row.get("tag")),
            ("mood_emoji", row.get("mood_emoji")),
            ("created_at", row.get("created_at")),
            ("content", content),
        ) if v not in (None, "")
    }


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
    """
    emotion / entity 分支：查 memories。

    这个 category 配了名额、而且这个词没有自己指定 target_tag 的话，
    按 tag 一个个取，各取各的名额。
    """
    quota = CATEGORY_QUOTA.get(kw["category"])
    if quota and not kw["target_tag"]:
        out = []
        for tag, n in quota:
            sub = dict(kw)
            sub["target_tag"] = tag
            sub["limit"] = n
            out.extend(_query_one_tag(conn, sub, seen))
        return out
    return _query_one_tag(conn, kw, seen)


def _query_one_tag(conn, kw, seen: set) -> list:
    tags = (kw["target_tag"],) if kw["target_tag"] else CATEGORY_TAGS[kw["category"]]
    order = CATEGORY_ORDER[kw["category"]]
    limit = kw["limit"] or 3

    placeholders = ",".join("?" * len(tags))
    sql = f"SELECT * FROM memories WHERE tag IN ({placeholders})"
    params = [*tags]

    if CATEGORY_MATCH_CONTENT.get(kw["category"]):
        # 关键词自己也得出现在这条记忆里，否则捞回来的只是「最近的」。
        # LIKE 的通配符要转义，不然词表里一个 % 或 _ 就变成万能匹配。
        needle = (kw["keyword"].replace("\\", "\\\\")
                  .replace("%", "\\%").replace("_", "\\_"))
        sql += (" AND (IFNULL(title,'') LIKE ? ESCAPE '\\' "
                "OR IFNULL(content,'') LIKE ? ESCAPE '\\')")
        params += [f"%{needle}%", f"%{needle}%"]

    sql += f" ORDER BY {order} LIMIT ?"
    params.append(max(limit * OVERFETCH, MIN_FETCH))
    rows = conn.execute(sql, params).fetchall()

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


def _bump_activation(conn, rows) -> None:
    """
    浮现即回升：这次真的返回给予予的记忆，activation_count +1、
    last_activated_at 推到现在，并就地重算 strength。

    只对【最终真的返回了】的那几条动手——截断掉的不算浮现过。
    pinned 的 anchor 也记次数（那是真实发生过的事），但 strength 不碰。

    跟 24 小时去重不冲突：去重挡的是「今天再浮现一次」，不是「永远不能」。
    所以每条记忆最多每 24 小时回升一次——这反而是好的，否则一次对话里
    同一条被反复浮现，强度就飙上天了。
    """
    if not rows:
        return
    now = datetime.now(timezone.utc).astimezone()
    now_iso = now.replace(microsecond=0).isoformat()
    for r in rows:
        nxt = dict(r)
        nxt["activation_count"] = (r.get("activation_count") or 0) + 1
        nxt["last_activated_at"] = now_iso
        if strength.is_manual(nxt):
            conn.execute(
                "UPDATE memories SET activation_count = ?, last_activated_at = ? "
                "WHERE id = ?",
                (nxt["activation_count"], now_iso, r["id"]),
            )
        else:
            conn.execute(
                "UPDATE memories SET activation_count = ?, last_activated_at = ?, "
                "strength = ? WHERE id = ?",
                (nxt["activation_count"], now_iso, strength.derived(nxt, now), r["id"]),
            )


def memory_reflex(text: str, brief: bool = True) -> str:
    """
    反射 — 把文本对词表做子串匹配，命中则浮现对应记忆。

    brief=True（默认）只回标题 + 50 字摘要；brief=False 回整行含 content 全文。
    默认收着，是因为多词命中就是 n×limit 条全文一起灌进来，上下文会炸。

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
            from_memories = set()      # timeline 那支不在 memories 表里，别去 UPDATE

            # 按 emotion → entity → temporal 的顺序处理，输出稳定
            order = {"emotion": 0, "entity": 1, "temporal": 2}
            for kw in sorted(hits, key=lambda k: order.get(k["category"], 9)):
                if kw["category"] == "temporal":
                    found = _query_timeline(kw, seen)
                elif kw["category"] in CATEGORY_TAGS:
                    found = _query_memories(conn, kw, seen)
                    from_memories.update(r["id"] for r in found)
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
                if len(results) >= MAX_TOTAL_RESULTS:
                    results = results[:MAX_TOTAL_RESULTS]
                    break

            # 截断之后才回升——被截掉的那几条没进予予的上下文，不算浮现过
            _bump_activation(conn, [r for r in results if r.get("id") in from_memories])

            conn.commit()
            if brief:
                results = [_slim(r) for r in results]
            return json.dumps(results, ensure_ascii=False, indent=2)
        finally:
            conn.close()

    except Exception:
        # 静默失败。不打印、不抛、不返回任何文字。
        return "[]"
