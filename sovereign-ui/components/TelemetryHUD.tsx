"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { subscribeTelemetry, type TelemetryRow } from "@/lib/supabase";
import InferenceBadge from "@/components/InferenceBadge";

const FALLBACK_INTERVAL = 2200;

function mockTick(): TelemetryRow {
  return {
    id:           Math.random(),
    cpu:          30 + Math.random() * 55,
    temp:         42 + Math.random() * 22,
    latency:      8  + Math.random() * 40,
    bandwidth:    120 + Math.random() * 880,
    active_nodes: Math.floor(3 + Math.random() * 9),
    inserted_at:  new Date().toISOString(),
  };
}

const ZERO_ROW: TelemetryRow = {
  id: 0, cpu: 0, temp: 0, latency: 0, bandwidth: 0, active_nodes: 0, inserted_at: "",
};

interface MetricBarProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  warn?: number;
}

function MetricBar({ label, value, unit, max, warn }: MetricBarProps) {
  const pct = Math.min((value / max) * 100, 100);
  const hot = warn && value > warn;

  return (
    <div className="space-y-1">
      <div className="flex justify-between font-mono text-[10px] uppercase tracking-widest">
        <span className="text-zinc-500">{label}</span>
        <span className={hot ? "text-ghost-crimson" : "text-ghost-amber"}>
          {value.toFixed(1)}{unit}
        </span>
      </div>
      <div className="h-px w-full bg-white/5 relative overflow-hidden">
        <motion.div
          className={`h-px absolute left-0 top-0 ${hot ? "bg-ghost-crimson" : "bg-ghost-amber"}`}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function TelemetryHUD() {
  // Zero initial state avoids SSR/client hydration mismatch from Math.random()
  const [live, setLive]           = useState<TelemetryRow>(ZERO_ROW);
  const [realtimeOk, setRealtimeOk] = useState(false);
  // Ref so the setInterval closure always sees the latest value without re-creating
  const realtimeOkRef             = useRef(false);

  useEffect(() => {
    // Seed with a mock tick on the client only
    setLive(mockTick());

    const ch = subscribeTelemetry((row) => {
      setLive(row);
      setRealtimeOk(true);
      realtimeOkRef.current = true;
    });

    const timer = setInterval(() => {
      if (!realtimeOkRef.current) setLive(mockTick());
    }, FALLBACK_INTERVAL);

    return () => {
      ch.unsubscribe();
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="glass-panel corner-accent p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="font-serif text-sm tracking-widest text-zinc-300 uppercase">
          Node Telemetry
        </span>
        <AnimatePresence mode="wait">
          <motion.span
            key={realtimeOk ? "live" : "sim"}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`font-mono text-[9px] uppercase tracking-[0.2em] px-2 py-0.5 border ${
              realtimeOk
                ? "border-ghost-success/30 text-ghost-success"
                : "border-ghost-amber/30 text-ghost-amber animate-pulse-amber"
            }`}
          >
            {realtimeOk ? "● LIVE" : "◌ SIM"}
          </motion.span>
        </AnimatePresence>
      </div>

      <MetricBar label="CPU"       value={live.cpu ?? 0}       max={100}  unit="%" warn={80} />
      <MetricBar label="Temp"      value={live.temp ?? 0}      max={95}   unit="°C" warn={85} />
      <MetricBar label="Latency"   value={live.latency ?? 0}   max={200}  unit="ms" warn={120} />
      <MetricBar label="Bandwidth" value={live.bandwidth ?? 0} max={1000} unit=" Mb" />

      <div className="pt-1 flex items-center gap-2">
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">
          Active Nodes
        </span>
        <div className="flex gap-1">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className={`w-1.5 h-1.5 rounded-full transition-colors duration-500 ${
                i < (live.active_nodes ?? 0) ? "bg-ghost-amber" : "bg-white/10"
              }`}
            />
          ))}
        </div>
        <span className="font-mono text-[10px] text-ghost-amber ml-auto">
          {live.active_nodes ?? 0}
        </span>
      </div>

      <div className="pt-2 border-t border-white/5">
        <InferenceBadge />
      </div>
    </div>
  );
}
