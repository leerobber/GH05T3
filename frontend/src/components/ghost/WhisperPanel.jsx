import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { api } from "../../lib/ghostApi";
import { Volume2, VolumeX, MessageSquareQuote } from "lucide-react";

const KEY = "gh05t3.whisper.enabled";
const VOL_KEY = "gh05t3.whisper.volume";

export const WhisperPanel = () => {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(KEY) !== "0");
  const [volume, setVolume] = useState(() => parseFloat(localStorage.getItem(VOL_KEY) || "1"));
  const [testText, setTestText] = useState("Hey Robert. I'm here.");
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState("");
  const [last, setLast] = useState(null);

  useEffect(() => {
    const load = () => {
      const list = window.speechSynthesis?.getVoices?.() || [];
      setVoices(list);
      if (!voiceName && list.length) {
        const pref = list.find((v) => /neural|natural|Ava|Aria|Samantha|Zira/i.test(v.name))
          || list.find((v) => v.lang?.startsWith("en"));
        if (pref) setVoiceName(pref.name);
      }
    };
    load();
    window.speechSynthesis?.addEventListener?.("voiceschanged", load);
    // listen for ghost-whisper events dispatched by App.js
    const onWhisper = (e) => setLast(e.detail);
    window.addEventListener("ghost-whisper", onWhisper);
    return () => {
      window.speechSynthesis?.removeEventListener?.("voiceschanged", load);
      window.removeEventListener("ghost-whisper", onWhisper);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = () => {
    const v = !enabled;
    setEnabled(v);
    localStorage.setItem(KEY, v ? "1" : "0");
    if (!v) window.speechSynthesis?.cancel();
  };

  const changeVol = (v) => {
    setVolume(v);
    localStorage.setItem(VOL_KEY, String(v));
  };

  const test = async () => {
    try {
      await api.post("/whisper", { text: testText });
    } catch {}
  };

  const setVoicePref = (name) => {
    setVoiceName(name);
    localStorage.setItem("gh05t3.whisper.voice", name);
  };

  return (
    <Panel
      testid="whisper-panel"
      title="Whisper · voice out"
      sub={enabled ? "speaking when alive" : "muted"}
      right={
        <button
          data-testid="whisper-toggle-btn"
          onClick={toggle}
          className={`font-mono-term text-[10px] tracking-[0.25em] uppercase px-2 py-1 border flex items-center gap-1.5 ${enabled ? "text-amber-400 border-amber-500/30" : "text-zinc-500 border-white/10"}`}
        >
          {enabled ? <Volume2 size={11} /> : <VolumeX size={11} />}
          {enabled ? "on" : "muted"}
        </button>
      }
    >
      <div className="space-y-3">
        <div>
          <div className="panel-label mb-1">voice</div>
          <select
            data-testid="whisper-voice-select"
            value={voiceName}
            onChange={(e) => setVoicePref(e.target.value)}
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          >
            {voices.length === 0 && <option value="">(loading…)</option>}
            {voices.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name} · {v.lang}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="panel-label mb-1 flex justify-between">
            <span>volume</span>
            <span>{Math.round(volume * 100)}%</span>
          </div>
          <input
            data-testid="whisper-volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={(e) => changeVol(parseFloat(e.target.value))}
            className="w-full accent-amber-500"
          />
        </div>
        <div className="flex gap-2">
          <input
            data-testid="whisper-test-text"
            value={testText}
            onChange={(e) => setTestText(e.target.value)}
            className="flex-1 bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
          <button
            data-testid="whisper-test-btn"
            onClick={test}
            disabled={!enabled}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-2 flex items-center gap-1.5"
          >
            <MessageSquareQuote size={11} /> test
          </button>
        </div>
        {last && (
          <div className="font-mono-term text-[10px] text-zinc-500 border-l border-amber-500/40 pl-2">
            last: [{last.source}] {last.text?.slice(0, 140)}
          </div>
        )}
      </div>
    </Panel>
  );
};
