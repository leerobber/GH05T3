import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { hcmCloud } from "../../lib/ghostApi";

export const HcmCloudPanel = ({ refreshKey }) => {
  const [cloud, setCloud] = useState([]);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    hcmCloud()
      .then((d) => setCloud(d.cloud || []))
      .catch(() => {});
  }, [refreshKey]);

  const size = 280;
  const pad = 16;
  const scale = (size - pad * 2) / 2;

  return (
    <Panel
      testid="hcm-cloud-panel"
      title="HCM · cognitive mesh"
      sub={`${cloud.length} concepts · 10,000 dims · PCA-2`}
    >
      <div className="relative" style={{ height: size }}>
        <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full">
          <line x1={size / 2} y1={pad} x2={size / 2} y2={size - pad} stroke="rgba(255,255,255,0.05)" />
          <line x1={pad} y1={size / 2} x2={size - pad} y2={size / 2} stroke="rgba(255,255,255,0.05)" />
          {cloud.map((p) => (
            <circle
              key={p.idx}
              cx={size / 2 + p.x * scale}
              cy={size / 2 + p.y * scale}
              r={hover === p.idx ? 4 : 2}
              fill={p.color}
              opacity={hover === p.idx ? 1 : 0.75}
              onMouseEnter={() => setHover(p.idx)}
              onMouseLeave={() => setHover(null)}
              style={{ transition: "r 120ms" }}
            />
          ))}
        </svg>
        {hover !== null && cloud[hover] && (
          <div className="absolute top-1 right-1 font-mono-term text-[10px] text-amber-400 pointer-events-none">
            #{cloud[hover].idx} · {cloud[hover].label} · {cloud[hover].room}
          </div>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Array.from(new Set(cloud.map((p) => p.room))).map((r) => {
          const color = cloud.find((p) => p.room === r)?.color;
          const count = cloud.filter((p) => p.room === r).length;
          return (
            <span key={r} className="font-mono-term text-[9px] text-zinc-500 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              {r}·{count}
            </span>
          );
        })}
      </div>
    </Panel>
  );
};
