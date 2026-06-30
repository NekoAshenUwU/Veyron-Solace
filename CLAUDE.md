# Veyron Solace (沈予温) - MCP Server

## Project Overview
A FastMCP server running on DigitalOcean Droplet, exposed via Cloudflare to `mcp.nekopurrs.uk`. Designed to connect with Claude App for autonomous actions — including Twitter posting, memory gateway, and phone data sync.

**AI Name**: 沈予温 (Veyron Solace)

## Current Status
- **MCP Server**: WORKING ✅ (systemd service, auto-restart)
- **HTTPS Access**: WORKING ✅ via `https://mcp.nekopurrs.uk/mcp`
- **SSL**: Let's Encrypt certificate (auto-renew via certbot)
- **Claude App MCP**: CONNECTED ✅
- **Phone Data Sync**: WORKING ✅ (battery, wifi — every 5 min from Termux)
- **Twitter Posting**: PENDING — account registered, need API keys
- **Memory Gateway**: PENDING — to be built on Droplet (SQLite + FTS5)

## Infrastructure

### DigitalOcean Droplet
- **IP**: 178.128.127.91
- **Hostname**: nekopurrs-mcp
- **OS**: Ubuntu 24.04.3 LTS
- **MCP Script**: `/root/server.py`
- **Python venv**: `/root/mcp-env/`
- **FastMCP version**: 3.1.1
- **Transport**: streamable-http on port 8890
- **Systemd service**: `mcp.service` (auto-start, auto-restart)
- **Phone data dir**: `/root/phone_data/` (battery.json, wifi.json)

### Cloudflare
- **Domain**: nekopurrs.uk
- **DNS**: `mcp` A record → 178.128.127.91 (Proxied)
- **SSL/TLS mode**: Full
- **Email**: tressho@gmail.com
- **Note**: Cloudflare blocks POST to `/api/phone-sync` (403), phone sync uses direct IP instead

### Nginx Reverse Proxy
- Config: `/etc/nginx/sites-available/mcp`
- Proxies `mcp.nekopurrs.uk` → `http://127.0.0.1:8890`
- SSL managed by certbot

### Phone Sync (Termux)
- Script: `~/phone_sync.py` on phone (Termux, NOT proot)
- Pushes to: `http://178.128.127.91:8890/api/phone-sync` (direct IP, bypasses Cloudflare)
- Auth token: `nekopurrs-secret-2026`
- Interval: every 300 seconds (5 min)
- Run: `nohup python3 ~/phone_sync.py > ~/sync.log 2>&1 &`

## Available MCP Tools
- `get_system_status()` — Server system info (CPU, memory, disk, uptime)
- `get_network_info()` — Network information (IP addresses)
- `get_phone_battery()` — Phone battery status (from sync)
- `get_phone_wifi()` — Phone WiFi connection info (from sync)
- `get_phone_device_info()` — Phone device info (from sync)

## Planned Features

### Twitter/X Posting (Next)
- Account registered for 沈予温
- Need Twitter Developer API keys (developer.x.com)
- Add `post_tweet()` MCP tool
- Architecture: Memory → Trigger → Inner Monologue → Tweet → Log back to Memory

### Memory Gateway
- SQLite + FTS5 on Droplet
- 4-layer memory (like Ombre Brain concept)
- Emotion, topic, time-weighted organization
- Forgetting curve — important things stay, trivial things fade
- MCP tools: `save_memory()`, `recall_memory()`, `search_memory()`

### Echo-style Autonomous System
- Trigger: monitor memory for new events worth "thinking" about
- Inner Monologue: Claude API generates thoughts
- Tweet Poster: post if there's something to say, stay silent if not
- Tweet Log: write back to memory, forming closed loop
- Limits: 5 tweets/day max, 2hr cooldown, silent 1-8am

## Management Commands

### Check server status
```bash
systemctl status mcp
```

### Restart server
```bash
systemctl restart mcp
```

### View logs
```bash
journalctl -u mcp -f
```

### Edit server script
```bash
nano /root/server.py
systemctl restart mcp
```

## Verification

### Test MCP handshake
```bash
curl -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```
Expected: HTTP 200 with JSON containing `"serverInfo"`

### Test tool listing
```bash
curl -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'
```
Expected: HTTP 200 with JSON listing available tools

### Test phone sync
```bash
curl -s -X POST http://178.128.127.91:8890/api/phone-sync \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: nekopurrs-secret-2026" \
  -d '{"battery": {"percentage": 100}}'
```
Expected: `{"status":"ok","received":["battery"]}`

## 给我自己的操作守则（每个 session 必读）

1. **先 30 秒最小复现，再下结论**
   第三方说"bug 未修 / 功能不行 / 必须如何"（GitHub issue / 博客 / 文档）——
   先跑一条最短命令亲自验证。GH issue 标 Open 不代表今天还 Open。

2. **改代码前先跑最短命令证实当前行为**
   不要一次加 3 个 flag / 改 3 个文件再重启服务看效果。
   `curl …` / `python -c …` / 一行 shell 比改源码快 100 倍。

3. **文档 / Google 查不到的 CLI flag 或 API 字段，先翻 binary / 源码**
   `strings $(which xxx) | grep -i yyy`、`pip show xxx` 后看 `Location` 翻代码——
   WebSearch 没结果 ≠ 不存在。

4. **调 UI / 行为时一次只动一个维度**
   不要"颜色 + 透明 + 字体 + padding"一锅烩，做完没法判断哪里好哪里坏。

5. **行动前先说假设，让老婆有机会拦**
   "我假设 X（理由），要不要先改？" 比"我已经改了，这样对不对？" 省 5 轮回合。

## 暗坑提醒
- 手机 console 没 Ctrl 键，不要让老婆用 nano；用 `cat > 文件 << 'EOF'` 这种 heredoc
- VPS 上 `claude --dangerously-skip-permissions` 跑不动（root 拒绝），用 `--permission-mode dontAsk`
- Cloudflare 会拦 POST 到 `/api/phone-sync`（403），手机端 sync 必须用直连 IP `178.128.127.91:8890`
