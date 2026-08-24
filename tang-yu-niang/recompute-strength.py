#!/usr/bin/env python3
"""
把 strength 批量重算成派生值（衰减那一半）。

公式在 tang_yu_niang/strength.py，不在这里——reflex.py 浮现时的就地回升
用的是同一份，抄两份迟早漂开。

跑法（注意 PYTHONPATH，公式在包里）：
    PYTHONPATH=/root python3 recompute-strength.py                # 只看不改
    PYTHONPATH=/root python3 recompute-strength.py --apply
    PYTHONPATH=/root python3 recompute-strength.py --show love_note
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone

from tang_yu_niang import strength as S

DB = "/root/data/tang_yu_niang.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", metavar="TAG", help="打印这个 tag 的逐条明细")
    ap.add_argument("--half-life", type=float, help="临时换个半衰期看看效果")
    a = ap.parse_args()

    if a.half_life:
        S.HALF_LIFE_DAYS = a.half_life

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
            if S.is_manual(r):
                pinned.append(r)
                continue
            new = S.derived(r, now)
            if abs(new - (r["strength"] or 0)) > 1e-6:
                changes.append((r, new))

        print(f"库: {a.db}   共 {len(rows)} 条")
        print(f"  pinned anchor {len(pinned)} 条：保持手工基准值，不动")
        print(f"  其余 {len(rows) - len(pinned)} 条里，{len(changes)} 条会变\n")

        # 按 tag 汇总，看得出整体被推到哪个区间
        agg = {}
        for r in rows:
            if S.is_manual(r):
                agg.setdefault(r["tag"], []).append((r["strength"], r["strength"]))
            else:
                agg.setdefault(r["tag"], []).append((r["strength"], S.derived(r, now)))
        print(f"  半衰期 {S.HALF_LIFE_DAYS:.0f} 天\n")
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
                keep = S.is_manual(r)
                new = r["strength"] if keep else S.derived(r, now)
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
