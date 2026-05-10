import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

const QUICK_QUESTIONS = [
  'Is it safe to sign?',
  'What are the critical risks?',
  'Do I have financial risk?',
  'Explain the most dangerous clause',
  'What should I negotiate?',
  'Is this one-sided?',
];

// ── Markdown renderer (bold, lists, verdicts) ────────────────────────────────
function RenderMarkdown({ text }) {
  if (!text) return null;
  const lines = text.split('\n');
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-2" />;

        // Verdict badges
        if (line.startsWith('✅') || line.startsWith('⚠️') || line.startsWith('❌')) {
          const color = line.startsWith('✅') ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
            : line.startsWith('❌') ? 'text-red-700 bg-red-50 border-red-200'
            : 'text-amber-700 bg-amber-50 border-amber-200';
          return (
            <div key={i} className={`rounded-lg border px-3 py-2 text-sm font-semibold ${color}`}>
              {renderInline(line)}
            </div>
          );
        }

        // Section headers (**VERDICT**, **EVIDENCE**, etc.)
        if (/^\*\*[A-Z ]+\*\*/.test(line)) {
          return (
            <p key={i} className="mt-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              {line.replace(/\*\*/g, '')}
            </p>
          );
        }

        // Bullet list
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2 text-sm">
              <span className="mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
              <span>{renderInline(line.slice(2))}</span>
            </div>
          );
        }

        return <p key={i} className="text-sm leading-6">{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>
      : part
  );
}

RenderMarkdown.propTypes = { text: PropTypes.string };

// ── Message bubble ────────────────────────────────────────────────────────────
function Message({ role, content, streaming }) {
  const isUser = role === 'user';
  return (
    <div className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
        isUser ? 'bg-teal-600 text-white' : 'bg-slate-200 text-slate-600'
      }`}>
        {isUser ? 'You' : 'AI'}
      </div>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
        isUser ? 'bg-teal-600 text-white rounded-tr-sm' : 'bg-slate-100 text-slate-800 rounded-tl-sm'
      }`}>
        {isUser
          ? content
          : <RenderMarkdown text={content} />
        }
        {streaming && (
          <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-slate-500 align-middle" />
        )}
      </div>
    </div>
  );
}

Message.propTypes = {
  role: PropTypes.oneOf(['user', 'assistant']).isRequired,
  content: PropTypes.string.isRequired,
  streaming: PropTypes.bool,
};

// ── Typing dots ───────────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex gap-2.5">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-600">AI</div>
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3">
        {[0, 150, 300].map((delay) => (
          <span key={delay} className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: `${delay}ms` }} />
        ))}
      </div>
    </div>
  );
}

// ── Main ChatPanel ────────────────────────────────────────────────────────────
export default function ChatPanel({ documentId }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I've analysed this document with **HyDE retrieval + Llama 3.3 70B**. Ask me anything about it." },
  ]);
  const [followups, setFollowups]   = useState([]);
  const [input, setInput]           = useState('');
  const [loading, setLoading]       = useState(false);
  const [streaming, setStreaming]   = useState(false);
  const bottomRef                   = useRef(null);
  const historyRef                  = useRef([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send(question) {
    const text = (question || input).trim();
    if (!text || loading) return;
    setInput('');
    setFollowups([]);

    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const history = historyRef.current.map(m => ({ role: m.role, content: m.content }));

    try {
      const token = window.localStorage.getItem('clauseguard_access_token');

      // ── Try streaming endpoint ──────────────────────────────────────────
      const resp = await fetch(`${API_BASE}/api/v1/chat/${documentId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: text, history }),
      });

      if (resp.ok && resp.body) {
        setStreaming(true);
        setLoading(false);
        // Add empty assistant message to stream into
        setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let accumulated = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;
            try {
              const evt = JSON.parse(raw);
              if (evt.chunk) {
                accumulated += evt.chunk;
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: 'assistant', content: accumulated };
                  return updated;
                });
              }
              if (evt.done) {
                if (evt.followups?.length) setFollowups(evt.followups);
              }
            } catch (_) {}
          }
        }

        setStreaming(false);
        historyRef.current = [
          ...historyRef.current,
          userMsg,
          { role: 'assistant', content: accumulated },
        ];
        return;
      }

      // ── Fallback: non-streaming ─────────────────────────────────────────
      const json = await resp.json().catch(() => ({}));
      const answer = json?.answer || json?.detail || 'Something went wrong.';
      setMessages(prev => [...prev, { role: 'assistant', content: answer }]);
      historyRef.current = [...historyRef.current, userMsg, { role: 'assistant', content: answer }];

    } catch (err) {
      const msg = err?.message || 'Network error.';
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  const showQuick = messages.length <= 1 && !loading;

  return (
    <div className="glass-card flex flex-col" style={{ height: '560px' }}>

      {/* Header */}
      <div className="border-b border-slate-200 px-5 py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="section-label">AI Document Assistant</p>
            <h3 className="mt-0.5 text-sm font-semibold text-slate-900">
              HyDE + Multi-query · Llama 3.3 70B
            </h3>
          </div>
          <span className="flex h-2 w-2 rounded-full bg-emerald-400" title="Groq connected" />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.map((m, i) => (
          <Message key={i} role={m.role} content={m.content}
            streaming={streaming && i === messages.length - 1} />
        ))}
        {loading && !streaming && <TypingDots />}
        <div ref={bottomRef} />
      </div>

      {/* Quick questions */}
      {showQuick && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {QUICK_QUESTIONS.map(q => (
            <button key={q} type="button" onClick={() => send(q)} disabled={loading}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-teal-400 hover:bg-teal-50 hover:text-teal-700 disabled:opacity-40">
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Follow-up suggestions */}
      {followups.length > 0 && !loading && (
        <div className="border-t border-slate-100 px-4 py-2">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Ask next</p>
          <div className="flex flex-wrap gap-2">
            {followups.map(q => (
              <button key={q} type="button" onClick={() => send(q)}
                className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-700 transition hover:bg-teal-100">
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
            placeholder="Ask anything about this document…" rows={1} disabled={loading}
            className="flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-teal-400 focus:bg-white disabled:opacity-50" />
          <button type="button" onClick={() => send()} disabled={loading || !input.trim()}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition hover:bg-teal-700 disabled:opacity-40"
            aria-label="Send">
            ↑
          </button>
        </div>
        <p className="mt-1 text-center text-xs text-slate-400">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}

ChatPanel.propTypes = { documentId: PropTypes.string.isRequired };
