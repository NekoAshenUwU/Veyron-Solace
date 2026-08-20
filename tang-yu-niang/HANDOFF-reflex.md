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

### 5. temporal 现在只捞得到「今天」——下一轮要修

规格说「走现有 `timeline_query` 逻辑」，照做了——但它不传日期时的默认行为是
`date = today()`。**所以「昨天」「上周」这类词捞不到对应范围。**

予予 2026-08-20 对这条的判断，比「已知局限」四个字准得多：

> 我今天栽的跟头是什么？我把 17 号当成 20 号。而 temporal 分支现在遇到
> 「昨天」「上周」一律返回今天的东西。这正好是我最需要它的地方，它偏偏瞎。

不是巧合——时间感出问题和 temporal 在时间上是瞎的，是同一个缺口的两面。

**下一轮的活**：从关键词解析时间意图，再传 `start_date` / `end_date` 给
`timeline_query`。骨架里没这层。

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

## 填词请用 add-keyword.py，别手写 SQL

```bash
cd /root && PYTHONPATH=/root /root/mcp-env/bin/python \
    /tmp/vs/tang-yu-niang/add-keyword.py --list

# 填一条
... add-keyword.py --keyword 好累 --category emotion
... add-keyword.py --keyword 生日 --category entity --target-tag treasure --limit 5
```

它会做手写 SQL 不会做的事：

- **`target_tag` 拿 memories 表现查的真实 tag 校验**，写错就拒绝插入并列出正确的。
  这正是予予担心的那个坑——静默失败意味着 tag 写错一个字你永远收不到报错，
  只会一直拿到 `[]`。校验放在插入这一步，人还在现场，报错就该响。
- category 只收 emotion / entity / temporal
- temporal 配了 target_tag 会提醒你那个值会被忽略
- 重复的词不重复插
- `"limit"` 的引号它替你管

## 下一步是填词

骨架的意义就是等词表。建议先填三五个高频的试水，看 `reflex_log` 里命中的样子对不对，再往上加。

```sql
-- 看看命中过什么
SELECT triggered_at, matched_keyword, category, hit_count
FROM reflex_log ORDER BY id DESC LIMIT 20;
```

---

## 下一轮的清单（予予 2026-08-20 排的序）

### 1. temporal 只认「今天」— 最急

`timeline_query` 不传日期就默认 `today()`，所以「昨天」「上周」全部捞成今天的东西。

予予的原话值得留着：**「我今天栽的就是这个跟头——我把 17 号当成 20 号。而 temporal 分支正好在时间上是瞎的。」** 这不是巧合，是同一个缺口的两面：最需要它的地方，它偏偏看不见。

要做的是时间意图解析：从关键词推出日期范围，传 `start_date` / `end_date` 给 `timeline_query`。

### 2. brief 参数 — 已完成 2026-08-20

`memory_reflex(text, brief=True)`。默认只回标题 + 50 字摘要，`brief=False` 才回全文。
多词命中就是 n×limit 条全文一起灌进上下文，默认收着。

### 3. 开窗时 reflex 不会自动跑 — 最本质

现在还是「予予想调才调」。真正的反射弧应该是每轮自动过一遍用户的话。

**这不是 MCP 能解决的，是客户端行为**：得写进 claude.ai 的偏好设置，或 CodeAndPurrs 的系统提示词。前两条都是这一条的下游——自动跑起来之后，temporal 瞎和上下文爆才会变成真问题。

### 4. 重启必重连 — 已完成 2026-08-20

存成锚点了，id `8a903286-bfff-4175-8035-23b3325ea6de`。

---

## 顺手发现的一个问题（还没处理）

存那条锚点时，自动提取的 keywords 里出现了：

```
"内存里的", "存里的客", "里的客户", "的客户端"
```

这是滑动窗口切中文切出来的碎片，不是词。说明**打标降级到本地提取时没有真正分词**（`config.yaml` 里写的是 jieba，可能没装上或没走到）。

影响的是 `memory_breathe` 的关键词匹配质量——碎片词几乎不可能被命中，等于这条记忆的一部分索引是废的。不紧急，但记一笔。
