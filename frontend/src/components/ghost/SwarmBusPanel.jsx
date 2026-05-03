import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, Bot, Github, Send, Zap, Search, RefreshCw,
  AlertTriangle, CheckCircle, Loader2, KeyRound, Eye, EyeOff,
  Shield, Cpu, Network,
} from "lucide-react";
import {
  gw3WsUrl, gw3Agents, gw3Delegate, gw3Convos, gw3ConvoSearch,
  gw3GithubStatus, gw3GithubSyncMemory, gw3ClaudeTrain, gw3KairosElite,
  gw3SecretsStatus, gw3SaveSecrets,
} from "../../lib/ghostApi";

// ── palette ───────────────────────────────────────────────────────
const C = {
  bg:       "#03050a",
  panel:    "#060c14",
  border:   "rgba(0,200,255,0.12)",
  borderHi: "rgba(0,200,255,0.35)",
  cyan:     "#00c8ff",
  cyanDim:  "#00648a",
  amber:    "#f59e0b",
  amberDim: "#7a5010",
  purple:   "#9333ea",
  green:    "#10b981",
  red:      "#ef4444",
  ghost:    "#e2e8f0",
  muted:    "#475569",
  deep:     "#0a111c",
};

const AGENT_COLORS = {
  ORACLE:   "#00c8ff", FORGE:    "#ff9933", CODEX:    "#9333ea",
  SENTINEL: "#ef4444", NEXUS:    "#10b981", GITHUB:   "#cbd5e1",
  CLAUDE:   "#cc785c", OMEGA:    "#f59e0b", KAIROS:   "#9333ea",
  SAGE:     "#00c8ff", USER:     "#e2e8f0", SYSTEM:   "#475569",
  GH05T3:   "#ff7820", GATEWAY:  "#f59e0b",
};
const MSG_ICONS = {
  chat:"💬", task:"📋", result:"✅", thought:"💭",
  critique:"🔍", verdict:"⚖️", kairos:"⚡", github:"🐙",
  claude:"🧠", system:"⚙️", heartbeat:"💓", error:"🔴",
};
const AGENTS_ORDER = ["ORACLE","FORGE","CODEX","SENTINEL","NEXUS"];

const agentColor = (id) =>
  AGENT_COLORS[(id||"").toUpperCase().split("-")[0]] || "#64748b";

const timeAgo = (ts) => {
  if (!ts) return "";
  const s = Date.now()/1000 - ts;
  if (s < 60)   return `${~~s}s`;
  if (s < 3600) return `${~~(s/60)}m`;
  return new Date(ts*1000).toLocaleTimeString();
};

// ── keyframe injection ────────────────────────────────────────────
const HOLO_CSS = `
  @keyframes holo-scan {
    0%   { transform: translateY(-100%); opacity: 0; }
    10%  { opacity: 0.06; }
    90%  { opacity: 0.06; }
    100% { transform: translateY(1200%); opacity: 0; }
  }
  @keyframes holo-pulse {
    0%,100% { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
    50%      { box-shadow: 0 0 0 6px transparent; opacity: 0.7; }
  }
  @keyframes holo-ring {
    0%   { transform: scale(1);   opacity: 0.7; }
    100% { transform: scale(2.4); opacity: 0; }
  }
  @keyframes holo-flicker {
    0%,100% { opacity: 1; }
    92%     { opacity: 1; }
    93%     { opacity: 0.7; }
    94%     { opacity: 1; }
    97%     { opacity: 0.85; }
  }
  @keyframes msg-appear {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes dot-live {
    0%,100% { box-shadow: 0 0 4px 1px #00c8ff88; }
    50%     { box-shadow: 0 0 10px 3px #00c8ffcc; }
  }
  @keyframes grid-drift {
    0%   { background-position: 0 0; }
    100% { background-position: 40px 40px; }
  }
  @keyframes conn-flow {
    0%   { stroke-dashoffset: 24; }
    100% { stroke-dashoffset: 0; }
  }
  .holo-panel {
    position: relative;
    background: ${C.panel};
    border: 1px solid ${C.border};
    animation: holo-flicker 8s infinite;
    overflow: hidden;
  }
  .holo-panel::before {
    content: '';
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 39px,
      rgba(0,200,255,0.03) 39px,
      rgba(0,200,255,0.03) 40px
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 39px,
      rgba(0,200,255,0.03) 39px,
      rgba(0,200,255,0.03) 40px
    );
    pointer-events: none;
    animation: grid-drift 20s linear infinite;
    z-index: 0;
  }
  .holo-panel::after {
    content: '';
    position: absolute; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, ${C.cyan}88, transparent);
    animation: holo-scan 4s linear infinite;
    pointer-events: none;
    z-index: 1;
  }
  .holo-inner { position: relative; z-index: 2; }
  .holo-tab-active {
    background: linear-gradient(135deg, rgba(0,200,255,0.08), rgba(0,200,255,0.02));
    border-color: rgba(0,200,255,0.4) !important;
    color: ${C.cyan} !important;
    text-shadow: 0 0 8px ${C.cyan}88;
  }
  .holo-tab {
    transition: all 160ms ease;
    border: 1px solid rgba(255,255,255,0.07);
    color: ${C.muted};
  }
  .holo-tab:hover { color: ${C.ghost}; border-color: rgba(0,200,255,0.2); }
  .msg-row { animation: msg-appear 220ms ease both; }
  .agent-node-ring {
    position: absolute; inset: 0;
    border-radius: 50%;
    border: 1px solid currentColor;
    animation: holo-ring 2s ease-out infinite;
  }
  .ws-live-dot {
    animation: dot-live 1.4s ease-in-out infinite;
  }
  .holo-input {
    background: ${C.deep};
    border: 1px solid rgba(0,200,255,0.15);
    color: ${C.ghost};
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    outline: none;
    transition: border-color 150ms ease;
  }
  .holo-input:focus { border-color: rgba(0,200,255,0.45); box-shadow: 0 0 0 1px rgba(0,200,255,0.15); }
  .holo-btn {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    transition: all 150ms ease;
    border: 1px solid rgba(0,200,255,0.2);
    color: ${C.muted};
  }
  .holo-btn:hover { border-color: rgba(0,200,255,0.5); color: ${C.cyan}; background: rgba(0,200,255,0.05); }
  .holo-btn:disabled { opacity: 0.3; pointer-events: none; }
  .holo-btn-primary {
    border-color: rgba(245,158,11,0.35) !important;
    color: ${C.amber} !important;
  }
  .holo-btn-primary:hover { background: rgba(245,158,11,0.08) !important; border-color: rgba(245,158,11,0.6) !important; }
  .holo-select {
    background: ${C.deep};
    border: 1px solid rgba(0,200,255,0.15);
    color: ${C.muted};
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    outline: none;
  }
  .conn-line { animation: conn-flow 1.5s linear infinite; }
`;

let _cssInjected = false;
function injectCss() {
  if (_cssInjected || typeof document === "undefined") return;
  const el = document.createElement("style");
  el.textContent = HOLO_CSS;
  document.head.appendChild(el);
  _cssInjected = true;
}

// ── sub-components ────────────────────────────────────────────────

function MsgRow({ msg, fresh }) {
  const color = agentColor(msg.src);
  const icon  = MSG_ICONS[msg.msg_type] || "·";
  const isThou = msg.msg_type === "thought";
  return (
    <div
      className="msg-row flex gap-2 py-1.5"
      style={{
        borderBottom: "1px solid rgba(0,200,255,0.06)",
        opacity: isThou ? 0.45 : 1,
        animationDelay: fresh ? "0ms" : "none",
      }}
    >
      <span style={{ fontFamily:"monospace", fontSize:10, color:C.muted, width:16, flexShrink:0, paddingTop:2 }}>
        {icon}
      </span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:"flex", alignItems:"baseline", gap:6, flexWrap:"wrap" }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700, color, textShadow:`0 0 6px ${color}66` }}>
            {msg.src}
          </span>
          {msg.dst && msg.dst !== "*" && (
            <span style={{ fontFamily:"monospace", fontSize:9, color:C.muted }}>→ {msg.dst}</span>
          )}
          <span style={{ fontFamily:"monospace", fontSize:9, color:"#2d3f50", marginLeft:"auto", flexShrink:0 }}>
            {timeAgo(msg.timestamp||msg.ts)}
          </span>
        </div>
        <p style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:"#94a3b8", lineHeight:1.5, wordBreak:"break-word", margin:0 }}>
          {(msg.content||"").slice(0,280)}
          {(msg.content||"").length > 280 && <span style={{ color:C.muted }}> …</span>}
        </p>
      </div>
    </div>
  );
}

function AgentNodeSvg({ agents }) {
  const size = 200;
  const cx   = size/2, cy = size/2, r = 72;
  const n    = agents.length || 1;
  const positions = agents.map((_, i) => {
    const theta = (i/n)*Math.PI*2 - Math.PI/2;
    return { x: cx + Math.cos(theta)*r, y: cy + Math.sin(theta)*r };
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow:"visible" }}>
      {/* connection ring */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(0,200,255,0.08)" strokeWidth={1} />
      {/* edges */}
      {agents.map((_, i) => {
        const a = positions[i];
        const b = positions[(i+1)%n];
        const active = agents[i]?.[1]?.active && agents[(i+1)%n]?.[1]?.active;
        return (
          <line
            key={i}
            x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={active ? "rgba(0,200,255,0.25)" : "rgba(0,200,255,0.06)"}
            strokeWidth={active ? 1 : 0.5}
            strokeDasharray={active ? "4 4" : "2 6"}
            className={active ? "conn-line" : ""}
          />
        );
      })}
      {/* center node */}
      <circle cx={cx} cy={cy} r={8} fill="rgba(245,158,11,0.15)" stroke="rgba(245,158,11,0.5)" strokeWidth={1} />
      <text x={cx} y={cy+4} textAnchor="middle" fill="#f59e0b" fontSize={6} fontFamily="monospace" fontWeight="bold">GH05T3</text>
      {/* agent nodes */}
      {agents.map(([id, meta], i) => {
        const { x, y } = positions[i];
        const color = agentColor(id);
        const active = meta?.active;
        return (
          <g key={id}>
            {active && (
              <circle cx={x} cy={y} r={12}
                fill="none"
                stroke={color}
                strokeWidth={0.8}
                opacity={0.4}
                style={{ animation:"holo-ring 2.5s ease-out infinite", transformOrigin:`${x}px ${y}px` }}
              />
            )}
            <circle
              cx={x} cy={y} r={8}
              fill={active ? `${color}22` : "rgba(30,40,50,0.8)"}
              stroke={active ? color : "#2d3f50"}
              strokeWidth={active ? 1.5 : 1}
              style={{ filter: active ? `drop-shadow(0 0 4px ${color}88)` : "none" }}
            />
            <text x={x} y={y+3} textAnchor="middle" fill={active ? color : "#475569"}
              fontSize={5} fontFamily="monospace" fontWeight="bold">
              {id.slice(0,3)}
            </text>
            {active && (
              <circle cx={x+6} cy={y-6} r={2.5}
                fill={color}
                style={{ filter:`drop-shadow(0 0 3px ${color})` }}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

function AgentCard({ id, meta }) {
  const color  = agentColor(id);
  const active = meta?.active;
  const upSec  = meta?.uptime ? ~~meta.uptime : null;
  return (
    <div
      style={{
        display:"flex", alignItems:"center", gap:10,
        padding:"8px 10px",
        borderBottom:"1px solid rgba(0,200,255,0.06)",
        background: active ? `linear-gradient(90deg, ${color}08, transparent)` : "transparent",
        transition:"background 300ms",
      }}
    >
      <div style={{ position:"relative", width:10, height:10, flexShrink:0 }}>
        <div
          style={{
            width:10, height:10, borderRadius:"50%",
            background: active ? color : "#1e2d3d",
            boxShadow: active ? `0 0 6px ${color}88` : "none",
          }}
          className={active ? "ws-live-dot" : ""}
        />
      </div>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, fontWeight:700, width:72, flexShrink:0, color: active ? color : C.muted, textShadow: active ? `0 0 8px ${color}66` : "none" }}>
        {id}
      </span>
      <span style={{ fontFamily:"monospace", fontSize:10, color:C.muted, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
        {meta?.description || meta?.role || ""}
      </span>
      {upSec !== null && (
        <span style={{ fontFamily:"monospace", fontSize:9, color:"#2d3f50", flexShrink:0 }}>
          {upSec < 3600 ? `${~~(upSec/60)}m` : `${~~(upSec/3600)}h`}
        </span>
      )}
      <div style={{ display:"flex", gap:4 }}>
        {meta?.msgs_recv !== undefined && (
          <span style={{ fontFamily:"monospace", fontSize:9, color:C.muted }}>
            {meta.msgs_recv}↙
          </span>
        )}
        {meta?.tasks !== undefined && (
          <span style={{ fontFamily:"monospace", fontSize:9, color:C.amberDim }}>
            {meta.tasks}⚡
          </span>
        )}
      </div>
    </div>
  );
}

// ── header badge ──────────────────────────────────────────────────

function WsBadge({ wsState, onReconnect }) {
  const cfg = {
    off:        { label:"OFF",        color:"#334155",  dot:"#334155" },
    connecting: { label:"LINKING",    color:C.amber,    dot:C.amber   },
    live:       { label:"LIVE",       color:C.cyan,     dot:C.cyan    },
    error:      { label:"ERR",        color:C.red,      dot:C.red     },
  }[wsState] || { label:"?", color:C.muted, dot:C.muted };

  return (
    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
      <div
        style={{
          width:7, height:7, borderRadius:"50%",
          background:cfg.dot,
          boxShadow: wsState === "live" ? `0 0 8px ${cfg.dot}` : "none",
        }}
        className={wsState === "live" ? "ws-live-dot" : ""}
      />
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, letterSpacing:"0.2em", color:cfg.color }}>
        {cfg.label}
      </span>
      {wsState !== "live" && (
        <button onClick={onReconnect} style={{ color:C.amber, background:"none", border:"none", cursor:"pointer", padding:0, display:"flex" }}>
          <RefreshCw size={9} />
        </button>
      )}
    </div>
  );
}

// ── main panel ────────────────────────────────────────────────────

const TABS = [
  { id:"stream",  icon:<Activity size={10}/>,  label:"stream"  },
  { id:"agents",  icon:<Cpu     size={10}/>,   label:"agents"  },
  { id:"github",  icon:<Github  size={10}/>,   label:"github"  },
  { id:"claude",  icon:<Zap     size={10}/>,   label:"claude"  },
  { id:"keys",    icon:<Shield  size={10}/>,   label:"keys"    },
];

export const SwarmBusPanel = () => {
  injectCss();

  const [msgs,      setMsgs]      = useState([]);
  const [agents,    setAgents]    = useState({});
  const [wsState,   setWsState]   = useState("off");
  const [task,      setTask]      = useState("");
  const [target,    setTarget]    = useState("");
  const [busy,      setBusy]      = useState(false);
  const [result,    setResult]    = useState(null);
  const [tab,       setTab]       = useState("stream");
  const [ghInfo,    setGhInfo]    = useState(null);
  const [search,    setSearch]    = useState("");
  const [elite,     setElite]     = useState([]);
  const [keyStatus, setKeyStatus] = useState(null);
  const [akInput,   setAkInput]   = useState("");
  const [ghInput,   setGhInput]   = useState("");
  const [showAk,    setShowAk]    = useState(false);
  const [showGh,    setShowGh]    = useState(false);
  const [freshIdx,  setFreshIdx]  = useState(-1);

  const wsRef      = useRef(null);
  const streamRef  = useRef(null);
  const autoScroll = useRef(true);

  // ── WebSocket ──────────────────────────────────────────────────
  const connectWs = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    setWsState("connecting");
    const ws = new WebSocket(gw3WsUrl());
    wsRef.current = ws;
    ws.onopen  = () => setWsState("live");
    ws.onerror = () => setWsState("error");
    ws.onclose = () => setWsState("off");
    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type === "ping" || d.type === "hello") return;
        setMsgs((prev) => {
          const next = [...prev, d].slice(-200);
          setFreshIdx(next.length - 1);
          return next;
        });
        if (autoScroll.current && streamRef.current) {
          setTimeout(() => {
            if (streamRef.current)
              streamRef.current.scrollTop = streamRef.current.scrollHeight;
          }, 30);
        }
      } catch {}
    };
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const d = await gw3Agents();
      setAgents(d.agents || {});
    } catch {}
  }, []);

  const loadConvos = useCallback(async () => {
    try {
      const d = await gw3Convos(80);
      setMsgs(d.messages || []);
    } catch {}
  }, []);

  const loadKeyStatus = useCallback(async () => {
    try {
      const d = await gw3SecretsStatus();
      setKeyStatus(d);
    } catch {}
  }, []);

  useEffect(() => {
    loadConvos();
    loadAgents();
    loadKeyStatus();
    connectWs();
    return () => wsRef.current?.close();
  }, []); // eslint-disable-line

  useEffect(() => {
    const iv = setInterval(loadAgents, 10000);
    return () => clearInterval(iv);
  }, [loadAgents]);

  // ── actions ───────────────────────────────────────────────────
  const delegate = async () => {
    if (!task.trim()) return;
    setBusy(true); setResult(null);
    try {
      const r = await gw3Delegate(task.trim(), target || null);
      setResult({ ok:true, routed_to: r.routed_to });
      setTask("");
    } catch (e) {
      setResult({ ok:false, error: e?.response?.data?.detail || e.message });
    } finally { setBusy(false); }
  };

  const loadGithub = async () => {
    setBusy(true);
    try { const d = await gw3GithubStatus(); setGhInfo(d); }
    catch (e) { setGhInfo({ error: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const syncMemory = async () => {
    setBusy(true);
    try { await gw3GithubSyncMemory(); setResult({ ok:true, routed_to:"GITHUB" }); }
    catch (e) { setResult({ ok:false, error: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const trainClaude = async () => {
    setBusy(true); setResult(null);
    try {
      const d = await gw3ClaudeTrain("agent_systems", 5);
      setResult({ ok:true, routed_to:`CLAUDE — ${d.count} scenarios` });
    } catch (e) { setResult({ ok:false, error: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const loadElite = async () => {
    try { const d = await gw3KairosElite(); setElite(d); } catch {}
  };

  const saveKeys = async () => {
    if (!akInput.trim() && !ghInput.trim()) return;
    setBusy(true); setResult(null);
    try {
      const d = await gw3SaveSecrets(akInput.trim()||null, ghInput.trim()||null);
      setResult({ ok:true, routed_to:`saved: ${d.updated.join(", ")}` });
      setAkInput(""); setGhInput(""); loadKeyStatus();
    } catch (e) { setResult({ ok:false, error: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const handleSearch = async () => {
    if (!search.trim()) { loadConvos(); return; }
    try { const d = await gw3ConvoSearch(search.trim()); setMsgs(d.results||[]); } catch {}
  };

  const agentEntries  = Object.entries(agents);
  const activeCount   = agentEntries.filter(([,m]) => m.active).length;
  const keysAlert     = keyStatus && (!keyStatus.anthropic_api_key?.set || !keyStatus.github_pat?.set);

  // ── render ────────────────────────────────────────────────────
  return (
    <div className="holo-panel" style={{ padding:"1.25rem" }}>
      <div className="holo-inner">

        {/* ── HEADER ── */}
        <header style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:14 }}>
          <div>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, letterSpacing:"0.25em", textTransform:"uppercase", color:C.cyan, textShadow:`0 0 12px ${C.cyan}66`, display:"flex", alignItems:"center", gap:6 }}>
              <Network size={11} color={C.cyan} />
              SWARM BUS v3
            </div>
            <div style={{ fontFamily:"monospace", fontSize:10, color:C.muted, marginTop:3 }}>
              <span style={{ color: activeCount > 0 ? C.cyan : "#334155" }}>{activeCount}</span>
              <span style={{ color:"#1e2d3d" }}>/{agentEntries.length}</span>
              <span style={{ color:"#2d3f50" }}> agents · </span>
              <span style={{ color: msgs.length > 0 ? C.amberDim : "#2d3f50" }}>{msgs.length}</span>
              <span style={{ color:"#2d3f50" }}> msgs</span>
            </div>
          </div>
          <WsBadge wsState={wsState} onReconnect={connectWs} />
        </header>

        {/* ── TAB BAR ── */}
        <div style={{ display:"flex", gap:3, marginBottom:14 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`holo-tab ${tab === t.id ? "holo-tab-active" : ""}`}
              style={{ position:"relative", flex:1, display:"flex", alignItems:"center", justifyContent:"center", gap:4, padding:"5px 4px", background:"none", cursor:"pointer" }}
            >
              {t.icon}
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, letterSpacing:"0.15em" }}>{t.label}</span>
              {t.id === "keys" && keysAlert && (
                <span style={{ position:"absolute", top:2, right:2, width:5, height:5, borderRadius:"50%", background:C.amber, boxShadow:`0 0 4px ${C.amber}` }} />
              )}
            </button>
          ))}
        </div>

        {/* ── STREAM tab ── */}
        {tab === "stream" && (
          <>
            <div style={{ display:"flex", gap:4, marginBottom:8 }}>
              <input
                className="holo-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="search conversations…"
                style={{ flex:1, padding:"5px 8px" }}
              />
              <button className="holo-btn" onClick={handleSearch} style={{ padding:"0 8px", cursor:"pointer" }}>
                <Search size={11} />
              </button>
              <button className="holo-btn" onClick={() => { setSearch(""); loadConvos(); }} style={{ padding:"0 8px", cursor:"pointer" }}>
                <RefreshCw size={11} />
              </button>
            </div>

            <div
              ref={streamRef}
              onScroll={(e) => {
                const el = e.currentTarget;
                autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
              }}
              style={{
                height:224, overflowY:"auto", paddingRight:4,
                scrollbarWidth:"thin", scrollbarColor:`${C.cyanDim} transparent`,
              }}
            >
              {msgs.length === 0 && (
                <div style={{ textAlign:"center", padding:"32px 0", fontFamily:"monospace", fontSize:11, color:"#2d3f50" }}>
                  <div style={{ marginBottom:8 }}>◈ no messages</div>
                  <div style={{ fontSize:10, color:"#1e2d3d" }}>gateway_v3 offline — run run.bat</div>
                </div>
              )}
              {msgs.map((m, i) => (
                <MsgRow key={m.id||i} msg={m} fresh={i === freshIdx} />
              ))}
            </div>

            {/* delegate */}
            <div style={{ marginTop:12 }}>
              <div style={{ display:"flex", gap:4 }}>
                <input
                  className="holo-input"
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !busy && delegate()}
                  placeholder="delegate task to swarm…"
                  style={{ flex:1, padding:"6px 8px" }}
                />
                <select
                  className="holo-select"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  style={{ padding:"0 6px", cursor:"pointer" }}
                >
                  <option value="">auto</option>
                  {AGENTS_ORDER.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
                <button
                  className="holo-btn holo-btn-primary"
                  onClick={delegate}
                  disabled={busy || !task.trim()}
                  style={{ padding:"0 12px", cursor:"pointer", display:"flex", alignItems:"center", gap:4 }}
                >
                  {busy ? <Loader2 size={11} style={{ animation:"spin 1s linear infinite" }}/> : <Send size={11}/>}
                </button>
              </div>
              {result && (
                <div style={{ display:"flex", alignItems:"center", gap:5, marginTop:6, fontFamily:"monospace", fontSize:10, color: result.ok ? C.green : C.red }}>
                  {result.ok ? <><CheckCircle size={10}/> routed → {result.routed_to}</> : <><AlertTriangle size={10}/> {result.error}</>}
                </div>
              )}
            </div>
          </>
        )}

        {/* ── AGENTS tab ── */}
        {tab === "agents" && (
          <div>
            {agentEntries.length === 0 ? (
              <div style={{ textAlign:"center", padding:"32px 0", fontFamily:"monospace", fontSize:11, color:"#2d3f50" }}>
                <div>◈ no agents registered</div>
                <div style={{ fontSize:10, marginTop:6, color:"#1e2d3d" }}>start gateway_v3 → run.bat</div>
              </div>
            ) : (
              <div style={{ display:"flex", gap:12, marginBottom:12 }}>
                <AgentNodeSvg agents={agentEntries} />
                <div style={{ flex:1, display:"flex", flexDirection:"column", justifyContent:"center", gap:4 }}>
                  {agentEntries.map(([id, meta]) => (
                    <div key={id} style={{ display:"flex", alignItems:"center", gap:6 }}>
                      <div style={{ width:6, height:6, borderRadius:"50%", background: meta.active ? agentColor(id) : "#2d3f50", boxShadow: meta.active ? `0 0 5px ${agentColor(id)}` : "none", flexShrink:0 }} />
                      <span style={{ fontFamily:"monospace", fontSize:10, fontWeight:700, color: meta.active ? agentColor(id) : C.muted, width:60 }}>{id}</span>
                      <span style={{ fontFamily:"monospace", fontSize:9, color:C.muted, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {meta.description||meta.role||""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {agentEntries.map(([id, meta]) => (
              <AgentCard key={id} id={id} meta={meta} />
            ))}
            <button
              className="holo-btn"
              onClick={loadAgents}
              style={{ marginTop:8, width:"100%", padding:"7px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}
            >
              <RefreshCw size={9}/> refresh agents
            </button>
          </div>
        )}

        {/* ── GITHUB tab ── */}
        {tab === "github" && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {ghInfo && !ghInfo.error && (
              <div style={{ background:C.deep, border:`1px solid rgba(0,200,255,0.12)`, padding:"10px 12px", fontFamily:"monospace" }}>
                <div style={{ fontSize:12, fontWeight:700, color:C.ghost, marginBottom:4 }}>{ghInfo.name}</div>
                <div style={{ display:"flex", gap:16, fontSize:10, color:C.muted }}>
                  <span>⭐ {ghInfo.stars}</span>
                  <span>🍴 {ghInfo.forks}</span>
                  <span>🐛 {ghInfo.open_issues}</span>
                </div>
                <div style={{ fontSize:9, color:"#2d3f50", marginTop:4 }}>
                  {ghInfo.default_branch} · {new Date(ghInfo.updated).toLocaleDateString()}
                </div>
              </div>
            )}
            {ghInfo?.error && (
              <div style={{ fontFamily:"monospace", fontSize:10, color:C.red, border:`1px solid rgba(239,68,68,0.2)`, padding:"8px 10px" }}>
                {ghInfo.error}
              </div>
            )}
            <div style={{ display:"flex", gap:6 }}>
              <button className="holo-btn" onClick={loadGithub} disabled={busy}
                style={{ flex:1, padding:"8px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}>
                <Github size={11}/> repo status
              </button>
              <button className="holo-btn" onClick={syncMemory} disabled={busy}
                style={{ flex:1, padding:"8px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}>
                {busy ? <Loader2 size={11} style={{ animation:"spin 1s linear infinite" }}/> : <RefreshCw size={11}/>}
                sync memory
              </button>
            </div>
            {result && (
              <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"monospace", fontSize:10, color: result.ok ? C.green : C.red }}>
                {result.ok ? <><CheckCircle size={10}/> {result.routed_to}</> : <><AlertTriangle size={10}/> {result.error}</>}
              </div>
            )}
          </div>
        )}

        {/* ── CLAUDE tab ── */}
        {tab === "claude" && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            <div style={{ fontFamily:"monospace", fontSize:10, color:C.muted, border:`1px solid rgba(255,255,255,0.04)`, padding:"8px 10px", lineHeight:1.6 }}>
              CLAUDE-TRAINER generates synthetic KAIROS training data (~$0.003/batch of 5).
              Requires ANTHROPIC_API_KEY set in keys tab.
            </div>
            <div style={{ display:"flex", gap:6 }}>
              <button className="holo-btn holo-btn-primary" onClick={trainClaude} disabled={busy}
                style={{ flex:1, padding:"8px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}>
                {busy ? <Loader2 size={11} style={{ animation:"spin 1s linear infinite" }}/> : <Zap size={11}/>}
                train batch (5)
              </button>
              <button className="holo-btn" onClick={() => { loadElite(); }}
                style={{ flex:1, padding:"8px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}>
                elite archive
              </button>
            </div>
            {result && (
              <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"monospace", fontSize:10, color: result.ok ? C.green : C.red }}>
                {result.ok ? <><CheckCircle size={10}/> {result.routed_to}</> : <><AlertTriangle size={10}/> {result.error}</>}
              </div>
            )}
            {elite.length > 0 && (
              <div>
                <div style={{ fontFamily:"monospace", fontSize:9, letterSpacing:"0.2em", color:C.muted, textTransform:"uppercase", marginBottom:6 }}>
                  elite cycles ({elite.length})
                </div>
                {elite.slice(-5).map((c) => (
                  <div key={c.id} style={{ fontFamily:"monospace", fontSize:10, border:`1px solid rgba(255,255,255,0.04)`, padding:"6px 8px", display:"flex", justifyContent:"space-between", marginBottom:3 }}>
                    <span style={{ color:"#64748b", flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      #{c.id} {c.proposal?.slice(0,60)}
                    </span>
                    <span style={{ color:C.green, flexShrink:0, marginLeft:8 }}>{c.score?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── KEYS tab ── */}
        {tab === "keys" && (
          <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
            {keyStatus && (
              <div style={{ display:"flex", gap:12, fontFamily:"monospace", fontSize:10 }}>
                <div style={{ display:"flex", alignItems:"center", gap:5, color: keyStatus.anthropic_api_key?.set ? C.green : C.amber }}>
                  {keyStatus.anthropic_api_key?.set ? <CheckCircle size={10}/> : <AlertTriangle size={10}/>}
                  Claude {keyStatus.anthropic_api_key?.set ? keyStatus.anthropic_api_key.preview : "NOT SET"}
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:5, color: keyStatus.github_pat?.set ? C.green : C.amber }}>
                  {keyStatus.github_pat?.set ? <CheckCircle size={10}/> : <AlertTriangle size={10}/>}
                  GitHub {keyStatus.github_pat?.set ? keyStatus.github_pat.preview : "NOT SET"}
                </div>
              </div>
            )}

            {[
              { label:"Anthropic API Key", val:akInput, set:setAkInput, show:showAk, setShow:setShowAk, ph:"sk-ant-api03-…", hint:"console.anthropic.com → API Keys" },
              { label:"GitHub PAT",        val:ghInput, set:setGhInput, show:showGh, setShow:setShowGh, ph:"ghp_…",           hint:"github.com → Settings → Developer settings → PAT (classic)" },
            ].map(({ label, val, set, show, setShow, ph, hint }) => (
              <div key={label}>
                <div style={{ fontFamily:"monospace", fontSize:9, letterSpacing:"0.15em", textTransform:"uppercase", color:C.muted, marginBottom:5 }}>{label}</div>
                <div style={{ display:"flex", gap:4 }}>
                  <input
                    className="holo-input"
                    type={show ? "text" : "password"}
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    placeholder={ph}
                    autoComplete="off"
                    style={{ flex:1, padding:"6px 8px" }}
                  />
                  <button
                    className="holo-btn"
                    onClick={() => setShow((v) => !v)}
                    tabIndex={-1}
                    style={{ padding:"0 8px", cursor:"pointer" }}
                  >
                    {show ? <EyeOff size={11}/> : <Eye size={11}/>}
                  </button>
                </div>
                <div style={{ fontFamily:"monospace", fontSize:9, color:"#2d3f50", marginTop:3 }}>{hint}</div>
              </div>
            ))}

            <div style={{ display:"flex", gap:6 }}>
              <button
                className="holo-btn holo-btn-primary"
                onClick={saveKeys}
                disabled={busy || (!akInput.trim() && !ghInput.trim())}
                style={{ flex:1, padding:"8px 0", display:"flex", alignItems:"center", justifyContent:"center", gap:5, cursor:"pointer" }}
              >
                {busy ? <Loader2 size={11} style={{ animation:"spin 1s linear infinite" }}/> : <KeyRound size={11}/>}
                save to .env
              </button>
              <button className="holo-btn" onClick={loadKeyStatus} style={{ padding:"0 12px", cursor:"pointer" }}>
                <RefreshCw size={11}/>
              </button>
            </div>

            {result && (
              <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"monospace", fontSize:10, color: result.ok ? C.green : C.red }}>
                {result.ok ? <><CheckCircle size={10}/> {result.routed_to}</> : <><AlertTriangle size={10}/> {result.error}</>}
              </div>
            )}

            <div style={{ fontFamily:"monospace", fontSize:9, color:"#1e2d3d", lineHeight:1.6 }}>
              Written to backend/.env on TatorTot — hot-loaded, no restart needed.
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
