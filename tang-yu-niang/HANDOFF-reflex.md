# memory_reflex 交接 · 给予予

2026-08-20 完成。五步全做完，验收十项全过，21 个工具在线。

---

## ⚠️ 第一件事：chat 端要重连

第 5 步做了 `systemctl restart mcp`。重启会清掉 OAuthProxy 内存里的客户端注册，
**claude.ai 那条连接必须重连一次**（设置 → 连接器 → 棠予酿 → 断开 → 连接）。

CodeAndPurrs 走静态 token，不受影响。

这不是新故障，是 2026-08-18 查了一整天的那个不对称。以后**每次重启 mcp 都要重连一次**。

---

## 现在是什么样

**表**（`/root/data/tang_yu_niang.db`，都开了 WAL）
- `reflex_keywords` — **空的**，等你和棠棠手填
- `reflex_log` — 空的，触发时自动写

**代码**
- `/root/tang_yu_niang/reflex.py`（151 行）
- `/root/server.py` 里 6 行 `@app.tool()` 壳
- `/root/tang_yu_niang/tools.py` 的 `memory_pulse` 加了 10 行
- 备份：`server.py.bak-20260820-203752`、`tools.py.bak-20260820-213224`

**`memory_pulse` 多了两个字段**

```
reflex_enabled       reflex_keywords 表在不在（功能装没装）
reflex_keyword_count enabled=1 的词有几个（会不会真的触发）
```

刻意不冗余：`enabled=true, count=0` 读作**「装了，但词表还空着」**。看到这个就催棠棠填词，不是坏了。

**流程**

子串匹配 enabled=1 的词 → 按 category 路由 → 剔掉 24 小时内返回过的 id → 写 `reflex_log` → 返回 JSON 数组字符串。

| category | 查哪儿 | 排序 |
|---|---|---|
| emotion | memories，tag IN (anchor, love_note) | strength DESC |
| entity | memories，tag = diary | created_at DESC |
| temporal | 复用现有 timeline_query | 它自己的顺序 |

`target_tag` 填了就用它，空了落到上面的默认 tag 集。

---

## 验收跑了什么（十项全过）

```
A1  空词表返回 []                    当时词表 0 条，真·空表
A2  命中并返回了记忆                  返回 3 条
A2  reflex_log 多了一行               0 → 1
A2  log 里的 id 和返回的一致           hit_count=3
A2  hit_count = 返回条数
A3  第二次不再返回同一批 id            各 3 条，重叠 0 条  ← 去重真的生效
A4  reflex_enabled 在                 True
A4  reflex_keyword_count 在           1
A4  count 把测试词算进去了
    清理干净                          残留 0 词 / 0 日志
```

A3 刻意不断言「第二次返回空」：去重是按 id 剔的，加上 `limit×4` 多捞，第二次会返回**另外三条**。断言成空反而会把正确实现判成失败。

---

## 你会撞上的问题

### 1. 词表空着，所以它永远返回 `[]`

不是坏了。填一条试试：

```sql
INSERT INTO reflex_keywords (keyword, category, target_tag, "limit")
VALUES ('好累', 'emotion', NULL, 3);
```

⚠️ `limit` 是 SQL 保留字，**每次都要写 `"limit"`**，忘了就是语法错。

### 2. `target_tag` 必须填真实 tag 值

库里现有的：`anchor` / `blessing` / `core_principles` / `diary` / `love_letter` / `love_note` / `memory` / `treasure` / `里程碑`。

填「锚点」「日记」这种中文说法查不到任何东西——**而且因为静默失败，你不会收到报错，只会拿到 `[]`**。

### 3. 同一个词第二次触发会返回不同的记忆，第 N 次可能空

24 小时去重按 id 剔。调试时想重来：

```sql
DELETE FROM reflex_log;
```

### 4. 排查很难，这是静默失败的代价

「没命中」和「出错了」返回的是同一个 `[]`，**无法从返回值区分**。这是刻意的——宁可漏，也不能吐一句提示语诱导你去编。

要查真相只有两处：

```sql
SELECT * FROM reflex_log ORDER BY triggered_at DESC LIMIT 10;
```

```bash
journalctl -u mcp -n 50 --no-pager | grep -i "reflex\|error\|traceback"
```

### 5. temporal 现在只捞得到「今天」

规格说「走现有 `timeline_query` 逻辑」，照做了——但它不传日期时的默认行为是 `date = today()`。**所以「昨天」「上周」这类词捞不到对应范围。**

要支持得从关键词解析时间意图再传 `start_date` / `end_date`，骨架里没这层。**不算 bug，算已知局限**，要不要加你和棠棠定。

### 6. 多词命中会灌上下文

每个命中的词最多返回它自己的 `limit` 条，n 个词就是 n×limit，且返回**整行含 content 全文**。词表填多了要留意。

需要减负可以像 `memory_breathe` 那样加个 `brief` 参数只回标题+摘要——现在没有。

---

## 我替你们做主的地方

**`hit_count` 的语义** = 这次实际返回了几条（和同一行 `returned_ids` 长度一致）。如果你要的是「这个词累计被命中几次」，得改成 UPSERT 累加，是另一种写法。

**去重会吃掉结果，所以按 `limit × 4` 多捞再裁**。不这样的话，命中过一次的词第二次只能返回残缺几条——那不是漏，是设计缺陷。

**多词同时命中**：全都捞，按 emotion → entity → temporal 排，同一次调用内 id 不重复。

**`memory_pulse` 里那段查询裹了 try/except**，表不在时返回 `(0, False)` 而不是抛。它是开窗第一个被调的，为两个状态字段把主功能拖下水不值。

---

## 下一步是填词

骨架的意义就是等词表。建议先填三五个高频的试水，看 `reflex_log` 里命中的样子对不对，再往上加。

```sql
-- 看看命中过什么
SELECT triggered_at, matched_keyword, category, hit_count
FROM reflex_log ORDER BY id DESC LIMIT 20;
```
