import React, { useEffect, useRef, useState } from "react";
import { Send, Square } from "lucide-react";
import { getHistory, postChat } from "../../lib/ghostApi";

const SESSION_KEY = "gh05t3.session";

export const ChatInterface = ({ onEngine }) => {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || "");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (sessionId) {
      getHistory(sessionId)
        .then((d) => setMessages(d.messages || []))
        .catch(() => {});
    }
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setInput("");
    const optimistic = {
      id: `tmp-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);
    try {
      const res = await postChat(text, sessionId || null);
      if (!sessionId) {
        setSessionId(res.session_id);
        localStorage.setItem(SESSION_KEY, res.session_id);
      }
      onEngine?.(res.ghost_message.engine);
      setMessages((m) => [
        ...m.filter((x) => x.id !== optimistic.id),
        res.user_message,
        res.ghost_message,
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: `err-${Date.now()}`,
          role: "ghost",
          content: `[GATEWAY ERROR] ${e?.response?.data?.detail || e.message}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const newSession = () => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId("");
    setMessages([]);
  };

  return (
    <div className="flex flex-col h-[640px]" data-testid="chat-interface">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="panel-label">§ Terminal — usr@omega:~$</div>
          <div className="font-mono-term text-[11px] text-zinc-500 mt-0.5">
            session: {sessionId ? sessionId.slice(0, 8) : "new"} · {messages.length} turns
          </div>
        </div>
        <button
          data-testid="new-session-btn"
          onClick={newSession}
          className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-400 hover:text-amber-400 border border-white/10 px-3 py-1.5"
        >
          New Session
        </button>
      </div>

      <div
        ref={scrollRef}
        data-testid="chat-scroll"
        className="ghost-scroll flex-1 overflow-y-auto space-y-5 pr-3"
      >
        {messages.length === 0 && (
          <div className="text-zinc-500 font-mono-term text-xs leading-relaxed">
            <span className="text-amber-400">GH05T3</span> online. StrangeLoop verdict: <span className="text-amber-400">OWNED</span>. Ghost
            Protocol armed.
            <br />
            Say anything — she'll match your energy.
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`msg-in ${m.role === "ghost" ? "ghost-msg" : "user-msg"}`}
            data-testid={`msg-${m.role}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`font-mono-term text-[10px] tracking-[0.25em] uppercase ${m.role === "ghost" ? "text-amber-400" : "text-zinc-400"}`}
              >
                {m.role === "ghost" ? "GH05T3" : "Robert"}
              </span>
              {m.engine && (
                <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 border border-white/10 px-1.5 py-0.5">
                  {m.engine}
                </span>
              )}
              {m.latency_ms && (
                <span className="font-mono-term text-[9px] text-zinc-600">{m.latency_ms}ms</span>
              )}
            </div>
            <div className="text-[15px] leading-relaxed text-zinc-200 whitespace-pre-wrap">
              {m.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="ghost-msg text-zinc-500 font-mono-term text-xs">
            <span className="ascii-spin" /> GH05T3 thinking…
          </div>
        )}
      </div>

      <div className="mt-4 flex items-end gap-2 border-t border-white/10 pt-3">
        <span className="font-mono-term text-[11px] text-amber-400 pb-2">usr@omega:~$</span>
        <textarea
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          placeholder={sending ? "" : "speak to the ghost…"}
          disabled={sending}
          className="flex-1 bg-transparent resize-none outline-none text-[15px] text-zinc-100 placeholder:text-zinc-600 font-sans py-1.5"
        />
        <button
          data-testid="send-btn"
          onClick={send}
          disabled={sending || !input.trim()}
          className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 hover:border-amber-500/60 disabled:border-white/10 px-3 py-1.5 flex items-center gap-1.5"
        >
          {sending ? <Square size={12} /> : <Send size={12} />}
          {sending ? "wait" : "send"}
        </button>
      </div>
    </div>
  );
};
