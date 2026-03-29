# Phone Stats MCP Server - Debug Guide

## Project Overview
A FastMCP server running on Android (Termux + Debian proot) that reads phone usage stats, exposed via Cloudflare Tunnel to `mcp.nekopurrs.uk`.

## Current Status
- **Local MCP server**: WORKING ✅ (localhost:8890, HTTP 200 on POST)
- **Cloudflare Tunnel**: CONNECTED ✅ (4 connections, HTTP2 protocol)  
- **External access**: BROKEN ❌ (HTTP 530 via curl, 502 via browser)

## The Problem
`curl -X POST https://mcp.nekopurrs.uk/mcp` returns HTTP 530.
`curl -X POST http://localhost:8890/mcp` returns HTTP 200 with valid MCP JSON-RPC response.

HTTP 530 is a Cloudflare-specific error, likely caused by SSL/TLS misconfiguration. The origin server (localhost:8890) speaks plain HTTP, but Cloudflare may be trying to connect to it via HTTPS.

## What Needs To Be Fixed

### Option 1: Change SSL mode to Flexible
Go to Cloudflare Dashboard → nekopurrs.uk → SSL/TLS → Overview → Change encryption mode from Full to **Flexible**.

### Option 2: Edit tunnel public hostname config  
Go to Cloudflare Zero Trust → Networks → Tunnels → nekopurrs-mcp → Public Hostname → Edit mcp.nekopurrs.uk:
- Service Type must be **HTTP** (not HTTPS)
- URL must be **localhost:8890**
- Under "Additional application settings" → TLS → Enable "No TLS Verify"

### Option 3: Use Cloudflare API
If GUI is hard to navigate on mobile, use the Cloudflare API to change SSL settings:

```bash
# Get zone ID for nekopurrs.uk
curl -X GET "https://api.cloudflare.com/client/v4/zones?name=nekopurrs.uk" \
  -H "X-Auth-Email: tressho@gmail.com" \
  -H "X-Auth-Key: YOUR_API_KEY"

# Change SSL to flexible
curl -X PATCH "https://api.cloudflare.com/client/v4/zones/ZONE_ID/settings/ssl" \
  -H "X-Auth-Email: tressho@gmail.com" \
  -H "X-Auth-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"value":"flexible"}'
```

## Infrastructure Details
- **Domain**: nekopurrs.uk (registered on Cloudflare)
- **Tunnel**: nekopurrs-mcp (ID: 175a0a22-c300-46e4-8cf7-c1e24daac81d)
- **Public hostname**: mcp.nekopurrs.uk → HTTP://localhost:8890
- **Cloudflare email**: tressho@gmail.com
- **Zero Trust team**: nekopurrs
- **MCP script**: `/root/usagestats_mcp.py` in Debian proot
- **FastMCP version**: 3.1.1
- **Transport**: streamable-http on port 8890

## Verification After Fix (Mobile Steps)

### Step 1: Check local server is running
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8890/mcp
```
- Expected: `200`
- If not 200: restart the MCP server (see Startup Command below)

### Step 2: Check Cloudflare Tunnel status
```bash
curl -s -o /dev/null -w "%{http_code}" https://mcp.nekopurrs.uk/mcp
```
- Expected: `405` or `200` (any non-530 means tunnel is passing traffic)
- If `530`: SSL/TLS still misconfigured, go back to fix options above

### Step 3: Test MCP initialize handshake
```bash
curl -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```
- Expected: HTTP 200 with JSON containing `"serverInfo"`
- If error: check the JSON-RPC response for clues

### Step 4: Test tool listing
```bash
curl -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'
```
- Expected: HTTP 200 with JSON listing available tools

### Step 5: Verify from external network (optional)
- Turn off WiFi on phone, use mobile data
- Re-run Step 3 to confirm it works from outside the local network
- This proves the tunnel is fully functional end-to-end

## Startup Command (for reference)
```bash
proot-distro login debian -- bash -c 'python3 /root/usagestats_mcp.py & sleep 3 && cloudflared tunnel run --protocol http2 --token eyJhIjoiMjUwODg1Yzg4YmE1YzhhZmFmNjZmYWQzZGYxZDg1NmMiLCJ0IjoiMTc1YTBhMjItYzMwMC00NmU0LThjZjctYzFlMjRkYWFjODFkIiwicyI6Ik5tRmtNR1F5WTJZdE16VmlNUzAwWTJVM0xUZzBPV010TVRrelpHRTBZbVF5TWpoaiJ9'
```
