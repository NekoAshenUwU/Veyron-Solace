#!/usr/bin/env bash
#
# 棠予酿 / MCP 双路健康检查
#
# 为什么是"双路"：mcp.service 上并存两套认证，任何一套断了另一套都察觉不到。
#   - OAuth 路      → Claude.ai 连接器（chat 端的予予走这条）
#   - 静态 token 路 → TANG_WEB_TOKEN（CodeAndPurrs 前端 / tang-web 走这条）
#
# 为什么是"主动探针"：不能拿"最近一条日记有多旧"当健康信号——那反映的是
# 有没有人在用，不是系统好不好。所以这个脚本自己去敲端点。
#
# 用法：
#   ./tang-health-check.sh            # 跑一次，全部正常时退出码 0
#   MIN_TOOLS=25 ./tang-health-check.sh
#   ALERT_CMD='curl -s -X POST https://...' ./tang-health-check.sh
#
set -uo pipefail

ENV_FILE="${ENV_FILE:-/root/mcp-oauth.env}"
MCP_HOST="${MCP_HOST:-https://mcp.nekopurrs.uk}"
MCP_URL="$MCP_HOST/mcp"
WELL_KNOWN="$MCP_HOST/.well-known/oauth-protected-resource/mcp"
DB="${DB:-/root/data/tang_yu_niang.db}"
SERVICE="${SERVICE:-mcp}"
MIN_TOOLS="${MIN_TOOLS:-20}"
SINCE="${SINCE:-30 min ago}"
ALERT_CMD="${ALERT_CMD:-}"

fail=0
say()     { echo "[$(date -Is)] $*"; }
problem() { fail=1; say "FAIL $*"; }

# --- 读 env 拿 TANG_WEB_TOKEN（值不会被打印）-------------------------------
if [[ -r "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
else
    problem "env 文件不可读: $ENV_FILE"
fi

# --- 1. 服务还活着吗 --------------------------------------------------------
if systemctl is-active --quiet "$SERVICE"; then
    say "OK   systemd 服务运行中: $SERVICE"
else
    problem "systemd 服务未运行: $SERVICE"
fi

# --- 2. 静态 token 路（CodeAndPurrs 前端走这条）-----------------------------
# MCP Streamable HTTP 必须先 initialize 拿到 Mcp-Session-Id，后续请求都要带上。
# 直接发 tools/list 会被服务端拒：Bad Request: Missing session ID。
mcp_list_tools() {
    local auth="$1" hdr sid init

    hdr=$(mktemp); init=$(mktemp)
    trap 'rm -f "$hdr" "$init"' RETURN

    curl -sS --max-time 20 -D "$hdr" -o "$init" -X POST "$MCP_URL" \
        -H "$auth" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
             "protocolVersion":"2024-11-05","capabilities":{},
             "clientInfo":{"name":"tang-health-check","version":"1.0"}}}' 2>/dev/null

    sid=$(grep -i '^mcp-session-id:' "$hdr" | tr -d '\r' | cut -d' ' -f2-)
    if [[ -z "$sid" ]]; then
        echo "INIT_FAILED $(head -c 300 "$init")"
        return 1
    fi

    # 握手第二步：告诉服务端初始化完成
    curl -sS --max-time 20 -o /dev/null -X POST "$MCP_URL" \
        -H "$auth" -H "Mcp-Session-Id: $sid" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' 2>/dev/null

    curl -sS --max-time 20 -X POST "$MCP_URL" \
        -H "$auth" -H "Mcp-Session-Id: $sid" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' 2>/dev/null
}

if [[ -n "${TANG_WEB_TOKEN:-}" ]]; then
    body=$(mcp_list_tools "Authorization: Bearer $TANG_WEB_TOKEN")
    if [[ "$body" == INIT_FAILED* ]]; then
        problem "静态 token 路握手失败: ${body#INIT_FAILED }"
    else
        n=$(grep -o '"name":"[^"]*"' <<<"$body" | sort -u | wc -l)
        if (( n >= MIN_TOOLS )); then
            say "OK   静态 token 路: $n 个工具"
        else
            problem "静态 token 路只列出 $n 个工具（期望 >= $MIN_TOOLS）"
            say "     响应开头: $(head -c 300 <<<"$body")"
        fi
    fi
else
    problem "TANG_WEB_TOKEN 未设置——前端那条路无法检查"
fi

# --- 3. OAuth 路（Claude.ai / chat 端走这条）--------------------------------
# 注意能力边界：这里只能验服务端的 OAuth 机制是否健康，验不了 Claude.ai
# 手里那个 token 有没有过期。客户端 token 死掉要靠第 4 步的日志扫描发现。
wk=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$WELL_KNOWN" 2>/dev/null)
if [[ "$wk" == "200" ]]; then
    say "OK   OAuth discovery 端点正常 (200)"
else
    problem "OAuth discovery 返回 $wk（期望 200）: $WELL_KNOWN"
fi

chal=$(curl -sS -i --max-time 20 -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' 2>&1)
if grep -qi 'www-authenticate: *Bearer' <<<"$chal" && grep -qi 'resource_metadata=' <<<"$chal"; then
    say "OK   OAuth 401 挑战格式正确（客户端能据此自动重新授权）"
else
    problem "OAuth 401 挑战缺失或格式不对——客户端将无法自动重连"
fi

# --- 4. 最近有没有客户端被拒（2026-08-18 那次就是这个信号）------------------
authfail=$(journalctl -u "$SERVICE" --since "$SINCE" --no-pager 2>/dev/null \
           | grep -c 'invalid_token' || true)
if (( authfail > 0 )); then
    say "WARN 最近「$SINCE」内出现 $authfail 次 invalid_token"
    say "     → 某个客户端的授权可能已失效。chat 端的修法：claude.ai 断开重连棠予酿"
fi

# --- 5. 数据库可读 + WAL 仍然生效 -------------------------------------------
if [[ -r "$DB" ]]; then
    jm=$(python3 -c "import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute('PRAGMA journal_mode').fetchone()[0])" "$DB" 2>&1)
    cnt=$(python3 -c "import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute('select count(*) from memories').fetchone()[0])" "$DB" 2>&1)
    if [[ "$jm" == "wal" ]]; then
        say "OK   数据库: journal_mode=wal, memories=$cnt 条"
    else
        problem "$DB 的 journal_mode=$jm（期望 wal）——并发写会锁库"
    fi
else
    problem "数据库不可读: $DB"
fi

# --- 收尾 -------------------------------------------------------------------
if (( fail )); then
    say "===> 有问题，见上面的 FAIL 行"
    [[ -n "$ALERT_CMD" ]] && eval "$ALERT_CMD"
    exit 1
fi
say "===> 全部正常"
exit 0
