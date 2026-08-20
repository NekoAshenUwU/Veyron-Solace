#!/usr/bin/env python3
"""
往 reflex_keywords 填词。校验不过就拒绝插入，并告诉你错在哪。

为什么要这个工具：memory_reflex 是静默失败的——target_tag 写错一个字，
查询查不到任何东西，但它不会报错，只会一直返回 []。你会以为词没生效，
其实是 tag 拼错了。

「静默」这个要求是针对返回给模型的内容（不能诱导它编），不是针对填词。
填词是人在操作，报错就该响。所以这里的校验全部大声失败。

用法：
    cd /root && PYTHONPATH=/root /root/mcp-env/bin/python add-keyword.py \
        --keyword 好累 --category emotion
    ... --keyword 生日 --category entity --target-tag treasure --limit 5
    ... --list        # 只看当前词表和可用的 tag，不插入
"""

import argparse
import sqlite3
import sys

DB = "/root/data/tang_yu_niang.db"
CATEGORIES = ("emotion", "entity", "temporal")


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def real_tags(c):
    """真实存在的 tag，从 memories 表现查——写死列表会过期。"""
    return [r[0] for r in c.execute(
        "SELECT DISTINCT tag FROM memories WHERE tag IS NOT NULL ORDER BY tag"
    ).fetchall()]


def show(c):
    tags = real_tags(c)
    print("可用的 target_tag（从 memories 表现查）：")
    for t in tags:
        n = c.execute("SELECT COUNT(*) FROM memories WHERE tag = ?", (t,)).fetchone()[0]
        print(f"    {t:<18} {n} 条")
    print()
    rows = c.execute(
        'SELECT id, keyword, category, target_tag, "limit", enabled '
        "FROM reflex_keywords ORDER BY id"
    ).fetchall()
    print(f"当前词表（{len(rows)} 条）：")
    if not rows:
        print("    （空）")
    for r in rows:
        flag = "" if r["enabled"] else "  [已停用]"
        print(f"    {r['id']:>3}  {r['keyword']:<12} {r['category']:<9} "
              f"tag={r['target_tag'] or '(默认)':<14} limit={r['limit']}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword")
    ap.add_argument("--category", choices=CATEGORIES)
    ap.add_argument("--target-tag", default=None)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    c = conn()
    try:
        if a.list or not a.keyword:
            show(c)
            if not a.list:
                print("\n要填词请给 --keyword 和 --category")
            return 0

        if not a.category:
            print("× --category 必填，只能是 emotion / entity / temporal", file=sys.stderr)
            return 1

        # 这一条就是予予担心的：tag 写错一个字，查询静默返回空
        if a.target_tag:
            tags = real_tags(c)
            if a.target_tag not in tags:
                print(f"× target_tag「{a.target_tag}」在 memories 表里不存在，拒绝插入。",
                      file=sys.stderr)
                print(f"  真实的 tag 只有这些：{' / '.join(tags)}", file=sys.stderr)
                print("  （填「锚点」「日记」这类中文说法查不到东西，而且不会报错）",
                      file=sys.stderr)
                return 1

        if a.category == "temporal" and a.target_tag:
            print("！temporal 走的是 timeline_query，不看 target_tag，这个值会被忽略。")

        if a.limit < 1:
            print("× --limit 至少是 1", file=sys.stderr)
            return 1

        dup = c.execute(
            "SELECT id FROM reflex_keywords WHERE keyword = ? AND category = ? "
            "AND IFNULL(target_tag,'') = IFNULL(?,'')",
            (a.keyword, a.category, a.target_tag),
        ).fetchone()
        if dup:
            print(f"！这条已经存在了（id={dup['id']}），没有重复插入。")
            return 0

        c.execute(
            'INSERT INTO reflex_keywords (keyword, category, target_tag, "limit") '
            "VALUES (?, ?, ?, ?)",
            (a.keyword, a.category, a.target_tag, a.limit),
        )
        c.commit()
        print(f"✓ 已加：{a.keyword}  ({a.category}, "
              f"tag={a.target_tag or '默认'}, limit={a.limit})")
        print()
        show(c)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
