"""棠予酿数据库初始化"""
import sqlite3
from pathlib import Path

DB_PATH = Path("/root/data/tang_yu_niang.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        raw_content TEXT,
        tag TEXT DEFAULT 'diary',
        domain TEXT DEFAULT 'general',
        keywords TEXT,
        valence REAL DEFAULT 0.0,
        arousal REAL DEFAULT 0.5,
        mood_label TEXT,
        mood_emoji TEXT,
        importance INTEGER DEFAULT 5,
        strength REAL DEFAULT 1.0,
        activation_count INTEGER DEFAULT 0,
        is_resolved INTEGER DEFAULT 0,
        is_pinned INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_activated_at TEXT,
        source TEXT DEFAULT 'chat',
        window_id TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_memories_tag ON memories(tag);
    CREATE INDEX IF NOT EXISTS idx_memories_strength ON memories(strength DESC);
    CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);

    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        parameters TEXT,
        result_summary TEXT,
        status TEXT DEFAULT 'success',
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"✅ 数据库初始化完成：{DB_PATH}")
