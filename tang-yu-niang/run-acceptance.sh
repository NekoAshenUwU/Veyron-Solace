#!/usr/bin/env bash
# 第 5 步：验收 → 重启 → 确认工具仍正常加载
set -uo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"

echo "════ 1/3  行为验收（重启前，直接调 Python 函数）"
# PYTHONPATH 是必须的：python 跑脚本文件时放进 sys.path 的是「脚本所在目录」
# （这里是 /tmp/vs/...），不是 cwd。光 cd /root 找不到 tang_yu_niang 包。
cd /root && PYTHONPATH="/root${PYTHONPATH:+:$PYTHONPATH}" \
    /root/mcp-env/bin/python "$SRC/verify-reflex.py"
rc=$?
echo
if [[ $rc -ne 0 ]]; then
    echo "验收没全过，先不重启。把上面的 FAIL 发出来。"
    exit 1
fi

echo "════ 2/3  重启 mcp.service"
systemctl restart mcp
# FastMCP 起来 + 连上游 MCP 要时间，3 秒不够
sleep 10
systemctl is-active mcp && echo "  服务在跑"
journalctl -u mcp -n 15 --no-pager | grep -iE "error|traceback|reflex" || echo "  启动日志没有报错"
echo

echo "════ 3/3  工具是否全部加载（走静态 token，绕开 OAuth）"
set -a; . /root/mcp-oauth.env; set +a
INIT=$(mktemp)
curl -sS -i --max-time 20 -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Authorization: Bearer $TANG_WEB_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
       "protocolVersion":"2024-11-05","capabilities":{},
       "clientInfo":{"name":"acceptance","version":"1.0"}}}' > "$INIT" 2>&1

SID=$(grep -i '^mcp-session-id:' "$INIT" | tr -d '\r' | cut -d' ' -f2-)

if [[ -z "$SID" ]]; then
    echo "  握手失败，拿不到 session id。原始响应："
    sed 's/^/    /' "$INIT" | head -25
    echo
    echo "  注意：这一段验的是「静态 token 能不能打 /mcp」，跟 memory_reflex 无关。"
    echo "  服务本身是否健康看上面 2/3 段；工具是否注册可以直接看代码或用 chat 端确认。"
    rm -f "$INIT"
    exit 1
fi
rm -f "$INIT"

curl -sS --max-time 20 -X POST https://mcp.nekopurrs.uk/mcp \
  -H "Authorization: Bearer $TANG_WEB_TOKEN" -H "Mcp-Session-Id: $SID" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' | sort -u > /tmp/tools.txt

echo "  共 $(wc -l < /tmp/tools.txt) 个工具："
sed 's/^/    /' /tmp/tools.txt
echo
grep -qx "memory_reflex" /tmp/tools.txt \
  && echo "  ✓ memory_reflex 已加载" \
  || echo "  ✗ memory_reflex 没出现——检查 journalctl -u mcp"

echo
echo "════ 完成"
echo "⚠️  刚才重启清掉了 OAuthProxy 的客户端注册。"
echo "    chat 端（claude.ai）现在需要重连一次：设置 → 连接器 → 棠予酿 → 断开 → 连接。"
echo "    CodeAndPurrs 走静态 token，不受影响。"
