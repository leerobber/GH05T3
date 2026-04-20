import React from "react";

export const Panel = ({ title, sub, right, className = "", children, testid, crimson = false, bgImage }) => (
  <section
    data-testid={testid}
    className={`panel ${crimson ? "panel-crimson" : ""} relative overflow-hidden ${className}`}
    style={
      bgImage
        ? { backgroundImage: `linear-gradient(180deg, rgba(15,15,17,0.92), rgba(15,15,17,0.98)), url(${bgImage})`, backgroundSize: "cover", backgroundPosition: "center" }
        : undefined
    }
  >
    {(title || right) && (
      <header className="flex items-center justify-between mb-3">
        <div>
          {title && <div className="panel-label">{title}</div>}
          {sub && <div className="text-[11px] text-zinc-500 font-mono-term mt-0.5">{sub}</div>}
        </div>
        {right}
      </header>
    )}
    {children}
  </section>
);

export const Stat = ({ label, value, delta, accent = "amber" }) => {
  const color = accent === "amber" ? "text-amber-400" : accent === "crimson" ? "text-rose-400" : "text-zinc-100";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="panel-label">{label}</span>
      <span className={`font-serif-display text-2xl leading-none ${color}`}>{value}</span>
      {delta !== undefined && (
        <span className="font-mono-term text-[10px] text-zinc-500">{delta}</span>
      )}
    </div>
  );
};

export const Bar = ({ value, max = 1, color = "var(--ghost-amber)" }) => (
  <div className="w-full h-[1px] bg-white/10">
    <div
      className="h-full"
      style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color, transition: "width 400ms ease" }}
    />
  </div>
);

export const Dot = ({ kind = "idle" }) => <span className={`dot dot-${kind}`} />;
