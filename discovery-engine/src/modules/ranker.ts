type Inputs = {
  structure: { files: string[] };
  deps: { edges: { from: string; to: string; error?: string }[] };
  runtime: { issues: { file?: string; message: string }[] };
  staticIssues: { issues: string[] };
  python: { issues: { file: string; line: number | null; message: string }[] };
  pythonImports: { issues: { file: string; message: string }[] };
  pythonPackages: { created: string[] };
};

export function rankIssues(inputs: Inputs) {
  const scores = new Map<string, { score: number; signals: any }>();

  function bump(path: string, amount: number, signalKey: string, detail: string) {
    const entry = scores.get(path) || { score: 0, signals: {} };
    entry.score += amount;
    entry.signals[signalKey] = (entry.signals[signalKey] || []).concat(detail);
    scores.set(path, entry);
  }

  // Dependency errors
  for (const edge of inputs.deps.edges) {
    if (edge.error) {
      bump(edge.from, 3, "dependency", edge.error);
    }
  }

  // Runtime JS/TS issues
  for (const issue of inputs.runtime.issues) {
    const path = issue.file || "runtime:unknown";
    bump(path, 4, "runtime", issue.message);
  }

  // Python traceback issues
  for (const issue of inputs.python.issues) {
    bump(
      issue.file,
      5,
      "python",
      `${issue.message}${issue.line ? " (line " + issue.line + ")" : ""}`
    );
  }

  // Python import issues
  for (const issue of inputs.pythonImports.issues) {
    bump(issue.file, 4, "python-import", issue.message);
  }

  // Python package normalization (created __init__.py)
  for (const created of inputs.pythonPackages.created) {
    bump(created, 2, "python-package", "auto-created __init__.py");
  }

  // Static lint issues
  for (const raw of inputs.staticIssues.issues) {
    bump("static:global", 2, "static", raw.slice(0, 200));
  }

  const result = Array.from(scores.entries()).map(([path, data]) => ({
    path,
    severity:
      data.score >= 10
        ? "critical"
        : data.score >= 6
        ? "high"
        : data.score >= 3
        ? "medium"
        : "low",
    signals: data.signals,
  }));

  return result.sort((a, b) => {
    const order = (sev: string) =>
      sev === "critical" ? 3 : sev === "high" ? 2 : sev === "medium" ? 1 : 0;
    return order(b.severity) - order(a.severity);
  });
}
