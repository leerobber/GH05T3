import React, { useState, useEffect, useCallback } from "react";
import { Radio, RefreshCw, PlusCircle, Trash2, Wifi, WifiOff } from "lucide-react";
import { Panel, Dot } from "./primitives";
import { listPeers, pingPeers, pushSyncAll, registerPeer, removePeer } from "../../lib/ghostApi";
import { toast } from "sonner";

const ROLE_COLOR = {
  primary: "text-amber-400 border-amber-500/40",
  peer:    "text-cyan-400 border-cyan-500/40",
};

function LatencyBar({ ms }) {
  if (ms == null) return <span className="text-zinc-600">—</span>;
  const color = ms < 80 ? "text-emerald-400" : ms < 300 ? "text-amber-400" : "text-rose-400";
  return <span className={`font-mono-term text-[9px] ${color}`}>{ms}ms</span>;
}

function PeerRow({ peer, onRemove }) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-0">
      <span className={`flex-shrink-0 ${peer.online ? "text-emerald-400" : "text-zinc-600"}`}>
        {peer.online ? <Wifi size={11} /> : <WifiOff size={11} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-mono-term text-[11px] text-zinc-200 truncate">{peer.label}</span>
          <span className={`font-mono-term text-[8px] border px-1 flex-shrink-0 ${ROLE_COLOR[peer.role] || ROLE_COLOR.peer}`}>
            {peer.role}
          </span>
        </div>
        <div className="font-mono-term text-[9px] text-zinc-600 truncate mt-0.5">{peer.url}</div>
        <div className="flex items-center gap-2 mt-0.5">
          <LatencyBar ms={peer.latency_ms} />
          {peer.last_sync && (
            <span className="font-mono-term text-[9px] text-zinc-600">
              synced {new Date(peer.last_sync).toLocaleTimeString()}
            </span>
          )}
          {(peer.sync_sent > 0 || peer.sync_recv > 0) && (
            <span className="font-mono-term text-[9px] text-zinc-500">
              ↑{peer.sync_sent} ↓{peer.sync_recv}
            </span>
          )}
        </div>
      </div>
      <button
        onClick={() => onRemove(peer.url)}
        className="flex-shrink-0 text-zinc-600 hover:text-rose-400"
        title="remove peer"
      >
        <Trash2 size={10} />
      </button>
    </div>
  );
}

function AddPeerForm({ onAdd, onCancel }) {
  const [url,   setUrl]   = useState("");
  const [label, setLabel] = useState("");
  const [role,  setRole]  = useState("peer");
  const [busy,  setBusy]  = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await onAdd(url.trim(), label.trim() || url.trim(), role);
      setUrl(""); setLabel(""); setRole("peer");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-2 space-y-1.5 border-t border-white/10 pt-2">
      <input
        autoFocus
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://peer-host:8001"
        className="w-full font-mono-term text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-200 px-2 py-1 placeholder:text-zinc-600"
      />
      <div className="flex gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="label (e.g. Laptop)"
          className="flex-1 font-mono-term text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-2 py-1 placeholder:text-zinc-600"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="font-mono-term text-[10px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-1 py-1"
        >
          <option value="peer">peer</option>
          <option value="primary">primary</option>
        </select>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || !url.trim()}
          className="font-mono-term text-[10px] uppercase tracking-widest text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 px-3 py-1"
        >
          {busy ? "…" : "+ add"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="font-mono-term text-[10px] text-zinc-500 hover:text-zinc-300 border border-zinc-700 px-2 py-1"
        >
          cancel
        </button>
      </div>
    </form>
  );
}

export function PeersPanel() {
  const [data,      setData]      = useState(null);
  const [pinging,   setPinging]   = useState(false);
  const [syncing,   setSyncing]   = useState(false);
  const [showAdd,   setShowAdd]   = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await listPeers();
      setData(d);
    } catch (e) {
      console.warn("peers load:", e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handlePing = async () => {
    setPinging(true);
    try {
      const d = await pingPeers();
      setData((prev) => ({ ...prev, peers: d.peers }));
      toast("Peers pinged");
    } catch (e) {
      toast.error("Ping failed: " + e.message);
    } finally {
      setPinging(false);
    }
  };

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await pushSyncAll();
      toast("Sync push queued");
      setTimeout(load, 3000);
    } catch (e) {
      toast.error("Sync failed: " + e.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleAdd = async (url, label, role) => {
    try {
      await registerPeer(url, label, role);
      await load();
      setShowAdd(false);
      toast(`Peer ${label} registered`);
    } catch (e) {
      toast.error("Register failed: " + e.message);
    }
  };

  const handleRemove = async (url) => {
    try {
      await removePeer(url);
      setData((prev) => ({
        ...prev,
        peers: (prev?.peers || []).filter((p) => p.url !== url),
      }));
      toast("Peer removed");
    } catch (e) {
      toast.error("Remove failed: " + e.message);
    }
  };

  const self   = data?.self;
  const peerList = data?.peers || [];
  const online = peerList.filter((p) => p.online).length;

  return (
    <Panel
      testid="peers-panel"
      title="Peer Mesh"
      sub={`${self?.label || "—"} · ${self?.role || "—"} · ${online}/${peerList.length} online`}
      right={
        <div className="flex items-center gap-1.5">
          <button
            onClick={handlePing}
            disabled={pinging}
            className="font-mono-term text-[9px] text-zinc-400 hover:text-zinc-200 disabled:text-zinc-600 border border-zinc-700 px-1.5 py-0.5 flex items-center gap-1"
          >
            <Radio size={9} /> {pinging ? "…" : "ping"}
          </button>
          <button
            onClick={handleSyncAll}
            disabled={syncing}
            className="font-mono-term text-[9px] text-cyan-400 hover:text-cyan-300 disabled:text-zinc-600 border border-cyan-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            <RefreshCw size={9} className={syncing ? "animate-spin" : ""} />
            {syncing ? "…" : "sync all"}
          </button>
          <button
            onClick={() => setShowAdd((v) => !v)}
            className="font-mono-term text-[9px] text-amber-400 hover:text-amber-300 border border-amber-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            <PlusCircle size={9} /> peer
          </button>
        </div>
      }
    >
      {self && (
        <div className="mb-2 pb-2 border-b border-white/5 flex items-center gap-2">
          <Dot kind="active" />
          <span className="font-mono-term text-[10px] text-zinc-300">{self.url}</span>
          <span className={`font-mono-term text-[8px] border px-1 ${ROLE_COLOR[self.role] || ROLE_COLOR.peer}`}>
            {self.role}
          </span>
        </div>
      )}

      {showAdd && (
        <AddPeerForm onAdd={handleAdd} onCancel={() => setShowAdd(false)} />
      )}

      {peerList.length === 0 ? (
        <div className="font-mono-term text-[10px] text-zinc-600 py-3 text-center">
          no peers configured — add one or set PEER_URLS in .env
        </div>
      ) : (
        <div className="max-h-56 overflow-y-auto ghost-scroll pr-1">
          {peerList.map((p) => (
            <PeerRow key={p.url} peer={p} onRemove={handleRemove} />
          ))}
        </div>
      )}
    </Panel>
  );
}
