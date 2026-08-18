// 写入类工具的批准链路。
//
// 予予要写日记时，Claude Code CLI 发现 memory_grow 不在 --allowedTools 里，
// 就会去调 --permission-prompt-tool 指定的那个 MCP 工具。这个文件就是那个
// 工具的实现：它把请求挂起，通过 SSE 推给浏览器，等棠棠点了「允许」再放行。
//
// 三个入口，都挂在 proxy.mjs 已有的 http server 上：
//   POST /mcp/approval           —— 给 CLI 用的极简 MCP 端点
//   GET  /api/permission/stream  —— 给浏览器用的 SSE，推送待批准的请求
//   POST /api/permission/decide  —— 浏览器回传 { id, allow }
//
// 设计上刻意不跟聊天会话绑定：这是你们俩自己的站，同一时刻只有棠棠在用，
// 全局广播就够了，也就不必去动 proxy.mjs 里聊天那套 SSE 的管线。

import { randomUUID } from 'node:crypto';

// 超时兜底：没人点就自动拒绝，绝不再出现「予予永远在等」那种死锁
const TIMEOUT_MS = 5 * 60 * 1000;

const pending = new Map();  // id -> { info, resolve, timer }
const clients = new Set();  // 浏览器的 SSE res

function sseSend(res, event, data) {
  try { res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`); } catch {}
}

function broadcast(event, data) {
  for (const res of clients) sseSend(res, event, data);
}

function settle(id, allow, reason) {
  const p = pending.get(id);
  if (!p) return;
  clearTimeout(p.timer);
  pending.delete(id);
  broadcast('resolved', { id, allow });
  p.resolve({ allow, reason });
}

function ask(info) {
  const id = randomUUID();
  return new Promise((resolve) => {
    const timer = setTimeout(
      () => settle(id, false, '超过 5 分钟没有回应，这次自动拒绝了。你可以让我再试一次。'),
      TIMEOUT_MS,
    );
    pending.set(id, { info, resolve, timer });
    broadcast('ask', { id, ...info });
    console.log(`[approval] 等待批准 ${id} → ${info.tool}`);
  });
}

// ---------- 浏览器侧：SSE ----------
export function handlePermissionStream(req, res) {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',   // 让 nginx 不要缓冲
  });
  res.write(': connected\n\n');
  clients.add(res);

  // 页面刷新过也不会漏：把还挂着的请求补发一遍
  for (const [id, p] of pending) sseSend(res, 'ask', { id, ...p.info });

  const ka = setInterval(() => { try { res.write(': ka\n\n'); } catch {} }, 25000);
  req.on('close', () => { clearInterval(ka); clients.delete(res); });
}

// ---------- 浏览器侧：回传决定 ----------
export async function handlePermissionDecide(req, res, readJSON) {
  const body = await readJSON(req).catch(() => ({}));
  const { id, allow, reason } = body || {};
  if (!pending.has(id)) {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: false, error: '这个请求不存在或已经过期了' }));
    return;
  }
  settle(id, !!allow, reason || (allow ? '棠棠允许了' : '棠棠这次不让写'));
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: true }));
}

// ---------- CLI 侧：极简 MCP over HTTP ----------
const TOOL_NAME = 'approval_ask';

export async function handleApprovalMcp(req, res, readJSON) {
  if (req.method !== 'POST') { res.writeHead(405); res.end(); return; }

  const msg = await readJSON(req).catch(() => null);
  if (!msg || !msg.method) { res.writeHead(400); res.end(); return; }

  // 通知类消息没有 id，不需要回 body
  if (String(msg.method).startsWith('notifications/')) {
    res.writeHead(202); res.end(); return;
  }

  const reply = (result) => {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Mcp-Session-Id': 'codeandpurrs-approval',
    });
    res.end(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result }));
  };

  switch (msg.method) {
    case 'initialize':
      return reply({
        protocolVersion: msg.params?.protocolVersion || '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'approval', version: '1.0.0' },
      });

    case 'tools/list':
      return reply({
        tools: [{
          name: TOOL_NAME,
          description: '把一次工具调用交给棠棠批准。Claude Code 在需要授权时会自动调用它，不要主动调。',
          inputSchema: {
            type: 'object',
            properties: {
              tool_name: { type: 'string', description: '要调用的工具名' },
              input:     { type: 'object', description: '调用参数' },
            },
          },
        }],
      });

    case 'tools/call': {
      const params = msg.params || {};
      // 参数名以实际收到的为准，先打进日志，方便对不上时排查
      console.log('[approval] tools/call 原始参数:', JSON.stringify(params).slice(0, 800));
      const a = params.arguments || {};
      const decision = await ask({
        tool:  a.tool_name || a.toolName || a.tool || '未知工具',
        input: a.input ?? a.tool_input ?? a,
        at:    new Date().toISOString(),
      });
      console.log(`[approval] 结果 → ${decision.allow ? '允许' : '拒绝'}（${decision.reason}）`);
      // Claude Code 实际校验的是 PermissionResult：
      //   允许 → { behavior: 'allow', updatedInput: <原样回传参数> }
      //   拒绝 → { behavior: 'deny',  message: '...' }
      // 注意：文档里写的 {"allow": true} 是错的，运行时会被 zod 拒掉
      //（2026-08-18 实测，报 invalid_union · path: behavior）。
      const payload = decision.allow
        ? { behavior: 'allow', updatedInput: a.input ?? a.tool_input ?? {} }
        : { behavior: 'deny', message: decision.reason };
      return reply({ content: [{ type: 'text', text: JSON.stringify(payload) }] });
    }

    default:
      return reply({});
  }
}
