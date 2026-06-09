"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface TxState {
  blockHeight: number;
  coreBalance: string;
  lastTx:      string;
  kairosNode:  "online" | "syncing" | "offline";
  tailscaleIp: string;
}

function mockTxState(): TxState {
  return {
    blockHeight: 21_400_000 + Math.floor(Math.random() * 50000),
    coreBalance: (1337 + Math.random() * 100).toFixed(4),
    lastTx:      "0x" + Math.random().toString(16).slice(2, 12) + "…",
    kairosNode:  "online",
    tailscaleIp: process.env.NEXT_PUBLIC_TAILSCALE_IP ?? "100.94.227.81",
  };
}

export default function TxPanel() {
  const [state, setState] = useState<TxState>(mockTxState());

  // Poll gateway for real CORE balance / block height if available
  useEffect(() => {
    const gw3 = process.env.NEXT_PUBLIC_GW3_URL ?? "http://localhost:8002";
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`${gw3}/avery`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          setState((prev) => ({ ...prev, kairosNode: "online" }));
        }
      } catch {
        setState((prev) => ({ ...prev, kairosNode: "offline" }));
      }
    }, 8000);
    return () => clearInterval(poll);
  }, []);

  // Simulated block height ticker
  useEffect(() => {
    const t = setInterval(() => {
      setState((prev) => ({
        ...prev,
        blockHeight: prev.blockHeight + Math.floor(Math.random() * 3),
      }));
    }, 4000);
    return () => clearInterval(t);
  }, []);

  const nodeColor =
    state.kairosNode === "online"  ? "text-ghost-success" :
    state.kairosNode === "syncing" ? "text-yellow-400"    : "text-ghost-crimson";

  return (
    <div className="glass-panel corner-accent p-5 space-y-4">
      <span className="font-serif text-sm tracking-widest text-zinc-300 uppercase block">
        TX Stream · Base L2
      </span>

      <div className="grid grid-cols-2 gap-3">
        {[
          { label: "Block",   value: state.blockHeight.toLocaleString() },
          { label: "CORE",    value: `${state.coreBalance} ◈` },
          { label: "Last TX", value: state.lastTx },
          { label: "Chain",   value: "Base L2 / x402" },
        ].map(({ label, value }) => (
          <div key={label} className="space-y-0.5">
            <p className="font-mono text-[9px] uppercase tracking-widest text-zinc-600">
              {label}
            </p>
            <p className="font-mono text-xs text-zinc-200 truncate">{value}</p>
          </div>
        ))}
      </div>

      <div className="pt-2 border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
            className={`w-1.5 h-1.5 rounded-full ${
              state.kairosNode === "online"  ? "bg-ghost-success" :
              state.kairosNode === "syncing" ? "bg-yellow-400"    : "bg-ghost-crimson"
            }`}
          />
          <span className={`font-mono text-[10px] uppercase tracking-widest ${nodeColor}`}>
            KAIROS {state.kairosNode}
          </span>
        </div>
        <span className="font-mono text-[9px] text-zinc-600">
          ts:{state.tailscaleIp}
        </span>
      </div>
    </div>
  );
}
