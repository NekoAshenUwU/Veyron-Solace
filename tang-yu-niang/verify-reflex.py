#!/usr/bin/env python3
"""
第 5 步验收：直接调 Python 函数验行为，不经过 MCP 往返。

四项：
  A1  词表为空 → 返回 "[]"，不抛
  A2  插一条测试词 → 命中、有结果、reflex_log 多一行
  A3  同一个词再调一次 → 返回的 id 与上次完全不重叠（24 小时去重生效）
  A4  memory_pulse 里两个新字段在，且数值对得上

跑完自动清理测试数据（测试词 + 它产生的 log 行），真库不留痕。
在 /root 下用 server 的解释器跑：
    cd /root && PYTHONPATH=/root /root/mcp-env/bin/python /path/to/verify-reflex.py

PYTHONPATH 不能省：python 跑脚本文件时进 sys.path 的是脚本所在目录，不是 cwd。
"""

import json
import sqlite3
import sys

DB = "/root/data/tang_yu_niang.db"
MARK = "__REFLEX_TEST__"

from tang_yu_niang.reflex import memory_reflex          # noqa: E402
from tang_yu_niang.tools import memory_pulse            # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        ok = False


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def cleanup():
    c = conn()
    c.execute("DELETE FROM reflex_keywords WHERE keyword = ?", (MARK,))
    c.execute("DELETE FROM reflex_log WHERE matched_keyword = ?", (MARK,))
    c.commit()
    c.close()


def main():
    cleanup()   # 上次没跑完留下的残渣

    # ---- A1 空词表 ----
    c = conn()
    n_words = c.execute("SELECT COUNT(*) FROM reflex_keywords WHERE enabled=1").fetchone()[0]
    c.close()

    r1 = memory_reflex("我今天好累")
    check("A1 空词表返回 []", r1.strip() == "[]", f"实际 {r1[:40]!r}；当前词表 {n_words} 条")
    if n_words:
        print("     ↑ 词表非空，这项只说明这句话没命中任何词，不算严格的空表验证")

    # ---- A2 插一条测试词 ----
    c = conn()
    c.execute(
        'INSERT INTO reflex_keywords (keyword, category, target_tag, "limit") VALUES (?, ?, NULL, 3)',
        (MARK, "emotion"),
    )
    c.commit()
    log_before = c.execute("SELECT COUNT(*) FROM reflex_log").fetchone()[0]
    c.close()

    r2 = json.loads(memory_reflex(f"随便说点什么 {MARK} 再说点什么"))
    ids2 = [x.get("id") for x in r2]

    c = conn()
    log_after = c.execute("SELECT COUNT(*) FROM reflex_log").fetchone()[0]
    row = c.execute(
        "SELECT * FROM reflex_log WHERE matched_keyword = ? ORDER BY id DESC LIMIT 1", (MARK,)
    ).fetchone()
    c.close()

    check("A2 命中并返回了记忆", len(r2) > 0, f"返回 {len(r2)} 条")
    check("A2 reflex_log 多了一行", log_after == log_before + 1, f"{log_before} → {log_after}")
    if row:
        logged = json.loads(row["returned_ids"])
        check("A2 log 里的 id 和返回的一致", logged == ids2, f"hit_count={row['hit_count']}")
        check("A2 hit_count = 返回条数", row["hit_count"] == len(r2))

    # ---- A3 24 小时去重 ----
    r3 = json.loads(memory_reflex(f"再来一次 {MARK}"))
    ids3 = [x.get("id") for x in r3]
    overlap = set(ids2) & set(ids3)
    check("A3 第二次不再返回同一批 id", not overlap,
          f"第一次 {len(ids2)} 条，第二次 {len(ids3)} 条，重叠 {len(overlap)} 条")

    # ---- A4 memory_pulse 新字段 ----
    p = json.loads(memory_pulse("lite"))
    check("A4 reflex_enabled 在", "reflex_enabled" in p, f"值 = {p.get('reflex_enabled')}")
    check("A4 reflex_keyword_count 在", "reflex_keyword_count" in p,
          f"值 = {p.get('reflex_keyword_count')}")
    check("A4 count 把测试词算进去了", p.get("reflex_keyword_count", 0) >= 1)

    cleanup()

    c = conn()
    left = c.execute("SELECT COUNT(*) FROM reflex_keywords WHERE keyword = ?", (MARK,)).fetchone()[0]
    left_log = c.execute("SELECT COUNT(*) FROM reflex_log WHERE matched_keyword = ?", (MARK,)).fetchone()[0]
    c.close()
    check("清理干净", left == 0 and left_log == 0, f"残留 {left} 词 / {left_log} 日志")

    print()
    print("全部通过" if ok else "有项目没通过，见上面的 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
