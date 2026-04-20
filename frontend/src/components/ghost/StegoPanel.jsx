import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { stegoCover, stegoDecode, stegoEncode } from "../../lib/ghostApi";
import { Lock, Unlock } from "lucide-react";

export const StegoPanel = () => {
  const [secret, setSecret] = useState("RUN!");
  const [cover, setCover] = useState("");
  const [covertext, setCovertext] = useState("");
  const [bits, setBits] = useState(null);
  const [decoded, setDecoded] = useState("");
  const [capacity, setCapacity] = useState(0);

  useEffect(() => {
    stegoCover().then((d) => {
      setCover(d.cover);
      setCapacity(d.capacity_bytes);
    });
  }, []);

  const enc = async () => {
    const r = await stegoEncode(secret, cover);
    setCovertext(r.covertext);
    setBits(r.bits);
  };

  const dec = async () => {
    const r = await stegoDecode(covertext, Math.ceil((bits || 0) / 8) || null);
    setDecoded(r.secret);
  };

  return (
    <Panel
      testid="stego-panel"
      title="GhostVeil · steganography"
      sub={`capacity: ${capacity} bytes in cover`}
    >
      <div className="space-y-2">
        <div>
          <div className="panel-label mb-1">secret (≤ {capacity} bytes)</div>
          <input
            data-testid="stego-secret"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
        </div>
        <div className="flex gap-2">
          <button
            data-testid="stego-encode-btn"
            onClick={enc}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 border border-amber-500/30 px-2.5 py-1 flex items-center gap-1.5"
          >
            <Lock size={11} /> encode
          </button>
          <button
            data-testid="stego-decode-btn"
            onClick={dec}
            disabled={!covertext}
            className="font-mono-term text-[10px] tracking-[0.25em] uppercase text-zinc-300 disabled:text-zinc-600 border border-white/10 px-2.5 py-1 flex items-center gap-1.5"
          >
            <Unlock size={11} /> decode
          </button>
          {bits !== null && (
            <span className="font-mono-term text-[10px] text-zinc-500 self-center">
              {bits} bits written
            </span>
          )}
        </div>
        {covertext && (
          <div>
            <div className="panel-label mb-1">covertext (looks normal)</div>
            <div
              data-testid="stego-covertext"
              className="bg-black border border-white/10 p-2 font-sans text-[11px] leading-relaxed text-zinc-300 max-h-32 overflow-y-auto ghost-scroll whitespace-pre-wrap"
            >
              {covertext}
            </div>
          </div>
        )}
        {decoded && (
          <div>
            <div className="panel-label mb-1">recovered secret</div>
            <div
              data-testid="stego-decoded"
              className="font-mono-term text-sm text-amber-400 bg-black border border-amber-500/30 p-2"
            >
              {decoded}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
};
