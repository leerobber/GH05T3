import { useState, useEffect, useRef, useCallback, useMemo } from "react";

// ══════════════════════════════════════════════════════════════════
// GH05T3 v3 — UNIFIED COMMAND DASHBOARD
// Steampunk industrial aesthetic | Live swarm conversations
// ══════════════════════════════════════════════════════════════════

const API  = "http://127.0.0.1:8002";
const WS   = "ws://127.0.0.1:8002/ws";
const SECRET = "";  // set GH05T3_SECRET or leave blank

// ── THEME ────────────────────────────────────────────────────────
const T = {
  bg:         "#0e0b08",
  bgPanel:    "#1a120a",
  bgDeep:     "#0a0704",
  brass:      "#d4941c",
  brassDim:   "#7a5010",
  copper:     "#c47a35",
  ember:      "#ff7820",
  emberGlow:  "rgba(255,120,32,0.15)",
  steam:      "#e8d8b8",
  steamDim:   "#a09070",
  ok:         "#8bc668",
  err:        "#d44040",
  warn:       "#e0a040",
  purple:     "#9966ff",
  cyan:       "#40c8d4",
  border:     "#2a1a0a",
  oracle:     "#40c8d4",
  forge:      "#ff9933",
  codex:      "#9966ff",
  sentinel:   "#d44040",
  nexus:      "#8bc668",
  github:     "#cccccc",
  claude:     "#cc785c",
  omega:      "#d4941c",
};

const AGENT_COLORS = {
  ORACLE:   T.oracle,  FORGE:   T.forge,  CODEX:    T.codex,
  SENTINEL: T.sentinel, NEXUS:  T.nexus,  GITHUB:   T.github,
  CLAUDE:   T.claude,  OMEGA:   T.omega,  KAIROS:   T.purple,
  SAGE:     T.cyan,    USER:    T.steam,  SYSTEM:   T.brassDim,
  GH05T3:   T.ember,   GATEWAY: T.brass,
};

const MSG_ICONS = {
  chat:      "💬", task:    "📋", result:  "✅",
  thought:   "💭", critique:"🔍", verdict: "⚖️",
  kairos:    "⚡", github:  "🐙", claude:  "🧠",
  system:    "⚙️", heartbeat:"💓", error:  "🔴",
};

const fontHead = `'Cinzel', 'Trajan Pro', 'IM Fell English SC', serif`;
const fontMono = `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`;
const fontBody = `'IM Fell English', Georgia, serif`;

// ── HELPERS ───────────────────────────────────────────────────────
const headers = { "Content-Type": "application/json", "X-GH05T3-Secret": SECRET };
const get  = (path) => fetch(API + path, { headers }).then(r => r.json()).catch(e => ({ error: e.message }));
const post = (path, body) => fetch(API + path, { method: "POST", headers, body: JSON.stringify(body) })
  .then(r => r.json()).catch(e => ({ error: e.message }));

function timeAgo(ts) {
  const s = (Date.now() / 1000) - ts;
  if (s < 60)  return `${~~s}s ago`;
  if (s < 3600) return `${~~(s/60)}m ago`;
  return new Date(ts * 1000).toLocaleTimeString();
}

function agentColor(id) {
  const key = (id || "").toUpperCase().split("-")[0];
  return AGENT_COLORS[key] || T.steamDim;
}

// ── COMPONENTS ────────────────────────────────────────────────────

function GlowDot({ color, pulse }) {
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: color,
      boxShadow: pulse ? `0 0 6px ${color}, 0 0 12px ${color}44` : "none",
      animation: pulse ? "pulse 2s infinite" : "none",
    }} />
  );
}

function Panel({ title, children, style = {}, accent }) {
  const c = accent || T.brass;
  return (
    <div style={{
      background: `linear-gradient(180deg, ${T.bgPanel} 0%, ${T.bgDeep} 100%)`,
      border: `1px solid ${T.border}`,
      borderTop: `2px solid ${c}`,
      borderRadius: 2,
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      ...style,
    }}>
      <div style={{
        padding: "7px 14px", background: "rgba(0,0,0,0.5)",
        borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", gap: 8,
        fontFamily: fontHead, fontSize: 10, letterSpacing: "0.2em",
        color: c, textTransform: "uppercase", flexShrink: 0,
      }}>
        <span style={{ opacity: 0.6 }}>⚙</span>
        <span>{title}</span>
        <span style={{ marginLeft: "auto", width: 6, height: 6,
          borderRadius: "50%", background: c, boxShadow: `0 0 4px ${c}` }} />
      </div>
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {children}
      </div>
    </div>
  );
}

// ── AGENT BADGE ───────────────────────────────────────────────────

function AgentBadge({ id, online, taskCount, msgCount }) {
  const color = agentColor(id);
  return (
    <div style={{
      padding: "8px 12px",
      background: online ? `${color}0a` : "rgba(0,0,0,0.3)",
      border: `1px solid ${online ? color + "40" : T.border}`,
      borderRadius: 2, transition: "all 0.3s",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <GlowDot color={color} pulse={online} />
        <span style={{ fontFamily: fontMono, fontSize: 12, color, fontWeight: 700 }}>{id}</span>
        {!online && <span style={{ fontSize: 9, color: T.steamDim }}>(offline)</span>}
      </div>
      {online && (
        <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
          <span style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>
            📋 {taskCount || 0}
          </span>
          <span style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>
            💬 {msgCount || 0}
          </span>
        </div>
      )}
    </div>
  );
}

// ── CONVERSATION MESSAGE ──────────────────────────────────────────

function ConvMessage({ msg, compact }) {
  const [expanded, setExpanded] = useState(false);
  const color  = agentColor(msg.src);
  const icon   = MSG_ICONS[msg.msg_type] || "•";
  const isLong = msg.content && msg.content.length > 200;

  return (
    <div style={{
      padding: compact ? "5px 12px" : "8px 14px",
      borderBottom: `1px solid ${T.border}`,
      background: msg.msg_type === "error"
        ? "rgba(212,64,64,0.06)"
        : msg.msg_type === "thought"
        ? "rgba(153,102,255,0.04)"
        : "transparent",
      animation: "fadeIn 0.3s ease",
    }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        {/* Icon + Agent */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 120, flexShrink: 0 }}>
          <span style={{ fontSize: 12 }}>{icon}</span>
          <span style={{
            fontFamily: fontMono, fontSize: 11, fontWeight: 700,
            color, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {msg.src}
          </span>
        </div>

        {/* Arrow + dst */}
        {msg.dst && msg.dst !== "*" && (
          <span style={{ color: T.steamDim, fontSize: 10, fontFamily: fontMono, flexShrink: 0 }}>
            → {msg.dst}
          </span>
        )}

        {/* Channel */}
        <span style={{
          fontSize: 9, color: T.brassDim, fontFamily: fontMono,
          background: "rgba(212,148,28,0.1)", padding: "1px 6px", borderRadius: 2,
          whiteSpace: "nowrap", flexShrink: 0,
        }}>
          {msg.channel}
        </span>

        {/* Timestamp */}
        <span style={{ marginLeft: "auto", fontSize: 9, color: T.steamDim,
                        fontFamily: fontMono, flexShrink: 0 }}>
          {msg.ts_human || timeAgo(msg.timestamp)}
        </span>
      </div>

      {/* Content */}
      {msg.content && (
        <div style={{
          marginTop: 4, marginLeft: 20,
          fontFamily: fontMono, fontSize: 11, color: T.steam,
          lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {isLong && !expanded
            ? msg.content.slice(0, 200) + "…"
            : msg.content}
          {isLong && (
            <button onClick={() => setExpanded(!expanded)} style={{
              background: "none", border: "none",
              color: T.brass, cursor: "pointer", fontSize: 10,
              fontFamily: fontMono, marginLeft: 8,
            }}>
              [{expanded ? "collapse" : "expand"}]
            </button>
          )}
        </div>
      )}

      {/* Metadata badges */}
      {msg.metadata && Object.keys(msg.metadata).length > 0 && !compact && (
        <div style={{ display: "flex", gap: 6, marginTop: 4, marginLeft: 20, flexWrap: "wrap" }}>
          {msg.metadata.sage_score !== undefined && (
            <span style={{ fontSize: 9, fontFamily: fontMono, padding: "1px 6px",
              background: "rgba(139,198,104,0.1)", color: T.ok, borderRadius: 2 }}>
              SAGE {(msg.metadata.sage_score * 100).toFixed(0)}%
            </span>
          )}
          {msg.metadata.is_elite && (
            <span style={{ fontSize: 9, fontFamily: fontMono, padding: "1px 6px",
              background: "rgba(255,120,32,0.15)", color: T.ember, borderRadius: 2 }}>
              ⚡ ELITE
            </span>
          )}
          {msg.metadata.cycle_id && (
            <span style={{ fontSize: 9, fontFamily: fontMono, padding: "1px 6px",
              background: "rgba(153,102,255,0.1)", color: T.purple, borderRadius: 2 }}>
              Ω#{msg.metadata.cycle_id}
            </span>
          )}
          {msg.metadata.commit_url && (
            <a href={msg.metadata.commit_url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 9, fontFamily: fontMono, padding: "1px 6px",
                background: "rgba(204,204,204,0.1)", color: T.github, borderRadius: 2,
                textDecoration: "none" }}>
              🐙 View commit
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ── TERMINAL ──────────────────────────────────────────────────────

function Terminal({ onEmit }) {
  const [input, setInput]   = useState("");
  const [target, setTarget] = useState("OMEGA");
  const [mode, setMode]     = useState("chat");   // chat | task | train | github | claude
  const [busy, setBusy]     = useState(false);
  const [lastResult, setLastResult] = useState(null);

  async function run() {
    if (!input.trim() || busy) return;
    setBusy(true);
    const cmd = input.trim();
    setInput("");

    try {
      let result;
      if (mode === "chat") {
        result = await post("/chat", { message: cmd });
        setLastResult(result);
        onEmit?.(`Chat: ${result.response?.slice(0, 100)}`);
      } else if (mode === "task") {
        result = await post("/swarm/delegate", { task: cmd, agent: target === "AUTO" ? null : target });
        setLastResult(result);
      } else if (mode === "train") {
        result = await post("/claude/train", { domain: cmd, count: 5 });
        setLastResult({ count: result.count, domain: result.domain });
      } else if (mode === "github") {
        result = await post("/github/commit", undefined);
        setLastResult(result);
      } else if (mode === "claude") {
        result = await post("/claude/upgrade", { topic: cmd } );
        setLastResult({ proposal: result.proposal?.slice(0, 200) });
      }
    } catch (e) {
      setLastResult({ error: e.message });
    }
    setBusy(false);
  }

  return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, height: "100%" }}>
      {/* Mode selector */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {["chat", "task", "train", "github", "claude"].map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            background: mode === m ? `${T.brass}22` : "none",
            border: `1px solid ${mode === m ? T.brass : T.border}`,
            color: mode === m ? T.brass : T.steamDim,
            fontFamily: fontMono, fontSize: 10, padding: "3px 10px",
            borderRadius: 2, cursor: "pointer", textTransform: "uppercase",
          }}>{m}</button>
        ))}
        {mode === "task" && (
          <select value={target} onChange={e => setTarget(e.target.value)}
            style={{ background: T.bgDeep, color: T.cyan, border: `1px solid ${T.border}`,
              fontFamily: fontMono, fontSize: 10, padding: "3px 8px" }}>
            {["AUTO","ORACLE","FORGE","CODEX","SENTINEL","NEXUS","CLAUDE","GITHUB"].map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        )}
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 6 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && run()}
          placeholder={
            mode === "chat"   ? "Message GH05T3..." :
            mode === "task"   ? "Delegate task..." :
            mode === "train"  ? "Domain (e.g. agent_systems)..." :
            mode === "github" ? "Press Enter to commit & push..." :
            "Upgrade topic..."
          }
          style={{
            flex: 1, background: "#0a0704", color: T.steam,
            border: `1px solid ${T.border}`, borderRadius: 2,
            padding: "8px 12px", fontFamily: fontMono, fontSize: 12,
            outline: "none",
          }}
        />
        <button onClick={run} disabled={busy} style={{
          background: busy ? "none" : `${T.ember}22`,
          border: `1px solid ${busy ? T.border : T.ember}`,
          color: busy ? T.steamDim : T.ember,
          fontFamily: fontMono, fontSize: 11, padding: "8px 16px",
          borderRadius: 2, cursor: busy ? "not-allowed" : "pointer",
        }}>
          {busy ? "…" : "FIRE"}
        </button>
      </div>

      {/* Result */}
      {lastResult && (
        <div style={{
          flex: 1, background: T.bgDeep, border: `1px solid ${T.border}`,
          padding: 10, borderRadius: 2, overflow: "auto",
          fontFamily: fontMono, fontSize: 11, color: T.steam,
          whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {lastResult.error
            ? <span style={{ color: T.err }}>❌ {lastResult.error}</span>
            : JSON.stringify(lastResult, null, 2)}
        </div>
      )}
    </div>
  );
}

// ── CONVERSATION PANEL ────────────────────────────────────────────

function ConversationPanel({ messages, filter, setFilter }) {
  const bottomRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [compact, setCompact]       = useState(false);
  const [search, setSearch]         = useState("");

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, autoScroll]);

  const filtered = useMemo(() => {
    let msgs = messages;
    if (filter.channel) msgs = msgs.filter(m => m.channel === filter.channel);
    if (filter.src)     msgs = msgs.filter(m => m.src === filter.src);
    if (filter.type)    msgs = msgs.filter(m => m.msg_type === filter.type);
    if (search)         msgs = msgs.filter(m =>
      m.content?.toLowerCase().includes(search.toLowerCase()) ||
      m.src?.toLowerCase().includes(search.toLowerCase())
    );
    return msgs;
  }, [messages, filter, search]);

  const channels = useMemo(() =>
    ["", ...new Set(messages.map(m => m.channel))].filter(Boolean),
    [messages]);

  const agents = useMemo(() =>
    ["", ...new Set(messages.map(m => m.src))].filter(Boolean),
    [messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Filters */}
      <div style={{
        padding: "6px 12px", background: "rgba(0,0,0,0.4)",
        borderBottom: `1px solid ${T.border}`,
        display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center",
      }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="search…"
          style={{ background: T.bgDeep, color: T.steam, border: `1px solid ${T.border}`,
            borderRadius: 2, padding: "2px 8px", fontFamily: fontMono, fontSize: 10,
            width: 120 }}
        />
        <select value={filter.channel || ""} onChange={e => setFilter(f => ({...f, channel: e.target.value || null}))}
          style={{ background: T.bgDeep, color: T.steamDim, border: `1px solid ${T.border}`,
            fontFamily: fontMono, fontSize: 10 }}>
          <option value="">All channels</option>
          {channels.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filter.src || ""} onChange={e => setFilter(f => ({...f, src: e.target.value || null}))}
          style={{ background: T.bgDeep, color: T.steamDim, border: `1px solid ${T.border}`,
            fontFamily: fontMono, fontSize: 10 }}>
          <option value="">All agents</option>
          {agents.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={filter.type || ""} onChange={e => setFilter(f => ({...f, type: e.target.value || null}))}
          style={{ background: T.bgDeep, color: T.steamDim, border: `1px solid ${T.border}`,
            fontFamily: fontMono, fontSize: 10 }}>
          <option value="">All types</option>
          {Object.keys(MSG_ICONS).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={() => setCompact(!compact)} style={{
          background: "none", border: `1px solid ${T.border}`,
          color: T.steamDim, fontSize: 10, fontFamily: fontMono,
          padding: "2px 8px", cursor: "pointer",
        }}>{compact ? "expand" : "compact"}</button>
        <button onClick={() => setFilter({})} style={{
          background: "none", border: `1px solid ${T.border}`,
          color: T.brassDim, fontSize: 10, fontFamily: fontMono,
          padding: "2px 8px", cursor: "pointer",
        }}>clear</button>
        <button onClick={() => setAutoScroll(!autoScroll)} style={{
          background: autoScroll ? `${T.ok}22` : "none",
          border: `1px solid ${autoScroll ? T.ok : T.border}`,
          color: autoScroll ? T.ok : T.steamDim,
          fontSize: 10, fontFamily: fontMono, padding: "2px 8px", cursor: "pointer",
        }}>auto-scroll</button>
        <span style={{ marginLeft: "auto", fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>
          {filtered.length}/{messages.length} msgs
        </span>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.map((m, i) => (
          <ConvMessage key={m.id || i} msg={m} compact={compact} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── MAIN DASHBOARD ────────────────────────────────────────────────

export default function GH05T3Dashboard() {
  const [wsState, setWsState]     = useState("disconnected");
  const [messages, setMessages]   = useState([]);
  const [agents, setAgents]       = useState({});
  const [systemStats, setStats]   = useState(null);
  const [githubInfo, setGithubInfo] = useState(null);
  const [tab, setTab]             = useState("conversations");
  const [filter, setFilter]       = useState({});
  const wsRef = useRef(null);

  // ── WebSocket ──────────────────────────────────────────────────
  useEffect(() => {
    let alive = true, backoff = 1000;
    function connect() {
      if (!alive) return;
      const ws = new WebSocket(WS);
      wsRef.current = ws;
      setWsState("connecting");
      ws.onopen = () => { setWsState("connected"); backoff = 1000; };
      ws.onclose = () => { setWsState("disconnected"); if (alive) setTimeout(connect, backoff); backoff = Math.min(backoff*2, 15000); };
      ws.onerror = () => setWsState("error");
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "hello") {
            setAgents(prev => {
              const next = {...prev};
              (data.node?.agents || []).forEach(id => { if (!next[id]) next[id] = { active: true }; });
              return next;
            });
          } else if (data.type === "ping") {
            // ignore
          } else {
            // Normalize bus message
            const msg = {
              id:        data.id || Math.random().toString(36).slice(2),
              channel:   data.channel  || "#broadcast",
              msg_type:  data.msg_type || "chat",
              src:       data.src      || "system",
              dst:       data.dst      || "*",
              content:   data.content  || "",
              metadata:  data.metadata || {},
              timestamp: data.timestamp || Date.now()/1000,
              ts_human:  data.ts_human || new Date((data.timestamp||Date.now()/1000)*1000).toLocaleTimeString(),
            };
            setMessages(prev => [...prev.slice(-999), msg]);
          }
        } catch {}
      };
    }
    connect();
    return () => { alive = false; wsRef.current?.close(); };
  }, []);

  // ── Periodic polls ─────────────────────────────────────────────
  useEffect(() => {
    async function poll() {
      const [status, ag, gh] = await Promise.all([
        get("/status"),
        get("/swarm/agents"),
        get("/github/status"),
      ]);
      if (status && !status.error) setStats(status);
      if (ag && !ag.error)         setAgents(ag.agents || {});
      if (gh && !gh.error)         setGithubInfo(gh);
    }
    poll();
    const t = setInterval(poll, 10000);
    return () => clearInterval(t);
  }, []);

  const wsColor = wsState === "connected" ? T.ok : wsState === "connecting" ? T.warn : T.err;

  const TABS = [
    { id: "conversations", label: "💬 Conversations" },
    { id: "swarm",         label: "🤖 Swarm" },
    { id: "terminal",      label: "⌨ Terminal" },
    { id: "stats",         label: "📊 Stats" },
  ];

  return (
    <div style={{
      background: T.bg, minHeight: "100vh", color: T.steam,
      display: "flex", flexDirection: "column",
      fontFamily: fontBody,
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=JetBrains+Mono:wght@400;700&family=IM+Fell+English&display=swap');
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: #0a0704; }
        ::-webkit-scrollbar-thumb { background: #2a1a0a; } select,input,button { outline: none; }
      `}</style>

      {/* ── HEADER ── */}
      <div style={{
        background: `linear-gradient(180deg, ${T.bgPanel} 0%, ${T.bgDeep} 100%)`,
        borderBottom: `1px solid ${T.brassDim}`,
        padding: "10px 20px",
        display: "flex", alignItems: "center", gap: 20,
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 22, filter: "drop-shadow(0 0 12px #ff7820)" }}>👻</span>
            <span style={{
              fontFamily: fontHead, fontSize: 20, letterSpacing: "0.3em",
              color: T.brass, textShadow: `0 0 20px ${T.brassDim}`,
            }}>GH05T3</span>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: T.brassDim,
              letterSpacing: "0.2em", alignSelf: "flex-end", paddingBottom: 2 }}>
              v3.0 — UNIFIED COMMAND
            </span>
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: T.steamDim, marginTop: 2 }}>
            TatorTot · Lenovo LOQ 15AHP10 · Tri-GPU Mesh · {Object.keys(agents).length} Agents
          </div>
        </div>

        {/* WS status */}
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          {/* Live conv count */}
          <div style={{
            padding: "4px 12px", background: `${T.ember}11`,
            border: `1px solid ${T.ember}33`, borderRadius: 2,
            fontFamily: fontMono, fontSize: 11, color: T.ember,
          }}>
            {messages.length} msgs
          </div>

          {/* GitHub */}
          {githubInfo && (
            <div style={{
              padding: "4px 12px", background: "rgba(204,204,204,0.06)",
              border: "1px solid rgba(204,204,204,0.15)", borderRadius: 2,
              fontFamily: fontMono, fontSize: 10, color: T.github,
            }}>
              🐙 {githubInfo.name} ⭐{githubInfo.stars}
            </div>
          )}

          {/* WS */}
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "4px 12px",
            background: `${wsColor}11`, border: `1px solid ${wsColor}33`, borderRadius: 2,
          }}>
            <GlowDot color={wsColor} pulse={wsState === "connected"} />
            <span style={{ fontFamily: fontMono, fontSize: 10, color: wsColor, textTransform: "uppercase" }}>
              {wsState}
            </span>
          </div>
        </div>
      </div>

      {/* ── AGENT STATUS BAR ── */}
      <div style={{
        display: "flex", gap: 6, padding: "6px 20px",
        background: "rgba(0,0,0,0.4)", borderBottom: `1px solid ${T.border}`,
        overflowX: "auto",
      }}>
        {Object.entries(agents).map(([id, info]) => (
          <div key={id} style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "2px 10px", borderRadius: 2, whiteSpace: "nowrap",
            background: `${agentColor(id)}08`,
            border: `1px solid ${agentColor(id)}30`,
          }}>
            <GlowDot color={agentColor(id)} pulse={info.active} />
            <span style={{ fontFamily: fontMono, fontSize: 10, color: agentColor(id) }}>{id}</span>
          </div>
        ))}
      </div>

      {/* ── TABS ── */}
      <div style={{
        display: "flex", borderBottom: `1px solid ${T.border}`,
        background: T.bgDeep,
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "8px 20px", background: "none", border: "none",
            borderBottom: `2px solid ${tab === t.id ? T.brass : "transparent"}`,
            color: tab === t.id ? T.brass : T.steamDim,
            fontFamily: fontHead, fontSize: 11, letterSpacing: "0.1em",
            cursor: "pointer", transition: "all 0.15s",
          }}>{t.label}</button>
        ))}
      </div>

      {/* ── MAIN CONTENT ── */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", padding: 0 }}>

        {tab === "conversations" && (
          <div style={{ flex: 1, overflow: "hidden" }}>
            <Panel title={`Live Swarm Conversations  •  ${messages.length} total`}
                   style={{ height: "100%" }} accent={T.brass}>
              <ConversationPanel messages={messages} filter={filter} setFilter={setFilter} />
            </Panel>
          </div>
        )}

        {tab === "swarm" && (
          <div style={{
            flex: 1, overflow: "auto", padding: 16,
            display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: 10, alignContent: "start",
          }}>
            {Object.entries(agents).map(([id, info]) => (
              <AgentBadge key={id} id={id} online={info.active}
                          taskCount={info.tasks} msgCount={info.msgs_recv} />
            ))}
          </div>
        )}

        {tab === "terminal" && (
          <div style={{ flex: 1, overflow: "hidden" }}>
            <Panel title="Command Terminal" style={{ height: "100%" }} accent={T.ember}>
              <Terminal onEmit={(msg) => console.log(msg)} />
            </Panel>
          </div>
        )}

        {tab === "stats" && systemStats && (
          <div style={{ flex: 1, overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {/* Omega */}
            <Panel title="Omega Loop" accent={T.brass}>
              <div style={{ padding: 12, display: "flex", gap: 20, flexWrap: "wrap" }}>
                {Object.entries(systemStats.omega_loop || {}).map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>{k}</div>
                    <div style={{ fontSize: 14, color: T.brass, fontFamily: fontMono }}>{String(v)}</div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* KAIROS */}
            <Panel title="KAIROS Evolutionary Engine" accent={T.purple}>
              <div style={{ padding: 12, display: "flex", gap: 20, flexWrap: "wrap" }}>
                {Object.entries(systemStats.kairos || {}).map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>{k}</div>
                    <div style={{ fontSize: 14, color: T.purple, fontFamily: fontMono }}>{String(v)}</div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Conv log stats */}
            <Panel title="Conversation Log" accent={T.ember}>
              <div style={{ padding: 12, display: "flex", gap: 20, flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>total messages</div>
                  <div style={{ fontSize: 20, color: T.ember, fontFamily: fontMono }}>{messages.length}</div>
                </div>
                {Object.entries(
                  messages.reduce((acc, m) => ({ ...acc, [m.src]: (acc[m.src] || 0) + 1 }), {})
                ).sort((a,b) => b[1]-a[1]).slice(0, 8).map(([agent, count]) => (
                  <div key={agent}>
                    <div style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>{agent}</div>
                    <div style={{ fontSize: 14, color: agentColor(agent), fontFamily: fontMono }}>{count}</div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* GitHub */}
            {githubInfo && (
              <Panel title="GitHub" accent={T.github}>
                <div style={{ padding: 12, display: "flex", gap: 20, flexWrap: "wrap" }}>
                  {Object.entries(githubInfo).map(([k, v]) => (
                    <div key={k}>
                      <div style={{ fontSize: 9, color: T.steamDim, fontFamily: fontMono }}>{k}</div>
                      <div style={{ fontSize: 13, color: T.github, fontFamily: fontMono }}>
                        {k === "url" ? <a href={v} target="_blank" rel="noopener noreferrer"
                          style={{ color: T.github }}>link</a> : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </div>
        )}
      </div>

      {/* ── FOOTER ── */}
      <div style={{
        padding: "5px 20px", background: T.bgDeep,
        borderTop: `1px solid ${T.border}`,
        display: "flex", gap: 16, alignItems: "center",
        fontFamily: fontMono, fontSize: 9, color: T.steamDim,
      }}>
        <span style={{ color: T.brassDim }}>GH05T3 v3</span>
        <span>Sovereign Core · TatorTot · Lenovo LOQ 15AHP10</span>
        <span style={{ color: T.steamDim }}>RTX 5050 :8001 · Radeon 780M :8002 · Ryzen 7 :8003</span>
        <span style={{ marginLeft: "auto" }}>{new Date().toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
