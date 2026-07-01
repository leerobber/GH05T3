import fs from "fs";
import path from "path";

export async function analyzeLogs(rootDir: string) {
  const issues: { file?: string; message: string }[] = [];

  const possibleLogDirs = [
    path.join(rootDir, "logs"),
    path.join(rootDir, "log"),
    path.join(rootDir, "tmp"),
  ];

  for (const logDir of possibleLogDirs) {
    if (!fs.existsSync(logDir)) continue;

    for (const entry of fs.readdirSync(logDir)) {
      const full = path.join(logDir, entry);
      if (!full.endsWith(".log")) continue;

      let content: string;
      try {
        content = fs.readFileSync(full, "utf8");
      } catch {
        continue;
      }

      const lines = content.split("\n");
      for (const line of lines) {
        if (
          /Cannot find module/.test(line) ||
          /TypeError/.test(line) ||
          /ReferenceError/.test(line) ||
          /Failed to load resource/.test(line)
        ) {
          issues.push({ message: line });
        }
      }
    }
  }

  return { issues };
}
