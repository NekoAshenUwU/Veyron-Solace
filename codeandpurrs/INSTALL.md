# CodeAndPurrs 写入批准链路 — 安装

让予予在 CodeAndPurrs 里能**读**棠予酿（自动），也能**写**（先问过棠棠）。

背景与整条链路的诊断记录见 [`../docs/tang-yu-niang-runbook.md`](../docs/tang-yu-niang-runbook.md)。

## 它怎么工作

```
予予要写日记
  → CLI 发现 memory_grow 不在 --allowedTools 里
  → 调用 --permission-prompt-tool 指定的 mcp__approval__approval_ask
  → approval.mjs 挂起这次调用，通过 SSE 把内容推给浏览器
  → 棠棠在弹窗看到日记正文，点「允许写入」
  → 浏览器 POST 回决定 → 工具返回 {"allow":true} → CLI 继续，日记落库
```

5 分钟没人点就自动拒绝并告诉予予，不会再出现「予予永远在等」。

## 两个文件

| 文件 | 放到 |
|---|---|
| `server/approval.mjs` | `/var/www/codeandpurrs/server/approval.mjs` |
| `src/ApprovalGate.tsx` | `/var/www/codeandpurrs/src/ApprovalGate.tsx` |

## 三处改动

### 1. `server/proxy.mjs` 顶部，加 import

```js
import {
  handleApprovalMcp,
  handlePermissionStream,
  handlePermissionDecide,
} from './approval.mjs';
```

### 2. `server/proxy.mjs` 请求处理函数的**最开头**（在 `const isChat = ...` 那一堆之前），加三行拦截

```js
// —— 批准链路，直接 return，不走下面的路由 ——
if (req.url?.startsWith('/mcp/approval'))          return handleApprovalMcp(req, res, readJSON);
if (req.url?.startsWith('/api/permission/stream')) return handlePermissionStream(req, res);
if (req.url?.startsWith('/api/permission/decide')) return handlePermissionDecide(req, res, readJSON);
```

### 3. `server/proxy.mjs` 的 `if (mem) { ... }` 分支，整段换成

```js
if (mem) {
  const httpServer = { type: 'http', url: mem.url };
  if (mem.token) httpServer.headers = { Authorization: `Bearer ${mem.token}` };

  // 除了棠予酿，再挂一个本地的批准 MCP —— 它就跑在这个进程自己身上
  const mcpConfig = JSON.stringify({
    mcpServers: {
      [mem.name]: httpServer,
      approval: { type: 'http', url: `http://127.0.0.1:${PORT}/mcp/approval` },
    },
  });

  // 读取类自动放行；写入类故意不列，好让它落到批准工具那里
  const READ_TOOLS = [
    'memory_pulse', 'memory_breathe', 'memory_tidal',
    'love_note_draw', 'timeline_query',
  ];

  args.push(
    '--mcp-config', mcpConfig,
    '--allowedTools', READ_TOOLS.map((x) => `mcp__${mem.name}__${x}`).join(','),
    '--permission-prompt-tool', 'mcp__approval__approval_ask',
  );
}
```

> `PORT` 用 proxy.mjs 里已有的端口变量；没有的话直接写 `8787`。

### 4. `src/App.tsx`，把弹窗挂上

```tsx
import ApprovalGate from './ApprovalGate';

// 放在最外层 JSX 里，位置随意
<ApprovalGate />
```

## 装完

```bash
cd /var/www/codeandpurrs
npm run build      # 前端要重新打包
pm2 restart codeandpurrs
pm2 logs codeandpurrs --lines 30
```

## 先验后端，再验整条

前端还没打包也能单独验后端 —— 这条会**挂住不返回**，因为它在等你点：

```bash
curl -sS -X POST http://127.0.0.1:8787/mcp/approval \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"approval_ask",
       "arguments":{"tool_name":"memory_grow","input":{"date":"2026-08-18",
       "content":"这是一次测试","weather":"🌙"}}}}'
```

挂住 = 后端通了。这时候：

- 网页开着 → 弹窗应该已经跳出来了，点一下，curl 立刻返回 `{"allow":true,...}`
- 不想开网页 → 另开一个终端手动放行（`<id>` 从 `pm2 logs` 里的 `[approval] 等待批准 <id>` 抄）：

```bash
curl -sS -X POST http://127.0.0.1:8787/api/permission/decide \
  -H 'Content-Type: application/json' -d '{"id":"<id>","allow":true}'
```

- 什么都不做 → 5 分钟后自动返回 `{"allow":false,...}`，这是超时兜底，符合预期

## 排查

**弹窗不出现**：确认 nginx 没有缓冲 SSE。approval.mjs 已经发了 `X-Accel-Buffering: no`，如果还不行，在 nginx 的 `/api/permission/` location 里加 `proxy_buffering off;`。

**参数对不上**（弹窗里字段是空的）：`pm2 logs` 里找 `[approval] tools/call 原始参数:`，把那行贴出来，按实际参数名调 `approval.mjs` 里 `a.tool_name || a.toolName || ...` 那几行。

**予予说没权限但没弹窗**：检查 `--permission-prompt-tool` 的值是不是正好 `mcp__approval__approval_ask` —— 服务器名 `approval` 必须和 `mcpConfig` 里的 key 一字不差。
