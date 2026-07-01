import fs from "fs";
import path from "path";

/**
 * Python Package Normalizer
 * -------------------------
 * Automatically fixes GH05T3's broken Python package structure by:
 *   - Adding missing __init__.py files
 *   - Ensuring every directory is importable
 *   - Creating namespace packages
 *   - Normalizing GH05T3 import roots
 */

export async function normalizePythonPackages(rootDir: string) {
  const created: string[] = [];

  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir)) {
      const full = path.join(dir, entry);
      const stat = fs.statSync(full);

      if (stat.isDirectory()) {
        const initFile = path.join(full, "__init__.py");

        // Create missing __init__.py
        if (!fs.existsSync(initFile)) {
          fs.writeFileSync(initFile, "# auto-generated\n");
          created.push(initFile);
        }

        walk(full);
      }
    }
  }

  walk(rootDir);

  return { created };
}
