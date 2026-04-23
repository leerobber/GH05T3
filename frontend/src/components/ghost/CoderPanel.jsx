import React, { useEffect, useState } from "react";
import { Panel } from "./primitives";
import { coderRepos, coderRun, coderRuns } from "../../lib/ghostApi";
import { GitBranch, Play, CheckCircle2, AlertCircle, ExternalLink, Loader2 } from "lucide-react";

/** Coder sub-agent panel — GitHub + PyTest full loop. */
export const CoderPanel = () => {
  const [repos, setRepos] = useState(null);
  const [repo, setRepo] = useState("");
  const [task, setTask] = useState("");
  const [subdir, setSubdir] = useState("");
  const [testTarget, setTestTarget] = useState("");
  const [iters, setIters] = useState(3);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);

  const loadRepos = async () => {
    try {
      const r = await coderRepos();
      setRepos(r);
      if (!repo && r.repos?.length) {
        setRepo(r.repos[0].full_name);
      }
    } catch {
      /* ignore */
    }
  };
  const loadRuns = async () => {
    try {
      const r = await coderRuns(6);
      setRuns(r.runs || []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    loadRepos();
    loadRuns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    if (!repo || !task.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await coderRun({
        repo,
        task: task.trim(),
        subdir: subdir.trim() || null,
        test_target: testTarget.trim() || null,
        max_iterations: Math.max(1, Math.min(6, Number(iters) || 3)),
        open_pr: true,
      });
      setResult(r);
      loadRuns();
    } catch (e) {
      setResult({ ok: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
    }
  };

  if (!repos) return null;

  const noPat = !repos.has_pat;

  return (
    <Panel
      testid="coder-panel"
      title="Coder · github + pytest"
      sub={noPat ? "GITHUB_PAT missing" : `${(repos.repos || []).length} repos whitelisted`}
      right={
        <span className="font-mono-term text-[9px] tracking-[0.2em] uppercase flex items-center gap-1.5 text-zinc-500">
          <GitBranch size={10} /> branch: gh05t3/*
        </span>
      }
    >
      {noPat && (
        <div
          data-testid="coder-no-pat"
          className="font-mono-term text-[11px] text-amber-400 border border-amber-500/30 p-2 mb-3 flex items-center gap-2"
        >
          <AlertCircle size={12} /> set GITHUB_PAT in backend/.env to enable
        </div>
      )}
      <div className="space-y-2">
        <div>
          <div className="panel-label mb-1">repository</div>
          <select
            data-testid="coder-repo-select"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            disabled={busy || noPat}
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          >
            {(repos.repos || []).map((r) => (
              <option key={r.full_name} value={r.full_name}>
                {r.full_name} {r.language ? `· ${r.language}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="panel-label mb-1">task (the change you want)</div>
          <textarea
            data-testid="coder-task-input"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            placeholder="fix the failing tests in tests/test_foo.py — the edge-case for empty input is not handled"
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50 resize-none"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="panel-label mb-1">test subdir (optional)</div>
            <input
              data-testid="coder-subdir-input"
              value={subdir}
              onChange={(e) => setSubdir(e.target.value)}
              placeholder="backend"
              className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
            />
          </div>
          <div>
            <div className="panel-label mb-1">max iterations</div>
            <input
              data-testid="coder-iters-input"
              type="number"
              min={1}
              max={6}
              value={iters}
              onChange={(e) => setIters(e.target.value)}
              className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
            />
          </div>
        </div>
        <div>
          <div className="panel-label mb-1">test target (optional — scope pytest)</div>
          <input
            data-testid="coder-target-input"
            value={testTarget}
            onChange={(e) => setTestTarget(e.target.value)}
            placeholder="tests/test_pattern_memory.py or tests/"
            className="w-full bg-black border border-white/10 p-2 font-mono-term text-xs text-zinc-200 outline-none focus:border-amber-500/50"
          />
        </div>
        <button
          data-testid="coder-run-btn"
          onClick={run}
          disabled={busy || noPat || !task.trim()}
          className="w-full font-mono-term text-[10px] tracking-[0.25em] uppercase text-amber-400 disabled:text-zinc-600 border border-amber-500/30 px-3 py-2 flex items-center justify-center gap-2 hover:bg-amber-500/5"
        >
          {busy ? (
            <>
              <Loader2 size={12} className="animate-spin" /> clone · test · patch · pr…
            </>
          ) : (
            <>
              <Play size={12} /> run coder loop
            </>
          )}
        </button>
      </div>

      {result && (
        <div
          data-testid="coder-result"
          className={`mt-3 font-mono-term text-[11px] p-2 border ${
            result.ok ? "border-emerald-500/30 text-emerald-300" : "border-rose-500/30 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-1.5 mb-1">
            {result.ok ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
            {result.ok ? "tests green" : "failed"}
            {result.iterations != null && ` · ${result.iterations} iter`}
          </div>
          {result.error && <div className="text-rose-400">{result.error}</div>}
          {result.final && (
            <div className="text-zinc-400">
              pytest: passed={result.final.passed} · failed={result.final.failed}
            </div>
          )}
          {result.pr_url && (
            <a
              data-testid="coder-pr-link"
              href={result.pr_url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-amber-400 hover:text-amber-300"
            >
              <ExternalLink size={11} /> view PR
            </a>
          )}
        </div>
      )}

      {runs.length > 0 && (
        <div className="mt-3">
          <div className="panel-label mb-1">recent runs</div>
          <div className="space-y-1 max-h-36 overflow-auto">
            {runs.map((r) => (
              <div
                key={r.result?.task_id || Math.random()}
                data-testid={`coder-run-${r.result?.task_id}`}
                className="flex items-center justify-between font-mono-term text-[10px] border border-white/10 px-2 py-1"
              >
                <span className="text-zinc-400 truncate max-w-[55%]">
                  {r.repo?.split("/").pop()} · {r.task.slice(0, 40)}
                </span>
                <span className={r.result?.ok ? "text-emerald-400" : "text-rose-400"}>
                  {r.result?.ok ? "ok" : "fail"} · {r.result?.iterations ?? 0}i
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
};
