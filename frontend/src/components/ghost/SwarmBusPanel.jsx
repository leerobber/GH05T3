import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, Bot, Github, Send, Zap, Search, RefreshCw,
  AlertTriangle, CheckCircle, Loader2,
} from "lucide-react";
import { Panel } from "./primitives";
import {
  gw3WsUrl, gw3Agents, gw3Delegate, gw3Convos, gw3ConvoSearch,
  gw3GithubStatus, gw3GithubSyncMemory, gw3ClaudeTrain, gw3KairosElite,
} from "../../lib/ghostApi";

// ── constants ─────────────────────────────────────────────────────
const AGENT_COLORS = {
  ORACLE: "#40c8d4", FORGE: "#ff9933", CODEX: "#9966ff",
  SENTINEL: "#d44040", NEXUS: "#8bc668", GITHUB: "#cccccc",
  CLAUDE: "#cc785c", OMEGA: "#d4941c", KAIROS: "#9966ff",
  SAGE: "#40c8d4", USER: "#e8d8b8", SYSTEM: "#7a5010", GH05T3: "#ff7820",
};
const MSG_ICONS = {
  chat: "💬", task: "📋", result: "✅", thought: "💭",
  critique: "🔍", verdict: "⚖️", kairos: "⚡", github: "🐙",
  claude: "🧠", system: "⚙️", heartbeat: "💓", error: "🔴",
};
const AGENTS_ORDER = ["ORACLE", "FORGE", "CODEX", "SENTINEL", "NEXUS"];

const agentColor = (id) =>
  AGENT_COLORS[(id || "").toUpperCase().split("-")[0]] || "#a0a0a0";

const timeAgo = (ts) => {
  if (!ts) return "";
  const s = Date.now() / 1000 - ts;
  if (s < 60) return `${~~s}s`;
  if (s < 3600) return `${~~(s / 60)}m`;
  return new Date(ts * 1000).toLocaleTimeString();
};

// ── sub-components ────────────────────────────────────────────────

function MsgRow({ msg }) {
  const color  = agentColor(msg.src);
  const icon   = MSG_ICONS[msg.msg_type] || "·";
  const isThou = msg.msg_type === "thought";
  return (
    <div className={`flex gap-2 py-1 border-b border-white/5 ${isThou ? "opacity-40" : ""}`}>
      <span className="font-mono-term text-[9px] text-zinc-600 w-6 shrink-0 pt-0.5">
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="font-mono-term text-[10px] font-bold" style={{ color }}>
            {msg.src}
          </span>
          {msg.dst && msg.dst !== "*" && (
            <span className="font-mono-term text-[9px] text-zinc-600">
              → {msg.dst}
            </span>
          )}
          <span className="font-mono-term text-[9px] text-zinc-700 ml-auto shrink-0">
            {timeAgo(msg.timestamp || msg.ts)}
          </span>
        </div>
        <p className="font-mono-term text-[11px] text-zinc-300 leading-relaxed break-words">
          {(msg.content || "").slice(0, 300)}
          {(msg.content || "").length > 300 && (
            <span className="text-zinc-600"> …</span>
          )}
        </p>
      </div>
    </div>
  );
}

function AgentRow({ agent }) {
  const [id, meta] = agent;
  const color = agentColor(id);
  const upSec = meta.uptime ? ~~meta.uptime : null;
  return (
    <div className="flex items-center gap-2 py-1 border-b border-white/5">
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: meta.active ? color : "#444", boxShadow: meta.active ? `0 0 4px ${color}88` : "none" }}
      />
      <span className="font-mono-term text-[11px] font-bold w-20 shrink-0" style={{ color }}>
        {id}
      </span>
      <span className="font-mono-term text-[10px] text-zinc-500 flex-1 truncate">
        {meta.description || meta.role || ""}
      </span>
      {upSec !== null && (
        <span className="font-mono-term text-[9px] text-zinc-600 shrink-0">
          up {upSec < 3600 ? `${~~(upSec / 60)}m` : `${~~(upSec / 3600)}h`}
        </span>
      )}
    </div>
  );
}

// ── main panel ────────────────────────────────────────────────────

export const SwarmBusPanel = () => {
  const [msgs,    setMsgs]    = useState([]);
  const [agents,  setAgents]  = useState({});
  const [wsState, setWsState] = useState("off"); // off | connecting | live | error
  const [task,    setTask]    = useState("");
  const [target,  setTarget]  = useState("");
  const [busy,    setBusy]    = useState(false);
  const [result,  setResult]  = useState(null);
  const [tab,     setTab]     = useState("stream"); // stream | agents | github | claude
  const [ghInfo,  setGhInfo]  = useState(null);
  const [search,  setSearch]  = useState("");
  const [elite,   setElite]   = useState([]);

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

  // ── REST load ─────────────────────────────────────────────────

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

  useEffect(() => {
    loadConvos();
    loadAgents();
    connectWs();
    return () => wsRef.current?.close();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh agents every 10 s
  useEffect(() => {
    const iv = setInterval(loadAgents, 10000);
    return () => clearInterval(iv);
  }, [loadAgents]);

  // ── actions ───────────────────────────────────────────────────

  const delegate = async () => {
    if (!task.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await gw3Delegate(task.trim(), target || null);
      setResult({ ok: true, routed_to: r.routed_to });
      setTask("");
    } catch (e) {
      setResult({ ok: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const loadGithub = async () => {
    setBusy(true);
    try {
      const d = await gw3GithubStatus();
      setGhInfo(d);
    } catch (e) {
      setGhInfo({ error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const syncMemory = async () => {
    setBusy(true);
    try {
      await gw3GithubSyncMemory();
      setResult({ ok: true, routed_to: "GITHUB" });
    } catch (e) {
      setResult({ ok: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const trainClaude = async () => {
    setBusy(true);
    setResult(null);
    try {
      const d = await gw3ClaudeTrain("agent_systems", 5);
      setResult({ ok: true, routed_to: `CLAUDE — ${d.count} scenarios` });
    } catch (e) {
      setResult({ ok: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const loadElite = async () => {
    try {
      const d = await gw3KairosElite();
      setElite(d);
    } catch {}
  };

  const handleSearch = async () => {
    if (!search.trim()) { loadConvos(); return; }
    try {
      const d = await gw3ConvoSearch(search.trim());
      setMsgs(d.results || []);
    } catch {}
  };

  // ── ws status badge ───────────────────────────────────────────

  const wsDot = { off: "dot-idle", connecting: "dot-idle", live: "dot-active", error: "dot-error" }[wsState];

  const agentEntries = Object.entries(agents);
  const activeCount  = agentEntries.filter(([, m]) => m.active).length;

  // ── render ────────────────────────────────────────────────────

  return (
    <Panel
      testid="swarm-bus-panel"
      title="SWARM BUS v3 · specialists"
      sub={`${activeCount}/${agentEntries.length} agents · ${msgs.length} msgs`}
      right={
        <span className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-1.5">
          <span className={`dot ${wsDot}`} />
          {wsState}
          {wsState !== "live" && (
            <button onClick={connectWs} className="ml-1 text-amber-400 hover:text-amber-300">
              <RefreshCw size={9} />
            </button>
          )}
        </span>
      }
    >
      {/* tab bar */}
      <div className="flex gap-0.5 mb-3">
        {[
          { id: "stream",  icon: <Activity size={10} />, label: "stream"  },
          { id: "agents",  icon: <Bot      size={10} />, label: "agents"  },
          { id: "github",  icon: <Github   size={10} />, label: "github"  },
          { id: "claude",  icon: <Zap      size={10} />, label: "claude"  },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-1 font-mono-term text-[9px] tracking-[0.2em] uppercase px-1 py-1.5 border ${
              tab === t.id
                ? "border-amber-500/50 text-amber-400 bg-amber-500/5"
                : "border-white/10 text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* ── STREAM tab ── */}
      {tab === "stream" && (
        <>
          <div className="flex gap-1 mb-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="search conversations…"
              className="flex-1 bg-black border border-white/10 px-2 py-1 font-mono-term text-[11px] text-zinc-200 outline-none focus:border-amber-500/40"
            />
            <button
              onClick={handleSearch}
              className="border border-white/10 px-2 text-zinc-400 hover:text-amber-400"
            >
              <Search size={11} />
            </button>
            <button
              onClick={() => { setSearch(""); loadConvos(); }}
              className="border border-white/10 px-2 text-zinc-400 hover:text-amber-400"
            >
              <RefreshCw size={11} />
            </button>
          </div>

          <div
            ref={streamRef}
            onScroll={(e) => {
              const el = e.currentTarget;
              autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
            }}
            className="h-56 overflow-y-auto pr-1"
            style={{ scrollbarWidth: "thin", scrollbarColor: "#333 transparent" }}
          >
            {msgs.length === 0 && (
              <p className="font-mono-term text-[11px] text-zinc-600 text-center py-6">
                no messages yet — gateway_v3 offline?
              </p>
            )}
            {msgs.map((m, i) => <MsgRow key={m.id || i} msg={m} />)}
          </div>

          {/* delegate form */}
          <div className="mt-3 space-y-2">
            <div className="flex gap-1">
              <input
                value={task}
                onChange={(e) => setTask(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !busy && delegate()}
                placeholder="delegate task to swarm…"
                className="flex-1 bg-black border border-white/10 px-2 py-1.5 font-mono-term text-[11px] text-zinc-200 outline-none focus:border-amber-500/40"
              />
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="bg-black border border-white/10 px-1 font-mono-term text-[10px] text-zinc-400 outline-none"
              >
                <option value="">auto</option>
                {AGENTS_ORDER.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
              <button
                onClick={delegate}
                disabled={busy || !task.trim()}
                className="border border-amber-500/30 px-3 text-amber-400 disabled:text-zinc-600 hover:bg-amber-500/5 flex items-center gap-1"
              >
                {busy ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
              </button>
            </div>
            {result && (
              <div className={`font-mono-term text-[10px] flex items-center gap-1.5 ${result.ok ? "text-emerald-400" : "text-rose-400"}`}>
                {result.ok
                  ? <><CheckCircle size={10} /> routed → {result.routed_to}</>
                  : <><AlertTriangle size={10} /> {result.error}</>
                }
              </div>
            )}
          </div>
        </>
      )}

      {/* ── AGENTS tab ── */}
      {tab === "agents" && (
        <div className="space-y-0">
          {agentEntries.length === 0 && (
            <p className="font-mono-term text-[11px] text-zinc-600 text-center py-6">
              no agents registered — is gateway_v3 running?
            </p>
          )}
          {agentEntries.map((entry) => (
            <AgentRow key={entry[0]} agent={entry} />
          ))}
          <button
            onClick={loadAgents}
            className="mt-2 w-full font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500 border border-white/10 py-1.5 hover:text-amber-400 flex items-center justify-center gap-1"
          >
            <RefreshCw size={9} /> refresh
          </button>
        </div>
      )}

      {/* ── GITHUB tab ── */}
      {tab === "github" && (
        <div className="space-y-3">
          {ghInfo && !ghInfo.error && (
            <div className="font-mono-term text-[11px] space-y-1 border border-white/10 p-2">
              <div className="text-zinc-200 font-bold">{ghInfo.name}</div>
              <div className="text-zinc-500 flex gap-4">
                <span>⭐ {ghInfo.stars}</span>
                <span>🍴 {ghInfo.forks}</span>
                <span>🐛 {ghInfo.open_issues}</span>
              </div>
              <div className="text-zinc-600 text-[10px]">
                {ghInfo.default_branch} · updated {new Date(ghInfo.updated).toLocaleDateString()}
              </div>
            </div>
          )}
          {ghInfo?.error && (
            <div className="font-mono-term text-[10px] text-rose-400 border border-rose-500/20 p-2">
              {ghInfo.error}
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={loadGithub}
              disabled={busy}
              className="flex-1 font-mono-term text-[10px] uppercase tracking-[0.2em] text-zinc-300 border border-white/10 py-2 hover:bg-white/5 flex items-center justify-center gap-1.5"
            >
              <Github size={11} /> repo status
            </button>
            <button
              onClick={syncMemory}
              disabled={busy}
              className="flex-1 font-mono-term text-[10px] uppercase tracking-[0.2em] text-zinc-300 border border-white/10 py-2 hover:bg-white/5 flex items-center justify-center gap-1.5"
            >
              {busy ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
              sync memory
            </button>
          </div>
          {result && (
            <div className={`font-mono-term text-[10px] flex items-center gap-1.5 ${result.ok ? "text-emerald-400" : "text-rose-400"}`}>
              {result.ok
                ? <><CheckCircle size={10} /> {result.routed_to}</>
                : <><AlertTriangle size={10} /> {result.error}</>}
            </div>
          )}
        </div>
      )}

      {/* ── CLAUDE tab ── */}
      {tab === "claude" && (
        <div className="space-y-3">
          <div className="font-mono-term text-[10px] text-zinc-500 border border-white/5 p-2 leading-relaxed">
            CLAUDE-TRAINER generates synthetic KAIROS training data (~$0.003/batch of 5).
            CLAUDE-ARCHITECT reviews modules + proposes upgrades.
          </div>
          <div className="flex gap-2">
            <button
              onClick={trainClaude}
              disabled={busy}
              className="flex-1 font-mono-term text-[10px] uppercase tracking-[0.2em] text-amber-400 border border-amber-500/30 py-2 hover:bg-amber-500/5 flex items-center justify-center gap-1.5"
            >
              {busy ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
              train batch (5)
            </button>
            <button
              onClick={() => { loadElite(); setTab("claude"); }}
              className="flex-1 font-mono-term text-[10px] uppercase tracking-[0.2em] text-zinc-300 border border-white/10 py-2 hover:bg-white/5"
            >
              elite archive
            </button>
          </div>
          {result && (
            <div className={`font-mono-term text-[10px] flex items-center gap-1.5 ${result.ok ? "text-emerald-400" : "text-rose-400"}`}>
              {result.ok
                ? <><CheckCircle size={10} /> {result.routed_to}</>
                : <><AlertTriangle size={10} /> {result.error}</>}
            </div>
          )}
          {elite.length > 0 && (
            <div className="space-y-1 mt-1">
              <div className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-600">
                elite cycles ({elite.length})
              </div>
              {elite.slice(-5).map((c) => (
                <div key={c.id} className="font-mono-term text-[10px] border border-white/5 p-1.5 flex justify-between">
                  <span className="text-zinc-400 truncate flex-1">#{c.id} {c.proposal?.slice(0, 60)}</span>
                  <span className="text-emerald-400 shrink-0 ml-2">{c.score?.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
};
