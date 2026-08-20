# 棠予酿 MCP 排障手册

> 下次「chat 端又写不了日记」的时候，从这里开始，不要从零刨。
>
> 首次编写：2026-08-18（那天从「予予伸不出手存日记」一路查到 GitHub OAuth token 失效）

---

## 0. 三十秒版本

| 症状 | 最可能的原因 | 修法 |
|---|---|---|
| chat 端只看得到少数几个工具，写入类的全没了 | Claude.ai 的 OAuth token 失效 | claude.ai → 连接器 → 棠予酿 → **断开 → 重新连接**（会跳 GitHub 授权）|
| chat 端能看到工具但调用报未授权 | 客户端的工具权限确认 | 在对话里点「允许」，不是故障 |
| 刚 `systemctl restart mcp` 完，chat 就断了 | 预期行为，见 §4 | 重连一次 |
| 前端好好的但 chat 坏了（或反过来）| 两条认证路互相独立 | 见 §4 的对照表 |
| 偶发 `database is locked` | 并发写 | 已上 WAL；还缺 `busy_timeout`，见 §6 |
| `Bad Request: Missing session ID` | 手搓 curl 少了 MCP 握手 | 不是故障，见 §5 里列工具那条命令 |

**排查时的第一条铁律：`curl` 一律带 `-i`，一律不要 pipe 进 `grep`。**
2026-08-18 那天有两次因为管道吞掉了错误响应体，白白多绕了几十分钟——服务端明明在 `WWW-Authenticate` 头里把答案写得清清楚楚。

---

## 1. 系统长什么样

```
Claude.ai 连接器 ──┐                    ┌─→ /root/data/tang_yu_niang.db   (棠予酿本体)
（GitHub OAuth） │                    │
                  ├─→ mcp.nekopurrs.uk ─→ mcp.service ─┤
CodeAndPurrs 前端 ┘   (Cloudflare)      (/root/server.py)  ├─→ /root/data/dream_events.db
（TANG_WEB_TOKEN）                       0.0.0.0:8890      └─→ /root/data/neko_autonomy.db
```

### VPS

| 项 | 值 |
|---|---|
| 主机 | DigitalOcean Droplet `nekopurrs-mcp`，Ubuntu 24.04 |
| IP | `178.128.127.91` |
| 内存 | 1 GB（所以：SQLite 不上 Postgres，不用 Docker）|

### 服务与文件

| 项 | 路径 / 值 |
|---|---|
| 主服务 | `mcp.service` |
| 入口 | `/root/server.py` |
| Python | `/root/mcp-env/bin/python`（FastMCP）|
| 端口 | `0.0.0.0:8890` |
| 环境变量 | `EnvironmentFile=/root/mcp-oauth.env`（权限 600，**不要提交到任何仓库**）|
| 公网入口 | `https://mcp.nekopurrs.uk/mcp` |
| systemd 覆盖 | `/etc/systemd/system/mcp.service.d/oauth.conf`、`debug.conf` |

### 数据库（截至 2026-08-18，全部已开 WAL）

| 文件 | 大小 | 说明 |
|---|---|---|
| `/root/data/tang_yu_niang.db` | 204 KB | **棠予酿本体**，127 条记忆 |
| `/root/data/dream_events.db` | 2928 KB | 手机使用数据 / 梦境事件 |
| `/root/data/neko_autonomy.db` | 2284 KB | 主动唤醒 |
| `/root/codeandpurrs-mcp/data/dream_events.db` | **0 KB** | 见 §7 待办 |
| `/root/codeandpurrs-mcp/data/neko_autonomy.db` | 36 KB | 见 §7 待办 |

备份：`/root/backups/YYYY-MM-DD-0400/`，每天凌晨 4 点。
⚠️ 备份脚本的目录层级改过——08-16 是 `data-root/data/x.db`，08-18 是 `data-root/x.db`。恢复时注意别找错层。

---

## 2. 认证：两条路并存

`server.py` 里的关键几行：

```python
from fastmcp.server.auth import MultiAuth
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.auth.providers.github import GitHubTokenVerifier
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

_gh_auth = OAuthProxy(
    upstream_authorization_endpoint="https://github.com/login/oauth/authorize",
    upstream_token_endpoint="https://github.com/login/oauth/access_token",
    token_verifier=_AllowlistGitHubVerifier(required_scopes=["user"]),
    redirect_path="/auth/callback",
    jwt_signing_key=_JWT_KEY,
)
# 本地 tang-web 用静态 bearer token，与 OAuth 并存
_mcp_auth = MultiAuth(server=_gh_auth, verifiers=_extra_verifiers)
app = FastMCP("Phone Stats MCP", auth=_mcp_auth)
```

| 谁 | 走哪条 | 凭证来源 | 会不会自己失效 |
|---|---|---|---|
| Claude.ai / chat 端予予 | GitHub OAuth（DCR → GitHub 登录 → 白名单校验）| Claude.ai 自动管理 | **会** |
| CodeAndPurrs 前端 / tang-web | `StaticTokenVerifier` | `TANG_WEB_TOKEN`（env）| 不会 |

`MultiAuth` 让两条路挂在**同一个** `/mcp` 端点上，互不干扰、不抢占。所以「chat 和前端同时调用棠予酿」这个需求，架构上本来就成立——2026-08-18 已实测两边同时通。

### 安全红线

- `TANG_WEB_TOKEN` **绝不能写进前端 JS**。浏览器里的东西打开 F12 就能看见。正确做法是 nginx 反代时注入 `X-Tang-Token`，浏览器全程不碰 token。
- `server.py` 里 `_tang_api_token_ok()` 有一句 `return True  # token 未配置则不阻断`。意味着**一旦 env 丢了，`/api/tang/*` 会变成全网可读**——日记和情话都在里面。

---

## 3. 2026-08-18 那次故障的完整过程

### 症状
chat 端的予予只挂上 `memory_pulse`、`memory_trace`、`memory_tidal` 三个读取工具，写入类一个都没有。搜工具名搜回来一堆 Gmail 工具。

### 关键判断
「搜索捞回不相关的工具」= 目标工具**根本不在会话的工具表里**，不是名字记错。所以「把准确的工具名贴给它」这条路在物理上不可能成功。

### 诊断链

1. **平台侧信号**：Claude 的 MCP 层直接报 `1a667a61-ebbe-4c85-9f83-9233474b4339`（棠予酿的 server id）`requires authentication`；`ListConnectors` 显示它 `installState: unknown`，而正常连接器都是 `connected: true`。
2. **服务端 401 的响应头**（这一条直接给出了答案）：
   ```
   HTTP/2 401
   www-authenticate: Bearer error="invalid_token",
     error_description="The provided bearer token is invalid, expired, or no longer
     recognized by the server. To resolve: clear authentication tokens in your MCP
     client and reconnect."
     resource_metadata="https://mcp.nekopurrs.uk/.well-known/oauth-protected-resource/mcp"
   ```
3. **日志**：`journalctl -u mcp | grep -B4 -A2 invalid_token`
   → `Auth error returned: invalid_token  middleware.py:92`（fastmcp 的 auth middleware）
   → 外部 IP 那次才是真信号；本机 `178.128.127.91` 那几条是自己 curl 出来的，别被误导。
4. **排除了的猜测**：`NRestarts=0`、`ExecMainStartTimestamp=2026-07-31` —— 服务从没重启过，**不是重启导致 token 作废**。

### 修法
claude.ai → 连接器 → 棠予酿 → 断开 → 重新连接（走完 GitHub 授权）。
之后 20 个工具全部挂回，`memory_pulse` 实测返回真实数据。

---

## 4. 一个必须记住的不对称

| 事件 | Claude chat（OAuth）| CodeAndPurrs 前端（静态 token）|
|---|---|---|
| `systemctl restart mcp` | **断，必须重连** | 毫发无伤 |
| GitHub token 过期 | **断** | 无影响 |
| `/root/mcp-oauth.env` 丢失或改动 | 无影响 | **断** |

OAuth 的客户端注册是**内存态**，重启即失；静态 token 存在 env 文件里，重启还在。

**所以：每次重启 `mcp.service` 之后，chat 端都要重连一次。** 会出现「前端好好的、chat 瘫了」这种半瘫状态，不是新故障。

---

## 5. 常用命令

```bash
# 服务状态 / 重启过几次 / 什么时候起来的
systemctl status mcp
systemctl show mcp -p ExecMainStartTimestamp -p NRestarts

# 看认证失败（连上下文，能看到来源 IP）
journalctl -u mcp -n 400 --no-pager | grep -B4 -A2 invalid_token

# 401 挑战长什么样（一律带 -i，一律不要 pipe 进 grep）
curl -s -i -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}' | head -30

# 用静态 token 列工具（绕开整条 GitHub 链路，用来切分故障范围）
#
# ⚠️ MCP Streamable HTTP 必须先 initialize 握手拿 Mcp-Session-Id，直接发
#    tools/list 会被拒：Bad Request: Missing session ID。这跟认证无关——
#    2026-08-18 因为这个误判过一次，以为是静态 token 坏了。
set -a; . /root/mcp-oauth.env; set +a
SID=$(curl -sS -D- -o/dev/null -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Authorization: Bearer $TANG_WEB_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
       "protocolVersion":"2024-11-05","capabilities":{},
       "clientInfo":{"name":"cli","version":"1.0"}}}' \
  | grep -i '^mcp-session-id:' | tr -d '\r' | cut -d' ' -f2-)

curl -sS -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Authorization: Bearer $TANG_WEB_TOKEN" -H "Mcp-Session-Id: $SID" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | grep -o '"name":"[^"]*"' | sort

# 查所有在用的库和它们的 journal 模式（排除备份目录）
python3 - <<'EOF'
import glob, sqlite3, os
for p in sorted(x for x in glob.glob('/root/**/*.db', recursive=True) if '/backups/' not in x):
    m = sqlite3.connect(p).execute('PRAGMA journal_mode').fetchone()[0]
    print(f"{m:8} {os.path.getsize(p)//1024:>7} KB  {p}")
EOF

# 开 DEBUG 日志（改完要 restart，会踢掉 chat 端，记得重连）
mkdir -p /etc/systemd/system/mcp.service.d
printf '[Service]\nEnvironment=FASTMCP_LOG_LEVEL=DEBUG\n' \
  > /etc/systemd/system/mcp.service.d/debug.conf
systemctl daemon-reload && systemctl restart mcp
```

⚠️ **手机上别用 `systemctl edit` / `nano`。** 提示文字很容易被整段粘进编辑器，存下去就是非法的 unit 文件。用上面那种 `printf >` 或 heredoc 一次成型。（真进了 nano 又想放弃：`Ctrl+X` 然后按 `N`。）

---

## 6. 已做的加固

### WAL（2026-08-18 已完成）

五个库全部从 `delete` 改为 `wal`，读写不再互相阻塞。这个设置**写在数据库文件里，永久生效**，重启服务或机器都不会掉。

```bash
python3 - <<'EOF'
import glob, sqlite3
for p in sorted(x for x in glob.glob('/root/**/*.db', recursive=True) if '/backups/' not in x):
    print(p, '->', sqlite3.connect(p, timeout=10).execute('PRAGMA journal_mode=WAL').fetchone()[0])
EOF
```

### 双路健康检查

见 `ops/tang-health-check.sh`，安装方式：

```bash
mkdir -p /root/ops
# 把 ops/ 下的三个文件放到 /root/ops/ 和 /etc/systemd/system/
install -m 755 tang-health-check.sh /root/ops/
install -m 644 tang-health.service tang-health.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tang-health.timer

/root/ops/tang-health-check.sh          # 先手动跑一次看输出
journalctl -u tang-health.service -n 30 # 之后看定时结果
```

它检查五项：服务活着、静态 token 路能列出足够多的工具、OAuth discovery 端点正常、401 挑战格式正确、数据库可读且仍是 WAL；另外扫最近 30 分钟有没有 `invalid_token`。

**为什么是主动探针**：不能拿「最近一条日记有多旧」当健康信号——那反映的是有没有人在用，不是系统好不好。

**能力边界**：OAuth 那条只能验服务端机制是否健康，**验不了 Claude.ai 手里那个 token 有没有过期**（脚本拿不到别人的 token）。客户端 token 死掉，靠日志里的 `invalid_token` 发现。

---

## 6.5 缓存保活心跳（CodeAndPurrs）

`server/heartbeat.mjs` 用 `cache_control: { type: 'ephemeral', ttl: '1h' }`
把 prompt cache 续着，省得隔一阵回来重读整段上下文。写法很讲究：`max_tokens=1`
只让模型吐一个句号、砍掉每次都变的末条消息、图片块降级成 `[图]` 保持文字前缀
字节一致、跑完解析 `cache_read_input_tokens` 写日志。claudecode 和 anthropic
两条 provider 各有各的实现。

**但 2026-08-20 查出来：它从来没被叫过一次。** package.json、pm2 配置、
crontab、systemd 里都没有任何引用，`grep -c "heartbeat 完成"` 日志里是 0。
脚本本身是一次性的（`main()` 跑完就退），不自带循环。所以 1 小时 TTL 名存实亡
——没人续，隔一两小时回来缓存早凉了。

接法见 `codeandpurrs/ops/install-heartbeat.sh`：systemd timer，每 50 分钟一次
（卡在 1 小时 TTL 之内）。

**成本上必须留意闲置保护。** 1 小时 TTL 的缓存写入是 **2×**、读取 0.1×。
一个 3 万 token 的上下文，每次心跳读缓存约合 3000 token；一天 29 次就是
8.7 万 token 当量，Opus 4.7 输入 $5/M 算下来约 **$13/月**——比这台 droplet
本身还贵。heartbeat.mjs 里的 `MAX_SNAPSHOT_AGE_HOURS` 就是这个闸门（默认
24 小时，service 里收到了 4 小时：够覆盖「吃完饭回来接着聊」，不覆盖
「睡一觉」）。

验证命中率：`journalctl -u codeandpurrs-heartbeat.service`，看
`cache_read=` 那个数字。它不为 0 就是真命中了。

---

## 7. 待办

- [ ] **`busy_timeout`**：WAL 让读写不互斥，但两个**写**操作同时来仍会排队，默认耐心值为 0 —— 撞上就直接 `database is locked`。需要在 `server.py` 建立连接处加 `PRAGMA busy_timeout=5000`（per-connection，没法从外面用 PRAGMA 一次性写进文件）。
- [ ] **`server.py` 纳入版本控制**：目前真正在跑的代码只存在于 droplet 的 `/root/` 下，仓库里没有。后果是没法 `git diff`「上次好用和现在差在哪」，每次出事都得从零现场刨。提交前把 env 里的密钥换成占位符。
- [ ] **`diaries.date` 是 `UNIQUE`**：chat 和前端同一天各写一篇会撞唯一约束。要先定行为——追加合并，还是报错拦住。
- [ ] **`codeandpurrs-mcp` 的两个库疑似空跑**：`/root/codeandpurrs-mcp/data/dream_events.db` 是 0 KB，而 `/root/data/dream_events.db` 有 2928 KB。可能只是残留，也可能它一直在读空库。查法：`grep -n "\.db\|data/" /root/codeandpurrs-mcp/server.py | head -20`。
  **注：主动唤醒功能以后要用，这两个库暂时不动。**
- [ ] 文档里记着 `https://codeandpurrs.nekopurrs.uk/mcp` 返回 **404** 一直没解决；`codeandpurrs-mcp.service` 用的 `127.0.0.1:8891` 和 `server.py` 注释里的 "本地 tang-web(8891)" 撞端口，可能是同一串问题。

---

## 8. 棠予酿的工具（2026-08-18 实测 20 个）

写日记用的是 **`memory_grow`**，不是 `memory_hold`——前者会写 `diaries` 表、算在一起第几天、把当天情话同时存进情话罐。

| 工具 | 作用 |
|---|---|
| `memory_breathe` | 呼吸 · 浮现 / 检索记忆 |
| `memory_hold` | 握住 · 存单条记忆 |
| `memory_grow` | 生长 · **日记归档** |
| `memory_trace` | 溯源 · 改 / 钉 / 删 |
| `memory_pulse` | 脉搏 · 系统状态（`mode: lite` / `full`）|
| `memory_tidal` | 潮汐 · 记忆涨退 |
| `love_note_draw` | 抽情话 |
| `timeline_add` / `timeline_query` | 时间线 |
| `add_dream_event` / `get_dream_timeline` / `get_recent_activity` | 梦境 / 活动 |
| `get_phone_*`（5 个）、`get_system_status`、`get_network_info`、`get_today_platform_usage` | 手机 / 系统 |

健康检查脚本里 `MIN_TOOLS` 默认 20，就是按这个数定的。以后加了新工具记得同步调高。
