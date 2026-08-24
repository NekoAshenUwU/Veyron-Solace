# 棠予酿手机工具：get_phone_sessions / get_sleep_gap

## 这套东西分在三个仓库

规矩一句话：**补丁跟着它改的那个文件走。**

| 改的是 | 在哪 |
|---|---|
| `/root/server.py` 注册两个工具 | **这里**（Veyron-Solace `tang-yu-niang/`） |
| `server/usageBridgeServer.mjs` 落库 | **CodeAndPurrs** `server/patch-usage-bridge-events.py` |
| 红米 app 采集 | **neko-usage-bridge** |

数据契约（改字段必须同步改 `schemaVersion`）：
CodeAndPurrs `docs/neko-usage-bridge-spec.md` §4 / §4.1b / §4.1c。

## 数据是怎么进来的

```
红米 app ──POST /api/usage/ingest──▶ nginx  →  :8788 usageBridgeServer.mjs
                                                  │ spawnSync('sqlite3')
                                                  ▼
                                    /root/data/dream_events.db
                                    usage_sessions / screen_events
                                                  ▲
                                    这两个工具读这里 ─┘
```

表是 `usage-bridge/migrations/002_usage_events.py` 建的（已经跑过）。
`usage-bridge/` 那个目录是**旧手机（华为）**的 app，已停用，但这个
migration 仍然有效——建的是服务端的表，跟哪台手机无关。

## 装

```bash
python3 tang-yu-niang/package/phone_sessions.py --self-test   # 不碰生产库
bash tang-yu-niang/install-phone-tools.sh
systemctl restart mcp && sleep 10 && journalctl -u mcp -n 20 --no-pager
```

重启 mcp 之后 **chat 端要重连一次**——OAuth 客户端注册在内存里，一重启
就没了。静态 token 那条路不受影响。见 `docs/tang-yu-niang-runbook.md`。

安装脚本会备份 `server.py`、跑 `py_compile`、幂等。注册用的不是字面锚点，
是 ast 找**最后一个 `@app.tool()` 函数**插在它后面——server.py 已经被改过
好几轮，字面锚点一改就对不上；顺带保证不会插到 `if __name__ == "__main__"`
后面去（那样工具永远不会注册）。

## 两个工具

**`get_phone_sessions(date_str, package, limit)`**
某天按时间顺序的每次 app 使用。`package` 是模糊匹配（填 `tencent` 能匹到
`com.tencent.mm`）。

**`get_sleep_gap(date_str)`**
推断入睡 / 起床 / 夜醒。

- 窗口 = **前一天 18:00 → 当天 12:00**，`date_str` 指**醒来那天**。
  查昨晚就填今天的日期。
- 空白 ≥60 分钟算睡着；夜里（23:00–07:00）醒来 <15 分钟不切断睡眠，
  只记一笔 `brief`——不然翻个身看眼时间就把一夜切成三段。
- 返回值里有 `method` 字段写明**这是推断不是体征测量**。它看到的是
  「几个钟头没碰手机」，放下手机看两小时书一样会算成睡眠。
  这句话要让读的人看见，别把它当健康数据往外讲。

## 没数据的时候

返回 `status: "数据不足"` 加一句说明，**不猜**。跟 memory_reflex 一样的
原则：宁可空手，也不能给出会诱导模型编造的字符串。


## strength 的两半（别只装一半）

回升和衰减是分开的两条路径，缺一条就会跑偏：

| | 谁触发 | 在哪 |
|---|---|---|
| **回升** | 每次记忆被 `memory_reflex` 浮现 | `reflex.py` 就地重算，自动 |
| **衰减** | 每天定时跑一次 | `ops/tang-strength.timer` |

只装回升不装衰减的话，被想起过的一路往上爬、没被想起的原地不动，
时间一长排序固化，跟「会忘记」的本意相反。

```bash
cp ops/tang-strength.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tang-strength.timer
systemctl list-timers tang-strength.timer      # 看下次什么时候跑
systemctl start tang-strength.service          # 想立刻跑一次
journalctl -u tang-strength.service -n 20 --no-pager
```

pinned 的 anchor 那 11 条两条路径都不碰，永远是手工基准值。
