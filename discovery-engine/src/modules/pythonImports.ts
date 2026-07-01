import fs from "fs";
import path from "path";

/**
 * Python Import Analyzer (Corrected)
 * ----------------------------------
 * Ignores:
 *   - Python standard library modules
 *   - Builtins
 *   - Third-party packages in venv
 *   - Frozen importlib modules
 *   - Empty imports
 *
 * Only flags:
 *   - Missing GH05T3 project modules
 */

const BUILTINS = new Set([
  "os","sys","json","time","math","random","logging","asyncio","threading",
  "subprocess","pathlib","typing","functools","itertools","uuid","argparse",
  "contextlib","socket","urllib","re","dataclasses","inspect","traceback",
  "importlib","http","email","base64","hashlib","statistics","collections",
  "sqlite3","tempfile","shutil","textwrap","socketserver","mmap","wave"
]);

export async function analyzePythonImports(rootDir: string) {
  const pyFiles: string[] = [];
  const issues: { file: string; message: string }[] = [];

  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir)) {
      const full = path.join(dir, entry);
      const stat = fs.statSync(full);

      if (stat.isDirectory()) {
        walk(full);
      } else if (entry.endsWith(".py")) {
        pyFiles.push(full);
      }
    }
  }

  walk(rootDir);

  const localModules = new Set(
    pyFiles.map(f => path.basename(f).replace(".py", "").toLowerCase())
  );

  for (const file of pyFiles) {
    const content = fs.readFileSync(file, "utf8");
    const lines = content.split("\n");

    for (const line of lines) {
      const importMatch =
        line.match(/^import ([\w\.]+)/) ||
        line.match(/^from ([\w\.]+) import/);

      if (!importMatch) continue;

      const imported = importMatch[1].split(".")[0].toLowerCase();

      if (!imported || imported.trim() === "") continue;

      if (BUILTINS.has(imported)) continue;

      if (file.includes(".venv")) continue;

      const sitePkgPath = path.join(rootDir, "backend", ".venv", "Lib", "site-packages");
      if (fs.existsSync(sitePkgPath)) {
        const pkgDirs = fs.readdirSync(sitePkgPath).map(d => d.toLowerCase());
        if (pkgDirs.some(d => d.startsWith(imported))) continue;
      }

      if (!localModules.has(imported)) {
        issues.push({
          file,
          message: `Missing GH05T3 module: ${imported}`
        });
      }
    }
  }

  return { issues };
}
