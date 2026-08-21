#!/usr/bin/env python3
"""
棠予酿 · memory_reflex 骨架：建两张表。

只建表，不塞任何预设词——词表由棠棠和予予手动填。

可重复执行：全部 CREATE ... IF NOT EXISTS，跑几次都一样。
跑法：
    python3 001_reflex_tables.py                     # 默认 /root/data/tang_yu_niang.db
    python3 001_reflex_tables.py --db /path/to.db
    python3 001_reflex_tables.py --dry-run           # 只看要执行什么，不落盘
"""

import argparse
import sqlite3
import sys

DEFAULT_DB = "/root/data/tang_yu_niang.db"

# 时间统一用 ISO 8601，跟 memories / diaries 那几张表保持一致
# （SQLite 的 datetime('now') 是 "YYYY-MM-DD HH:MM:SS"，中间没有 T，混着用
#  以后排序和比较会出怪事）
NOW = "strftime('%Y-%m-%dT%H:%M:%S', 'now')"

DDL = [
    # ---------- 词表 ----------
    f"""
    CREATE TABLE IF NOT EXISTS reflex_keywords (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword     TEXT    NOT NULL,
        category    TEXT    NOT NULL
                    CHECK (category IN ('emotion', 'entity', 'temporal')),
        target_tag  TEXT,                       -- 要捞的 tag；NULL = 不限
        "limit"     INTEGER NOT NULL DEFAULT 3,
        enabled     INTEGER NOT NULL DEFAULT 1  CHECK (enabled IN (0, 1)),
        created_at  TEXT    NOT NULL DEFAULT ({NOW})
    )
    """,
    # 命中查询走的是 enabled + keyword，建个复合索引
    """
    CREATE INDEX IF NOT EXISTS idx_reflex_keywords_lookup
        ON reflex_keywords (enabled, keyword)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reflex_keywords_category
        ON reflex_keywords (category)
    """,

    # ---------- 触发日志 ----------
    f"""
    CREATE TABLE IF NOT EXISTS reflex_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        matched_keyword TEXT    NOT NULL,
        category        TEXT,
        returned_ids    TEXT    NOT NULL DEFAULT '[]',   -- JSON 数组
        hit_count       INTEGER NOT NULL DEFAULT 0,
        triggered_at    TEXT    NOT NULL DEFAULT ({NOW})
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reflex_log_time
        ON reflex_log (triggered_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reflex_log_keyword
        ON reflex_log (matched_keyword)
    """,
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        for stmt in DDL:
            print(stmt.strip(), ";\n", sep="")
        return 0

    conn = sqlite3.connect(args.db, timeout=10)
    try:
        # 跟今天开的 WAL 保持一致；并发写不至于直接 database is locked
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")

        for stmt in DDL:
            conn.execute(stmt)
        conn.commit()

        print(f"库: {args.db}\n")
        for table in ("reflex_keywords", "reflex_log"):
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}  ({n} 行)")
            for c in cols:
                nn = "NOT NULL" if c[3] else ""
                dflt = f"DEFAULT {c[4]}" if c[4] is not None else ""
                print(f"    {c[1]:<16}{c[2]:<9}{nn:<9}{dflt}")
            print()

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_reflex%' ORDER BY name"
        ).fetchall()
        print("索引:", ", ".join(r[0] for r in idx) or "（无）")
        print("\n建好了。词表是空的——等棠棠和予予手填。")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
