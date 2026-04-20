import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { kairosRecent } from "../../lib/ghostApi";
import { ChevronRight } from "lucide-react";

export const TranscriptPanel = ({ refreshKey }) => {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    kairosRecent()
      .then((d) => setRows(d.cycles || []))
      .catch(() => {});
  }, [refreshKey]);

  return (
    <Panel
      testid="transcript-panel"
      title="SAGE · transcript"
      sub="proposer · critic · verifier"
    >
      <div className="space-y-1 max-h-80 overflow-y-auto ghost-scroll pr-2">
        {rows.length === 0 && (
          <div className="font-mono-term text-[11px] text-zinc-600">
            no cycles yet. run one.
          </div>
        )}
        {rows.map((r) => (
          <div key={r.id} className="border-b border-white/5 last:border-0">
            <button
              data-testid={`transcript-row-${r.cycle_num}`}
              onClick={() => setOpen(open === r.id ? null : r.id)}
              className="w-full flex items-center gap-2 py-1.5 hover:bg-white/5"
            >
              <ChevronRight
                size={11}
                className={`transition-transform ${open === r.id ? "rotate-90" : ""} text-zinc-500`}
              />
              <span className="font-mono-term text-[10px] text-zinc-500">#{r.cycle_num}</span>
              <span className={`font-mono-term text-[10px] ${r.elite ? "text-amber-400" : r.verdict === "PASS" ? "text-emerald-400" : r.verdict === "FAIL" ? "text-rose-400" : "text-zinc-300"}`}>
                {r.verdict}·{r.critic_decision}
              </span>
              <span className="font-mono-term text-[10px] text-zinc-400 flex-1 text-left truncate">{r.proposal}</span>
              <span className="font-mono-term text-[10px] text-amber-400">{r.final_score}</span>
            </button>
            {open === r.id && (
              <div className="pl-4 pb-3 space-y-2 font-mono-term text-[10px] text-zinc-400">
                <div>
                  <span className="text-amber-400">[proposer: {r.proposer}]</span> {r.proposal}
                </div>
                <div>
                  <span className="text-amber-400">[critic: {r.critic}]</span>{" "}
                  <span className="text-zinc-300">{r.critic_decision}</span> — {r.critic_reason}
                </div>
                <div>
                  <span className="text-amber-400">[verifier: {r.verifier}]</span>{" "}
                  <span className="text-zinc-300">{r.verdict}</span> — {r.verifier_rationale}
                </div>
                <div className="text-zinc-500">
                  score = {r.base_score} × {r.multiplier} = {r.final_score}{" "}
                  {r.elite && <span className="text-amber-400">ELITE</span>}{" "}
                  {r.archived && <span className="text-emerald-400">archived</span>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
};
