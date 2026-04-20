import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Laptop, Send, Terminal, Camera, X, RotateCw } from "lucide-react";

export const CompanionPanel = () => {
  const [status, setStatus] = useState(null);
  const [pairCode, setPairCode] = useState(null);
  const [shot, setShot] = useState(null);
  const [cmd, setCmd] = useState("git status");
  const [shellOut, setShellOut] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.get("/companion/status").then((r) => setStatus(r.data)).catch(() => {});
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 6000);
    return () => clearInterval(t);
  }, []);

  const newCode = async () => {
    const r = await api.post("/companion/pair");
    setPairCode(r.data);
    refresh();
  };

  const cmdCall = async (action, args = {}) => {
    setBusy(true);
    try {
      const r = await api.post("/companion/command", { action, args });
      return r.data.result;
    } catch (e) {
      return { error: e?.response?.data?.detail || e.message };
    } finally {
      setBusy(false);
    }
  };

  const screenshot = async () => {
    const r = await cmdCall("screenshot");
    if (r?.png_b64) setShot(r.png_b64);
    else setShot(null);
  };

  const shell = async () => {
    const r = await cmdCall("shell", { cmd });
    setShellOut(r);
  };

  const revoke = async (tok) => {
    const full = status?.connected?.find((c) => c.token_hint === tok)?.token_hint;
    if (!window.confirm("Sever this companion session?")) return;
    // we only have token_hint on FE — for MVP, revoke the first connected
    await api.post("/companion/revoke", null, { params: { token: "*" } }).catch(() => {});
    refresh();
  };

  const online = (status?.connected || []).length > 0;
  const caps = status?.connected?.[0]?.capabilities || [];

  return (
    <Panel
      testid="companion-panel"
      title="Companion · local ghost"
      sub={online ? `${status.connected[0].label} · ${status.connected[0].info?.os || "?"}` : "no device paired"}
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 flex items-center gap-1.5">
          <Laptop size={11} />
          <span className={`dot ${online ? "dot-active" : "dot-idle"}`} />
          {online ? "linked" : "offline"}
        </span>
      }
    >
      {!online && (
        <div className="space-y-2">
          <button
            data-testid="companion-pair-btn"
            onClick={newCode}
            className="w-full font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 border border-amber-500/30 px-2 py-1.5"
          >
            pair new device
          </button>
          {pairCode && (
            <div className="border border-amber-500/30 p-3 text-center">
              <div className="panel-label mb-1">one-time code · expires 10 min</div>
              <div className="font-mono-term text-3xl text-amber-400 tracking-[0.3em]">{pairCode.code}</div>
              <div className="font-mono-term text-[10px] text-zinc-500 mt-2">
                On your laptop: <span className="text-zinc-300">python ghost_agent.py --pair-code {pairCode.code}</span>
              </div>
            </div>
          )}
          <div className="font-mono-term text-[10px] text-zinc-600 leading-relaxed">
            Install the companion from <code>/app/companion/</code>. See its README for flags.
          </div>
        </div>
      )}

      {online && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1">
            {caps.map((c) => (
              <span key={c} className="font-mono-term text-[9px] tracking-[0.15em] uppercase text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5">
                {c}
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            {caps.includes("screen_read") && (
              <button
                data-testid="companion-screenshot-btn"
                onClick={screenshot}
                disabled={busy}
                className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2 py-1 flex items-center gap-1.5"
              >
                <Camera size={11} /> eye
              </button>
            )}
            <button
              onClick={refresh}
              className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-400 border border-white/10 px-2 py-1 flex items-center gap-1.5"
            >
              <RotateCw size={11} /> refresh
            </button>
            <button
              data-testid="companion-revoke-btn"
              onClick={revoke}
              className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-rose-300 border border-rose-500/30 px-2 py-1 flex items-center gap-1.5 ml-auto"
            >
              <X size={11} /> revoke
            </button>
          </div>
          {shot && (
            <div className="border border-white/10 p-1 bg-black">
              <img src={`data:image/png;base64,${shot}`} alt="screen" className="w-full" />
            </div>
          )}
          {caps.includes("shell_exec") && (
            <div className="space-y-1.5">
              <div className="panel-label flex items-center gap-1.5">
                <Terminal size={10} /> shell (allow-list)
              </div>
              <div className="flex gap-1">
                <input
                  data-testid="companion-shell-cmd"
                  value={cmd}
                  onChange={(e) => setCmd(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && shell()}
                  className="flex-1 bg-black border border-white/10 p-1.5 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
                />
                <button
                  data-testid="companion-shell-btn"
                  onClick={shell}
                  disabled={busy}
                  className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2"
                >
                  <Send size={11} />
                </button>
              </div>
              {shellOut && (
                <pre className="font-mono-term text-[10px] text-zinc-400 bg-black border border-white/10 p-2 whitespace-pre-wrap max-h-40 overflow-y-auto ghost-scroll">
                  {shellOut.error
                    ? `err: ${shellOut.error}`
                    : `$ rc=${shellOut.rc}\n${shellOut.stdout}${shellOut.stderr ? "\n---stderr---\n" + shellOut.stderr : ""}`}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
};
