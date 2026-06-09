"use client";

import { useEffect, useRef, useState } from "react";

const BAR_COUNT = 32;

export default function Waveform({ playing }: { playing: boolean }) {
  // Flat initial state — no Math.random() to avoid SSR/client hydration mismatch
  const [bars, setBars] = useState(() =>
    Array.from({ length: BAR_COUNT }, () => 4)
  );
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!playing) {
      setBars(Array.from({ length: BAR_COUNT }, () => 4));
      return;
    }

    let frame = 0;
    const animate = () => {
      if (frame % 3 === 0) {
        setBars(Array.from({ length: BAR_COUNT }, (_, i) => {
          const base = Math.sin(frame * 0.05 + i * 0.4) * 10 + 14;
          return base + Math.random() * 8;
        }));
      }
      frame++;
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing]);

  return (
    <div className="flex items-end gap-px h-8 w-full">
      {bars.map((h, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm transition-[height] duration-75"
          style={{
            height: `${h}px`,
            background: `rgba(245,158,11,${0.4 + (h / 32) * 0.6})`,
          }}
        />
      ))}
    </div>
  );
}
