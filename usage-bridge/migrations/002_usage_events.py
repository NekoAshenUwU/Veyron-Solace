#!/usr/bin/env python3
"""
Neko Usage Bridge：从「快照式累计」升级为「事件式会话记录」的建表迁移。

两张新表，不塞进 dream_events 的 meta 里——meta 是 JSON blob，查不了、
也建不了索引，而这两张表最要紧的就是按时间范围查。

可重复执行：全部 CREATE ... IF NOT EXISTS。
跑法：
    python3 002_usage_events.py
    python3 002_usage_events.py --db /path/to.db
    python3 002_usage_events.py --dry-run
"""

import argparse
import sqlite3
import sys

DEFAULT_DB = "/root/data/dream_events.db"

DDL = [
    # ---------- 应用会话 ----------
    # UNIQUE(package, start_ts) 是幂等的关键：open=true 的会话下次会带真实
    # end_ts 回来，靠 UPSERT 覆盖同一行，而不是插出两条。
    """
    CREATE TABLE IF NOT EXISTS usage_sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        package     TEXT    NOT NULL,
        label       TEXT,
        start_ts    TEXT    NOT NULL,          -- ISO8601 带 +08:00
        end_ts      TEXT    NOT NULL,
        duration_ms INTEGER NOT NULL,
        open        INTEGER NOT NULL DEFAULT 0 CHECK (open IN (0, 1)),
        created_at  TEXT    NOT NULL,
        UNIQUE (package, start_ts)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_start ON usage_sessions (start_ts)",
    # 按 app 查某天的用法（get_phone_sessions 的 package 参数）
    "CREATE INDEX IF NOT EXISTS idx_sessions_pkg_start ON usage_sessions (package, start_ts)",
    # 收尾扫描：还开着的会话
    "CREATE INDEX IF NOT EXISTS idx_sessions_open ON usage_sessions (open) WHERE open = 1",

    # ---------- 屏幕事件 ----------
    """
    CREATE TABLE IF NOT EXISTS screen_events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL
                   CHECK (event_type IN ('interactive', 'non_interactive',
                                         'keyguard_shown', 'keyguard_hidden')),
        ts         TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (event_type, ts)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_screen_ts ON screen_events (ts)",
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
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        for stmt in DDL:
            conn.execute(stmt)
        conn.commit()

        print(f"库: {args.db}\n")
        for table in ("usage_sessions", "screen_events"):
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}  ({n} 行)")
            for c in cols:
                nn = "NOT NULL" if c[3] else ""
                dflt = f"DEFAULT {c[4]}" if c[4] is not None else ""
                print(f"    {c[1]:<12}{c[2]:<9}{nn:<9}{dflt}")
            print()

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND (name LIKE 'idx_sessions%' OR name LIKE 'idx_screen%') ORDER BY name"
        ).fetchall()
        print("索引:", ", ".join(r[0] for r in idx))

        # 现有快照表还在不在——新旧并存，别把它碰掉了
        old = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='dream_events'"
        ).fetchone()[0]
        print(f"\ndream_events 表: {'在' if old else '不在'}（新旧并存，没动它）")
        print("建好了。两张表都是空的，等 Bridge 上报。")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
