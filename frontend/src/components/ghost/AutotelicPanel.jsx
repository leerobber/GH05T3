import React, { useState, useCallback } from "react";
import { CheckCircle, PlusCircle, Trash2, Lightbulb, ChevronDown, ChevronUp } from "lucide-react";
import { Panel, Bar } from "./primitives";
import {
  createGoal, updateGoal, deleteGoal, completeGoal, suggestGoals,
} from "../../lib/ghostApi";
import { toast } from "sonner";

const PRIORITY_COLORS = {
  0: "text-rose-400 border-rose-500/40",
  1: "text-amber-400 border-amber-500/40",
  2: "text-cyan-400 border-cyan-500/40",
  3: "text-zinc-400 border-zinc-600/40",
};
const PRIORITY_LABELS = { 0: "CRIT", 1: "HIGH", 2: "MED", 3: "LOW" };
const CATEGORY_COLORS = {
  training:    "bg-amber-500/10 text-amber-400",
  security:    "bg-rose-500/10 text-rose-400",
  memory:      "bg-violet-500/10 text-violet-400",
  integration: "bg-cyan-500/10 text-cyan-400",
  meta:        "bg-emerald-500/10 text-emerald-400",
  general:     "bg-zinc-700/50 text-zinc-400",
};
const BAR_COLORS = {
  complete: "#22c55e",
  paused:   "#71717a",
  active:   "var(--ghost-amber)",
};
const TABS = ["all", "active", "complete", "paused"];
const CATEGORIES = ["general", "training", "security", "memory", "integration", "meta"];

function GoalRow({ goal, onUpdate, onDelete, onComplete }) {
  const [expanded, setExpanded] = useState(false);
  const [editProgress, setEditProgress] = useState(false);
  const [progressVal, setProgressVal] = useState(Math.round((goal.progress || 0) * 100));

  const handleProgressSave = async () => {
    try {
      await onUpdate(goal.id, { progress: progressVal / 100 });
    } catch {}
    setEditProgress(false);
  };

  const isDone = goal.status === "complete";

  return (
    <li className={`border-b border-white/5 pb-2 mb-2 last:border-0 last:mb-0 last:pb-0 ${isDone ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-2">
        <div className={`font-mono-term text-[9px] border px-1 py-0.5 mt-0.5 flex-shrink-0 ${PRIORITY_COLORS[goal.priority] || PRIORITY_COLORS[2]}`}>
          {PRIORITY_LABELS[goal.priority] || "MED"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="font-mono-term text-[11px] text-zinc-200 truncate">{goal.title}</span>
            <div className="flex items-center gap-1 flex-shrink-0">
              <span className="font-mono-term text-[9px] text-amber-400">{Math.round((goal.progress || 0) * 100)}%</span>
              <button
                onClick={() => setExpanded((v) => !v)}
                className="text-zinc-600 hover:text-zinc-400"
                title="expand"
              >
                {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-1 mt-0.5">
            <span className={`font-mono-term text-[9px] px-1 rounded ${CATEGORY_COLORS[goal.category] || CATEGORY_COLORS.general}`}>
              {goal.category}
            </span>
            <span className="font-mono-term text-[9px] text-zinc-600 truncate">{goal.detail}</span>
          </div>
          <div className="mt-1">
            <Bar value={goal.progress || 0} color={BAR_COLORS[goal.status] || BAR_COLORS.active} />
          </div>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 ml-10 space-y-2">
          {!isDone && (
            <div className="flex items-center gap-2">
              {editProgress ? (
                <>
                  <input
                    type="range" min={0} max={100} value={progressVal}
                    onChange={(e) => setProgressVal(Number(e.target.value))}
                    className="w-24 accent-amber-400"
                  />
                  <span className="font-mono-term text-[10px] text-amber-400 w-8">{progressVal}%</span>
                  <button onClick={handleProgressSave}
                    className="font-mono-term text-[10px] text-emerald-400 hover:text-emerald-300 border border-emerald-500/30 px-2 py-0.5">
                    set
                  </button>
                  <button onClick={() => setEditProgress(false)}
                    className="font-mono-term text-[10px] text-zinc-500 hover:text-zinc-300">
                    cancel
                  </button>
                </>
              ) : (
                <button onClick={() => setEditProgress(true)}
                  className="font-mono-term text-[10px] text-zinc-500 hover:text-amber-400 border border-zinc-700 px-2 py-0.5">
                  set progress
                </button>
              )}
              <button
                onClick={() => onComplete(goal.id)}
                className="font-mono-term text-[10px] text-emerald-400 hover:text-emerald-300 border border-emerald-500/30 px-2 py-0.5 flex items-center gap-1"
              >
                <CheckCircle size={10} /> done
              </button>
            </div>
          )}
          <div className="flex items-center gap-2">
            <select
              value={goal.status}
              onChange={(e) => onUpdate(goal.id, { status: e.target.value })}
              className="font-mono-term text-[10px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-1 py-0.5"
            >
              {["active", "paused", "abandoned", "complete"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button
              onClick={() => onDelete(goal.id)}
              className="font-mono-term text-[10px] text-rose-500 hover:text-rose-400 border border-rose-500/20 px-1.5 py-0.5 flex items-center gap-1"
            >
              <Trash2 size={10} /> remove
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function AddGoalForm({ onAdd, onCancel }) {
  const [title, setTitle]       = useState("");
  const [detail, setDetail]     = useState("");
  const [priority, setPriority] = useState(2);
  const [category, setCategory] = useState("general");
  const [busy, setBusy]         = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await onAdd(title.trim(), detail.trim(), Number(priority), category);
      setTitle(""); setDetail(""); setPriority(2); setCategory("general");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-3 space-y-2 border-t border-white/10 pt-3">
      <input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="goal title"
        maxLength={120}
        className="w-full font-mono-term text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-200 px-2 py-1 placeholder:text-zinc-600"
      />
      <input
        value={detail}
        onChange={(e) => setDetail(e.target.value)}
        placeholder="detail (optional)"
        maxLength={300}
        className="w-full font-mono-term text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-400 px-2 py-1 placeholder:text-zinc-600"
      />
      <div className="flex gap-2">
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="font-mono-term text-[10px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-1 py-1"
        >
          <option value={0}>critical</option>
          <option value={1}>high</option>
          <option value={2}>medium</option>
          <option value={3}>low</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="font-mono-term text-[10px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-1 py-1 flex-1"
        >
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || !title.trim()}
          className="font-mono-term text-[10px] tracking-widest uppercase text-amber-400 hover:text-amber-300 disabled:text-zinc-600 border border-amber-500/30 px-3 py-1"
        >
          {busy ? "adding…" : "+ add"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="font-mono-term text-[10px] text-zinc-500 hover:text-zinc-300 border border-zinc-700 px-2 py-1"
        >
          cancel
        </button>
      </div>
    </form>
  );
}

export function AutotelicPanel({ goals: initialGoals = [], onGoalsChange }) {
  const [goals, setGoals]       = useState(initialGoals);
  const [tab, setTab]           = useState("active");
  const [showAdd, setShowAdd]   = useState(false);
  const [suggesting, setSuggesting] = useState(false);

  // Sync when parent state updates (e.g. WS push)
  React.useEffect(() => { setGoals(initialGoals); }, [initialGoals]);

  const mutate = useCallback((updated) => {
    setGoals(updated);
    onGoalsChange?.(updated);
  }, [onGoalsChange]);

  const handleAdd = async (title, detail, priority, category) => {
    try {
      const goal = await createGoal(title, detail, priority, category);
      mutate([...goals, goal]);
      setShowAdd(false);
      toast("Goal added", { description: title });
    } catch (e) {
      toast.error("Failed to add goal: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleUpdate = async (id, fields) => {
    try {
      const updated = await updateGoal(id, fields);
      mutate(goals.map((g) => (g.id === id ? updated : g)));
    } catch (e) {
      toast.error("Update failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteGoal(id);
      mutate(goals.filter((g) => g.id !== id));
      toast("Goal removed");
    } catch (e) {
      toast.error("Delete failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleComplete = async (id) => {
    try {
      const updated = await completeGoal(id);
      mutate(goals.map((g) => (g.id === id ? updated : g)));
      toast.success("Goal completed");
    } catch (e) {
      toast.error("Complete failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleSuggest = async () => {
    setSuggesting(true);
    try {
      const suggestions = await suggestGoals(3);
      if (!suggestions.length) { toast("No new suggestions right now"); return; }
      for (const s of suggestions) {
        const goal = await createGoal(s.title, s.detail, s.priority ?? 2, s.category ?? "general");
        mutate((prev) => [...prev, goal]);
      }
      toast(`${suggestions.length} goal${suggestions.length > 1 ? "s" : ""} suggested`);
    } catch (e) {
      toast.error("Suggest failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setSuggesting(false);
    }
  };

  const filtered = goals.filter((g) => tab === "all" || g.status === tab);
  const activeCount = goals.filter((g) => g.status === "active").length;
  const completeCount = goals.filter((g) => g.status === "complete").length;

  return (
    <Panel
      testid="autotelic-panel"
      title="Autotelic Engine"
      sub={`${activeCount} active · ${completeCount} complete · ${goals.length} total`}
      right={
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleSuggest}
            disabled={suggesting}
            title="AI-suggest goals from current state"
            className="font-mono-term text-[9px] text-cyan-400 hover:text-cyan-300 disabled:text-zinc-600 border border-cyan-500/20 px-1.5 py-0.5 flex items-center gap-1"
          >
            <Lightbulb size={9} />
            {suggesting ? "…" : "suggest"}
          </button>
          <button
            onClick={() => setShowAdd((v) => !v)}
            className="font-mono-term text-[9px] text-amber-400 hover:text-amber-300 border border-amber-500/30 px-1.5 py-0.5 flex items-center gap-1"
          >
            <PlusCircle size={9} /> new
          </button>
        </div>
      }
    >
      <div className="flex gap-2 mb-3">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`font-mono-term text-[9px] tracking-widest uppercase px-2 py-0.5 border transition-colors ${
              tab === t
                ? "border-amber-500/50 text-amber-400"
                : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {showAdd && (
        <AddGoalForm onAdd={handleAdd} onCancel={() => setShowAdd(false)} />
      )}

      <ul className="space-y-0 max-h-72 overflow-y-auto ghost-scroll pr-1 mt-1">
        {filtered.length === 0 ? (
          <li className="font-mono-term text-[10px] text-zinc-600 py-4 text-center">
            no {tab !== "all" ? tab + " " : ""}goals
          </li>
        ) : (
          filtered.map((g) => (
            <GoalRow
              key={g.id}
              goal={g}
              onUpdate={handleUpdate}
              onDelete={handleDelete}
              onComplete={handleComplete}
            />
          ))
        )}
      </ul>
    </Panel>
  );
}
