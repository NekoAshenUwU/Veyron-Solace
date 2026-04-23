#!/usr/bin/env python3
"""
PreCompact hook: saves a diary entry to 棠予酿 before conversation compaction.
Called by Claude Code automatically. Reads session info from stdin, POSTs to MCP server.
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import date, datetime

MCP_BASE = "http://localhost:8890"


def mcp_post(payload: dict, session_id: str = "") -> tuple:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{MCP_BASE}/mcp", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        new_sid = resp.headers.get("Mcp-Session-Id", session_id)
        body = resp.read().decode()
        # streamable-http may return SSE; grab first data: line if so
        if body.startswith("data:"):
            for line in body.splitlines():
                if line.startswith("data:"):
                    body = line[5:].strip()
                    break
        return json.loads(body), new_sid


def main():
    try:
        stdin_data = json.load(sys.stdin)
    except Exception:
        stdin_data = {}

    trigger = stdin_data.get("trigger", "auto")
    summary = (
        stdin_data.get("summary")
        or stdin_data.get("context")
        or ""
    )

    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M")
    title = f"日记 {today} {now} [{trigger}压缩]"

    if summary:
        content = summary[:2000]
    else:
        content = f"{today} {now} 对话记忆压缩（{trigger}）— 无摘要可用"

    # Initialize MCP session
    try:
        _, session_id = mcp_post({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "precompact-diary", "version": "1.0"},
            },
            "id": 1,
        })
    except Exception:
        sys.exit(0)  # server not reachable — skip silently

    if not session_id:
        sys.exit(0)

    # Call memory_hold
    try:
        mcp_post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "memory_hold",
                "arguments": {
                    "title": title,
                    "content": content,
                    "tag": "diary",
                    "importance": 4,
                },
            },
            "id": 2,
        }, session_id)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
