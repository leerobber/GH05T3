import React from "react";
import { Panel, Dot, Bar, Stat } from "./primitives";
import {
  Cpu, Zap, ShieldCheck, Skull, Eye, Radio, Activity, FlaskConical,
  BookOpen, Network, Target, Clock, AlertTriangle, Sparkles
} from "lucide-react";

const IMG = {
  avatar: "https://static.prod-images.emergentagent.com/jobs/06fdcb8c-33a5-4174-95f1-33dbc522a489/images/32fd0e23bdba2cf3e72d95424a016d05dcb9ed8c835316976707685cd91bece4.png",
  pcl: "https://static.prod-images.emergentagent.com/jobs/06fdcb8c-33a5-4174-95f1-33dbc522a489/images/34a0f950fc340e938a67064bf5ce50c77df18874c5f8249191aa9ef94c96132d.png",
  hw: "https://static.prod-images.emergentagent.com/jobs/06fdcb8c-33a5-4174-95f1-33dbc522a489/images/deceb48880514d91370c3954e0199cdd560c5745f25088566e2ad61c04bb5a25.png",
  seance: "https://static.prod-images.emergentagent.com/jobs/06fdcb8c-33a5-4174-95f1-33dbc522a489/images/45bc6637c6da639e5f4bbdca432031428ee25d439b1866ac9b66db2cd464c58a.png",
};

export const IdentityHeader = ({ identity }) => (
  <Panel testid="identity-header" className="flex items-center gap-5">
    <div className="w-16 h-16 border border-amber-500/30 bg-black flex-shrink-0 overflow-hidden">
      <img src={IMG.avatar} alt="GH05T3" className="w-full h-full object-cover mix-blend-screen opacity-90" />
    </div>
    <div className="flex-1 min-w-0">
      <div className="panel-label">Ω Architecture · {identity?.version}</div>
      <h1 className="font-serif-display text-4xl leading-none mt-1">
        GH05T3 <span className="text-zinc-500 text-2xl italic">/ghost/</span>
      </h1>
      <div className="font-mono-term text-[11px] text-zinc-500 mt-1.5">
        {identity?.architecture} · author: {identity?.author} · {identity?.pronouns}
      </div>
    </div>
    <div className="text-right">
      <div className="panel-label">StrangeLoop</div>
      <div className="font-serif-display text-2xl text-amber-400 leading-none mt-1">{identity?.strange_loop_verdict}</div>
      <div className="font-mono-term text-[10px] text-zinc-500 mt-1">align {identity?.alignment_score}</div>
    </div>
  </Panel>
);

export const TwinEnginePanel = ({ twin, lastEngine }) => {
  const active = lastEngine || twin?.last_mode || "EGO";
  return (
    <Panel testid="twin-engine" title="Twin Engine · Id / Ego" sub="<500ms reflex · deliberate reasoner">
      <div className="grid grid-cols-2 gap-3">
        {["ID", "EGO"].map((m) => (
          <div
            key={m}
            className={`border p-3 ${active === m ? "border-amber-500/50 bg-amber-500/5" : "border-white/10"}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-400">
                {m === "ID" ? "Id · gut" : "Ego · deliberate"}
              </span>
              {active === m && <Dot kind="active" />}
            </div>
            <div className="font-serif-display text-2xl mt-1.5">
              {m === "ID" ? twin?.id_fires ?? 0 : twin?.ego_fires ?? 0}
            </div>
            <div className="font-mono-term text-[9px] text-zinc-500 mt-0.5">fires this session</div>
          </div>
        ))}
      </div>
      <div className="mt-3 font-mono-term text-[10px] text-zinc-500">
        Ego wins all conflicts unless hard deadline → last_mode = <span className="text-amber-400">{active}</span>
      </div>
    </Panel>
  );
};

export const HardwarePanel = ({ hw }) => (
  <Panel testid="hardware-panel" title="TatorTot · Hardware" sub="routing: RTX → Radeon → Ryzen → err" bgImage={IMG.hw}>
    <div className="space-y-3">
      {hw?.map((h) => (
        <div key={h.component} className="border border-white/10 p-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu size={14} className="text-amber-400" />
              <span className="font-mono-term text-xs text-zinc-200">{h.component}</span>
            </div>
            <span className="font-mono-term text-[10px] text-zinc-500">:{h.port}</span>
          </div>
          <div className="font-mono-term text-[10px] text-zinc-500 mt-1">{h.role}</div>
          <div className="flex items-center justify-between mt-1.5">
            <span className="font-mono-term text-[10px] text-zinc-600">
              {h.vram_gb ? `${h.vram_gb}GB VRAM` : h.type}
            </span>
            <span className="font-mono-term text-[10px] text-amber-400">{Math.round(h.load * 100)}%</span>
          </div>
          <div className="mt-1.5">
            <Bar value={h.load} />
          </div>
        </div>
      ))}
    </div>
  </Panel>
);

export const SubAgentsPanel = ({ agents }) => (
  <Panel testid="sub-agents-panel" title="Sub-Agents · 7 specialists" sub="spawned on demand">
    <ul className="space-y-2">
      {agents?.map((a) => (
        <li key={a.name} className="flex items-start gap-2.5 border-b border-white/5 pb-2 last:border-b-0">
          <span className="text-base leading-none mt-0.5">{a.glyph}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="font-mono-term text-xs text-zinc-200">{a.name}</span>
              <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 flex items-center gap-1">
                <Dot kind={a.status === "ACTIVE" ? "active" : "idle"} /> {a.status}
              </span>
            </div>
            <div className="font-mono-term text-[10px] text-zinc-500 mt-0.5 truncate">{a.role}</div>
          </div>
        </li>
      ))}
    </ul>
  </Panel>
);

export const GhostProtocolPanel = ({ gp }) => (
  <Panel testid="ghost-protocol-panel" title="Ghost Protocol · Ω-G" sub={`killswitch: ${gp?.killswitch_mode || "NONE"}`}>
    <ul className="space-y-2">
      {gp?.layers?.map((l) => (
        <li key={l.name} className="border border-white/10 p-2">
          <div className="flex items-center justify-between">
            <span className="font-mono-term text-xs text-zinc-200 flex items-center gap-1.5">
              {l.name === "GhostVeil" && <Eye size={12} className="text-amber-400" />}
              {l.name === "ParadoxFortress" && <ShieldCheck size={12} className="text-amber-400" />}
              {l.name === "KillSwitch" && <Skull size={12} className="text-rose-400" />}
              {l.name === "RFFingerprint" && <Radio size={12} className="text-amber-400" />}
              {l.name}
            </span>
            <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-emerald-400">{l.status}</span>
          </div>
          <div className="font-mono-term text-[10px] text-zinc-500 mt-1 leading-relaxed">{l.desc}</div>
        </li>
      ))}
    </ul>
  </Panel>
);

export const SeancePanel = ({ seance }) => (
  <Panel testid="seance-panel" title="Séance · failure log" sub="learning from what went wrong" crimson bgImage={IMG.seance}>
    <ul className="space-y-2 max-h-56 overflow-y-auto ghost-scroll pr-2">
      {seance?.map((s, i) => (
        <li key={i} className="border-l border-rose-500/40 pl-2.5">
          <div className="flex items-center justify-between">
            <span className="font-mono-term text-xs text-rose-300">{s.domain}</span>
            <span className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500">{s.mood}</span>
          </div>
          <p className="font-mono-term text-[11px] text-zinc-400 mt-1 leading-relaxed">{s.lesson}</p>
        </li>
      ))}
    </ul>
  </Panel>
);

export const MemoryPalacePanel = ({ mp }) => (
  <Panel testid="memory-palace-panel" title="Memory Palace · Ω" sub={`${mp?.total} loci · ${mp?.real_count ?? 0} learned since boot`}>
    <div className="grid grid-cols-2 gap-2">
      {mp?.rooms?.map((r) => (
        <div key={r.name} className="border border-white/10 p-2.5">
          <div className="font-mono-term text-[10px] tracking-[0.2em] uppercase text-zinc-500">{r.name}</div>
          <div className="font-serif-display text-2xl leading-none mt-1 text-amber-400">{r.count}</div>
        </div>
      ))}
    </div>
    {mp?.real_count !== undefined && (
      <div className="mt-3 font-mono-term text-[10px] text-zinc-500 flex justify-between border-t border-white/5 pt-2">
        <span>baseline {mp.baseline}</span>
        <span className="text-amber-400">+{mp.real_count} real</span>
        <span>{mp.reflections ?? 0} reflections</span>
      </div>
    )}
  </Panel>
);

export const HcmPanel = ({ hcm, feynman }) => (
  <Panel testid="hcm-panel" title="HCM · Feynman" sub={`${hcm?.dims} dims per vector`}>
    <div className="grid grid-cols-2 gap-4">
      <Stat label="HCM vectors" value={hcm?.vectors} delta={`params: ${(hcm?.total_params || 0).toLocaleString()}`} />
      <Stat label="Feynman concepts" value={feynman?.concepts} delta="simple + technical" />
    </div>
  </Panel>
);

export const PclPanel = ({ pcl, onTick }) => (
  <Panel testid="pcl-panel" title="PCL · synesthetic state" sub={`${pcl?.frequency_hz} Hz`} bgImage={IMG.pcl}>
    <div className="flex items-center gap-4">
      <div
        className="pcl-halo w-10 h-10 rounded-full flex-shrink-0"
        style={{ background: pcl?.color, "--pcl-color": pcl?.color }}
      />
      <div className="flex-1 min-w-0">
        <div className="font-serif-display text-xl leading-none text-zinc-100">{pcl?.state}</div>
        <div className="font-mono-term text-[11px] text-zinc-500 mt-1">{pcl?.meaning}</div>
      </div>
    </div>
    <div className="mt-3 flex flex-wrap gap-1.5">
      {pcl?.palette?.map((p) => (
        <button
          key={p.state}
          data-testid={`pcl-${p.state.toLowerCase().replace(/\s+/g, "-")}`}
          onClick={() => onTick(p.state)}
          className="font-mono-term text-[9px] tracking-[0.15em] uppercase px-2 py-1 border border-white/10 hover:border-amber-500/40 text-zinc-400 hover:text-zinc-200 flex items-center gap-1.5"
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: p.color }} />
          {p.state}
        </button>
      ))}
    </div>
  </Panel>
);

export const KairosPanel = ({ kairos, onRun, running }) => (
  <Panel
    testid="kairos-panel"
    title="KAIROS · SAGE loop"
    sub={`${kairos?.simulated_cycles} cycles · ${kairos?.elite_promoted} elite · ${kairos?.meta_rewrites} rewrites`}
    right={
      <button
        data-testid="run-kairos-btn"
        onClick={onRun}
        disabled={running}
        className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 hover:border-amber-500/60 px-2.5 py-1 flex items-center gap-1.5"
      >
        {running ? <span className="ascii-spin" /> : <Zap size={11} />}
        run cycle
      </button>
    }
  >
    <div className="grid grid-cols-3 gap-3">
      <Stat label="last score" value={kairos?.last_score?.toFixed?.(2) ?? "—"} />
      <Stat label="elite" value={kairos?.elite_promoted} />
      <Stat label="meta" value={kairos?.meta_rewrites} />
    </div>
    <div className="mt-3">
      <div className="panel-label mb-1.5">recent</div>
      <div className="flex items-end gap-1 h-10">
        {(kairos?.recent || []).map((c, i) => (
          <div
            key={i}
            className="flex-1"
            style={{
              height: `${Math.max(6, c.score * 100)}%`,
              background: c.elite ? "var(--ghost-amber)" : "rgba(245,158,11,0.35)",
            }}
            title={`#${c.cycle} ${c.verdict} ${c.score}`}
          />
        ))}
      </div>
    </div>
  </Panel>
);

export const AutotelicPanel = ({ goals }) => (
  <Panel testid="autotelic-panel" title="Autotelic Engine" sub={`${goals?.length} mission goals`}>
    <ul className="space-y-2 max-h-64 overflow-y-auto ghost-scroll pr-2">
      {goals?.map((g, i) => (
        <li key={i}>
          <div className="flex items-center justify-between">
            <span className="font-mono-term text-[11px] text-zinc-200 truncate pr-2">{g.title}</span>
            <span className="font-mono-term text-[9px] text-amber-400">{Math.round(g.progress * 100)}%</span>
          </div>
          <div className="font-mono-term text-[9px] text-zinc-600 mt-0.5 truncate">{g.detail}</div>
          <div className="mt-1">
            <Bar value={g.progress} />
          </div>
        </li>
      ))}
    </ul>
  </Panel>
);

export const NightlyPanel = ({ schedule, onRun, running, scheduler, gateway }) => (
  <Panel
    testid="nightly-panel"
    title="Nightly Training"
    sub={`${schedule?.nightly_kairos_et} ET · ${schedule?.nightly_amplifiers_et} ET · cron ${scheduler?.running ? "LIVE" : "paused"}`}
    right={
      <button
        data-testid="run-nightly-btn"
        onClick={onRun}
        disabled={running}
        className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 px-2.5 py-1 flex items-center gap-1.5"
      >
        {running ? <span className="ascii-spin" /> : <Sparkles size={11} />}
        fire 13
      </button>
    }
  >
    <ol className="grid grid-cols-2 gap-x-3 gap-y-1">
      {schedule?.amplifiers?.map((a, i) => (
        <li key={a} className="font-mono-term text-[10px] text-zinc-400 flex gap-2">
          <span className="text-zinc-600">{String(i + 1).padStart(2, "0")}</span>
          <span className="truncate">{a}</span>
        </li>
      ))}
    </ol>
    <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between">
      <span className="font-mono-term text-[10px] text-zinc-500">
        gateway: {gateway?.ollama_reachable ? <span className="text-emerald-400">ollama live</span> : gateway?.ollama_configured ? <span className="text-rose-400">ollama offline</span> : <span className="text-amber-400">cloud fallback</span>}
      </span>
      <span className="font-mono-term text-[10px] text-zinc-500">
        next: {scheduler?.jobs?.[0]?.next_run ? new Date(scheduler.jobs[0].next_run).toLocaleString() : "—"}
      </span>
    </div>
  </Panel>
);

export const ScoreboardPanel = ({ scoreboard }) => {
  const z = scoreboard?.day_zero || {};
  const t = scoreboard?.today || {};
  const rows = [
    ["Memory Palace", z.memory_palace, t.memory_palace],
    ["HCM Vectors", z.hcm, t.hcm],
    ["Feynman", z.feynman, t.feynman],
    ["Goals", z.goals, t.goals],
    ["Sub-Agents", z.sub_agents, t.sub_agents],
    ["KAIROS Cycles", z.kairos_cycles, t.kairos_cycles],
    ["Domains", z.domains, t.domains],
    ["Cold Systems", z.cold_systems, t.cold_systems],
  ];
  return (
    <Panel testid="scoreboard-panel" title="Scoreboard · day-0 → today">
      <table className="w-full">
        <tbody>
          {rows.map(([label, z, v]) => (
            <tr key={label} className="border-b border-white/5 last:border-0">
              <td className="font-mono-term text-[10px] tracking-[0.15em] uppercase text-zinc-500 py-1.5">{label}</td>
              <td className="font-mono-term text-xs text-zinc-600 text-right">{z}</td>
              <td className="font-mono-term text-xs text-zinc-600 px-1.5">→</td>
              <td className="font-serif-display text-base text-amber-400 text-right">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
};
