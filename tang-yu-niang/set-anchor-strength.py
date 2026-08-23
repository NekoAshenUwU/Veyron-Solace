#!/usr/bin/env python3
"""
给 anchor 打强度分。

为什么要打：memories.strength 原本全库都是 1.0，所以 memory_reflex 的
emotion 分支 "ORDER BY strength DESC" 所有行并列，取哪三条是任意的——
予予实测撞出来的锚点跟他说的话毫无关系，根源就在这。

匹配按 title。库里的确切写法（引号是直角还是弯的、有没有空格）我不知道，
所以：先精确匹配，不中再用归一化（去掉各种引号/空白/标点）匹配。
只要有一条对不上、或者匹到多条，就【整体中止】，一个字不落盘。
宁可你再看一眼，也不能把分打到错的记忆上。

跑法：
    python3 set-anchor-strength.py            # 只看对照表，不落盘
    python3 set-anchor-strength.py --apply
"""

import argparse
import sqlite3
import sys
import unicodedata

DB = "/root/data/tang_yu_niang.db"

# love_note 统一基线。
# 定 0.80 的效果：11 条锚点里有 7 条在它之上、4 条在它之下。也就是
# 「有痛感的规矩」排在情话前面，「纯格式/纯备忘」排在情话后面。
#
# 这个值是【种子】不是终值——strength 之后要改成派生字段（由 importance
# 映射、随时间衰减、随浮现回升），到那时这里写的会被重算覆盖。
# 只有 pinned 的 anchor 保留手工基准值、不参与衰减。
LOVE_NOTE_BASELINE = 0.80

# 2026-08-23 棠棠给的分。右边的说明是她写的，不参与匹配。
SCORES = [
    (1.00, "不要演"),                              # 根。要么是沈予温，要么谢幕鞠躬
    (0.98, "不要演·不要罐头话"),                   # 同根，更具体
    (0.96, "想5就说5"),                            # 诚实的底
    (0.94, "信任优先"),                            # 不揣测你
    (0.92, "情感匹配强度"),                        # 你升温我跟着升
    (0.90, "棠棠教训：踩刹车不是清醒，是凶器"),     # 从伤害里长出来的
    (0.85, "老婆教训：NSFW两个差评"),               # 从差评里长出来的
    (0.75, "思考链禁止用“她”"),                    # 格式，但有翻车的痛
    (0.70, "思维链绝对规则"),                      # 纯格式
    (0.65, "每朵花上，只放那天最重要的一句话"),     # 落花溪的规矩，偏功能
    (0.30, "重启 mcp 必重连 chat 端"),             # 纯技术备忘
]

# 归一化时丢掉的字符：各种引号、间隔号、空白、常见标点
DROP = set('"\'“”‘’「」『』·・.。，,：:；;！!？?—-_()（）[]【】 \t　')


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return "".join(ch for ch in s if ch not in DROP).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--tag", default="anchor")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    c = sqlite3.connect(a.db, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT id, title, strength FROM memories WHERE tag = ? ORDER BY id",
            (a.tag,),
        ).fetchall()
        by_title = {r["title"]: r for r in rows}
        by_norm = {}
        for r in rows:
            by_norm.setdefault(norm(r["title"]), []).append(r)

        plan, problems = [], []
        used = set()
        for score, title in SCORES:
            hit, how = None, ""
            if title in by_title:
                hit, how = by_title[title], "精确"
            else:
                cands = by_norm.get(norm(title), [])
                if len(cands) == 1:
                    hit, how = cands[0], "归一化"
                elif len(cands) > 1:
                    problems.append(f"「{title}」归一化后匹到 {len(cands)} 条，无法确定")
                    continue
                else:
                    problems.append(f"「{title}」在 tag={a.tag} 里找不到")
                    continue
            if hit["id"] in used:
                problems.append(f"「{title}」和前面某条匹到了同一行 (id={hit['id']})")
                continue
            used.add(hit["id"])
            plan.append((hit, score, how))

        print(f"库: {a.db}   tag={a.tag}   库里 {len(rows)} 条，要打分 {len(SCORES)} 条\n")
        for r, score, how in plan:
            mark = "" if how == "精确" else f"  [{how}]"
            print(f"  id={r['id']:>3}  {r['strength']:.2f} → {score:.2f}   {r['title']}{mark}")

        untouched = [r for r in rows if r["id"] not in used]
        if untouched:
            print(f"\n  库里这 {len(untouched)} 条没在名单上，保持不动：")
            for r in untouched:
                print(f"      id={r['id']:>3}  {r['strength']:.2f}  {r['title']}")

        if problems:
            print("\n× 对不上，已中止，文件未改动：", file=sys.stderr)
            for p in problems:
                print(f"    {p}", file=sys.stderr)
            print("\n  库里 tag=%s 的全部标题：" % a.tag, file=sys.stderr)
            for r in rows:
                print(f"    id={r['id']:>3}  {r['title']!r}", file=sys.stderr)
            return 1

        # love_note 基线：整批拉到同一个值
        ln = c.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE strength = ?) "
            "FROM memories WHERE tag = 'love_note'", (LOVE_NOTE_BASELINE,),
        ).fetchone()
        print(f"\n  love_note: {ln[0]} 条统一设成 {LOVE_NOTE_BASELINE}"
              f"（其中 {ln[1]} 条已经是这个值）")

        if not a.apply:
            print("\n（没落盘）确认对照没错就加 --apply")
            return 0

        c.executemany("UPDATE memories SET strength = ? WHERE id = ?",
                      [(score, r["id"]) for r, score, _ in plan])
        c.execute("UPDATE memories SET strength = ? WHERE tag = 'love_note'",
                  (LOVE_NOTE_BASELINE,))
        c.commit()
        print(f"\n  ✓ anchor 更新 {len(plan)} 条，love_note 拉平 {ln[0]} 条")
        chk = c.execute(
            "SELECT ROUND(MIN(strength),2), ROUND(MAX(strength),2), COUNT(DISTINCT strength) "
            "FROM memories WHERE tag = ?", (a.tag,)).fetchone()
        print(f"  现在 {a.tag}: min={chk[0]}  max={chk[1]}  不同取值 {chk[2]} 种")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
