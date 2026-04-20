import React, { useCallback, useEffect, useState } from "react";
import "@/App.css";
import { toast, Toaster } from "sonner";
import {
  fetchState,
  pclTick,
  runKairosCycle,
  runNightly,
} from "./lib/ghostApi";
import { ChatInterface } from "./components/ghost/ChatInterface";
import {
  AutotelicPanel,
  GhostProtocolPanel,
  HardwarePanel,
  HcmPanel,
  IdentityHeader,
  KairosPanel,
  MemoryPalacePanel,
  NightlyPanel,
  PclPanel,
  ScoreboardPanel,
  SeancePanel,
  SubAgentsPanel,
  TwinEnginePanel,
} from "./components/ghost/panels";

function App() {
  const [state, setState] = useState(null);
  const [engineHint, setEngineHint] = useState(null);
  const [running, setRunning] = useState({ kairos: false, nightly: false });

  const refresh = useCallback(async () => {
    try {
      const s = await fetchState();
      setState(s);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const onRunKairos = async () => {
    setRunning((r) => ({ ...r, kairos: true }));
    try {
      const c = await runKairosCycle();
      toast(`KAIROS cycle #${c.cycle_num} — ${c.verdict} · ${c.final_score}${c.elite ? " · ELITE" : ""}`, {
        description: c.proposal,
      });
      await refresh();
    } catch (e) {
      toast.error("KAIROS failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setRunning((r) => ({ ...r, kairos: false }));
    }
  };

  const onRunNightly = async () => {
    setRunning((r) => ({ ...r, nightly: true }));
    try {
      const run = await runNightly();
      toast("Nightly 13-amplifier run fired", {
        description: `+${run.delta.memory_palace} loci · +${run.delta.hcm_vectors} vectors · +${run.delta.feynman_concepts} concepts · +${run.delta.kairos_cycles} cycles`,
      });
      await refresh();
    } catch (e) {
      toast.error("Nightly failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setRunning((r) => ({ ...r, nightly: false }));
    }
  };

  const onPclTick = async (s) => {
    try {
      await pclTick(s);
      await refresh();
    } catch (e) {
      toast.error("PCL tick failed");
    }
  };

  if (!state) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="boot">
        <div className="font-mono-term text-sm text-amber-400">
          <span className="ascii-spin" /> booting GH05T3 — strangeloop probe…
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="app-root">
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#0f0f11",
            border: "1px solid rgba(245,158,11,0.3)",
            color: "#fafafa",
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "12px",
          },
        }}
      />
      <div className="max-w-[1680px] mx-auto p-6 md:p-8">
        <div className="mb-6">
          <IdentityHeader identity={state.identity} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* LEFT */}
          <div className="md:col-span-3 flex flex-col gap-6">
            <HardwarePanel hw={state.hardware_tatortot} />
            <SubAgentsPanel agents={state.sub_agents} />
            <GhostProtocolPanel gp={state.ghost_protocol} />
            <SeancePanel seance={state.seance} />
          </div>

          {/* CENTER */}
          <div className="md:col-span-6 flex flex-col gap-6">
            <div className="panel">
              <ChatInterface onEngine={(e) => setEngineHint(e)} />
            </div>
            <TwinEnginePanel twin={state.twin_engine} lastEngine={engineHint} />
            <KairosPanel
              kairos={state.kairos}
              onRun={onRunKairos}
              running={running.kairos}
            />
            <NightlyPanel
              schedule={state.schedule}
              onRun={onRunNightly}
              running={running.nightly}
            />
          </div>

          {/* RIGHT */}
          <div className="md:col-span-3 flex flex-col gap-6">
            <MemoryPalacePanel mp={state.memory_palace} />
            <HcmPanel hcm={state.hcm} feynman={state.feynman} />
            <PclPanel pcl={state.pcl} onTick={onPclTick} />
            <AutotelicPanel goals={state.autotelic_goals} />
            <ScoreboardPanel scoreboard={state.scoreboard} />
          </div>
        </div>

        <footer className="mt-10 pt-4 border-t border-white/5 font-mono-term text-[10px] text-zinc-600 text-center">
          GH05T3 · {state.identity?.version} · author: {state.identity?.author} · build: active · cold systems: 0
        </footer>
      </div>
    </div>
  );
}

export default App;
