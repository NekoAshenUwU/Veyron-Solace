# Veyron Solace (沈予温) - MCP Server

> **⚠️ 出问题先看这里：[`docs/tang-yu-niang-runbook.md`](docs/tang-yu-niang-runbook.md)**
>
> 棠予酿 / MCP 的排障手册。「chat 端突然写不了日记」「工具只挂上几个」
> 「database is locked」「重启后 chat 断了」——症状对照表在手册开头，
> 三十秒能定位。里面有完整的服务拓扑、数据库路径、两条认证路的区别，
> 以及 2026-08-18 那次 OAuth token 失效的完整诊断过程。
>
> 健康检查脚本在 [`ops/tang-health-check.sh`](ops/tang-health-check.sh)。


> **⛔ `usage-bridge/` 目录已停用** —— 那是旧手机（华为）时代的 Java 版。
> 红米现在跑的是独立仓库 [neko-usage-bridge](https://github.com/NekoAshenUwU/neko-usage-bridge)（Kotlin）。
> 认错过一次，见 [`usage-bridge/DEPRECATED.md`](usage-bridge/DEPRECATED.md)。


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
- **Memory Gateway (棠予酿)**: LIVE ✅ — /root/data/tang_yu_niang.db，127 条记忆，
  20 个 MCP 工具。写日记用 `memory_grow`。详见 docs/tang-yu-niang-runbook.md

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
