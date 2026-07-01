import fs from "fs";
import path from "path";

/**
 * Python Traceback Analyzer
 * -------------------------
 * Reads Python traceback logs and extracts:
 *   - file paths
 *   - line numbers
 *   - error messages
 *
 * Maps them back to actual files in the repo.
 *
 * This turns:
 *   runtime:unknown
 * into:
 *   CRITICAL  C:/Users/.../GH05T3/agents/psychology/genome.py
 */

export async function analyzePythonTracebacks(rootDir: string) {
  const issues: {
    file: string;
    line: number | null;
    message: string;
  }[] = [];

  const possibleLogDirs = [
    path.join(rootDir, "logs"),
    path.join(rootDir, "log"),
    path.join(rootDir, "tmp"),
    path.join(rootDir, "runtime"),
    path.join(rootDir, "gh05t3-logs")
  ];

  const tracebackRegex =
    /File \"(.+?)\", line (\d+), in ([\w_]+)|File \"(.+?)\", line (\d+)/g;

  const errorMessageRegex =
    /(TypeError|ValueError|RuntimeError|Exception|AttributeError|ImportError):(.+)/;

  for (const logDir of possibleLogDirs) {
    if (!fs.existsSync(logDir)) continue;

    for (const entry of fs.readdirSync(logDir)) {
      const full = path.join(logDir, entry);
      if (!full.endsWith(".log") && !full.endsWith(".txt")) continue;

      let content: string;
      try {
        content = fs.readFileSync(full, "utf8");
      } catch {
        continue;
      }

      const lines = content.split("\n");

      let lastErrorMessage: string | null = null;

      for (const line of lines) {
        const errMatch = errorMessageRegex.exec(line);
        if (errMatch) {
          lastErrorMessage = errMatch[0].trim();
        }

        let match;
        while ((match = tracebackRegex.exec(line))) {
          const filePath = match[1] || match[4];
          const lineNum = parseInt(match[2] || match[5] || "0");

          if (!filePath) continue;

          const resolved = path.resolve(rootDir, filePath);

          issues.push({
            file: resolved,
            line: isNaN(lineNum) ? null : lineNum,
            message: lastErrorMessage || "Python traceback"
          });
        }
      }
    }
  }

  return { issues };
}
