import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, Eye, EyeOff, ExternalLink, KeyRound, Loader2, X } from "lucide-react";
import { gw3SecretsStatus, gw3SaveSecrets } from "../../lib/ghostApi";

const DISMISSED_KEY = "gh05t3.v3secrets.dismissed";

export const V3SecretsModal = () => {
  const [status,   setStatus]   = useState(null);
  const [visible,  setVisible]  = useState(false);
  const [akInput,  setAkInput]  = useState("");
  const [ghInput,  setGhInput]  = useState("");
  const [grInput,  setGrInput]  = useState("");
  const [goInput,  setGoInput]  = useState("");
  const [showAk,   setShowAk]   = useState(false);
  const [showGh,   setShowGh]   = useState(false);
  const [showGr,   setShowGr]   = useState(false);
  const [showGo,   setShowGo]   = useState(false);
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
        const hasAnyLlm = s.anthropic_api_key?.set || s.groq_api_key?.set || s.google_ai_key?.set;
        if (!hasAnyLlm) setVisible(true);
      } catch {
        // gateway_v3 offline — stay hidden
      }
    };

    check();
    const iv = setInterval(check, 15_000);
    return () => clearInterval(iv);
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "1");
    setVisible(false);
  };

  const save = async () => {
    const hasAny = akInput.trim() || ghInput.trim() || grInput.trim() || goInput.trim();
    if (!hasAny) return;
    setBusy(true);
    setError("");
    try {
      await gw3SaveSecrets(
        akInput.trim() || null,
        ghInput.trim() || null,
        grInput.trim() || null,
        goInput.trim() || null,
      );
      setSaved(true);
      setAkInput(""); setGhInput(""); setGrInput(""); setGoInput("");
      const s = await gw3SecretsStatus();
      setStatus(s);
      const hasAnyLlm = s.anthropic_api_key?.set || s.groq_api_key?.set || s.google_ai_key?.set;
      if (hasAnyLlm) setTimeout(() => setVisible(false), 1800);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "save failed");
    } finally {
      setBusy(false);
    }
  };

  if (!visible) return null;

  const akSet = status?.anthropic_api_key?.set;
  const ghSet = status?.github_pat?.set;
  const grSet = status?.groq_api_key?.set;
  const goSet = status?.google_ai_key?.set;

  const KeyField = ({ label, hint, hintUrl, value, onChange, show, onShow, placeholder, isSet, preview }) => (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="font-mono-term text-[9px] uppercase tracking-[0.2em] text-zinc-500">
          {label}
        </label>
        {isSet && (
          <span className="font-mono-term text-[9px] text-emerald-400 flex items-center gap-1">
            <CheckCircle size={9} /> {preview}
          </span>
        )}
      </div>
      <div className="flex gap-1">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
          placeholder={isSet ? "already set — paste to update" : placeholder}
          autoComplete="off"
          className="flex-1 bg-black border border-white/10 px-3 py-2 font-mono-term text-[12px] text-zinc-100 outline-none focus:border-amber-500/50 placeholder:text-zinc-700"
        />
        <button
          onClick={() => onShow((v) => !v)}
          className="border border-white/10 px-2.5 text-zinc-500 hover:text-zinc-300"
          tabIndex={-1}
        >
          {show ? <EyeOff size={12} /> : <Eye size={12} />}
        </button>
      </div>
      {hint && (
        <a
          href={hintUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono-term text-[9px] text-zinc-600 hover:text-amber-400 mt-0.5 flex items-center gap-1"
        >
          <ExternalLink size={8} /> {hint}
        </a>
      )}
    </div>
  );

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
          <KeyRound size={12} /> first-boot setup
        </div>

        <h2 className="font-serif-display text-xl text-zinc-100 mb-1">
          Add your keys
        </h2>
        <p className="font-mono-term text-[11px] text-zinc-400 mb-4 leading-relaxed">
          At least one LLM key is required. Groq is free — no credit card.
          Keys are saved to <span className="text-zinc-300">backend/.env</span> on this machine.
        </p>

        <div className="space-y-3 mb-5">
          <KeyField
            label="Groq API Key (free)"
            hint="console.groq.com → API Keys — free, no card"
            hintUrl="https://console.groq.com"
            value={grInput} onChange={setGrInput}
            show={showGr} onShow={setShowGr}
            placeholder="gsk_…"
            isSet={grSet} preview={status?.groq_api_key?.preview}
          />
          <KeyField
            label="Anthropic API Key"
            hint="console.anthropic.com → API Keys"
            hintUrl="https://console.anthropic.com"
            value={akInput} onChange={setAkInput}
            show={showAk} onShow={setShowAk}
            placeholder="sk-ant-…"
            isSet={akSet} preview={status?.anthropic_api_key?.preview}
          />
          <KeyField
            label="Google AI Key (free)"
            hint="aistudio.google.com/app/apikey — free"
            hintUrl="https://aistudio.google.com/app/apikey"
            value={goInput} onChange={setGoInput}
            show={showGo} onShow={setShowGo}
            placeholder="AIza…"
            isSet={goSet} preview={status?.google_ai_key?.preview}
          />
          <KeyField
            label="GitHub Personal Access Token"
            hint="github.com → Settings → Developer settings → Tokens (classic) → repo scope"
            hintUrl="https://github.com/settings/tokens"
            value={ghInput} onChange={setGhInput}
            show={showGh} onShow={setShowGh}
            placeholder="ghp_…"
            isSet={ghSet} preview={status?.github_pat?.preview}
          />
        </div>

        {error && (
          <div className="font-mono-term text-[10px] text-rose-400 flex items-center gap-1.5 mb-3">
            <AlertTriangle size={10} /> {error}
          </div>
        )}

        {saved && !error && (
          <div className="font-mono-term text-[10px] text-emerald-400 flex items-center gap-1.5 mb-3">
            <CheckCircle size={10} /> saved — GH05T3 is live
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={busy || (!akInput.trim() && !ghInput.trim() && !grInput.trim() && !goInput.trim())}
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
