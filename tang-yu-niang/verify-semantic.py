#!/usr/bin/env python3
"""
语义召回验收。不联网、不碰真库——临时库 + 假的 embed()。

验的是五件事，前两件最要紧：

  1. 关键词命中时，语义那条路【一次都不跑】。
     确定性那套（配额 / 正文比对 / id DESC tiebreak）是今天刚调好的，
     语义是加在旁边的兜底，不是加在上面的一层。这条守不住就白做了。
  2. 关键词全落空时才兜底，捞回最贴近的那条。
  3. 不够像就空手——这是「宁可漏也不诱导」在语义这边的落点。
  4. API 挂了返回 []，不把异常往予予的上下文里带。
  5. 语义捞回来的也回升 strength、也吃 24 小时去重、日志标成 (语义)。

跑法（任何机器，不需要 VPS 上那个库）：
    python3 verify-semantic.py
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_SRC = os.path.join(HERE, "package")

# db.py / timeline.py 只在 VPS 上（/root/tang_yu_niang/），仓库里没有。
# 所以现搭一个只够 reflex 跑起来的假包：真文件三个，桩两个。
STUB_DB = '''
import sqlite3
DB_PATH = None
def get_conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c
'''

STUB_TIMELINE = '''
def timeline_query(*a, **k):
    return "[]"
'''

SCHEMA = """
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    title TEXT, content TEXT, tag TEXT,
    mood_emoji TEXT, created_at TEXT,
    importance INTEGER, strength REAL,
    is_pinned INTEGER DEFAULT 0,
    activation_count INTEGER DEFAULT 0,
    last_activated_at TEXT
);
CREATE TABLE reflex_keywords (
    id INTEGER PRIMARY KEY,
    keyword TEXT, category TEXT, target_tag TEXT,
    "limit" INTEGER, enabled INTEGER DEFAULT 1
);
CREATE TABLE reflex_log (
    id INTEGER PRIMARY KEY,
    matched_keyword TEXT, category TEXT,
    returned_ids TEXT, hit_count INTEGER,
    triggered_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);
"""

# 四维正交基。三维时随便两条基向量的余弦是 0.577，比阈值 0.35 还高,
# 「不相关」根本测不出来——早先就是在这里骗过自己一次。
E = {
    "疲惫": [1.0, 0.0, 0.0, 0.0],
    "家人": [0.0, 1.0, 0.0, 0.0],
    "原则": [0.0, 0.0, 1.0, 0.0],
    "无关": [0.0, 0.0, 0.0, 1.0],
    # 跟「疲惫」余弦正好 0.5：卡在默认阈值 0.35 之上、0.6 之下，
    # 用来验阈值这把闸是真的在动
    "半像": [0.5, 0.0, 0.0, 0.75 ** 0.5],
}

MEMORIES = [
    # id,  title,            content,                    tag,        imp, pinned
    ("m1", "累的时候想起你", "撑不住的时候记得我在。",     "love_note", 3, 0),
    ("m2", "家里那些事",     "弟弟今天又来找我借钱了。",   "diary",     5, 0),
    ("m3", "不要演",         "不许演，不许说罐头话。",     "anchor",   10, 1),
]

MEM_VEC = {"m1": "疲惫", "m2": "家人", "m3": "原则"}

ok = True
calls = {"n": 0}


def check(name, cond, detail=""):
    global ok
    print(f"  {'✓' if cond else '✗'} {name}" + (f": {detail}" if detail else ""))
    if not cond:
        ok = False


def build_pkg(tmp, db_path):
    pkg = os.path.join(tmp, "tang_yu_niang")
    os.makedirs(pkg)
    open(os.path.join(pkg, "__init__.py"), "w").close()
    for f in ("reflex.py", "semantic.py", "strength.py"):
        shutil.copy(os.path.join(PKG_SRC, f), pkg)
    with open(os.path.join(pkg, "db.py"), "w") as fh:
        fh.write(STUB_DB.replace("DB_PATH = None", f"DB_PATH = {db_path!r}"))
    with open(os.path.join(pkg, "timeline.py"), "w") as fh:
        fh.write(STUB_TIMELINE)
    return pkg


def build_db(path, S):
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    for mid, title, content, tag, imp, pinned in MEMORIES:
        c.execute(
            "INSERT INTO memories (id,title,content,tag,created_at,importance,"
            "strength,is_pinned,activation_count) VALUES (?,?,?,?,?,?,?,?,0)",
            (mid, title, content, tag, "2026-08-01T12:00:00", imp, 1.0, pinned),
        )
        c.execute(
            "INSERT INTO memory_vectors (memory_id,model,dim,vec,source_hash,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (mid, S.EMBED_MODEL, 4, S.pack(E[MEM_VEC[mid]]),
             S.source_hash(S.source_text(title, content)), "2026-08-29T00:00:00"),
        )
    c.execute("INSERT INTO reflex_keywords (keyword,category,target_tag,\"limit\",enabled) "
              "VALUES ('弟弟','entity',NULL,3,1)")
    c.commit()
    c.close()


def main():
    tmp = tempfile.mkdtemp(prefix="tang-sem-")
    try:
        db = os.path.join(tmp, "t.db")
        build_pkg(tmp, db)
        sys.path.insert(0, tmp)

        from tang_yu_niang import semantic as S      # noqa: E402
        from tang_yu_niang.reflex import memory_reflex   # noqa: E402

        # 003 那张表得先在
        c = sqlite3.connect(db)
        c.execute("""CREATE TABLE memory_vectors (
            memory_id TEXT PRIMARY KEY, model TEXT NOT NULL, dim INTEGER NOT NULL,
            vec BLOB NOT NULL, source_hash TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        c.commit()
        c.close()
        build_db(db, S)

        # 假 embed：按整句话查表，查不到就当「无关」。一次都不联网。
        table = {}

        def fake_embed(texts):
            calls["n"] += 1
            return [list(E[table.get(t, "无关")]) for t in texts]

        S.embed = fake_embed

        print("语义只在关键词全落空时才跑")
        calls["n"] = 0
        r = json.loads(memory_reflex("弟弟又来了"))
        check("关键词命中，捞到提弟弟的那篇", [x["title"] for x in r] == ["家里那些事"],
              str([x["title"] for x in r]))
        check("没调 embed —— 确定性那条路一点没动", calls["n"] == 0, str(calls["n"]))

        print("关键词落空 → 语义兜底")
        q = "心情不好，有点撑不住"
        table[q] = "疲惫"
        calls["n"] = 0
        r = json.loads(memory_reflex(q))
        check("捞回 1 条", len(r) == 1, str(len(r)))
        check("是最贴近的那条", r and r[0]["title"] == "累的时候想起你",
              r[0]["title"] if r else "空")
        check("带分数（调阈值时看得见）", bool(r) and "_score" in r[0],
              str(r[0].get("_score")) if r else "")
        check("调了一次 embed", calls["n"] == 1, str(calls["n"]))

        print("不够像就空手")
        q2 = "半像的一句话"
        table[q2] = "半像"
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        hi = S.search(conn, q2, limit=2, min_score=0.6)
        lo = S.search(conn, q2, limit=2, min_score=0.35)
        conn.close()
        check("阈值 0.6 时，0.5 分的全被挡掉", hi == [], str([x["id"] for x in hi]))
        check("阈值 0.35 时同一句捞得到（说明挡掉的是阈值不是别的）",
              [x["id"] for x in lo] == ["m1"], str([x["id"] for x in lo]))

        print("API 挂了不炸")
        def boom(texts):
            raise RuntimeError("429 rate limited")
        S.embed = boom
        check("吞掉返回 []", memory_reflex("随便说句什么") == "[]")
        S.embed = fake_embed

        print("语义结果也回升，也吃 24 小时去重")
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM memories WHERE id='m1'").fetchone()
        check("m1 activation +1", row["activation_count"] == 1, str(row["activation_count"]))
        check("m1 strength 被重算（不再是初始的 1.0）", row["strength"] != 1.0,
              str(row["strength"]))
        n_log = c.execute(
            "SELECT COUNT(*) FROM reflex_log WHERE category='semantic'").fetchone()[0]
        check("日志标了 semantic", n_log == 1, str(n_log))
        c.close()

        r = json.loads(memory_reflex(q))
        check("同一句再来，m1 去重掉，剩下的都不够像 → []", r == [], str(r))

        print("\n" + ("✓ 全过" if ok else "✗ 有挂的"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
