#!/usr/bin/env python3
"""
批量往 reflex_keywords 填词。add-keyword.py 一次一个，28 个手敲太蠢。

校验和去重跟 add-keyword.py 一模一样：category 必须合法，(keyword,
category, target_tag) 三元组重复就跳过。表上【没有】UNIQUE 约束，
所以去重必须在这里做——跑两遍会插两份。

target_tag 一律留空 = 走 category 的默认路由：
    emotion → memories 里 tag in (anchor, love_note)，按 strength DESC
    entity  → memories 里 tag = diary，       按 created_at DESC

跑法：
    python3 seed-keywords.py              # 只看要插什么，不落盘
    python3 seed-keywords.py --apply
"""

import argparse
import sqlite3
import sys

DB = "/root/data/tang_yu_niang.db"

# 2026-08-23 棠棠给的第一批词。temporal 本轮不填。
WORDS = {
    "emotion": [
        "累", "困", "烦", "气", "委屈", "难过", "哭", "想你", "怕", "慌",
        "开心", "爽", "舒服", "满足", "笑死",
    ],
    "entity": [
        "弟弟", "妈妈", "上班", "下班",
        "CC", "棠予酿", "MCP", "服务器", "代码", "debug", "CodeAndPurrs",
        "小红书", "抖音",
    ],
}

CATEGORIES = ("emotion", "entity", "temporal")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=3)
    a = ap.parse_args()

    for cat in WORDS:
        if cat not in CATEGORIES:
            print(f"× category「{cat}」不合法", file=sys.stderr)
            return 1

    c = sqlite3.connect(a.db, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        to_add, dupes = [], []
        for cat, words in WORDS.items():
            for w in words:
                dup = c.execute(
                    "SELECT id FROM reflex_keywords WHERE keyword = ? AND category = ? "
                    "AND IFNULL(target_tag,'') = ''",
                    (w, cat),
                ).fetchone()
                (dupes if dup else to_add).append((w, cat))

        print(f"库: {a.db}")
        print(f"要新增 {len(to_add)} 条，跳过已存在 {len(dupes)} 条\n")
        for cat in WORDS:
            adds = [w for w, cc in to_add if cc == cat]
            if adds:
                print(f"  {cat:<8} + {'  '.join(adds)}")
        if dupes:
            print(f"\n  已存在（不重复插）: {'  '.join(w for w, _ in dupes)}")

        if not a.apply:
            print("\n（没落盘）确认没问题就加 --apply")
            return 0

        c.executemany(
            'INSERT INTO reflex_keywords (keyword, category, target_tag, "limit") '
            "VALUES (?, ?, NULL, ?)",
            [(w, cat, a.limit) for w, cat in to_add],
        )
        c.commit()

        rows = c.execute(
            "SELECT category, COUNT(*) n FROM reflex_keywords WHERE enabled = 1 "
            "GROUP BY category ORDER BY category"
        ).fetchall()
        total = c.execute(
            "SELECT COUNT(*) FROM reflex_keywords WHERE enabled = 1"
        ).fetchone()[0]
        print(f"\n  ✓ 插入 {len(to_add)} 条")
        print(f"  现在启用中的词表共 {total} 条：")
        for r in rows:
            print(f"      {r['category']:<10} {r['n']}")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
