import React, { useState, useEffect, useCallback } from "react";
import { Eye, Zap, Database, RefreshCw, Activity } from "lucide-react";
import { Panel, Dot } from "./primitives";

const GW3 = process.env.REACT_APP_GW3_URL || "http://localhost:8002";

async function fetchChronicleStatus() {
  const r = await fetch(`${GW3}/chronicle/status`);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

async function triggerScan() {
  const r = await fetch(`${GW3}/chronicle/scan`, { method: "POST" });
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

function StatPill({ label, value, color = "text-zinc-300" }) {
  return (
    <div className="flex flex-col items-center px-3 py-1.5 border border-white/5 bg-zinc-900/60">
      <span className={`font-mono-term text-sm font-bold ${color}`}>{value ?? "—"}</span>
      <span className="font-mono-term text-[9px] text-zinc-500 uppercase tracking-widest">{label}</span>
    </div>
  );
}

function SourceBar({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono-term text-[10px] text-zinc-400 w-28 truncate">{label}</span>
      <div className="flex-1 bg-zinc-800 h-1">
        <div className="bg-violet-500 h-1" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono-term text-[10px] text-zinc-400 w-8 text-right">{count}</span>
    </div>
  );
}

export function ChroniclePanel() {
  const [data,     setData]     = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error,    setError]    = useState(null);

  const load = useCallback(async () => {
    try {
      const d = await fetchChronicleStatus();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      setTimeout(load, 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  const sources = data?.sources || {};
  const maxSrc  = Math.max(...Object.values(sources), 1);

  return (
    <Panel
      testid="chronicle-panel"
      title="Sovereign Recall"
      sub="CHRONICLE · Mira Solis · Chief Data Intelligence"
      right={
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="font-mono-term text-[9px] text-violet-400 hover:text-violet-300 disabled:text-zinc-600 border border-violet-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            <RefreshCw size={9} className={scanning ? "animate-spin" : ""} />
            {scanning ? "scanning…" : "scan now"}
          </button>
        </div>
      }
    >
      {error ? (
        <div className="font-mono-term text-[10px] text-rose-400 py-2">
          Chronicle offline — {error}
        </div>
      ) : (
        <>
          {/* Stats row */}
          <div className="grid grid-cols-4 gap-1 mb-3">
            <StatPill
              label="examples"
              value={data?.total_examples?.toLocaleString()}
              color="text-violet-300"
            />
            <StatPill
              label="tokens"
              value={data?.tokens}
              color="text-amber-300"
            />
            <StatPill
              label="quality min"
              value={data?.quality_threshold}
              color="text-zinc-300"
            />
            <StatPill
              label="scan (s)"
              value={data?.scan_interval}
              color="text-zinc-300"
            />
          </div>

          {/* Source breakdown */}
          {Object.keys(sources).length > 0 && (
            <div className="space-y-1 mb-3">
              <div className="font-mono-term text-[9px] text-zinc-500 uppercase tracking-widest mb-1">
                capture sources
              </div>
              {Object.entries(sources).map(([src, count]) => (
                <SourceBar key={src} label={src} count={count} max={maxSrc} />
              ))}
            </div>
          )}

          {/* Output path */}
          {data?.output_file && (
            <div className="border-t border-white/5 pt-2 mt-2">
              <div className="font-mono-term text-[9px] text-zinc-500 mb-0.5">output →</div>
              <div className="font-mono-term text-[9px] text-violet-300 truncate">
                {data.output_file}
              </div>
            </div>
          )}

          {/* Last scan */}
          {data?.last_scan && (
            <div className="font-mono-term text-[9px] text-zinc-600 mt-1">
              last scan: {new Date(data.last_scan * 1000).toLocaleTimeString()}
            </div>
          )}

          {!data && !error && (
            <div className="font-mono-term text-[10px] text-zinc-600 py-3 text-center">
              <Activity size={12} className="inline mr-1" />
              initializing sovereign recall…
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
