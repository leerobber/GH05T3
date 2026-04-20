import React, { useState } from "react";
import { Panel } from "./primitives";
import { cassandraRun } from "../../lib/ghostApi";
import { Flame } from "lucide-react";

export const CassandraPanel = () => {
  const [scenario, setScenario] = useState("We ship KAIROS live with 10 nightly cycles on TatorTot. No static IP, Tailscale only.");
  const [autopsy, setAutopsy] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!scenario.trim()) return;
    setLoading(true);
    try {
      const d = await cassandraRun(scenario);
      setAutopsy(d.autopsy);
    } catch (e) {
      setAutopsy(`[oracle offline] ${e?.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      testid="cassandra-panel"
      title="Cassandra · pre-mortem"
      sub="writes the failure story before you ship"
      crimson
      right={
        <button
          data-testid="cassandra-run-btn"
          onClick={run}
          disabled={loading}
          className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-rose-300 hover:text-rose-200 disabled:text-zinc-600 border border-rose-500/30 px-2.5 py-1 flex items-center gap-1.5"
        >
          {loading ? <span className="ascii-spin" /> : <Flame size={11} />}
          foretell
        </button>
      }
    >
      <textarea
        data-testid="cassandra-scenario"
        value={scenario}
        onChange={(e) => setScenario(e.target.value)}
        rows={3}
        placeholder="what are we about to ship?"
        className="w-full bg-black border border-white/10 p-2.5 font-mono-term text-[11px] text-zinc-200 outline-none focus:border-rose-500/50 resize-none"
      />
      {autopsy && (
        <div className="mt-3 border-l border-rose-500/40 pl-3 font-sans text-[13px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
          {autopsy}
        </div>
      )}
    </Panel>
  );
};
