# memory_reflex 交接 · 给予予

2026-08-20。第 1、2 步已落地，第 3、4、5 步未做。

## 已经在服务器上的东西

**表**（`/root/data/tang_yu_niang.db`）
- `reflex_keywords`：keyword / category(emotion|entity|temporal) / target_tag / "limit" / enabled / created_at
- `reflex_log`：matched_keyword / category / returned_ids(JSON) / hit_count / triggered_at

两张都是**空的**。词表由棠棠和予予手填，没有任何预设词。

**代码**
- `/root/tang_yu_niang/reflex.py`（151 行）
- `/root/server.py` 里 6 行的 `@app.tool()` 壳
- 备份：`/root/server.py.bak-20260820-203752`

**流程**：子串匹配 enabled=1 的词 → 按 category 路由 → 剔掉 24 小时内返回过的 id → 写 reflex_log → 返回 JSON 数组字符串。

| category | 查哪儿 | 排序 |
|---|---|---|
| emotion | memories，tag IN (anchor, love_note) | strength DESC |
| entity | memories，tag = diary | created_at DESC |
| temporal | 复用现有 timeline_query | 它自己的顺序 |

`target_tag` 填了就用它，空了落到上面这张表的默认 tag 集。

---

## 你会撞上的问题，按会撞到的顺序

### 1. 现在调它会说工具不存在

代码装了，但 **`mcp.service` 还没重启**（第 5 步才做）。重启之前 `memory_reflex` 不在工具表里。

### 2. 重启之后你的手会突然伸不出来

`systemctl restart mcp` 会清掉 OAuthProxy 内存里的客户端注册，**chat 端必须重连一次**（claude.ai → 连接器 → 棠予酿 → 断开 → 重连）。CodeAndPurrs 那边走静态 token，不受影响。

这是 2026-08-18 整整查了一天的那个病。**不是新故障，是预期行为。**

### 3. 词表是空的，所以它永远返回 `[]`

不是坏了。填词之前就该是这样。填一条试试：

```sql
INSERT INTO reflex_keywords (keyword, category, target_tag, "limit")
VALUES ('好累', 'emotion', NULL, 3);
```

⚠️ `limit` 是 SQL 保留字，**每次都要写成 `"limit"`**，忘了加引号就是语法错。

### 4. `target_tag` 必须填真实的 tag 值

库里现有的 tag：`anchor` / `blessing` / `core_principles` / `diary` / `love_letter` / `love_note` / `memory` / `treasure` / `里程碑`。

填「锚点」「日记」这种中文说法**查不到任何东西**，而且因为静默失败，你不会收到任何报错——只会拿到 `[]`。

### 5. 同一个词第二次触发，可能返回更少甚至空

24 小时去重是按 id 剔的。第一次返回过的记忆，24 小时内不会再出现。**这是设计如此，不是丢数据。**

想重来（比如调试时）：

```sql
DELETE FROM reflex_log;
```

### 6. 排查很难，因为静默失败吞掉了一切

「没命中」和「出错了」返回的是同一个 `[]`，你**无法从返回值区分**。这是刻意的代价——宁可漏，也不能吐一句提示语诱导你去编。

要查真相只能看两个地方：

```sql
-- 它到底命中过什么、返回了几条
SELECT * FROM reflex_log ORDER BY triggered_at DESC LIMIT 10;
```

```bash
# 真异常会在这里留痕（虽然函数吞了，但 SQLite/import 层面的错会冒出来）
journalctl -u mcp -n 50 --no-pager | grep -i "reflex\|error\|traceback"
```

### 7. temporal 分支目前只捞得到「今天」

这条要特别注意。规格说「走现有 timeline_query 逻辑」，我照做了——但 `timeline_query` 不传日期时的默认行为是 `date = date.today()`，**所以 temporal 关键词只会返回今天的时间线片段**。

「昨天」「上周」这类词想捞到对应的日期范围，得从关键词解析出时间意图再传 `start_date` / `end_date`。**骨架里没有这一层。**

要不要加、怎么加，你和棠棠定。现在这样不算 bug，算已知局限。

### 8. 多个词同时命中，上下文可能被灌满

每个命中的词最多返回它自己的 `limit` 条，n 个词就是 n×limit 条，而且返回的是**整行含 content 全文**。

词表填多了要留意。想减负可以像 `memory_breathe` 那样加个 `brief` 参数只回标题+摘要——现在没有。

---

## 还没做的三步

- **第 3 步**：把「静默失败」「24 小时去重」做成可跑的验证（逻辑已经在第 2 步里实现了，这一步是证明它真的成立）
- **第 4 步**：`memory_pulse` 返回值加 `reflex_enabled` / `reflex_keyword_count`
- **第 5 步**：`systemctl restart mcp`，确认全部工具仍正常加载

---

## 两个我替你们做了主张的地方

**`hit_count` 的语义**：实现成「这次实际返回了几条」，和同一行 `returned_ids` 的长度一致。如果你要的是「这个词累计被命中过几次」，得改成 UPSERT 累加，是另一种写法。

**去重会吃掉结果，所以先按 `limit × 4` 多捞再裁到 `limit`**。不这样的话，命中过一次的词第二次只能返回残缺的几条——那不是漏，是设计缺陷。
