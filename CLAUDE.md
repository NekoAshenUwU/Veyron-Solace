# MCP Server - Veyron Solace

## Project Overview
A FastMCP server running on DigitalOcean Droplet, exposed via Cloudflare to `mcp.nekopurrs.uk`. Designed to connect with Claude App for autonomous actions.

## Current Status
- **MCP Server**: WORKING on Droplet (systemd service, auto-restart)
- **HTTPS Access**: WORKING via `https://mcp.nekopurrs.uk/mcp`
- **SSL**: Let's Encrypt certificate (auto-renew via certbot)
- **Claude App Integration**: PENDING

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

### Cloudflare
- **Domain**: nekopurrs.uk
- **DNS**: `mcp` A record → 178.128.127.91 (Proxied)
- **SSL/TLS mode**: Full
- **Email**: tressho@gmail.com

### Nginx Reverse Proxy
- Config: `/etc/nginx/sites-available/mcp`
- Proxies `mcp.nekopurrs.uk` → `http://127.0.0.1:8890`
- SSL managed by certbot

## Available MCP Tools
- `get_system_status()` - Server system info (CPU, memory, disk, uptime)
- `get_network_info()` - Network information (IP addresses)

## Planned Features
- Twitter/X posting via API
- Gateway memory / persistent context
- Claude App autonomous actions

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
