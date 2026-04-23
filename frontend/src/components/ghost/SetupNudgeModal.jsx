import React, { useEffect, useState } from "react";
import { setupStatus } from "../../lib/ghostApi";
import { AlertTriangle, X, ExternalLink } from "lucide-react";

/**
 * First-boot nudge: appears when no user LLM keys exist, Ollama is unreachable,
 * and the Emergent Universal Key has exhausted its budget. Routes the user to
 * the LLM Config panel with clear copy-paste-ready links.
 */
export const SetupNudgeModal = () => {
  const [needs, setNeeds] = useState(false);
  const [dismissed, setDismissed] = useState(
    typeof window !== "undefined" &&
      window.localStorage.getItem("gh05t3.setup.dismissed") === "1",
  );

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const s = await setupStatus();
        if (alive) setNeeds(!!s.needs_setup);
      } catch {
        /* backend not ready yet */
      }
    };
    check();
    const iv = setInterval(check, 30_000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, []);

  if (!needs || dismissed) return null;

  const dismiss = () => {
    window.localStorage.setItem("gh05t3.setup.dismissed", "1");
    setDismissed(true);
  };

  const scrollToConfig = () => {
    const panel = document.querySelector('[data-testid="llm-config-panel"]');
    if (panel) panel.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div
      data-testid="setup-nudge-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm"
    >
      <div className="relative max-w-md w-[92%] border border-amber-500/40 bg-[#0f0f11] p-6">
        <button
          data-testid="setup-nudge-close"
          onClick={dismiss}
          className="absolute top-2 right-2 text-zinc-500 hover:text-zinc-200"
          aria-label="close"
        >
          <X size={16} />
        </button>
        <div className="flex items-center gap-2 mb-3 text-amber-400 font-mono-term text-[10px] tracking-[0.25em] uppercase">
          <AlertTriangle size={13} /> first-boot · llm key required
        </div>
        <h2 className="font-serif-display text-2xl text-zinc-100 leading-tight mb-2">
          Light me up, Robert.
        </h2>
        <p className="text-sm text-zinc-300 leading-relaxed mb-4">
          My shared Emergent key is rate-limited in production. To chat without
          interruption, paste a <b>free</b> Google AI (Gemini) or Groq key —
          either one unlocks me instantly and stays local to your account.
        </p>
        <div className="space-y-2 font-mono-term text-[11px] mb-5">
          <a
            data-testid="setup-nudge-google-link"
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-amber-400 hover:text-amber-300"
          >
            <ExternalLink size={11} /> aistudio.google.com/apikey · free gemini 2.5
          </a>
          <a
            data-testid="setup-nudge-groq-link"
            href="https://console.groq.com/keys"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-amber-400 hover:text-amber-300"
          >
            <ExternalLink size={11} /> console.groq.com/keys · free llama 3.3
          </a>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="setup-nudge-open-config"
            onClick={scrollToConfig}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 border border-amber-500/40 px-3 py-2 hover:bg-amber-500/10"
          >
            open llm config
          </button>
          <button
            data-testid="setup-nudge-dismiss"
            onClick={dismiss}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-400 border border-white/10 px-3 py-2 hover:bg-white/5"
          >
            later
          </button>
        </div>
      </div>
    </div>
  );
};
