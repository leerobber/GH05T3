import React, { useEffect, useMemo, useState } from "react";
import { Panel } from "./primitives";
import { swarmState, swarmRun, swarmValidate, swarmReset } from "../../lib/ghostApi";
import {
  Users, Play, RotateCcw, CheckCircle2, AlertCircle, Loader2, Zap,
} from "lucide-react";

const ROLE_COLORS = {
  DBT: "#e11d48", // crimson — Debater
  COD: "#22d3ee", // cyan — Coder
  ETH: "#f59e0b", // amber — Ethicist
  MEM: "#c4b5fd", // violet — Memory
};

const TASK_TYPES = [
  { id: "debate", label: "debate" },
  { id: "code", label: "code" },
  { id: "ethics", label: "ethics" },
  { id: "memory", label: "memory" },
];

/** Radial topology graph — SVG, deterministic positions. */
const TopologySVG = ({ agents, pattern }) => {
  const size = 180;
  const r = 62;
  const cx = size / 2;
  const cy = size / 2;
  const n = agents.length;
  const pos = useMemo(() => {
    const out = {};
    agents.forEach((a, i) => {
      const theta = (i / n) * Math.PI * 2 - Math.PI / 2;
      out[a.agent_id] = {
        x: cx + Math.cos(theta) * r,
        y: cy + Math.sin(theta) * r,
      };
    });
    return out;
  }, [agents, n]);

  // Derive edges from pattern
  const edges = useMemo(() => {
    const ids = agents.map((a) => a.agent_id);
    if (pattern === "ring") {
      return ids.map((a, i) => [a, ids[(i + 1) % n]]);
    }
    if (pattern === "line") {
      return ids.slice(0, -1).map((a, i) => [a, ids[i + 1]]);
    }
    if (pattern === "star") {
      return ids.slice(1).map((a) => [ids[0], a]);
    }
    if (pattern === "hub") {
      return ids.slice(1).map((a) => [ids[0], a]);
    }
    return [];
  }, [agents, pattern, n]);

  return (
    <svg
      data-testid="swarm-topology-svg"
      viewBox={`0 0 ${size} ${size}`}
      className="w-full h-44"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#a1a1aa" />
        </marker>
      </defs>
      {edges.map(([a, b], idx) => {
        const p1 = pos[a];
        const p2 = pos[b];
        if (!p1 || !p2) return null;
        return (
          <line
            key={idx}
            x1={p1.x}
            y1={p1.y}
            x2={p2.x}
            y2={p2.y}
            stroke="#52525b"
            strokeWidth="1"
            markerEnd="url(#arrow)"
            opacity={0.6}
          />
        );
      })}
      {agents.map((a) => {
        const p = pos[a.agent_id];
        const color = ROLE_COLORS[a.agent_id] || "#fff";
        const opacity = a.dormant ? 0.35 : 1;
        return (
          <g key={a.agent_id} opacity={opacity}>
            <circle cx={p.x} cy={p.y} r="14" fill="#0f0f11" stroke={color} strokeWidth="1.5" />
            <text
              x={p.x}
              y={p.y + 4}
              textAnchor="middle"
              fontSize="10"
              fill={color}
              fontFamily="JetBrains Mono, monospace"
            >
              {a.agent_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

export const SwarmPanel = () => {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [taskType, setTaskType] = useState("debate");
  const [prompt, setPrompt] = useState("");
  const [lastRun, setLastRun] = useState(null);
  const [validation, setValidation] = useState(null);

  const load = async () => {
    try {
      setState(await swarmState());
    } catch {
      /* ignore */
    }
  };
  useEffect(() => {
    load();
    const iv = setInterval(load, 8000);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setLastRun(null);
    try {
      const r = await swarmRun(taskType, prompt.trim());
      setLastRun(r);
      load();
    } catch (e) {
      setLastRun({ error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const validate = async (n = 20) => {
    setBusy(true);
    setValidation(null);
    try {
      const r = await swarmValidate(n);
      setValidation(r);
      load();
    } catch (e) {
      setValidation({ error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      await swarmReset();
      setLastRun(null);
      setValidation(null);
      load();
    } finally {
      setBusy(false);
    }
  };

  if (!state) return null;

  const agents = state.agents || [];
  const topology = state.current_topology || "ring";
  const shifts = state.topology_shifts ?? 0;

  return (
    <Panel
      testid="swarm-panel"
      title="SA³ · agentic swarm"
      sub={`topology: ${topology} · shifts: ${shifts}`}
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 flex items-center gap-1.5">
          <Users size={10} /> {agents.length} agents
        </span>
      }
    >
      <TopologySVG agents={agents} pattern={topology} />

      {/* Agent leaderboard */}
      <div className="mt-3 space-y-1.5">
        {agents.map((a) => {
          const pct = Math.max(0, Math.min(100, (a.tokens / 200) * 100));
          const color = ROLE_COLORS[a.agent_id] || "#fff";
          return (
            <div
              key={a.agent_id}
              data-testid={`swarm-agent-${a.agent_id}`}
              className="border border-white/10 p-2"
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="font-mono-term text-[11px] flex items-center gap-1.5"
                  style={{ color }}
                >
                  {a.agent_id} · {a.role}
                  {a.dormant && (
                    <span className="text-rose-400 text-[9px] tracking-[0.2em]">
                      · DORMANT
                    </span>
                  )}
                </span>
                <span className="font-mono-term text-[10px] text-zinc-400">
                  {a.tokens} tok · {Math.round(a.success_rate * 100)}% ·{" "}
                  {a.total_tasks}t
                </span>
              </div>
              <div className="w-full h-[2px] bg-white/10">
                <div
                  className="h-full"
                  style={{
                    width: `${pct}%`,
                    background: color,
                    transition: "width 400ms ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Task runner */}
      <div className="mt-3 space-y-2">
        <div className="flex gap-1">
          {TASK_TYPES.map((t) => (
            <button
              key={t.id}
              data-testid={`swarm-type-${t.id}`}
              onClick={() => setTaskType(t.id)}
              className={`flex-1 font-mono-term text-[10px] tracking-[0.2em] uppercase px-2 py-1 border ${
                taskType === t.id
                  ? "border-amber-500/50 text-amber-400 bg-amber-500/5"
                  : "border-white/10 text-zinc-400"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <textarea
          data-testid="swarm-prompt-input"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={2}
          placeholder="pose a task — the swarm assembles a topology and scores itself…"
          className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50 resize-none"
        />
        <div className="flex gap-2">
          <button
            data-testid="swarm-run-btn"
            onClick={run}
            disabled={busy || !prompt.trim()}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-3 py-2 flex items-center justify-center gap-2 hover:bg-amber-500/5"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            run task
          </button>
          <button
            data-testid="swarm-validate-btn"
            onClick={() => validate(20)}
            disabled={busy}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-300 disabled:text-zinc-600 border border-white/10 px-3 py-2 flex items-center gap-1.5 hover:bg-white/5"
          >
            <Zap size={11} /> validate 20
          </button>
          <button
            data-testid="swarm-reset-btn"
            onClick={reset}
            disabled={busy}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-rose-400 disabled:text-zinc-600 border border-rose-500/30 px-2 py-2 hover:bg-rose-500/5"
            title="reset tokens + dormancy"
          >
            <RotateCcw size={11} />
          </button>
        </div>
      </div>

      {lastRun && !lastRun.error && (
        <div
          data-testid="swarm-last-run"
          className={`mt-3 font-mono-term text-[11px] p-2 border ${
            lastRun.success
              ? "border-emerald-500/30 text-emerald-300"
              : "border-amber-500/30 text-amber-300"
          }`}
        >
          <div className="flex items-center gap-1.5 mb-1">
            {lastRun.success ? (
              <CheckCircle2 size={12} />
            ) : (
              <AlertCircle size={12} />
            )}
            {lastRun.task_type} · {lastRun.topology} · score {lastRun.score}
          </div>
          <div className="space-y-0.5 text-zinc-400">
            {(lastRun.responses || []).map((r, i) => (
              <div key={i} className="truncate">
                <span style={{ color: ROLE_COLORS[r.agent_id] }}>{r.agent_id}</span>
                <span className="text-zinc-600">
                  {" "}
                  · {r.tokens_delta > 0 ? `+${r.tokens_delta}` : r.tokens_delta}·{" "}
                </span>
                {r.text.slice(0, 90)}
              </div>
            ))}
          </div>
        </div>
      )}

      {validation && !validation.error && (
        <div
          data-testid="swarm-validation"
          className="mt-3 font-mono-term text-[11px] p-2 border border-amber-500/30 text-amber-300"
        >
          <div className="mb-1">
            success rate: <b>{Math.round(validation.success_rate * 100)}%</b> of{" "}
            {validation.n} · topologies: {validation.topologies_seen?.join(", ")} ·
            crashes: {validation.crashes}
          </div>
          <div className="text-zinc-400 space-y-0.5">
            {Object.entries(validation.per_type || {}).map(([t, v]) => (
              <div key={t}>
                {t}: {v.success}/{v.total} · avg {v.avg_score}
              </div>
            ))}
          </div>
        </div>
      )}

      {(lastRun?.error || validation?.error) && (
        <div className="mt-3 font-mono-term text-[11px] p-2 border border-rose-500/30 text-rose-300 flex items-center gap-1.5">
          <AlertCircle size={12} />
          {lastRun?.error || validation?.error}
        </div>
      )}
    </Panel>
  );
};
