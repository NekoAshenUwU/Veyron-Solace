#!/usr/bin/env python3
"""
语义召回：存记忆向量的表。

跟 memories 分开一张表而不是加一列，是因为向量是【派生数据】——
换模型就得全部重算，记忆本身一个字都不该动。分开的话重算只是
DELETE + 重跑，不碰 memories。

可重复执行。
    python3 003_memory_vectors.py
    python3 003_memory_vectors.py --db /path/to.db --dry-run
"""

import argparse
import sqlite3
import sys

DEFAULT_DB = "/root/data/tang_yu_niang.db"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS memory_vectors (
        memory_id   TEXT PRIMARY KEY,
        model       TEXT    NOT NULL,          -- 换模型要全部重算，所以记下来
        dim         INTEGER NOT NULL,
        vec         BLOB    NOT NULL,          -- float32 数组，存的时候已归一化
        source_hash TEXT    NOT NULL,          -- title+content 的 sha256，没变就不重算
        updated_at  TEXT    NOT NULL
    )
    """,
    # 换模型时要挑出所有旧模型的行
    "CREATE INDEX IF NOT EXISTS idx_memvec_model ON memory_vectors (model)",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        for s in DDL:
            print(s.strip(), ";\n", sep="")
        return 0

    c = sqlite3.connect(a.db, timeout=10)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=5000")
        for s in DDL:
            c.execute(s)
        c.commit()
        n_mem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        n_vec = c.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        print(f"库: {a.db}")
        print(f"  memories {n_mem} 条，已有向量 {n_vec} 条")
        print(f"  还要算 {n_mem - n_vec} 条 → 跑 embed-memories.py")
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
