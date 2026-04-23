import React, { useCallback, useEffect, useState } from "react";
import "@/App.css";
import { toast, Toaster } from "sonner";
import { fetchState, pclTick, runKairosCycle, runNightly } from "./lib/ghostApi";
import { useGhostWS } from "./lib/useGhostWS";
import { ChatInterface } from "./components/ghost/ChatInterface";
import {
  AutotelicPanel, GhostProtocolPanel, HardwarePanel, HcmPanel,
  IdentityHeader, KairosPanel, MemoryPalacePanel, NightlyPanel,
  PclPanel, ScoreboardPanel, SeancePanel, SubAgentsPanel, TwinEnginePanel,
} from "./components/ghost/panels";
import { HcmCloudPanel } from "./components/ghost/HcmCloudPanel";
import { GhostShellPanel } from "./components/ghost/GhostShellPanel";
import { CassandraPanel } from "./components/ghost/CassandraPanel";
import { StegoPanel } from "./components/ghost/StegoPanel";
import { TelegramPanel } from "./components/ghost/TelegramPanel";
import { TranscriptPanel } from "./components/ghost/TranscriptPanel";
import { MemoryStreamPanel } from "./components/ghost/MemoryStreamPanel";
import { JournalPanel } from "./components/ghost/JournalPanel";
import { LlmConfigPanel } from "./components/ghost/LlmConfigPanel";
import { CompanionPanel } from "./components/ghost/CompanionPanel";
import { GhostEyePanel } from "./components/ghost/GhostEyePanel";
import { WhisperPanel } from "./components/ghost/WhisperPanel";
import { SetupNudgeModal } from "./components/ghost/SetupNudgeModal";
import { OllamaPanel } from "./components/ghost/OllamaPanel";
import { CoderPanel } from "./components/ghost/CoderPanel";

function speakWhisper(data) {
  try {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    if (localStorage.getItem("gh05t3.whisper.enabled") === "0") return;
    const text = (data?.text || "").slice(0, 1000);
    if (!text) return;
    const utt = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const pref = localStorage.getItem("gh05t3.whisper.voice");
    const voice =
      (pref && voices.find((v) => v.name === pref)) ||
      voices.find((v) => /neural|natural|Ava|Aria|Samantha|Zira/i.test(v.name)) ||
      voices.find((v) => v.lang?.startsWith("en"));
    if (voice) utt.voice = voice;
    utt.volume = parseFloat(localStorage.getItem("gh05t3.whisper.volume") || "1");
    utt.rate = data?.priority === "high" ? 1.05 : 1.0;
    utt.pitch = 1.0;
    if (data?.priority === "high") window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utt);
    // notify UI
    window.dispatchEvent(new CustomEvent("ghost-whisper", { detail: data }));
  } catch (e) {
    console.warn("whisper failed", e);
  }
}

function App() {
  const [state, setState] = useState(null);
  const [engineHint, setEngineHint] = useState(null);
  const [running, setRunning] = useState({ kairos: false, nightly: false });
  const [wsLive, setWsLive] = useState(false);
  const [cycleTick, setCycleTick] = useState(0);
  const [memTick, setMemTick] = useState(0);
  const [journalTick, setJournalTick] = useState(0);
  const [eyeFrame, setEyeFrame] = useState(null);

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
  }, [refresh]);

  useGhostWS((event, data) => {
    setWsLive(true);
    if (event === "hello" || event === "state_delta") {
      setState((prev) => ({ ...(prev || {}), ...(data || {}) }));
    } else if (event === "kairos_cycle") {
      setCycleTick((n) => n + 1);
      toast(`KAIROS #${data.cycle_num} · ${data.verdict} · ${data.final_score}${data.elite ? " · ELITE" : ""}`, {
        description: data.proposal,
      });
    } else if (event === "nightly") {
      toast("Nightly amplifiers fired", {
        description: `+${data.delta.memory_palace} loci · +${data.delta.hcm_vectors} vectors · +${data.delta.feynman_concepts} concepts`,
      });
    } else if (event === "seance") {
      toast.error(`Séance captured: ${data.domain}`, { description: data.lesson });
    } else if (event === "memory_added") {
      setMemTick((n) => n + 1);
    } else if (event === "reflection") {
      setJournalTick((n) => n + 1);
      toast("Self-reflection written", { description: data.text?.slice(0, 120) });
    } else if (event === "strangeloop") {
      toast(`StrangeLoop: ${data.verdict}`, {
        description: `alignment ${data.alignment?.toFixed?.(2)}`,
      });
    } else if (event === "distill") {
      toast("Distiller synthesized a rule", { description: data.rule });
      setMemTick((n) => n + 1);
    } else if (event === "ghosteye") {
      setEyeFrame(data);
    } else if (event === "ghosteye_whisper") {
      speakWhisper(data);
    } else if (event === "ghosteye_stuck") {
      toast("GhostEye: stuck detected", {
        description: `KAIROS #${data.cycle}: ${data.proposal}`,
      });
    } else if (event === "cassandra") {
      // no toast — displayed inline
    }
  });

  const onRunKairos = async () => {
    setRunning((r) => ({ ...r, kairos: true }));
    try {
      await runKairosCycle();
    } catch (e) {
      toast.error("KAIROS failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setRunning((r) => ({ ...r, kairos: false }));
      refresh();
    }
  };
  const onRunNightly = async () => {
    setRunning((r) => ({ ...r, nightly: true }));
    try {
      await runNightly();
    } catch (e) {
      toast.error("Nightly failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setRunning((r) => ({ ...r, nightly: false }));
      refresh();
    }
  };
  const onPclTick = async (s) => {
    try { await pclTick(s); } catch {}
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
      <SetupNudgeModal />
      <Toaster
        theme="dark" position="bottom-right"
        toastOptions={{
          style: {
            background: "#0f0f11", border: "1px solid rgba(245,158,11,0.3)",
            color: "#fafafa", fontFamily: "JetBrains Mono, monospace", fontSize: "12px",
          },
        }}
      />
      <div className="max-w-[1680px] mx-auto p-6 md:p-8">
        <div className="mb-6 flex items-start gap-3">
          <div className="flex-1">
            <IdentityHeader identity={state.identity} />
          </div>
        </div>
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-500 flex items-center gap-2">
            <span className={`dot ${wsLive ? "dot-active" : "dot-idle"}`} /> telemetry: {wsLive ? "live ws" : "polling"}
          </span>
          <span className="font-mono-term text-[10px] text-zinc-600">
            gateway: {state.gateway?.ollama_reachable ? "ollama" : "claude fallback"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-3 flex flex-col gap-6">
            <HardwarePanel hw={state.hardware_tatortot} />
            <SubAgentsPanel agents={state.sub_agents} />
            <GhostProtocolPanel gp={state.ghost_protocol} />
            <SeancePanel seance={state.seance} />
            <TelegramPanel />
            <CompanionPanel />
            <GhostEyePanel liveFrame={eyeFrame} />
          </div>
          <div className="md:col-span-6 flex flex-col gap-6">
            <div className="panel">
              <ChatInterface onEngine={(e) => setEngineHint(e)} />
            </div>
            <TwinEnginePanel twin={state.twin_engine} lastEngine={engineHint} />
            <KairosPanel kairos={state.kairos} onRun={onRunKairos} running={running.kairos} />
            <TranscriptPanel refreshKey={cycleTick} />
            <CassandraPanel />
            <GhostShellPanel />
            <NightlyPanel
              schedule={state.schedule}
              onRun={onRunNightly}
              running={running.nightly}
              scheduler={state.scheduler}
              gateway={state.gateway}
            />
            <OllamaPanel />
            <CoderPanel />
          </div>
          <div className="md:col-span-3 flex flex-col gap-6">
            <MemoryPalacePanel mp={state.memory_palace} />
            <HcmPanel hcm={state.hcm} feynman={state.feynman} />
            <HcmCloudPanel refreshKey={cycleTick} />
            <MemoryStreamPanel refreshKey={memTick} />
            <JournalPanel refreshKey={journalTick} />
            <PclPanel pcl={state.pcl} onTick={onPclTick} />
            <WhisperPanel />
            <AutotelicPanel goals={state.autotelic_goals} />
            <LlmConfigPanel />
            <StegoPanel />
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
