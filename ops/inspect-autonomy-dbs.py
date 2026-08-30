#!/usr/bin/env python3
"""
看清 neko_autonomy.db 和 dream_events.db 各存什么。

这是主动唤醒的开工前置（见 docs/proactive-wake-design.md）：唤醒的状态
（上次发言时间、今天发了几条、说过哪些理由、静音开关）要落在其中一个里，
选错了就会重演「改了一边没改另一边」。

【只读】——以 mode=ro 打开，一个字都不写。
【不打印任何一行内容】——只打印表名、字段名、行数、时间范围。
那几个库里有她的日记和对话，看结构不需要看内容。

    python3 inspect-autonomy-dbs.py
"""

import os
import sqlite3
import sys

CANDIDATES = [
    "/root/data/dream_events.db",
    "/root/codeandpurrs-mcp/data/dream_events.db",
    "/root/codeandpurrs-mcp/data/neko_autonomy.db",
    "/root/data/neko_autonomy.db",
    "/root/data/tang_yu_niang.db",
]

# 这些字段名一看就是时间，用来报「数据从什么时候到什么时候」
TIME_HINTS = ("ts", "at", "time", "date", "created", "updated", "start", "end")


def looks_like_time(col: str) -> bool:
    c = col.lower()
    return any(h in c for h in TIME_HINTS)


def inspect(path: str) -> None:
    size = os.path.getsize(path)
    print(f"\n{'=' * 62}")
    print(f"{path}   {size / 1024:.0f} KB")
    if size == 0:
        print("  空文件——建了没用过，或者用的根本不是它")
        return
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as e:
        print(f"  打不开: {e}")
        return
    try:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if not tables:
            print("  一张表都没有")
            return
        for tbl in tables:
            try:
                n = c.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
            except sqlite3.Error:
                n = "?"
            cols = [r[1] for r in c.execute(f'PRAGMA table_info("{tbl}")')]
            print(f"\n  {tbl}  ({n} 行)")
            print(f"    字段: {', '.join(cols)}")
            # 时间范围：帮着判断这张表是活的还是早就停了
            for col in cols:
                if not looks_like_time(col) or n in (0, "?"):
                    continue
                try:
                    lo, hi = c.execute(
                        f'SELECT MIN("{col}"), MAX("{col}") FROM "{tbl}"').fetchone()
                except sqlite3.Error:
                    continue
                if lo is None:
                    continue
                lo, hi = str(lo)[:19], str(hi)[:19]
                print(f"    {col}: {lo} → {hi}" + ("   ← 只有一个值" if lo == hi else ""))
                break
    finally:
        c.close()


def main() -> int:
    print("主动唤醒开工前置：这几个库现在各存什么")
    print("（只读打开，不打印任何一行内容）")
    seen = set()
    found = False
    for path in CANDIDATES:
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        if os.path.isfile(path):
            found = True
            inspect(path)
        else:
            print(f"\n{'=' * 62}\n{path}\n  不存在")
    if not found:
        print("\n一个都没找到。用这个再搜一遍：")
        print("  find /root -name '*.db' -size +0 2>/dev/null | head -20")
        return 1
    print(f"\n{'=' * 62}")
    print("要看的是：哪个库还在被写（时间范围到今天），哪个是残留。")
    print("唤醒状态就落在还活着的那个里，不新建第三个库。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
