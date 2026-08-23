#!/usr/bin/env python3
"""
把 strength 重算成派生值。

    strength =
        pinned 的 anchor  → 手工基准值，原样不动，不衰减
        其他              → clamp(base × 衰减 + 回升, 下限, 1.0)

    base   = importance 映射（见 IMPORTANCE_TO_BASE / TAG_BASE）
    衰减   = 0.5 ** (距上次浮现的天数 / HALF_LIFE_DAYS)
             上次浮现取 last_activated_at，没有就用 created_at
    回升   = BOOST_PER_ACTIVATION × ln(1 + activation_count)
    下限   = base × 系数，系数按 activation_count 分档（见 FLOOR_TIERS）

下限为什么要分档：统一下限会让「常想起的」和「从没想起过的」沉到同一深度，
跟记忆的本意相反。被反复浮现过的本来就该更难沉。

跑法：
    python3 recompute-strength.py                # 只看会变成什么，不落盘
    python3 recompute-strength.py --apply
    python3 recompute-strength.py --show love_note   # 只看某个 tag 的明细
"""

import argparse
import math
import sqlite3
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", metavar="TAG", help="打印这个 tag 的逐条明细")
    ap.add_argument("--half-life", type=float, help="临时换个半衰期看看效果")
    a = ap.parse_args()

    if a.half_life:
        global HALF_LIFE_DAYS
        HALF_LIFE_DAYS = a.half_life

    now = datetime.now(timezone.utc).astimezone()
    c = sqlite3.connect(a.db, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT id, title, tag, importance, strength, activation_count, "
            "is_pinned, created_at, last_activated_at FROM memories"
        ).fetchall()

        pinned, changes = [], []
        for r in rows:
            # pinned 的 anchor 是手工基准，不参与任何计算
            if r["is_pinned"] and r["tag"] == "anchor":
                pinned.append(r)
                continue
            new = derived(r, now)
            if abs(new - (r["strength"] or 0)) > 1e-6:
                changes.append((r, new))

        print(f"库: {a.db}   共 {len(rows)} 条")
        print(f"  pinned anchor {len(pinned)} 条：保持手工基准值，不动")
        print(f"  其余 {len(rows) - len(pinned)} 条里，{len(changes)} 条会变\n")

        # 按 tag 汇总，看得出整体被推到哪个区间
        agg = {}
        for r in rows:
            if r["is_pinned"] and r["tag"] == "anchor":
                agg.setdefault(r["tag"], []).append((r["strength"], r["strength"]))
            else:
                agg.setdefault(r["tag"], []).append((r["strength"], derived(r, now)))
        print(f"  半衰期 {HALF_LIFE_DAYS:.0f} 天\n")
        print("  tag               条数    现在          重算后        不同取值")
        for tag, vals in sorted(agg.items()):
            o = [v[0] or 0 for v in vals]
            n = [v[1] for v in vals]
            cur = f"{min(o):.2f}-{max(o):.2f}"
            nxt = f"{min(n):.2f}-{max(n):.2f}"
            print(f"  {tag:<16}{len(vals):>4}   {cur:<12}  {nxt:<12}  {len(set(n))}")

        if a.show:
            print(f"\n  tag={a.show} 明细：")
            for r in rows:
                if r["tag"] != a.show:
                    continue
                keep = r["is_pinned"] and r["tag"] == "anchor"
                new = r["strength"] if keep else derived(r, now)
                flag = "  [pinned 不动]" if keep else ""
                print(f"    imp={r['importance']} act={r['activation_count']:<3} "
                      f"{r['strength']:.2f} → {new:.4f}  {r['title'][:28]}{flag}")

        if not a.apply:
            print("\n（没落盘）确认没问题就加 --apply")
            return 0

        c.executemany("UPDATE memories SET strength = ? WHERE id = ?",
                      [(new, r["id"]) for r, new in changes])
        c.commit()
        print(f"\n  ✓ 更新 {len(changes)} 条，pinned anchor {len(pinned)} 条没动")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
