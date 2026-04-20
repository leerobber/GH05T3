import React, { useEffect, useRef, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Eye, EyeOff, Image as ImageIcon } from "lucide-react";

export const GhostEyePanel = ({ liveFrame }) => {
  const [frames, setFrames] = useState([]);
  const [enabled, setEnabled] = useState(true);
  const [showing, setShowing] = useState(null);
  const pushedRef = useRef(new Set());

  const load = () => {
    api.get("/ghosteye/recent", { params: { limit: 8 } })
      .then((r) => setFrames(r.data.frames || []))
      .catch(() => {});
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (liveFrame && !pushedRef.current.has(liveFrame.id)) {
      pushedRef.current.add(liveFrame.id);
      setFrames((prev) => [liveFrame, ...prev].slice(0, 8));
    }
  }, [liveFrame]);

  const toggle = async () => {
    const next = !enabled;
    setEnabled(next);
    try {
      await api.post("/companion/ghosteye/toggle", null, { params: { enabled: next } });
    } catch {}
  };

  const viewFrame = async (id) => {
    try {
      const r = await api.get(`/ghosteye/frame/${id}`);
      setShowing(r.data);
    } catch {}
  };

  return (
    <Panel
      testid="ghosteye-panel"
      title="GhostEye · ambient context"
      sub={frames[0] ? `last: ${new Date(frames[0].timestamp).toLocaleTimeString()} · ${frames[0].active_app || "screen"}` : "no frames yet"}
      right={
        <button
          data-testid="ghosteye-toggle-btn"
          onClick={toggle}
          className={`font-mono-term text-[10px] tracking-[0.25em] uppercase px-2 py-1 border flex items-center gap-1.5 ${enabled ? "text-amber-400 border-amber-500/30" : "text-zinc-500 border-white/10"}`}
        >
          {enabled ? <Eye size={11} /> : <EyeOff size={11} />}
          {enabled ? "watching" : "paused"}
        </button>
      }
    >
      <div className="space-y-2 max-h-80 overflow-y-auto ghost-scroll pr-1">
        {frames.length === 0 && (
          <div className="font-mono-term text-[11px] text-zinc-600">
            GhostEye idle. Run companion with <code>--ghosteye</code> flag.
          </div>
        )}
        {frames.map((f) => (
          <button
            key={f.id}
            onClick={() => f.has_image && viewFrame(f.id)}
            className="w-full text-left border border-white/10 hover:border-amber-500/30 p-2"
          >
            <div className="flex items-center gap-2">
              {f.has_image ? <ImageIcon size={11} className="text-amber-400" /> : <span className="w-3" />}
              <span className="font-mono-term text-[10px] text-zinc-400 flex-1 truncate">
                {f.active_app || "screen"}
              </span>
              <span className="font-mono-term text-[9px] text-zinc-600">
                {new Date(f.timestamp).toLocaleTimeString()}
              </span>
            </div>
            {f.text && (
              <div className="mt-1 font-mono-term text-[10px] text-zinc-500 line-clamp-2 whitespace-pre-wrap">
                {f.text.slice(0, 160)}
              </div>
            )}
          </button>
        ))}
      </div>
      {showing && (
        <div
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-8"
          onClick={() => setShowing(null)}
        >
          <div className="max-w-5xl max-h-[90vh] overflow-auto border border-amber-500/30 bg-black">
            <img src={`data:image/png;base64,${showing.png_b64}`} alt="frame" />
            <div className="p-3 font-mono-term text-[11px] text-zinc-400">
              {showing.active_app} · {new Date(showing.timestamp).toLocaleString()}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
};
