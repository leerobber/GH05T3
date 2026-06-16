import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  GitBranch,
  Loader2,
  Radio,
  RefreshCw,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { Panel, Dot } from "../primitives/primitives";
import {
  gw3MeshPeers,
  gw3MeshSync,
  gw3Peers,
  gw3PeersPing,
  gw3PeersRefresh,
} from "../../../lib/ghostApi";

const roleClass = (role) => {
  if (role === "primary") return "text-amber-400 border-amber-500/40";
  if (role === "peer") return "text-cyan-400 border-cyan-500/40";
  return "text-zinc-400 border-zinc-700";
};

const fmtLatency = (ms) => {
  if (ms == null) return "—";
  return `${ms}ms`;
};

const fmtTime = (ts) => {
  if (!ts) return "never";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return String(ts);
  }
};

function PeerRow({ peer }) {
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-white/5 last:border-0">
      <span className={`mt-0.5 ${peer.online ? "text-emerald-400" : "text-zinc-600"}`}>
        {peer.online ? <Wifi size={11} /> : <WifiOff size={11} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono-term text-[11px] text-zinc-200 truncate">
            {peer.label || peer.url}
          </span>
          <span className={`font-mono-term text-[8px] border px-1 flex-shrink-0 uppercase ${roleClass(peer.role)}`}>
            {peer.role || "peer"}
          </span>
          {peer.version && (
            <span className="font-mono-term text-[8px] text-zinc-600 border border-white/5 px-1">
              v{peer.version}
            </span>
          )}
        </div>
        <div className="font-mono-term text-[9px] text-zinc-600 truncate mt-0.5">
          {peer.url}
        </div>
        <div className="flex items-center gap-2 mt-0.5 font-mono-term text-[9px] text-zinc-500 flex-wrap">
          <span>{fmtLatency(peer.latency_ms)}</span>
          <span>seen {fmtTime(peer.last_seen)}</span>
          <span>sync {fmtTime(peer.last_sync)}</span>
          <span>↑{peer.sync_sent ?? 0} ↓{peer.sync_recv ?? 0}</span>
        </div>
      </div>
    </div>
  );
}

function RelayRow({ peer }) {
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-white/5 last:border-0">
      <span className="mt-0.5 text-cyan-400">
        <GitBranch size={11} />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono-term text-[11px] text-zinc-200 truncate">
            {peer.label || "unknown"}
          </span>
          {peer.role && (
            <span className="font-mono-term text-[8px] text-cyan-400 border border-cyan-500/30 px-1 uppercase">
              {peer.role}
            </span>
          )}
        </div>
        <div className="font-mono-term text-[9px] text-zinc-600 truncate mt-0.5">
          {peer.url || "no relay url"}
        </div>
        <div className="font-mono-term text-[9px] text-zinc-500 mt-0.5">
          synced {fmtTime(peer.synced_at)}
        </div>
      </div>
    </div>
  );
}

export function PeersPanel() {
  const [data, setData] = useState(null);
  const [relayPeers, setRelayPeers] = useState([]);
  const [busy, setBusy] = useState({ refresh: false, ping: false, sync: false, relay: false });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const d = await gw3Peers();
      setData(d);
      setError("");
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    }
  }, []);

  const loadRelayPeers = useCallback(async () => {
    try {
      const d = await gw3MeshPeers();
      setRelayPeers(d.peers || []);
    } catch (e) {
      setRelayPeers([]);
      setError(e?.response?.data?.detail || e.message);
    }
  }, []);

  useEffect(() => {
    load();
    loadRelayPeers();
  }, [load, loadRelayPeers]);

  const self = data?.self || {};
  const peerList = data?.peers || [];
  const online = peerList.filter((p) => p.online).length;
  const tailscaleConfigured = Boolean(data?.tailscale_configured);

  const handleRefresh = async () => {
    setBusy((prev) => ({ ...prev, refresh: true }));
    try {
      const d = await gw3PeersRefresh();
      setData(d);
      setError("");
      toast("Peer discovery refreshed");
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      setError(msg);
      toast.error("Refresh failed: " + msg);
    } finally {
      setBusy((prev) => ({ ...prev, refresh: false }));
    }
  };

  const handlePing = async () => {
    setBusy((prev) => ({ ...prev, ping: true }));
    try {
      const d = await gw3PeersPing();
      setData(d);
      setError("");
      toast("Peer probe completed");
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      setError(msg);
      toast.error("Probe failed: " + msg);
    } finally {
      setBusy((prev) => ({ ...prev, ping: false }));
    }
  };

  const handleSync = async () => {
    setBusy((prev) => ({ ...prev, sync: true }));
    try {
      await gw3MeshSync();
      await loadRelayPeers();
      toast("Mesh relay sync queued");
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      setError(msg);
      toast.error("Sync failed: " + msg);
    } finally {
      setBusy((prev) => ({ ...prev, sync: false }));
    }
  };

  const handleRelayRefresh = async () => {
    setBusy((prev) => ({ ...prev, relay: true }));
    try {
      await loadRelayPeers();
      toast("Relay peers refreshed");
    } finally {
      setBusy((prev) => ({ ...prev, relay: false }));
    }
  };

  return (
    <Panel
      testid="peers-panel"
      title="Mesh"
      sub={`${self.label || "—"} · ${self.role || "—"} · ${online}/${peerList.length} live`}
      right={
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleRefresh}
            disabled={busy.refresh}
            className="font-mono-term text-[9px] text-zinc-400 hover:text-zinc-200 disabled:text-zinc-600 border border-zinc-700 px-1.5 py-0.5 flex items-center gap-1"
          >
            {busy.refresh ? <Loader2 size={9} className="animate-spin" /> : <RefreshCw size={9} />}
            refresh
          </button>
          <button
            onClick={handlePing}
            disabled={busy.ping}
            className="font-mono-term text-[9px] text-cyan-400 hover:text-cyan-300 disabled:text-zinc-600 border border-cyan-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            <Radio size={9} />
            {busy.ping ? "…" : "ping"}
          </button>
          <button
            onClick={handleSync}
            disabled={busy.sync}
            className="font-mono-term text-[9px] text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            {busy.sync ? <Loader2 size={9} className="animate-spin" /> : <GitBranch size={9} />}
            sync
          </button>
        </div>
      }
    >
      <div className="space-y-2">
        <div className="flex items-center gap-2 border-b border-white/5 pb-2">
          <Dot kind={tailscaleConfigured ? "active" : "idle"} />
          <div className="min-w-0 flex-1">
            <div className="font-mono-term text-[10px] text-zinc-200 truncate">
              {self.url || "mesh discovery disabled"}
            </div>
            <div className="font-mono-term text-[9px] text-zinc-600 uppercase tracking-[0.2em]">
              {self.discovery || "tailscale"} discovery
            </div>
          </div>
          {!tailscaleConfigured && (
            <span className="font-mono-term text-[9px] text-amber-400 flex items-center gap-1">
              <AlertTriangle size={9} /> tailscale api key missing
            </span>
          )}
        </div>

        {error && (
          <div className="font-mono-term text-[10px] text-rose-400 border border-rose-500/20 px-2 py-1.5 flex items-center gap-1.5">
            <AlertTriangle size={10} />
            <span className="truncate">{error}</span>
          </div>
        )}

        <div>
          <div className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-600 mb-1">
            live peers
          </div>
          {peerList.length === 0 ? (
            <div className="font-mono-term text-[10px] text-zinc-600 py-3 text-center">
              no live peers discovered
            </div>
          ) : (
            <div className="max-h-44 overflow-y-auto ghost-scroll pr-1">
              {peerList.map((peer) => (
                <PeerRow key={peer.url} peer={peer} />
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-600">
              git relay peers
            </div>
            <button
              onClick={handleRelayRefresh}
              disabled={busy.relay}
              className="font-mono-term text-[9px] text-zinc-500 hover:text-zinc-200 disabled:text-zinc-600 flex items-center gap-1"
            >
              {busy.relay ? <Loader2 size={9} className="animate-spin" /> : <RefreshCw size={9} />}
              reload
            </button>
          </div>
          {relayPeers.length === 0 ? (
            <div className="font-mono-term text-[10px] text-zinc-600 py-3 text-center">
              no relay manifests found
            </div>
          ) : (
            <div className="max-h-28 overflow-y-auto ghost-scroll pr-1">
              {relayPeers.map((peer) => (
                <RelayRow key={peer.label || peer.url} peer={peer} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
