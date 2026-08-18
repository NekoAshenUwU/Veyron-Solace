#!/usr/bin/env bash
# CodeAndPurrs 写入批准链路 —— 一键安装
# 每处改动都先断言匹配唯一，匹配不上就整个中止，不会改坏。
set -euo pipefail

APP="${APP:-/var/www/codeandpurrs}"
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)

[[ -f "$APP/server/proxy.mjs" ]] || { echo "找不到 $APP/server/proxy.mjs"; exit 1; }

echo "== 备份"
cp "$APP/server/proxy.mjs" "$APP/server/proxy.mjs.bak-$STAMP"
[[ -f "$APP/src/main.tsx" ]] && cp "$APP/src/main.tsx" "$APP/src/main.tsx.bak-$STAMP"

echo "== 放文件"
cp "$SRC/server/approval.mjs"   "$APP/server/approval.mjs"
cp "$SRC/src/ApprovalGate.tsx"  "$APP/src/ApprovalGate.tsx"

echo "== 改 proxy.mjs"
APP="$APP" python3 - <<'PY'
import os, pathlib, sys

app = pathlib.Path(os.environ['APP'])
p = app / 'server' / 'proxy.mjs'
t = p.read_text()

def once(needle, label):
    n = t.count(needle)
    if n != 1:
        sys.exit(f"× {label}：匹配到 {n} 处（需要正好 1 处），已中止，文件未改动")

# --- 1) import ---
imp = "import {\n  handleApprovalMcp,\n  handlePermissionStream,\n  handlePermissionDecide,\n} from './approval.mjs';\n"
if 'approval.mjs' not in t:
    lines = t.split('\n')
    at = 1 if lines and lines[0].startswith('#!') else 0
    lines.insert(at, imp)
    t = '\n'.join(lines)
    print("  ✓ import 已加")
else:
    print("  · import 已存在，跳过")

# --- 2) 路由拦截 ---
anchor = "const isChat = req.url?.startsWith('/api/chat')"
if '/api/permission/stream' not in t:
    once(anchor, "路由锚点 isChat")
    routes = (
        "// —— 批准链路，直接 return，不走下面的路由 ——\n"
        "  if (req.url?.startsWith('/mcp/approval'))          return handleApprovalMcp(req, res, readJSON);\n"
        "  if (req.url?.startsWith('/api/permission/stream')) return handlePermissionStream(req, res);\n"
        "  if (req.url?.startsWith('/api/permission/decide')) return handlePermissionDecide(req, res, readJSON);\n\n"
        "  " + anchor
    )
    t = t.replace(anchor, routes, 1)
    print("  ✓ 三条路由已加")
else:
    print("  · 路由已存在，跳过")

# --- 3) mcpConfig 里加上 approval server ---
old_cfg = "JSON.stringify({ mcpServers: { [mem.name]: httpServer } })"
if 'approval:' not in t:
    once(old_cfg, "mcpConfig")
    new_cfg = ("JSON.stringify({ mcpServers: { [mem.name]: httpServer, "
               "approval: { type: 'http', url: `http://127.0.0.1:${process.env.PORT || 8787}/mcp/approval` } } })")
    t = t.replace(old_cfg, new_cfg, 1)
    print("  ✓ approval MCP 已挂进 mcp-config")
else:
    print("  · approval MCP 已存在，跳过")

# --- 4) --permission-prompt-tool ---
old_args = ("'--allowedTools', ['memory_pulse','memory_breathe','memory_tidal',"
            "'love_note_draw','timeline_query'].map(x => `mcp__${mem.name}__${x}`).join(',')")
if '--permission-prompt-tool' not in t:
    once(old_args, "allowedTools 那一行（是否已跑过读取修复？）")
    t = t.replace(old_args, old_args + ", '--permission-prompt-tool', 'mcp__approval__approval_ask'", 1)
    print("  ✓ --permission-prompt-tool 已加")
else:
    print("  · --permission-prompt-tool 已存在，跳过")

p.write_text(t)

# --- 5) 弹窗挂载：单独一个 React root，不动 App 的树 ---
m = app / 'src' / 'main.tsx'
if m.exists():
    mt = m.read_text()
    if 'ApprovalGate' not in mt:
        mt += (
            "\n\n// —— 予予写入前的批准弹窗（独立挂载，不影响现有 App 树）——\n"
            "import ApprovalGate from './ApprovalGate';\n"
            "import { createRoot as __approvalRoot } from 'react-dom/client';\n"
            "const __gateEl = document.createElement('div');\n"
            "document.body.appendChild(__gateEl);\n"
            "__approvalRoot(__gateEl).render(<ApprovalGate />);\n"
        )
        m.write_text(mt)
        print("  ✓ 弹窗已挂到 main.tsx")
    else:
        print("  · 弹窗已挂载，跳过")
else:
    print("  ! 没找到 src/main.tsx，需要手动加一个 <ApprovalGate />")
PY

echo "== 语法检查"
node --check "$APP/server/approval.mjs"
node --check "$APP/server/proxy.mjs"

echo
echo "改完了。备份在 server/proxy.mjs.bak-$STAMP"
echo "接下来跑："
echo "  cd $APP && npm run build && pm2 restart codeandpurrs && pm2 logs codeandpurrs --lines 30"
