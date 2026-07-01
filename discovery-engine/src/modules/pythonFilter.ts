/**
 * Python Traceback Filter
 * -----------------------
 * Removes all Python traceback entries that are NOT part of the GH05T3 project.
 *
 * This filters out:
 *   - system Python files
 *   - site-packages
 *   - venv packages
 *   - asyncio internals
 *   - httpx/httpcore internals
 *   - uvicorn internals
 *   - requests/urllib3 internals
 *   - threading/subprocess internals
 *   - encodings
 *   - frozen modules
 *
 * After filtering, ONLY GH05T3 files remain.
 */

export function filterPythonIssues(pythonIssues: {
  file: string;
  line: number | null;
  message: string;
}[]) {
  const filtered = pythonIssues.filter(issue => {
    const f = issue.file.toLowerCase();

    // Keep only GH05T3 project files
    if (f.includes("gh05t3")) return true;

    // Everything else is noise
    return false;
  });

  return filtered;
}
