import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Search, Brain } from "lucide-react";

const TYPE_COLOR = {
  identity: "#f59e0b",
  fact: "#22d3ee",
  decision: "#c4b5fd",
  observation: "#facc15",
  rule: "#10b981",
  reflection: "#e11d48",
};

export const MemoryStreamPanel = ({ refreshKey }) => {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [searchHits, setSearchHits] = useState(null);
  const [stats, setStats] = useState(null);

  const reload = () => {
    api.get("/memory/recent", { params: { limit: 25 } })
      .then((r) => setItems(r.data.memories || []))
      .catch(() => {});
    api.get("/memory/stats").then((r) => setStats(r.data)).catch(() => {});
  };
  useEffect(reload, [refreshKey]);

  const search = async () => {
    if (!q.trim()) {
      setSearchHits(null);
      return;
    }
    const r = await api.get("/memory/search", { params: { q, k: 5 } });
    setSearchHits(r.data.hits);
  };

  const rows = searchHits ?? items;

  return (
    <Panel
      testid="memory-stream-panel"
      title="Memory · living stream"
      sub={stats ? `${stats.total} total · ${stats.by_type?.identity ?? 0} identity · ${stats.by_type?.rule ?? 0} rules` : "…"}
      right={<Brain size={14} className="text-amber-400" />}
    >
      <div className="flex gap-2 mb-2">
        <div className="flex-1 flex items-center border border-white/10 bg-black px-2">
          <Search size={12} className="text-zinc-500" />
          <input
            data-testid="memory-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="search semantic memory…"
            className="flex-1 bg-transparent outline-none font-mono-term text-xs text-zinc-200 p-1.5"
          />
        </div>
        <button
          data-testid="memory-search-btn"
          onClick={search}
          className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 border border-amber-500/30 px-2"
        >
          find
        </button>
        {searchHits && (
          <button
            onClick={() => {
              setSearchHits(null);
              setQ("");
            }}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-500 border border-white/10 px-2"
          >
            clear
          </button>
        )}
      </div>
      <div className="space-y-1.5 max-h-80 overflow-y-auto ghost-scroll pr-2">
        {rows.length === 0 && (
          <div className="font-mono-term text-[11px] text-zinc-600">no memories yet.</div>
        )}
        {rows.map((m, i) => (
          <div key={m.id || i} className="border-l pl-2 py-1" style={{ borderColor: TYPE_COLOR[m.type] || "#444" }}>
            <div className="flex items-center justify-between">
              <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase" style={{ color: TYPE_COLOR[m.type] || "#999" }}>
                {m.type}·{m.source}
              </span>
              <span className="font-mono-term text-[9px] text-zinc-600">
                {m.score !== undefined ? `score ${m.score}` : `imp ${m.importance ?? "—"}`}
              </span>
            </div>
            <div className="font-sans text-[12px] text-zinc-300 leading-snug">{m.content}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
};
