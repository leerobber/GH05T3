import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Zap, CheckCircle2, AlertCircle } from "lucide-react";

export const LlmConfigPanel = () => {
  const [status, setStatus] = useState(null);
  const [provider, setProvider] = useState("auto");
  const [gKey, setGKey] = useState("");
  const [grKey, setGrKey] = useState("");
  const [testOut, setTestOut] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get("/llm/config").then((r) => {
      setStatus(r.data);
      setProvider(r.data.provider || "auto");
    }).catch(() => {});
  };
  useEffect(load, []);

  const save = async () => {
    setBusy(true);
    try {
      const body = { nightly_provider: provider };
      if (gKey.trim()) body.google_api_key = gKey.trim();
      if (grKey.trim()) body.groq_api_key = grKey.trim();
      await api.post("/llm/config", body);
      setGKey("");
      setGrKey("");
      load();
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setTestOut(null);
    try {
      const r = await api.post("/llm/test");
      setTestOut({ ok: true, ...r.data });
    } catch (e) {
      setTestOut({ ok: false, err: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  return (
    <Panel
      testid="llm-config-panel"
      title="Nightly LLM · free router"
      sub={status.provider}
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 flex items-center gap-1.5">
          fallback: {status.fallback.split(":")[1]}
        </span>
      }
    >
      <div className="grid grid-cols-2 gap-2 mb-3">
        {["auto", "google", "groq", "ollama"].map((p) => (
          <button
            key={p}
            data-testid={`llm-provider-${p}`}
            onClick={() => setProvider(p)}
            className={`font-mono-term text-[10px] tracking-[0.2em] uppercase px-2 py-1.5 border ${
              provider === p ? "border-amber-500/50 text-amber-400 bg-amber-500/5" : "border-white/10 text-zinc-400"
            }`}
          >
            {p}
          </button>
        ))}
      </div>
      <div className="space-y-2">
        <div>
          <div className="panel-label mb-1 flex items-center gap-1.5">
            google ai studio key
            {status.has_google_key && <CheckCircle2 size={10} className="text-emerald-400" />}
          </div>
          <input
            data-testid="llm-google-key"
            type="password"
            value={gKey}
            onChange={(e) => setGKey(e.target.value)}
            placeholder={status.has_google_key ? "stored · paste to replace" : "AIza… (free tier, gemini-2.5-flash)"}
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
        </div>
        <div>
          <div className="panel-label mb-1 flex items-center gap-1.5">
            groq key
            {status.has_groq_key && <CheckCircle2 size={10} className="text-emerald-400" />}
          </div>
          <input
            data-testid="llm-groq-key"
            type="password"
            value={grKey}
            onChange={(e) => setGrKey(e.target.value)}
            placeholder={status.has_groq_key ? "stored · paste to replace" : "gsk_… (free tier, llama-3.3-70b)"}
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
        </div>
        <div className="flex gap-2">
          <button
            data-testid="llm-save-btn"
            onClick={save}
            disabled={busy}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2 py-1.5"
          >
            save
          </button>
          <button
            data-testid="llm-test-btn"
            onClick={test}
            disabled={busy}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-300 disabled:text-zinc-600 border border-white/10 px-2 py-1.5 flex items-center justify-center gap-1.5"
          >
            <Zap size={11} /> round-trip
          </button>
        </div>
        {testOut && (
          <div
            data-testid="llm-test-out"
            className={`font-mono-term text-[11px] p-2 border ${testOut.ok ? "border-emerald-500/30 text-emerald-300" : "border-rose-500/30 text-rose-300"}`}
          >
            {testOut.ok ? (
              <>
                <div className="flex items-center gap-1.5 mb-0.5">
                  <CheckCircle2 size={11} /> {testOut.engine}
                </div>
                <div className="text-zinc-300 font-sans">{testOut.text}</div>
              </>
            ) : (
              <div className="flex items-center gap-1.5">
                <AlertCircle size={11} /> {testOut.err}
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
};
