import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { demoGhostScript, runGhostScript } from "../../lib/ghostApi";
import { Play } from "lucide-react";

export const GhostShellPanel = () => {
  const [src, setSrc] = useState("");
  const [log, setLog] = useState([]);
  const [err, setErr] = useState(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    demoGhostScript().then((d) => {
      setSrc(d.source);
      setLog(d.result.log || []);
    });
  }, []);

  const execute = async () => {
    setRunning(true);
    setErr(null);
    try {
      const r = await runGhostScript(src);
      if (r.ok) setLog(r.log);
      else {
        setErr(r.error);
        setLog([]);
      }
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Panel
      testid="ghostshell-panel"
      title="GhostShell · GhostScript"
      sub="lexer → parser → AST → evaluator"
      right={
        <button
          data-testid="ghostshell-run-btn"
          onClick={execute}
          disabled={running}
          className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 px-2.5 py-1 flex items-center gap-1.5"
        >
          <Play size={11} /> run
        </button>
      }
    >
      <textarea
        data-testid="ghostshell-editor"
        value={src}
        onChange={(e) => setSrc(e.target.value)}
        rows={8}
        className="w-full bg-black border border-white/10 p-2.5 font-mono-term text-[11px] text-zinc-200 outline-none focus:border-amber-500/50 resize-none"
      />
      {err && (
        <div className="mt-2 font-mono-term text-[11px] text-rose-400">parse error: {err}</div>
      )}
      <div className="mt-3 font-mono-term text-[10px] text-zinc-500 space-y-1 max-h-40 overflow-y-auto ghost-scroll">
        {log.map((l, i) => (
          <div key={i}>
            <span className="text-amber-400">[{l.step}]</span>{" "}
            <span className="text-zinc-400">{l.agent}</span>{" "}
            <span className="text-zinc-300">{l.note}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
};
