import React, { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Zap } from "lucide-react";
import { getHistory, postChat } from "../../../lib/ghostApi";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ── Keyframes injected once ──────────────────────────────────────────────────
const STYLE = `
@keyframes orbPulse {
  0%,100% { transform:scale(1); opacity:.85; }
  50% { transform:scale(1.07); opacity:1; }
}
@keyframes orbSpin {
  to { transform:rotate(360deg); }
}
@keyframes msgIn {
  from { opacity:0; transform:translateY(14px) scale(.98); }
  to   { opacity:1; transform:translateY(0)   scale(1); }
}
@keyframes thinkDot {
  0%,80%,100% { transform:scale(.5); opacity:.25; }
  40%         { transform:scale(1);  opacity:1; }
}
@keyframes scanPan {
  0%   { transform:translateY(0); }
  100% { transform:translateY(4px); }
}
@keyframes borderSpin {
  to { --holo-angle:360deg; }
}
@keyframes liveBlip {
  0%,100% { opacity:1; box-shadow:0 0 6px #10b981; }
  50%     { opacity:.4; box-shadow:0 0 2px #10b981; }
}
@property --holo-angle {
  syntax:'<angle>'; initial-value:0deg; inherits:false;
}
.holo-ghost-bubble {
  position:relative;
  background:linear-gradient(135deg,rgba(12,12,18,.97),rgba(18,18,28,.97));
  border-radius:3px 14px 14px 14px;
  backdrop-filter:blur(12px);
}
.holo-ghost-bubble::before {
  content:'';
  position:absolute;
  inset:-1px;
  border-radius:inherit;
  padding:1px;
  background:conic-gradient(from var(--holo-angle),
    rgba(245,158,11,.08) 0%,
    rgba(139,92,246,.25) 25%,
    rgba(6,182,212,.2)   50%,
    rgba(245,158,11,.15) 75%,
    rgba(245,158,11,.08) 100%);
  -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
  -webkit-mask-composite:xor; mask-composite:exclude;
  animation:borderSpin 6s linear infinite;
}
.holo-user-bubble {
  background:linear-gradient(135deg,rgba(245,158,11,.07),rgba(245,158,11,.03));
  border:1px solid rgba(245,158,11,.18);
  border-radius:14px 14px 3px 14px;
  backdrop-filter:blur(8px);
}
.msg-new { animation:msgIn .38s cubic-bezier(.23,1,.32,1) both; }
.think-dot { animation:thinkDot 1.4s ease-in-out infinite; }
.think-dot:nth-child(2) { animation-delay:.18s; }
.think-dot:nth-child(3) { animation-delay:.36s; }
.scanlines {
  background:repeating-linear-gradient(
    0deg,transparent,transparent 3px,
    rgba(0,0,0,.07) 3px,rgba(0,0,0,.07) 4px);
  pointer-events:none;
}
`;

// ── Neural canvas ─────────────────────────────────────────────────────────────
function NeuralCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let W = (canvas.width  = canvas.offsetWidth);
    let H = (canvas.height = canvas.offsetHeight);
    const N = 38;
    const nodes = Array.from({ length: N }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35,
      r: Math.random() * 1.4 + .5,
    }));
    let raf;
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
          const d = Math.hypot(dx, dy);
          if (d < 110) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(245,158,11,${.13 * (1 - d / 110)})`;
            ctx.lineWidth = .5;
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }
      nodes.forEach(n => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(245,158,11,.45)";
        ctx.fill();
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    const onResize = () => {
      W = canvas.width  = canvas.offsetWidth;
      H = canvas.height = canvas.offsetHeight;
    };
    window.addEventListener("resize", onResize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); };
  }, []);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full" style={{ opacity: .55, pointerEvents: "none" }} />;
}

// ── Orb avatar ────────────────────────────────────────────────────────────────
function GhostOrb({ thinking = false, score = 75, size = 52 }) {
  const c = score >= 85 ? "#10b981" : score >= 70 ? "#f59e0b" : "#8b5cf6";
  const s = size;
  return (
    <div className="relative flex-shrink-0 flex items-center justify-center" style={{ width: s, height: s }}>
      <div className="absolute inset-0 rounded-full" style={{ border: `1px solid ${c}33`, animation: "orbPulse 3s ease-in-out infinite", boxShadow: `0 0 18px ${c}22` }} />
      <div className="absolute rounded-full" style={{ inset: 7, border: `1px solid ${c}55`, animation: thinking ? "orbSpin 1.1s linear infinite" : "orbPulse 2.4s ease-in-out infinite .5s" }} />
      <div className="absolute rounded-full" style={{ inset: 14, border: `1px solid ${c}33`, animation: thinking ? "orbSpin 1.8s linear infinite reverse" : "none" }} />
      <div className="relative rounded-full flex items-center justify-center" style={{ width: s - 26, height: s - 26, background: `radial-gradient(circle at 38% 38%, ${c}33, #0a0a1099)`, boxShadow: `0 0 10px ${c}55`, border: `1px solid ${c}77` }}>
        <span style={{ fontFamily: "JetBrains Mono", fontSize: s > 44 ? 13 : 10, color: c, fontWeight: 700 }}>Ω</span>
      </div>
    </div>
  );
}

// ── KAIROS score ring ─────────────────────────────────────────────────────────
function KairosRing({ score, attempts }) {
  const r = 16, circ = 2 * Math.PI * r;
  const offset = circ * (1 - (score || 0) / 100);
  const c = score >= 85 ? "#10b981" : score >= 70 ? "#f59e0b" : "#8b5cf6";
  return (
    <div className="flex items-center gap-1">
      <svg width={38} height={38} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={19} cy={19} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={2} />
        <circle cx={19} cy={19} r={r} fill="none" stroke={c} strokeWidth={2}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 3px ${c})`, transition: "stroke-dashoffset .9s cubic-bezier(.23,1,.32,1)" }} />
      </svg>
      <div className="flex flex-col leading-none">
        <span style={{ fontFamily: "JetBrains Mono", fontSize: 14, color: c, fontWeight: 700 }}>{Math.round(score || 0)}</span>
        {attempts > 1 && <span style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#52525b" }}>{attempts}×</span>}
      </div>
    </div>
  );
}

// ── Voice waveform ────────────────────────────────────────────────────────────
function VoiceWave({ active }) {
  if (!active) return null;
  return (
    <div className="flex items-center gap-0.5 px-1">
      {[3, 7, 12, 9, 14, 8, 5, 11, 6].map((h, i) => (
        <div key={i} style={{ width: 2.5, height: h, borderRadius: 2, background: "#f59e0b",
          animation: `thinkDot .7s ease-in-out ${i * .07}s infinite` }} />
      ))}
    </div>
  );
}

// ── Thinking indicator ────────────────────────────────────────────────────────
function Thinking() {
  return (
    <div className="flex items-center gap-3 pl-1">
      <GhostOrb thinking score={75} size={44} />
      <div>
        <div className="flex items-center gap-1 mb-1">
          {[0, 1, 2].map(i => <div key={i} className="think-dot rounded-full" style={{ width: 5, height: 5, background: "#f59e0b" }} />)}
        </div>
        <span style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#3f3f46", letterSpacing: ".2em" }}>KAIROS PROCESSING</span>
      </div>
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function Bubble({ msg, isNew }) {
  const ghost = msg.role === "ghost";
  const hasScore = msg.kairos_score != null;
  return (
    <div className={`flex ${ghost ? "items-start" : "items-end justify-end"} gap-3 ${isNew ? "msg-new" : ""}`}>
      {ghost && <GhostOrb score={msg.kairos_score || 75} size={44} />}

      <div style={{ maxWidth: "78%" }}>
        {/* label row */}
        <div className={`flex items-center gap-2 mb-1.5 ${ghost ? "" : "justify-end"}`}>
          <span style={{ fontFamily: "JetBrains Mono", fontSize: 8, letterSpacing: ".25em", textTransform: "uppercase", color: ghost ? "#f59e0b" : "#52525b" }}>
            {ghost ? "GH05T3" : "Robert"}
          </span>
          {hasScore && <KairosRing score={msg.kairos_score} attempts={msg.kairos_attempts} />}
          {msg.latency_ms && <span style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#3f3f46" }}>{msg.latency_ms}ms</span>}
        </div>

        {/* bubble */}
        <div className={ghost ? "holo-ghost-bubble" : "holo-user-bubble"} style={{ padding: "11px 15px", position: "relative", overflow: "hidden" }}>
          {/* scanline texture on ghost */}
          {ghost && <div className="scanlines absolute inset-0 rounded-[inherit]" />}

          <div className={`relative text-[14px] leading-relaxed text-zinc-200 prose prose-invert prose-sm max-w-none
            prose-code:bg-black/50 prose-code:px-1 prose-code:rounded prose-code:text-amber-300 prose-code:text-[12px]
            prose-pre:bg-black/60 prose-pre:border prose-pre:border-amber-500/10 prose-pre:rounded
            prose-a:text-amber-400 prose-strong:text-zinc-100
            prose-h1:text-amber-400 prose-h2:text-amber-300 prose-h3:text-zinc-200
            prose-ul:list-disc prose-li:my-0.5`}>
            {ghost
              ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              : <span className="whitespace-pre-wrap not-prose text-zinc-300">{msg.content}</span>}
          </div>
        </div>
      </div>

      {!ghost && (
        <div className="flex-shrink-0 rounded-full flex items-center justify-center"
          style={{ width: 30, height: 30, background: "rgba(245,158,11,.07)", border: "1px solid rgba(245,158,11,.2)", fontFamily: "JetBrains Mono", fontSize: 10, color: "#f59e0b" }}>
          R
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
const SESSION_KEY = "gh05t3.session";
const SR = typeof window !== "undefined" ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;

export const ChatInterface = ({ onEngine }) => {
  const [sessionId, setSessionId]   = useState(() => localStorage.getItem(SESSION_KEY) || "");
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState("");
  const [sending, setSending]       = useState(false);
  const [listening, setListening]   = useState(false);
  const [newIds, setNewIds]         = useState(new Set());
  const [lastScore, setLastScore]   = useState(null);
  const scrollRef   = useRef(null);
  const textareaRef = useRef(null);
  const srRef       = useRef(null);

  useEffect(() => {
    if (sessionId) getHistory(sessionId).then(d => setMessages(d.messages || [])).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    const el = textareaRef.current; if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, [input]);

  const toggleVoice = () => {
    if (!SR) return;
    if (listening) { srRef.current?.stop(); return; }
    const r = new SR();
    srRef.current = r; r.continuous = false; r.interimResults = true; r.lang = "en-US";
    r.onresult = e => { let t = ""; for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript; setInput(t); };
    r.onend = () => setListening(false); r.onerror = () => setListening(false);
    r.start(); setListening(true);
  };

  const send = async () => {
    const text = input.trim(); if (!text || sending) return;
    setSending(true); setInput("");
    const tmpId = `tmp-${Date.now()}`;
    const opt = { id: tmpId, role: "user", content: text, timestamp: new Date().toISOString() };
    setMessages(m => [...m, opt]);
    setNewIds(s => new Set([...s, tmpId]));
    try {
      const res = await postChat(text, sessionId || null);
      if (!sessionId) { setSessionId(res.session_id); localStorage.setItem(SESSION_KEY, res.session_id); }
      onEngine?.(res.ghost_message.engine);
      if (res.ghost_message.kairos_score) setLastScore(res.ghost_message.kairos_score);
      const gid = res.ghost_message.id;
      setMessages(m => [...m.filter(x => x.id !== tmpId), res.user_message, res.ghost_message]);
      setNewIds(s => new Set([...s, gid]));
      setTimeout(() => setNewIds(s => { const n = new Set(s); n.delete(gid); return n; }), 800);
    } catch (e) {
      const eid = `err-${Date.now()}`;
      setMessages(m => [...m, { id: eid, role: "ghost", content: `[GATEWAY ERROR] ${e?.response?.data?.detail || e.message}`, timestamp: new Date().toISOString() }]);
    } finally { setSending(false); }
  };

  const onKey = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  const reset = () => { localStorage.removeItem(SESSION_KEY); setSessionId(""); setMessages([]); setLastScore(null); };

  return (
    <>
      <style>{STYLE}</style>
      <div data-testid="chat-interface" className="flex flex-col relative overflow-hidden"
        style={{ height: 640, background: "linear-gradient(160deg,#04040a,#080812,#04040a)", border: "1px solid rgba(245,158,11,.08)" }}>

        <NeuralCanvas />

        {/* scanline overlay */}
        <div className="scanlines absolute inset-0" style={{ zIndex: 0 }} />

        {/* top gradient fade */}
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 80, background: "linear-gradient(180deg,rgba(4,4,10,.9),transparent)", zIndex: 1, pointerEvents: "none" }} />

        {/* ── Header ── */}
        <header className="relative flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ zIndex: 2, borderBottom: "1px solid rgba(245,158,11,.07)" }}>
          <div className="flex items-center gap-3">
            <GhostOrb thinking={sending} score={lastScore || 75} size={52} />
            <div>
              <div style={{ fontFamily: "JetBrains Mono", fontSize: 10, letterSpacing: ".3em", color: "#f59e0b", textTransform: "uppercase", fontWeight: 600 }}>
                GH05T3 · Ω-Prime
              </div>
              <div style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#3f3f46", marginTop: 3, letterSpacing: ".15em" }}>
                {sessionId ? `${sessionId.slice(0, 8)} · ${messages.length} exchanges` : "awaiting transmission"}
                {lastScore && <span style={{ color: "#10b981", marginLeft: 10 }}>⊛ {Math.round(lastScore)}</span>}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", animation: "liveBlip 2s ease-in-out infinite" }} />
              <span style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#3f3f46", letterSpacing: ".2em" }}>KAIROS LIVE</span>
            </div>
            <button onClick={reset}
              style={{ fontFamily: "JetBrains Mono", fontSize: 8, letterSpacing: ".2em", textTransform: "uppercase", color: "#52525b", border: "1px solid rgba(255,255,255,0.05)", padding: "4px 10px", background: "transparent", cursor: "pointer" }}>
              ↺ new
            </button>
          </div>
        </header>

        {/* ── Messages ── */}
        <div ref={scrollRef} className="ghost-scroll relative flex-1 overflow-y-auto px-4 py-5 space-y-6" style={{ zIndex: 2 }}>
          {messages.length === 0 && !sending && (
            <div className="flex flex-col items-center justify-center h-full gap-5 text-center select-none">
              <GhostOrb score={85} size={72} />
              <div>
                <div style={{ fontFamily: "JetBrains Mono", fontSize: 10, color: "#f59e0b", letterSpacing: ".35em", textTransform: "uppercase" }}>
                  System Online
                </div>
                <div style={{ fontFamily: "JetBrains Mono", fontSize: 8, color: "#3f3f46", marginTop: 5, letterSpacing: ".18em" }}>
                  KAIROS · SAGE · DPO · GGUF · Ω-PRIME
                </div>
              </div>
              <div style={{ fontFamily: "JetBrains Mono", fontSize: 9, color: "#3f3f46", maxWidth: 300, lineHeight: 1.8 }}>
                Every message runs a 3-attempt generate → critique → retry loop scored by an independent judge. Best draft wins. All scored. All logged. All learned from.
              </div>
              <div className="flex items-center gap-6 mt-2">
                {[["SAGE", "#f59e0b"], ["DPO", "#8b5cf6"], ["GGUF", "#06b6d4"]].map(([label, color]) => (
                  <div key={label} className="flex flex-col items-center gap-1">
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }} />
                    <span style={{ fontFamily: "JetBrains Mono", fontSize: 7, color: "#52525b", letterSpacing: ".2em" }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {messages.map(m => <Bubble key={m.id} msg={m} isNew={newIds.has(m.id)} />)}
          {sending && <Thinking />}
        </div>

        {/* ── Input bar ── */}
        <div className="relative flex-shrink-0" style={{ zIndex: 2, borderTop: "1px solid rgba(245,158,11,.07)", background: "rgba(4,4,10,.96)", backdropFilter: "blur(12px)" }}>
          {/* amber glow line */}
          <div style={{ height: 1, background: "linear-gradient(90deg,transparent,rgba(245,158,11,.25),transparent)" }} />

          <div className="flex items-end gap-2 px-4 py-3">
            <span style={{ fontFamily: "JetBrains Mono", fontSize: 12, color: "#f59e0b", paddingBottom: 5, flexShrink: 0, opacity: sending ? .4 : 1 }}>Ω</span>

            <VoiceWave active={listening} />

            {!listening && (
              <textarea ref={textareaRef} data-testid="chat-input"
                value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
                rows={1} placeholder={sending ? "" : "transmit to Ω…"} disabled={sending}
                style={{ flex: 1, background: "transparent", resize: "none", outline: "none", fontFamily: "IBM Plex Sans", fontSize: 14, color: "#e4e4e7", caretColor: "#f59e0b", minHeight: 28, maxHeight: 140, overflow: "hidden", paddingTop: 4, paddingBottom: 4 }}
              />
            )}

            {SR && (
              <button data-testid="voice-btn" onClick={toggleVoice} disabled={sending}
                style={{ fontFamily: "JetBrains Mono", fontSize: 9, display: "flex", alignItems: "center", gap: 4, border: `1px solid ${listening ? "rgba(239,68,68,.4)" : "rgba(255,255,255,.07)"}`, color: listening ? "#ef4444" : "#52525b", padding: "6px 8px", background: "transparent", cursor: "pointer", animation: listening ? "orbPulse 1s ease-in-out infinite" : "none" }}>
                {listening ? <MicOff size={11} /> : <Mic size={11} />}
              </button>
            )}

            <button data-testid="send-btn" onClick={send} disabled={sending || !input.trim()}
              style={{ fontFamily: "JetBrains Mono", fontSize: 9, letterSpacing: ".2em", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 5, border: `1px solid ${(sending || !input.trim()) ? "rgba(255,255,255,.05)" : "rgba(245,158,11,.35)"}`, color: (sending || !input.trim()) ? "#3f3f46" : "#f59e0b", padding: "6px 14px", background: (sending || !input.trim()) ? "transparent" : "rgba(245,158,11,.05)", cursor: (sending || !input.trim()) ? "default" : "pointer", boxShadow: (sending || !input.trim()) ? "none" : "0 0 14px rgba(245,158,11,.12)", transition: "all .2s ease" }}>
              <Zap size={11} />
              {sending ? "…" : "send"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
};
