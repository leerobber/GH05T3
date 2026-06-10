"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface InferenceHealth {
  status:  string;          // "ready" | "loading"
  backend: string;          // "vllm" | "hf"
  quant:   string;          // "nvfp4" | "fp8" | "nf4" | "none"
  tok_s:   number;
}

const POLL_MS = 5_000;

function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k t/s`;
  if (n > 0)     return `${Math.round(n)} t/s`;
  return "";
}

const QUANT_LABEL: Record<string, string> = {
  nvfp4: "NVFP4",
  fp8:   "FP8",
  nf4:   "NF4",
  none:  "BF16",
};

export default function InferenceBadge() {
  const [health, setHealth] = useState<InferenceHealth | null>(null);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_INFERENCE_URL ?? "http://localhost:8010";
    let active = true;

    const poll = async () => {
      try {
        const r = await fetch(`${base}/health`, {
          signal: AbortSignal.timeout(2500),
        });
        if (!active) return;
        if (r.ok) {
          const data = await r.json() as InferenceHealth;
          setHealth(data);
          setOnline(data.status === "ready");
        } else {
          setOnline(false);
        }
      } catch {
        if (active) setOnline(false);
      }
    };

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  if (!online || !health) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-white/15" />
        <span className="font-mono text-[9px] uppercase tracking-widest text-zinc-700">
          INFERENCE OFFLINE
        </span>
      </div>
    );
  }

  const isVllm   = health.backend === "vllm";
  const bLabel   = isVllm ? "vLLM" : "HF";
  const qLabel   = QUANT_LABEL[health.quant] ?? health.quant.toUpperCase();
  const speedStr = fmt(health.tok_s);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex items-center gap-1.5"
    >
      <motion.span
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2.5, repeat: Infinity }}
        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
          isVllm ? "bg-ghost-success" : "bg-ghost-amber"
        }`}
      />
      <span className={`font-mono text-[9px] uppercase tracking-widest ${
        isVllm ? "text-ghost-success" : "text-ghost-amber"
      }`}>
        {bLabel} · {qLabel}{speedStr && ` · ${speedStr}`}
      </span>
    </motion.div>
  );
}
