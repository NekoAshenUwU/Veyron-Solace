"""
strength 的唯一定义。

    strength =
        pinned 的 anchor → 手工基准值，原样不动，不衰减
        其他             → clamp(base × 衰减 + 回升, 下限, 1.0)

放在包里而不是脚本里，是因为它有两个调用方：
  · recompute-strength.py  批量重算（衰减那一半）
  · reflex.py              浮现时就地回升（回升那一半）
公式抄两份迟早漂开，漂开之后同一条记忆在两条路径上算出不同的值，
而且不会报错。
"""

import math
import sqlite3
from datetime import datetime, timezone

DB = "/root/data/tang_yu_niang.db"

# 半衰期。定 180 天不是拍脑袋：这个库的记忆跨度两百多天，而且绝大多数
# last_activated_at 是空的（只能拿 created_at 当基准）。定 30 天的话，
# 三个月以上的记忆一律撞到下限、全部并列——就是当初 strength 全 1.0 的
# 那个毛病换个数字重演一遍。180 天能让 90 天/200 天/365 天前的记忆真的
# 拉开档次。用 --half-life 可以现场比。
HALF_LIFE_DAYS = 180.0
BOOST_PER_ACTIVATION = 0.05    # 乘 ln(1+n)：第 1 次 +0.035，第 10 次 +0.12
CEILING = 1.0

# activation_count 上界（含） → 下限系数
FLOOR_TIERS = ((0, 0.40), (5, 0.50), (float("inf"), 0.60))


def floor_ratio(n: int) -> float:
    for upper, ratio in FLOOR_TIERS:
        if n <= upper:
            return ratio
    return FLOOR_TIERS[-1][1]


def importance_to_base(imp) -> float:
    """默认映射：importance / 10。库里实际取值 3-10。"""
    if imp is None:
        imp = 5
    return max(0.0, min(1.0, imp / 10.0))


# 某个 tag 想脱离 importance 单独定 base，写这里。
#
# love_note 是个真实的两难：29 条里 27 条 importance=3，按默认映射就是 0.30，
# 而 2 条 8/9 会一直霸占 emotion 那 1 个 love_note 名额，27 条基本轮不到。
# 空着 = 照 importance 走。填 0.80 = 29 条一律 0.80，情话内部纯靠衰减和
# 浮现次数拉开差距（谁最近被想起过，谁排前面）。
TAG_BASE = {
    # "love_note": 0.80,
}


def is_manual(row) -> bool:
    """pinned 的 anchor 是手工基准值，不参与衰减也不参与回升。"""
    return bool(row["is_pinned"]) and row["tag"] == "anchor"


def base_of(row) -> float:
    if row["tag"] in TAG_BASE:
        return TAG_BASE[row["tag"]]
    return importance_to_base(row["importance"])


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None


def derived(row, now) -> float:
    base = base_of(row)
    ref = _parse(row["last_activated_at"]) or _parse(row["created_at"])
    if ref is None:
        days = 0.0
    else:
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=now.tzinfo)
        days = max(0.0, (now - ref).total_seconds() / 86400.0)

    n = row["activation_count"] or 0
    value = base * (0.5 ** (days / HALF_LIFE_DAYS)) + BOOST_PER_ACTIVATION * math.log(1 + n)
    return round(min(CEILING, max(base * floor_ratio(n), value)), 4)


