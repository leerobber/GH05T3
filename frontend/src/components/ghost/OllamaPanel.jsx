import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { ollamaStatus, ollamaConfigure, ollamaPull } from "../../lib/ghostApi";
import { Cpu, CheckCircle2, AlertCircle, Download } from "lucide-react";

/** Ollama gateway panel — LOQ / TatorTot local runtime. */
export const OllamaPanel = () => {
  const [status, setStatus] = useState(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [pullMsg, setPullMsg] = useState(null);

  const load = async () => {
    try {
      const s = await ollamaStatus();
      setStatus(s);
      if (s.url && !url) setUrl(s.url);
    } catch {
      /* ignore */
    }
  };
  useEffect(() => {
    load();
    const iv = setInterval(load, 20_000);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const s = await ollamaConfigure(url.trim());
      setStatus(s);
    } finally {
      setBusy(false);
    }
  };

  const pull = async (model) => {
    setBusy(true);
    setPullMsg({ model, status: "pulling…" });
    try {
      const r = await ollamaPull(model);
      setPullMsg({ model, ok: r.ok, status: r.status || r.error });
      await load();
    } catch (e) {
      setPullMsg({ model, ok: false, status: e.message });
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  const reachable = !!status.reachable;
  const models = status.models || [];
  const pref = status.preferred || {};

  return (
    <Panel
      testid="ollama-panel"
      title="Ollama · LOQ runtime"
      sub={status.url || "not configured"}
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase flex items-center gap-1.5">
          {reachable ? (
            <span className="text-emerald-400 flex items-center gap-1">
              <CheckCircle2 size={10} /> online
            </span>
          ) : (
            <span className="text-zinc-500 flex items-center gap-1">
              <AlertCircle size={10} /> offline
            </span>
          )}
        </span>
      }
    >
      <div className="space-y-3">
        <div>
          <div className="panel-label mb-1">gateway url</div>
          <div className="flex gap-2">
            <input
              data-testid="ollama-url-input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://tatortot.local:11434"
              className="flex-1 bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
            />
            <button
              data-testid="ollama-save-btn"
              onClick={save}
              disabled={busy}
              className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-3 py-2"
            >
              set
            </button>
          </div>
          {status.error && (
            <div className="mt-1.5 font-mono-term text-[10px] text-rose-400">
              {status.error}
            </div>
          )}
        </div>

        <div>
          <div className="panel-label mb-1 flex items-center gap-1.5">
            <Cpu size={11} /> preferred models
          </div>
          <div className="space-y-1.5">
            {[
              ["proposer", pref.proposer, status.has_proposer],
              ["verifier", pref.verifier, status.has_verifier],
              ["critic", pref.critic, null],
            ].map(([role, name, present]) => (
              <div
                key={role}
                data-testid={`ollama-model-${role}`}
                className="flex items-center justify-between border border-white/10 px-2 py-1.5"
              >
                <div className="flex flex-col">
                  <span className="panel-label">{role}</span>
                  <span className="font-mono-term text-xs text-zinc-200">{name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {present === true && <CheckCircle2 size={12} className="text-emerald-400" />}
                  {present === false && <AlertCircle size={12} className="text-amber-400" />}
                  <button
                    data-testid={`ollama-pull-${role}`}
                    onClick={() => pull(name)}
                    disabled={busy || !reachable}
                    className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-300 disabled:text-zinc-600 border border-white/10 px-2 py-1 hover:bg-white/5 flex items-center gap-1"
                  >
                    <Download size={10} /> pull
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {pullMsg && (
          <div
            data-testid="ollama-pull-msg"
            className={`font-mono-term text-[11px] p-2 border ${
              pullMsg.ok === false
                ? "border-rose-500/30 text-rose-300"
                : "border-emerald-500/30 text-emerald-300"
            }`}
          >
            {pullMsg.model} · {pullMsg.status}
          </div>
        )}

        {models.length > 0 && (
          <div>
            <div className="panel-label mb-1">installed ({models.length})</div>
            <div className="font-mono-term text-[10px] text-zinc-400 max-h-24 overflow-auto space-y-0.5">
              {models.map((m) => (
                <div key={m} className="truncate">
                  {m}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
};
