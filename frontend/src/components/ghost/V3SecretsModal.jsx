import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, Eye, EyeOff, KeyRound, Loader2, X } from "lucide-react";
import { gw3SecretsStatus, gw3SaveSecrets } from "../../lib/ghostApi";

const DISMISSED_KEY = "gh05t3.v3secrets.dismissed";

export const V3SecretsModal = () => {
  const [status,   setStatus]   = useState(null);   // null = loading/offline
  const [visible,  setVisible]  = useState(false);
  const [akInput,  setAkInput]  = useState("");
  const [ghInput,  setGhInput]  = useState("");
  const [showAk,   setShowAk]   = useState(false);
  const [showGh,   setShowGh]   = useState(false);
  const [busy,     setBusy]     = useState(false);
  const [saved,    setSaved]    = useState(false);
  const [error,    setError]    = useState("");

  useEffect(() => {
    const dismissed = localStorage.getItem(DISMISSED_KEY) === "1";
    if (dismissed) return;

    const check = async () => {
      try {
        const s = await gw3SecretsStatus();
        setStatus(s);
        const needsKeys = !s.anthropic_api_key?.set || !s.github_pat?.set;
        if (needsKeys) setVisible(true);
      } catch {
        // gateway_v3 offline — stay hidden, no error
      }
    };

    check();
    // re-check every 15 s in case gateway comes online later
    const iv = setInterval(check, 15_000);
    return () => clearInterval(iv);
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "1");
    setVisible(false);
  };

  const save = async () => {
    if (!akInput.trim() && !ghInput.trim()) return;
    setBusy(true);
    setError("");
    try {
      const d = await gw3SaveSecrets(
        akInput.trim() || null,
        ghInput.trim() || null,
      );
      setSaved(true);
      setAkInput("");
      setGhInput("");
      // re-check status to update previews
      const s = await gw3SecretsStatus();
      setStatus(s);
      const stillNeeds = !s.anthropic_api_key?.set || !s.github_pat?.set;
      if (!stillNeeds) setTimeout(() => setVisible(false), 1800);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "save failed");
    } finally {
      setBusy(false);
    }
  };

  if (!visible) return null;

  const akSet = status?.anthropic_api_key?.set;
  const ghSet = status?.github_pat?.set;

  return (
    <div
      data-testid="v3-secrets-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
    >
      <div className="relative max-w-sm w-[94%] border border-amber-500/40 bg-[#0f0f11] p-6 shadow-2xl">
        <button
          onClick={dismiss}
          className="absolute top-2 right-2 text-zinc-500 hover:text-zinc-200"
          aria-label="close"
        >
          <X size={16} />
        </button>

        <div className="flex items-center gap-2 mb-2 text-amber-400 font-mono-term text-[10px] tracking-[0.25em] uppercase">
          <KeyRound size={12} /> v3 · first-boot setup
        </div>

        <h2 className="font-serif-display text-xl text-zinc-100 mb-1">
          Paste your keys
        </h2>
        <p className="font-mono-term text-[11px] text-zinc-400 mb-5 leading-relaxed">
          GH05T3 v3 needs two keys to unlock Claude + GitHub automation.
          Saved to <span className="text-zinc-300">backend/.env</span> on TatorTot.
        </p>

        <div className="space-y-4 mb-5">
          {/* Anthropic */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500">
                Anthropic API Key
              </label>
              {akSet && (
                <span className="font-mono-term text-[9px] text-emerald-400 flex items-center gap-1">
                  <CheckCircle size={9} /> {status.anthropic_api_key.preview}
                </span>
              )}
            </div>
            <div className="flex gap-1">
              <input
                type={showAk ? "text" : "password"}
                value={akInput}
                onChange={(e) => setAkInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && save()}
                placeholder={akSet ? "already set — paste to update" : "sk-ant-api03-…"}
                autoComplete="off"
                className="flex-1 bg-black border border-white/10 px-3 py-2 font-mono-term text-[12px] text-zinc-100 outline-none focus:border-amber-500/50 placeholder:text-zinc-700"
              />
              <button
                onClick={() => setShowAk((v) => !v)}
                className="border border-white/10 px-2.5 text-zinc-500 hover:text-zinc-300"
                tabIndex={-1}
              >
                {showAk ? <EyeOff size={12} /> : <Eye size={12} />}
              </button>
            </div>
            <p className="font-mono-term text-[9px] text-zinc-700 mt-0.5">
              console.anthropic.com → API Keys
            </p>
          </div>

          {/* GitHub */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500">
                GitHub Personal Access Token
              </label>
              {ghSet && (
                <span className="font-mono-term text-[9px] text-emerald-400 flex items-center gap-1">
                  <CheckCircle size={9} /> {status.github_pat.preview}
                </span>
              )}
            </div>
            <div className="flex gap-1">
              <input
                type={showGh ? "text" : "password"}
                value={ghInput}
                onChange={(e) => setGhInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && save()}
                placeholder={ghSet ? "already set — paste to update" : "ghp_…"}
                autoComplete="off"
                className="flex-1 bg-black border border-white/10 px-3 py-2 font-mono-term text-[12px] text-zinc-100 outline-none focus:border-amber-500/50 placeholder:text-zinc-700"
              />
              <button
                onClick={() => setShowGh((v) => !v)}
                className="border border-white/10 px-2.5 text-zinc-500 hover:text-zinc-300"
                tabIndex={-1}
              >
                {showGh ? <EyeOff size={12} /> : <Eye size={12} />}
              </button>
            </div>
            <p className="font-mono-term text-[9px] text-zinc-700 mt-0.5">
              github.com → Settings → Developer settings → Tokens (classic) → repo scope
            </p>
          </div>
        </div>

        {error && (
          <div className="font-mono-term text-[10px] text-rose-400 flex items-center gap-1.5 mb-3">
            <AlertTriangle size={10} /> {error}
          </div>
        )}

        {saved && !error && (
          <div className="font-mono-term text-[10px] text-emerald-400 flex items-center gap-1.5 mb-3">
            <CheckCircle size={10} /> saved — Claude + GitHub are live
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={busy || (!akInput.trim() && !ghInput.trim())}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/40 px-3 py-2.5 hover:bg-amber-500/10 flex items-center justify-center gap-2"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <KeyRound size={12} />}
            save keys
          </button>
          <button
            onClick={dismiss}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-500 border border-white/10 px-3 py-2.5 hover:bg-white/5"
          >
            later
          </button>
        </div>
      </div>
    </div>
  );
};
