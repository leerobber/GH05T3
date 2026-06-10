"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { subscribeTranscripts, type TranscriptRow } from "@/lib/supabase";

const SEED: TranscriptRow[] = [
  { id: 0, speaker: "Dr. Voss",  text: "The mesh doesn't just route packets — it routes intent.",           inserted_at: "" },
  { id: 1, speaker: "Avery",     text: "Every node is a decision point. That's the design.",               inserted_at: "" },
  { id: 2, speaker: "Dr. Voss",  text: "And KAIROS ensures those decisions compound over time?",            inserted_at: "" },
  { id: 3, speaker: "Avery",     text: "Continuously. The omega loop never stops.",                         inserted_at: "" },
];

export default function TranscriptFeed() {
  const [rows, setRows]   = useState<TranscriptRow[]>(SEED);
  const bottomRef         = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ch = subscribeTranscripts((row) => {
      setRows((prev) => [...prev, row].slice(-60));
    });
    return () => { ch.unsubscribe(); };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rows]);

  return (
    <div className="glass-panel corner-accent flex flex-col h-full min-h-[280px]">
      <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between">
        <span className="font-serif text-sm tracking-widest text-zinc-300 uppercase">
          Live Transcript
        </span>
        <span className="font-mono text-[9px] text-zinc-600">
          {rows.length} lines
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
        <AnimatePresence initial={false}>
          {rows.map((row, i) => (
            <motion.div
              key={row.id || i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="flex gap-3 items-start"
            >
              <span
                className={`font-mono text-[10px] uppercase tracking-widest shrink-0 pt-0.5 ${
                  row.speaker === "Avery"
                    ? "text-ghost-amber"
                    : "text-zinc-400"
                }`}
              >
                {row.speaker}
              </span>
              <span className="font-sans text-sm text-zinc-200 leading-relaxed">
                {row.text}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
