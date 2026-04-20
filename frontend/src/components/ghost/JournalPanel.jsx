import React, { useCallback, useEffect, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Feather, Eye } from "lucide-react";

export const JournalPanel = ({ refreshKey }) => {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [strange, setStrange] = useState(null);

  const load = useCallback(() => {
    api.get("/journal/recent", { params: { limit: 6 } })
      .then((r) => setEntries(r.data.entries || []))
      .catch(() => {});
  }, []);

  useEffect(load, [refreshKey, load]);

  const reflect = async () => {
    setLoading(true);
    try {
      await api.post("/journal/reflect");
      load();
    } finally {
      setLoading(false);
    }
  };
  const probe = async () => {
    setLoading(true);
    try {
      const r = await api.post("/strangeloop/probe");
      setStrange(r.data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      testid="journal-panel"
      title="Self-Awareness · journal"
      sub="reflection · strangeloop probe"
      right={
        <div className="flex gap-2">
          <button
            data-testid="journal-reflect-btn"
            onClick={reflect}
            disabled={loading}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2 py-1 flex items-center gap-1.5"
          >
            <Feather size={11} /> reflect
          </button>
          <button
            data-testid="strangeloop-probe-btn"
            onClick={probe}
            disabled={loading}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-300 disabled:text-zinc-600 border border-white/10 px-2 py-1 flex items-center gap-1.5"
          >
            <Eye size={11} /> probe
          </button>
        </div>
      }
    >
      {strange && (
        <div className="mb-3 border border-amber-500/30 p-2">
          <div className="font-mono-term text-[10px] tracking-[0.2em] uppercase text-amber-400">
            strangeloop · verdict {strange.verdict} · align {strange.alignment.toFixed(2)}
          </div>
          {strange.probe?.purpose && (
            <div className="font-sans text-[12px] text-zinc-300 mt-1">
              <span className="text-amber-400">purpose:</span> {strange.probe.purpose}
            </div>
          )}
        </div>
      )}
      <div className="space-y-3 max-h-80 overflow-y-auto ghost-scroll pr-2">
        {entries.length === 0 && (
          <div className="font-mono-term text-[11px] text-zinc-600">
            no reflections yet. tap reflect.
          </div>
        )}
        {entries.map((e) => (
          <div key={e._id || e.created_at} className="border-l-2 border-amber-500/40 pl-3">
            <div className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 mb-1">
              {new Date(e.created_at).toLocaleString()} · {e.engine}
            </div>
            <div className="font-serif-display text-[14px] leading-relaxed text-zinc-200 italic whitespace-pre-wrap">
              {e.text}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
};
