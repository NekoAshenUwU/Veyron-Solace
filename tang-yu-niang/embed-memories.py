#!/usr/bin/env python3
"""
把记忆算成向量存进 memory_vectors。第一次跑全量，之后只算变过的。

靠 source_hash（title+content 的 sha256）判断变没变——改过标题或正文的
会重算，没动过的一条 API 都不调。换模型（TANG_EMBED_MODEL 变了）则全部重算。

跑法（注意 PYTHONPATH，semantic 在包里）：
    PYTHONPATH=/root python3 embed-memories.py            # 只看要算多少，不调 API
    PYTHONPATH=/root python3 embed-memories.py --apply
    PYTHONPATH=/root python3 embed-memories.py --apply --limit 20   # 先试水几条
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone

from tang_yu_niang import semantic as S

DB = "/root/data/tang_yu_niang.db"
BATCH = 64          # 一次请求塞多少条

# 按 token 计费，只算【输入】，没有输出这一说。
# text-embedding-3-small 官网价 $0.02 / 百万 token（2026-08 查的，价格会变，
# 以 platform.openai.com/docs/pricing 为准）。--price 可以现场换个数。
DEFAULT_PRICE_PER_M = 0.02


def est_tokens(text: str) -> int:
    """
    粗估 token 数，往【多】了算，别让人以为比实际便宜。

    中文一个字大约就是一个 token（有时两三个字合成一个，所以这是上界）；
    ASCII 大约四个字符一个 token。真实值由 OpenAI 那边的分词器说了算，
    这里只是给个数量级，用来回答「大概要花多少钱」。
    """
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    rest = len(text) - cjk
    return cjk + (rest + 3) // 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, help="最多处理几条（试水用）")
    ap.add_argument("--price", type=float, default=DEFAULT_PRICE_PER_M,
                    help=f"每百万 token 多少美元（默认 {DEFAULT_PRICE_PER_M}）")
    a = ap.parse_args()

    c = sqlite3.connect(a.db, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        have = {
            r["memory_id"]: r["source_hash"]
            for r in c.execute(
                "SELECT memory_id, source_hash FROM memory_vectors WHERE model = ?",
                (S.EMBED_MODEL,),
            )
        }
        rows = c.execute("SELECT id, title, content, tag FROM memories").fetchall()

        todo = []
        for r in rows:
            text = S.source_text(r["title"], r["content"])
            if not text:
                continue
            h = S.source_hash(text)
            if have.get(r["id"]) != h:
                todo.append((r["id"], text, h))

        stale = c.execute(
            "SELECT COUNT(*) FROM memory_vectors WHERE model <> ?", (S.EMBED_MODEL,)
        ).fetchone()[0]

        print(f"库: {a.db}")
        print(f"  模型: {S.EMBED_MODEL}")
        print(f"  memories {len(rows)} 条，已有本模型向量 {len(have)} 条")
        print(f"  要算 {len(todo)} 条" + (f"（另有 {stale} 条是旧模型的，会留着不动）" if stale else ""))

        toks = sum(est_tokens(text) for _, text, _ in todo)
        cost = toks / 1_000_000 * a.price
        print(f"  粗估 {toks:,} token（往多了算）→ 约 ${cost:.4f} "
              f"（按 ${a.price}/百万 token）")
        if cost < 0.01:
            print("  ——不到一美分。")

        if a.limit:
            todo = todo[: a.limit]
            print(f"  --limit 只处理前 {len(todo)} 条")

        if not todo:
            print("\n没有要算的。")
            return 0
        if not a.apply:
            print(f"\n（没调 API）确认就加 --apply。会发 {(len(todo) + BATCH - 1) // BATCH} 个请求。")
            return 0

        now = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
        done = 0
        for i in range(0, len(todo), BATCH):
            chunk = todo[i : i + BATCH]
            try:
                vecs = S.embed([t for _, t, _ in chunk])
            except Exception as err:
                # 一批挂掉不该把前面成功的也丢了——前面的已经 commit 了
                print(f"\n× 第 {i // BATCH + 1} 批失败: {err}", file=sys.stderr)
                print(f"  已经存好 {done} 条，再跑一次会从没算的接着来。", file=sys.stderr)
                return 1
            c.executemany(
                "INSERT INTO memory_vectors (memory_id, model, dim, vec, source_hash, updated_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(memory_id) DO UPDATE SET "
                "model=excluded.model, dim=excluded.dim, vec=excluded.vec, "
                "source_hash=excluded.source_hash, updated_at=excluded.updated_at",
                [
                    (mid, S.EMBED_MODEL, len(v), S.pack(v), h, now)
                    for (mid, _, h), v in zip(chunk, vecs)
                ],
            )
            c.commit()          # 每批就落盘，中途断了不用从头来
            done += len(chunk)
            print(f"  … {done}/{len(todo)}")

        total = c.execute(
            "SELECT COUNT(*) FROM memory_vectors WHERE model = ?", (S.EMBED_MODEL,)
        ).fetchone()[0]
        size = c.execute(
            "SELECT COALESCE(SUM(LENGTH(vec)),0) FROM memory_vectors"
        ).fetchone()[0]
        print(f"\n  ✓ 存好 {done} 条，本模型共 {total} 条，向量占 {size/1024:.0f} KB")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
