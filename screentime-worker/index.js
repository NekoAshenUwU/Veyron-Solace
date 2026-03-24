/**
 * Veyron Screentime Worker
 * 手机采集 → Cloudflare Worker → Claude 读取
 *
 * 接口：
 *   GET /api/screentime/toggle/:app   — 手机端触发（打开/关闭 app 时调用）
 *   GET /api/screentime/status        — Claude 端查询当前使用情况
 *   GET /api/screentime/clear         — 清空所有数据（可选）
 */

const FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSc9p5a4mfl2aIGeLtBU2AiIzoqWMEMgULIgB0KBt-Q4BBg8QQ/formResponse';
const ENTRY_APP    = 'entry.225706119';
const ENTRY_ACTION = 'entry.1078108620';
const TTL_SECONDS  = 86400; // 只保留 24 小时数据
const CUTOFF_MS    = TTL_SECONDS * 1000;

const JSON_HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
};

/** 静默提交到 Google Form（不影响主流程） */
async function logToForm(app, action) {
  try {
    const body = new URLSearchParams({ [ENTRY_APP]: app, [ENTRY_ACTION]: action });
    await fetch(FORM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
  } catch (_) {}
}

/** toggle 逻辑：上次是 open 就改成 close，反之亦然 */
async function handleToggle(app, env) {
  const key = `app:${app}`;
  const now = Date.now();

  let data = await env.SCREENTIME.get(key, { type: 'json' });
  if (!data) data = { state: 'closed', openTime: null, sessions: [] };

  // 清理 24 小时前的历史
  const cutoff = now - CUTOFF_MS;
  data.sessions = (data.sessions || []).filter(s => s.start > cutoff);

  let action;
  if (data.state !== 'open') {
    // 打开
    data.state = 'open';
    data.openTime = now;
    action = 'open';
  } else {
    // 关闭，计算使用时长
    const duration = Math.round((now - data.openTime) / 1000); // 秒
    data.sessions.push({ start: data.openTime, end: now, duration });
    data.state = 'closed';
    data.openTime = null;
    const mins = Math.floor(duration / 60);
    const secs = duration % 60;
    action = mins > 0 ? `close|${mins}m${secs}s` : `close|${secs}s`;
  }

  await env.SCREENTIME.put(key, JSON.stringify(data), { expirationTtl: TTL_SECONDS });
  await logToForm(app, action);

  return { app, action, state: data.state };
}

/** 返回今日使用汇总，供 Claude 查询 */
async function handleStatus(env) {
  const list = await env.SCREENTIME.list({ prefix: 'app:' });
  const now = Date.now();
  const cutoff = now - CUTOFF_MS;

  const currentlyOpen = [];
  const today = [];

  for (const { name } of list.keys) {
    const appName = name.slice(4); // 去掉 'app:' 前缀
    const data = await env.SCREENTIME.get(name, { type: 'json' });
    if (!data) continue;

    const sessions = (data.sessions || []).filter(s => s.start > cutoff);
    const closedSeconds = sessions.reduce((sum, s) => sum + s.duration, 0);
    const openSeconds = data.state === 'open'
      ? Math.round((now - data.openTime) / 1000)
      : 0;
    const totalMinutes = Math.round((closedSeconds + openSeconds) / 60);

    if (data.state === 'open') currentlyOpen.push(appName);

    if (sessions.length > 0 || data.state === 'open') {
      today.push({
        app: appName,
        sessions: sessions.length + (data.state === 'open' ? 1 : 0),
        totalMinutes,
      });
    }
  }

  // 按使用时间降序
  today.sort((a, b) => b.totalMinutes - a.totalMinutes);

  return {
    currentlyOpen,
    today,
    asOf: new Date().toISOString(),
  };
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);

    // GET /api/screentime/toggle/:app
    if (pathname.startsWith('/api/screentime/toggle/')) {
      const app = decodeURIComponent(pathname.slice('/api/screentime/toggle/'.length));
      if (!app) {
        return new Response(JSON.stringify({ error: 'app name required' }), { status: 400, headers: JSON_HEADERS });
      }
      const result = await handleToggle(app, env);
      return new Response(JSON.stringify(result), { headers: JSON_HEADERS });
    }

    // GET /api/screentime/status
    if (pathname === '/api/screentime/status') {
      const result = await handleStatus(env);
      return new Response(JSON.stringify(result, null, 2), { headers: JSON_HEADERS });
    }

    // GET /api/screentime/clear  (清空数据用)
    if (pathname === '/api/screentime/clear') {
      const list = await env.SCREENTIME.list({ prefix: 'app:' });
      await Promise.all(list.keys.map(k => env.SCREENTIME.delete(k.name)));
      return new Response(JSON.stringify({ cleared: list.keys.length }), { headers: JSON_HEADERS });
    }

    return new Response(JSON.stringify({ error: 'not found' }), { status: 404, headers: JSON_HEADERS });
  },
};
