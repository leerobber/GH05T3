"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { motion } from "framer-motion";
import TelemetryHUD   from "@/components/TelemetryHUD";
import TranscriptFeed from "@/components/TranscriptFeed";
import UplinkConsole  from "@/components/UplinkConsole";
import TxPanel        from "@/components/TxPanel";
import Waveform       from "@/components/Waveform";

// Three.js must be client-only — no SSR
const Visualizer3D = dynamic(() => import("@/components/Visualizer3D"), {
  ssr: false,
  loading: () => (
    <div className="w-full min-h-[320px] flex items-center justify-center">
      <span className="font-mono text-[10px] text-ghost-amber animate-pulse-amber tracking-widest">
        INITIALIZING MESH…
      </span>
    </div>
  ),
});

export default function PodcastPage() {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0.31);

  return (
    <main className="min-h-screen bg-ghost-bg p-6 md:p-8">
      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8 flex items-start justify-between"
      >
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-ghost-amber mb-1">
            SOVEREIGN-PRIME v1.0
          </p>
          <h1 className="font-serif text-4xl md:text-5xl text-white tracking-tight">
            The Intelligence Mesh
          </h1>
          <p className="font-sans text-sm text-zinc-500 mt-1">
            Live sovereign broadcast · Supabase Realtime · GH05T3 engine
          </p>
        </div>
        <div className="text-right hidden md:block">
          <p className="font-mono text-[9px] uppercase tracking-widest text-zinc-600">
            FORGE LOG
          </p>
          <p className="font-mono text-xs text-zinc-400">2026-06-09</p>
        </div>
      </motion.header>

      {/* Main grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5">

        {/* ── Left col ─────────────────────────────── */}
        <div className="md:col-span-3 flex flex-col gap-5">
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1, duration: 0.45 }}
          >
            <TelemetryHUD />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.45 }}
          >
            <TxPanel />
          </motion.div>
        </div>

        {/* ── Center col ───────────────────────────── */}
        <div className="md:col-span-6 flex flex-col gap-5">

          {/* 3D Torus guest interface */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15, duration: 0.5 }}
            className="glass-panel corner-accent active-border overflow-hidden"
          >
            <div className="px-5 pt-5 pb-2 flex items-center justify-between">
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.25em] text-zinc-500">
                  Guest Interface
                </p>
                <p className="font-serif text-lg text-white mt-0.5">
                  Dr. Voss — Sovereign Intelligence Hour
                </p>
              </div>
              <span className="font-mono text-[9px] px-2 py-0.5 border border-ghost-amber/30 text-ghost-amber tracking-widest">
                EP 01
              </span>
            </div>

            <Visualizer3D />

            {/* Audio controls */}
            <div className="px-5 pb-5 space-y-3">
              <Waveform playing={playing} />

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="w-8 h-8 border border-ghost-amber/40 text-ghost-amber font-mono text-xs flex items-center justify-center hover:border-ghost-amber/80 hover:bg-ghost-amber/5 transition-colors"
                >
                  {playing ? "⏸" : "▶"}
                </button>

                {/* Progress bar */}
                <div
                  className="flex-1 h-px bg-white/10 relative cursor-pointer"
                  onClick={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setProgress((e.clientX - rect.left) / rect.width);
                  }}
                >
                  <div
                    className="h-px bg-ghost-amber absolute left-0 top-0"
                    style={{ width: `${progress * 100}%` }}
                  />
                  <div
                    className="w-2 h-2 bg-ghost-amber absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
                    style={{ left: `${progress * 100}%` }}
                  />
                </div>

                <span className="font-mono text-[10px] text-zinc-500 shrink-0">
                  {Math.floor(progress * 48)}:{String(Math.floor((progress * 48 % 1) * 60)).padStart(2,"0")} / 48:00
                </span>
              </div>
            </div>
          </motion.div>

          {/* Transcript feed */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.45 }}
            className="flex-1"
          >
            <TranscriptFeed />
          </motion.div>
        </div>

        {/* ── Right col ────────────────────────────── */}
        <div className="md:col-span-3 flex flex-col gap-5">
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.45 }}
            className="flex-1"
          >
            <UplinkConsole />
          </motion.div>

          {/* Episode info card */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3, duration: 0.45 }}
            className="glass-panel corner-accent p-5 space-y-3"
          >
            <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-600">
              Architect Stream
            </p>
            <p className="font-serif text-base text-white">
              Unlock full session + mesh access
            </p>
            <p className="font-sans text-xs text-zinc-500 leading-relaxed">
              Gated via Stripe · CORE token holders get automatic access through the x402 hook.
            </p>
            <a
              href="#"
              className="block w-full text-center font-mono text-[11px] uppercase tracking-widest py-2 border border-ghost-amber/40 text-ghost-amber hover:bg-ghost-amber/5 hover:border-ghost-amber/80 transition-colors"
            >
              Subscribe → Architect
            </a>
          </motion.div>
        </div>

      </div>
    </main>
  );
}
