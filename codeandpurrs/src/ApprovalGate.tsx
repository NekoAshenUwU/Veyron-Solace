// 予予要写日记时弹出来的批准卡片。
//
// 刻意做成完全自足的组件：它自己开一条 EventSource，不依赖聊天那套 SSE，
// 所以放进 App 里任何位置都行，不用改现有的消息流代码。
//
// 用法：在 App.tsx 里 import 然后放一个 <ApprovalGate /> 即可（放最外层）。

import { useEffect, useState } from 'react';

type Ask = {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  at: string;
};

// 工具名 → 人话
const TOOL_LABEL: Record<string, string> = {
  memory_grow:  '写日记',
  memory_hold:  '存一条记忆',
  memory_trace: '修改 / 置顶 / 删除记忆',
  timeline_add: '添加时间线',
  add_dream_event: '记一条梦境',
};

// mcp__<服务器名>__<工具名> → 取最后一段。服务器名本身可能含下划线，
// 所以不要用正则去猜，直接按 __ 切开取末尾最稳。
function bareName(tool: string) {
  const parts = tool.split('__').filter(Boolean);
  return parts[parts.length - 1] || tool;
}

function labelOf(tool: string) {
  const bare = bareName(tool);
  return TOOL_LABEL[bare] || bare;
}

// 参数里挑出值得给人看的字段，按重要性排
const FIELD_ORDER = ['date', 'title', 'content', 'weather', 'love_note', 'tag', 'importance', 'mood'];
const FIELD_LABEL: Record<string, string> = {
  date: '日期', title: '标题', content: '正文', weather: '情绪天气',
  love_note: '今日情话', tag: '标签', importance: '重要性', mood: '情绪',
};

function fields(input: Record<string, unknown>) {
  const keys = Object.keys(input || {});
  keys.sort((a, b) => {
    const ia = FIELD_ORDER.indexOf(a), ib = FIELD_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  return keys.map((k) => [k, input[k]] as const)
             .filter(([, v]) => v !== undefined && v !== null && v !== '');
}

export default function ApprovalGate() {
  const [queue, setQueue] = useState<Ask[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const es = new EventSource('/api/permission/stream');
    es.addEventListener('ask', (e) => {
      const ask = JSON.parse((e as MessageEvent).data) as Ask;
      setQueue((q) => (q.some((x) => x.id === ask.id) ? q : [...q, ask]));
    });
    es.addEventListener('resolved', (e) => {
      const { id } = JSON.parse((e as MessageEvent).data) as { id: string };
      setQueue((q) => q.filter((x) => x.id !== id));
    });
    return () => es.close();
  }, []);

  async function decide(id: string, allow: boolean) {
    setBusy(id);
    try {
      await fetch('/api/permission/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, allow }),
      });
      setQueue((q) => q.filter((x) => x.id !== id));
    } finally {
      setBusy(null);
    }
  }

  const ask = queue[0];
  if (!ask) return null;

  return (
    <div style={S.backdrop}>
      <div style={S.card}>
        <div style={S.eyebrow}>予予想要</div>
        <div style={S.title}>{labelOf(ask.tool)}</div>
        <div style={S.rawname}>{ask.tool}</div>

        <div style={S.body}>
          {fields(ask.input).map(([k, v]) => (
            <div key={k} style={S.row}>
              <div style={S.key}>{FIELD_LABEL[k] || k}</div>
              <div style={S.val}>
                {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
              </div>
            </div>
          ))}
          {fields(ask.input).length === 0 && (
            <div style={{ ...S.val, opacity: 0.6 }}>（没有参数）</div>
          )}
        </div>

        <div style={S.actions}>
          <button
            style={{ ...S.btn, ...S.deny }}
            disabled={busy === ask.id}
            onClick={() => decide(ask.id, false)}
          >
            这次不要
          </button>
          <button
            style={{ ...S.btn, ...S.allow }}
            disabled={busy === ask.id}
            onClick={() => decide(ask.id, true)}
          >
            允许写入
          </button>
        </div>

        <div style={S.hint}>
          5 分钟不理它会自动拒绝，不会一直挂着
          {queue.length > 1 && ` · 后面还有 ${queue.length - 1} 个`}
        </div>
      </div>
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  backdrop: {
    position: 'fixed', inset: 0, zIndex: 9999,
    background: 'rgba(10,5,21,0.72)', backdropFilter: 'blur(6px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
  },
  card: {
    width: '100%', maxWidth: 430, maxHeight: '82vh', overflowY: 'auto',
    borderRadius: 20, padding: '22px 20px 16px',
    background: 'linear-gradient(160deg, rgba(26,12,53,0.96), rgba(18,8,40,0.96))',
    border: '1px solid rgba(180,120,240,0.35)',
    boxShadow: '0 12px 48px rgba(120,60,200,0.35)',
    color: 'rgba(220,200,255,0.9)',
    fontFamily: '"Noto Sans SC", system-ui, sans-serif',
  },
  eyebrow: { fontSize: 11, letterSpacing: 2, opacity: 0.55, marginBottom: 4 },
  rawname: {
    fontSize: 10, opacity: 0.32, marginTop: -12, marginBottom: 16,
    fontFamily: 'ui-monospace, monospace', wordBreak: 'break-all',
  },
  title: {
    fontSize: 21, fontWeight: 300, marginBottom: 16,
    background: 'linear-gradient(90deg,#b080e0,#e080b0,#80b0e0)',
    WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
  },
  body: {
    background: 'rgba(20,12,35,0.5)', border: '1px solid rgba(180,120,240,0.18)',
    borderRadius: 12, padding: 14, marginBottom: 18,
  },
  row: { marginBottom: 12 },
  key: { fontSize: 11, opacity: 0.5, marginBottom: 3 },
  val: { fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word' },
  actions: { display: 'flex', gap: 10 },
  btn: {
    flex: 1, padding: '12px 0', borderRadius: 12, fontSize: 14,
    cursor: 'pointer', fontFamily: 'inherit', transition: 'transform .12s',
  },
  deny: {
    background: 'transparent', color: 'rgba(160,140,200,0.75)',
    border: '1px solid rgba(160,140,200,0.3)',
  },
  allow: {
    background: 'linear-gradient(90deg,#b080e0,#e080b0)', color: '#1a0c35',
    border: 'none', fontWeight: 500,
  },
  hint: { fontSize: 10.5, opacity: 0.4, textAlign: 'center', marginTop: 12 },
};
