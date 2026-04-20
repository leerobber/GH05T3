import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { tgConfigure, tgStart, tgStatus, tgStop } from "../../lib/ghostApi";
import { Send, Square, Link2 } from "lucide-react";

export const TelegramPanel = () => {
  const [status, setStatus] = useState(null);
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState("");

  const refresh = () => tgStatus().then(setStatus).catch(() => {});
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 6000);
    return () => clearInterval(t);
  }, []);

  const save = async () => {
    setMsg("saving…");
    try {
      const s = await tgConfigure({ bot_token: token });
      setStatus(s);
      setToken("");
      setMsg("token saved. press Start.");
    } catch (e) {
      setMsg("save failed: " + (e?.response?.data?.detail || e.message));
    }
  };
  const start = async () => {
    setMsg("starting…");
    try {
      const r = await tgStart();
      setMsg(r.ok ? (r.already ? "already running" : "started") : r.error);
      refresh();
    } catch (e) {
      setMsg("start failed: " + e.message);
    }
  };
  const stop = async () => {
    await tgStop();
    setMsg("stopped");
    refresh();
  };

  const running = status?.running;

  return (
    <Panel
      testid="telegram-panel"
      title="Telegram · remote ghost"
      sub={
        status?.configured
          ? `@${status.bot_username || "bot"} · chat: ${status.locked_chat_id ?? "unlocked"}`
          : "bot token not set"
      }
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase text-zinc-500 flex items-center gap-1.5">
          <span className={`dot ${running ? "dot-active" : "dot-idle"}`} />
          {running ? "polling" : "idle"}
        </span>
      }
    >
      {!status?.configured && (
        <div className="space-y-2">
          <input
            data-testid="tg-token"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="bot token from @BotFather"
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
          <button
            data-testid="tg-save-btn"
            onClick={save}
            disabled={!token.trim()}
            className="w-full font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 border border-amber-500/30 px-2.5 py-1.5 flex items-center justify-center gap-1.5"
          >
            <Link2 size={11} /> save token
          </button>
        </div>
      )}
      {status?.configured && (
        <div className="flex gap-2">
          <button
            data-testid="tg-start-btn"
            onClick={start}
            disabled={running}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2.5 py-1.5 flex items-center justify-center gap-1.5"
          >
            <Send size={11} /> start
          </button>
          <button
            data-testid="tg-stop-btn"
            onClick={stop}
            disabled={!running}
            className="flex-1 font-mono-term text-[10px] tracking-[0.25em] uppercase text-rose-300 disabled:text-zinc-600 border border-rose-500/30 px-2.5 py-1.5 flex items-center justify-center gap-1.5"
          >
            <Square size={11} /> stop
          </button>
        </div>
      )}
      {status?.last_error && (
        <div className="mt-2 font-mono-term text-[10px] text-rose-400">err: {status.last_error}</div>
      )}
      {msg && <div className="mt-2 font-mono-term text-[10px] text-zinc-500">{msg}</div>}
      <div className="mt-3 font-mono-term text-[10px] text-zinc-600 leading-relaxed">
        message /start, /status, /kairos, or anything. first message locks the chat_id.
      </div>
    </Panel>
  );
};
