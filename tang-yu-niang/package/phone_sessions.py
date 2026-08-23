#!/usr/bin/env python3
"""
棠予酿的两个手机工具：get_phone_sessions / get_sleep_gap。

读的是 Bridge 写进 usage_sessions / screen_events 的那两张表，
跟旧的快照统计（dream_events）井水不犯河水。

睡眠是【推断】出来的，不是测出来的：手机连着好几个钟头没有任何前台会话、
也没有一次亮屏，就当人睡了。所以它看到的是「没碰手机」，不是「睡着」——
放下手机看书两小时，这里一样会算成睡眠。工具的返回值里带 method 字段
写明这一点，免得读的人（包括模型）把它当成体征数据讲出去。

自检：
    python3 phone_sessions.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, date as _date, time as _time, timedelta, timezone

DEFAULT_DB = "/root/data/dream_events.db"
TZ = timezone(timedelta(hours=8))          # Asia/Kuching，跟 Bridge 那边一致

# 连续活动之间短于这个就并成一块，不算「分开的两次使用」
JOIN_MIN = 5
# 空白到这么久才算睡着
MIN_SLEEP_MIN = 60
# 夜里醒来短于这个，不切断睡眠，只记一笔 brief
SPLIT_MIN = 15
# 夜间窗口
NIGHT_START_H = 23
NIGHT_END_H = 7


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path, timeout=10)
    c.execute("PRAGMA busy_timeout=5000")
    c.row_factory = sqlite3.Row
    return c


def _today() -> str:
    return datetime.now(TZ).date().isoformat()


def _day_bounds(day: str) -> tuple[str, str]:
    d = _date.fromisoformat(day)
    lo = datetime.combine(d, _time(0, 0, 0), TZ)
    hi = datetime.combine(d, _time(23, 59, 59), TZ)
    return lo.isoformat(), hi.isoformat()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def get_phone_sessions(
    date_str: str | None = None,
    package: str | None = None,
    limit: int = 50,
    db_path: str = DEFAULT_DB,
) -> dict:
    """
    某一天的手机使用会话，按时间顺序。

    date_str  YYYY-MM-DD，不给就是今天
    package   包名片段，模糊匹配（"tencent" 能匹到 com.tencent.mm）
    limit     最多返回几条
    """
    day = date_str or _today()
    try:
        lo, hi = _day_bounds(day)
    except ValueError:
        return {"error": f"日期格式不对: {date_str}（要 YYYY-MM-DD）"}

    limit = max(1, min(int(limit or 50), 500))

    sql = ("SELECT package, label, start_ts, end_ts, duration_ms, open "
           "FROM usage_sessions WHERE start_ts BETWEEN ? AND ?")
    params: list = [lo, hi]
    if package:
        sql += " AND package LIKE ?"
        params.append(f"%{package}%")
    sql += " ORDER BY start_ts LIMIT ?"
    params.append(limit)

    c = _conn(db_path)
    try:
        rows = c.execute(sql, params).fetchall()
        total = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_ms), 0) FROM usage_sessions "
            "WHERE start_ts BETWEEN ? AND ?" + (" AND package LIKE ?" if package else ""),
            params[:2] + ([f"%{package}%"] if package else []),
        ).fetchone()
    finally:
        c.close()

    sessions = []
    for r in rows:
        sessions.append({
            "package": r["package"],
            "label": r["label"] or r["package"],
            "start": _fmt(datetime.fromisoformat(r["start_ts"])),
            "end": _fmt(datetime.fromisoformat(r["end_ts"])),
            "minutes": round(r["duration_ms"] / 60000, 1),
            "open": bool(r["open"]),
        })

    return {
        "date": day,
        "package_filter": package,
        "count": len(sessions),
        "total_matching": total[0],
        "total_minutes": round(total[1] / 60000, 1),
        "truncated": total[0] > len(sessions),
        "sessions": sessions,
    }


def _load_activity(day: str, db_path: str) -> tuple[list, str, str]:
    """
    取「前一天 18:00 → 当天 12:00」这个窗口里的全部活动痕迹。

    从 18:00 起是因为睡前那段得看得见，不然算不出是几点睡的；
    到中午 12:00 打住是因为再往后就是白天的正常使用了。
    """
    d = _date.fromisoformat(day)
    lo = datetime.combine(d - timedelta(days=1), _time(18, 0), TZ)
    hi = datetime.combine(d, _time(12, 0), TZ)
    lo_s, hi_s = lo.isoformat(), hi.isoformat()

    c = _conn(db_path)
    try:
        sess = c.execute(
            "SELECT start_ts, end_ts FROM usage_sessions "
            "WHERE end_ts >= ? AND start_ts <= ? ORDER BY start_ts",
            (lo_s, hi_s),
        ).fetchall()
        screen = c.execute(
            "SELECT ts FROM screen_events WHERE event_type IN "
            "('interactive', 'keyguard_hidden') AND ts BETWEEN ? AND ? ORDER BY ts",
            (lo_s, hi_s),
        ).fetchall()
    finally:
        c.close()

    spans = []
    for r in sess:
        a = max(datetime.fromisoformat(r["start_ts"]), lo)
        b = min(datetime.fromisoformat(r["end_ts"]), hi)
        if b > a:
            spans.append([a, b])
    # 亮屏是个时间点，给它零长度——它的作用是证明「这一刻人是醒的」
    for r in screen:
        t = datetime.fromisoformat(r["ts"])
        spans.append([t, t])

    spans.sort(key=lambda s: s[0])
    return spans, lo_s, hi_s


def _merge(spans: list) -> list:
    """相邻不到 JOIN_MIN 分钟的活动并成一块。"""
    out: list = []
    tol = timedelta(minutes=JOIN_MIN)
    for a, b in spans:
        if out and a - out[-1][1] <= tol:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _in_night(dt: datetime) -> bool:
    return dt.hour >= NIGHT_START_H or dt.hour < NIGHT_END_H


def get_sleep_gap(date_str: str | None = None, db_path: str = DEFAULT_DB) -> dict:
    """
    推断某一夜的睡眠：手机长时间没动 = 睡了。

    date_str 指的是【醒来那天】。查 2026-08-22 看的是 21 号晚上到 22 号早上。
    """
    day = date_str or _today()
    try:
        spans, win_lo, win_hi = _load_activity(day, db_path)
    except ValueError:
        return {"error": f"日期格式不对: {date_str}（要 YYYY-MM-DD）"}

    base = {
        "date": day,
        "window": {"from": win_lo, "to": win_hi},
        "method": "由手机无活动的空白推断，不是体征测量；放下手机做别的事也会算进去",
    }

    blocks = _merge(spans)
    if len(blocks) < 2:
        return {**base, "status": "数据不足",
                "note": "这个窗口里活动记录太少，推断不出来（Bridge 可能还没上报）",
                "activity_blocks": len(blocks)}

    # 块与块之间的空白 = 候选睡眠
    gaps = []
    for i in range(len(blocks) - 1):
        start, end = blocks[i][1], blocks[i + 1][0]
        minutes = (end - start).total_seconds() / 60
        if minutes >= MIN_SLEEP_MIN:
            gaps.append({"i": i, "start": start, "end": end, "minutes": minutes})

    if not gaps:
        return {**base, "status": "没找到睡眠",
                "note": f"整个窗口里没有超过 {MIN_SLEEP_MIN} 分钟的空白"}

    # 夜里醒来太短的（< SPLIT_MIN）不算把睡眠切断，把两段并回去
    segments: list = []
    wakes: list = []
    cur = dict(gaps[0])
    for nxt in gaps[1:]:
        wake_block = blocks[nxt["i"]]
        wake_min = (wake_block[1] - wake_block[0]).total_seconds() / 60
        brief = wake_min < SPLIT_MIN and _in_night(wake_block[0])
        wakes.append({
            "at": _fmt(wake_block[0]),
            "until": _fmt(wake_block[1]),
            "minutes": round(wake_min, 1),
            "brief": brief,
            "in_night_window": _in_night(wake_block[0]),
        })
        if brief:
            cur["end"] = nxt["end"]        # 并过去，当作没醒
            cur["minutes"] = (cur["end"] - cur["start"]).total_seconds() / 60
        else:
            segments.append(cur)
            cur = dict(nxt)
    segments.append(cur)

    total = sum(s["minutes"] for s in segments)
    return {
        **base,
        "status": "ok",
        "fell_asleep": _fmt(segments[0]["start"]),
        "woke_up": _fmt(segments[-1]["end"]),
        "total_sleep_minutes": round(total, 1),
        "total_sleep_hours": round(total / 60, 2),
        "segments": [
            {"from": _fmt(s["start"]), "to": _fmt(s["end"]),
             "minutes": round(s["minutes"], 1)}
            for s in segments
        ],
        "night_wakes": [w for w in wakes if w["in_night_window"]],
        "all_wakes": wakes,
    }


# ── 自检 ────────────────────────────────────────────────────────────────
# 直接照着验收标准那一夜造数据：
#   2026-08-22 → 21:12 睡 → 01:49 醒 → 02:25 再睡 → 06:35 起

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS usage_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, package TEXT NOT NULL, label TEXT,
        start_ts TEXT NOT NULL, end_ts TEXT NOT NULL, duration_ms INTEGER NOT NULL,
        open INTEGER NOT NULL DEFAULT 0 CHECK (open IN (0,1)), created_at TEXT NOT NULL,
        UNIQUE (package, start_ts))
    """,
    """
    CREATE TABLE IF NOT EXISTS screen_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        ts TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (event_type, ts))
    """,
]


def _self_test() -> int:
    """
    自检不依赖任何别的模块，也不碰生产库：临时库 + 直接插行。
    落库那一半是 CodeAndPurrs 的 usageBridgeServer.mjs 干的（Node），
    在那边验；这里只管「库里有这些行，工具能不能读对」。
    """
    import tempfile, os

    tmp = os.path.join(tempfile.mkdtemp(), "t.db")
    c = sqlite3.connect(tmp)
    for s in _DDL:
        c.execute(s)

    def S(pkg, a, b, label=None):
        a, b = a + "+08:00", b + "+08:00"
        ms = int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() * 1000)
        c.execute(
            "INSERT INTO usage_sessions (package,label,start_ts,end_ts,duration_ms,open,created_at)"
            " VALUES (?,?,?,?,?,0,'')", (pkg, label or pkg, a, b, ms),
        )

    def E(etype, at):
        c.execute("INSERT INTO screen_events (event_type,ts,created_at) VALUES (?,?,'')",
                  (etype, at + "+08:00"))

    # —— 21 号晚上，睡前刷手机 ——
    S("com.tencent.mm", "2026-08-21T20:30:00", "2026-08-21T21:12:00", "微信")
    # —— 01:49 醒来摸手机 36 分钟（会切断睡眠）——
    S("com.zhiliaoapp.musically", "2026-08-22T01:49:00", "2026-08-22T02:25:00", "TikTok")
    # —— 04:00 只亮了 3 分钟（不该切断睡眠）——
    S("com.android.systemui", "2026-08-22T04:00:00", "2026-08-22T04:03:00")
    # —— 早上起床 ——
    S("com.tencent.mm", "2026-08-22T06:35:00", "2026-08-22T07:10:00", "微信")
    # —— 白天，在窗口外，不该影响判断 ——
    S("com.tencent.mm", "2026-08-22T14:00:00", "2026-08-22T15:00:00", "微信")
    E("keyguard_hidden", "2026-08-22T01:49:00")
    E("keyguard_hidden", "2026-08-22T06:35:00")
    c.commit()
    c.close()

    fails = []

    def check(name, got, want):
        ok = got == want
        print(f"  {'✓' if ok else '×'} {name}: {got}" + ("" if ok else f"  (期望 {want})"))
        if not ok:
            fails.append(name)

    print("get_sleep_gap(2026-08-22)")
    r = get_sleep_gap("2026-08-22", db_path=tmp)
    check("状态", r["status"], "ok")
    check("入睡", r["fell_asleep"], "21:12")
    check("起床", r["woke_up"], "06:35")
    check("睡眠段数（36 分钟那次切开了）", len(r["segments"]), 2)
    check("第一段", (r["segments"][0]["from"], r["segments"][0]["to"]), ("21:12", "01:49"))
    check("第二段（4:00 那 3 分钟被并掉了）",
          (r["segments"][1]["from"], r["segments"][1]["to"]), ("02:25", "06:35"))
    check("总睡眠小时", r["total_sleep_hours"], round((277 + 250) / 60, 2))
    check("夜醒次数", len(r["night_wakes"]), 2)
    check("夜醒 1 时间", r["night_wakes"][0]["at"], "01:49")
    check("夜醒 1 时长", r["night_wakes"][0]["minutes"], 36.0)
    check("夜醒 1 不算 brief", r["night_wakes"][0]["brief"], False)
    check("夜醒 2 算 brief（没切断睡眠）", r["night_wakes"][1]["brief"], True)

    print("\nget_phone_sessions")
    r = get_phone_sessions("2026-08-22", db_path=tmp)
    check("22 号当天会话数（21 号那条不算）", r["count"], 4)
    check("按时间排序", [s["start"] for s in r["sessions"]],
          ["01:49", "04:00", "06:35", "14:00"])
    r = get_phone_sessions("2026-08-22", package="tencent", db_path=tmp)
    check("按 package 模糊过滤", [s["label"] for s in r["sessions"]], ["微信", "微信"])
    check("过滤后总时长（分钟）", r["total_minutes"], 95.0)
    r = get_phone_sessions("2026-08-22", limit=2, db_path=tmp)
    check("limit 生效", (r["count"], r["truncated"]), (2, True))
    r = get_phone_sessions("2026-08-30", db_path=tmp)
    check("空的一天不报错", (r["count"], r["total_minutes"]), (0, 0.0))
    r = get_sleep_gap("2026-08-30", db_path=tmp)
    check("没数据时给的是说明不是瞎猜", r["status"], "数据不足")
    r = get_phone_sessions("八月二十二", db_path=tmp)
    check("坏日期有 error", "error" in r, True)

    print()
    if fails:
        print(f"× 自检失败 {len(fails)} 项: {', '.join(fails)}")
        return 1
    print("✓ 自检全过")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--sessions", metavar="DATE", nargs="?", const="")
    ap.add_argument("--sleep", metavar="DATE", nargs="?", const="")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if args.sessions is not None:
        print(json.dumps(get_phone_sessions(args.sessions or None, db_path=args.db),
                         ensure_ascii=False, indent=2))
        return 0
    if args.sleep is not None:
        print(json.dumps(get_sleep_gap(args.sleep or None, db_path=args.db),
                         ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
