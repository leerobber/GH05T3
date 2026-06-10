"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { subscribeUplinkLogs, type UplinkLog } from "@/lib/supabase";

const SEED_LOGS: UplinkLog[] = [
  { level: "info",  message: "SwarmBus initialized — 3 agents online",        ts: "T+00:00" },
  { level: "info",  message: "KAIROS omega loop armed — threshold 0.90",       ts: "T+00:04" },
  { level: "info",  message: "Supabase Realtime channels subscribed",          ts: "T+00:05" },
  { level: "info",  message: "Podcast stream armed — Dr. Voss session active", ts: "T+00:07" },
];

const LEVEL_STYLE: Record<UplinkLog["level"], string> = {
  info:  "text-ghost-amber",
  warn:  "text-yellow-400",
  error: "text-ghost-crimson",
};

const LEVEL_PREFIX: Record<UplinkLog["level"], string> = {
  info:  "INF",
  warn:  "WRN",
  error: "ERR",
};

export default function UplinkConsole() {
  const [logs, setLogs] = useState<UplinkLog[]>(SEED_LOGS);
  const bottomRef       = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ch = subscribeUplinkLogs((log) => {
      setLogs((prev) => [...prev, log].slice(-80));
    });
    return () => { ch.unsubscribe(); };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="glass-panel corner-accent flex flex-col h-full min-h-[200px]">
      <div className="px-5 py-3 border-b border-white/5 flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-ghost-amber">
          ▶ Uplink Console
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-3 space-y-1.5 font-mono text-[11px]">
        <AnimatePresence initial={false}>
          {logs.map((log, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex gap-2"
            >
              <span className="text-zinc-600 shrink-0">{log.ts}</span>
              <span className={`shrink-0 ${LEVEL_STYLE[log.level]}`}>
                [{LEVEL_PREFIX[log.level]}]
              </span>
              <span className="text-zinc-300">{log.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
