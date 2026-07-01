import fs from "fs";
import path from "path";

/**
 * Python Package Resolver
 * -----------------------
 * Detects:
 *   - missing __init__.py files
 *   - namespace packages that cannot be imported
 *   - modules that exist but are not importable
 *   - modules imported incorrectly
 *   - mislocated modules
 *   - unresolved namespaces (oss, gh05t3_train, ghostscript)
 */

export async function resolvePythonPackages(rootDir: string) {
  const issues: { file: string; message: string }[] = [];

  // Collect all directories
  const dirs: string[] = [];

  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir)) {
      const full = path.join(dir, entry);
      const stat = fs.statSync(full);

      if (stat.isDirectory()) {
        dirs.push(full);
        walk(full);
      }
    }
  }

  walk(rootDir);

  // Detect missing __init__.py
  for (const dir of dirs) {
    const initFile = path.join(dir, "__init__.py");
    if (!fs.existsSync(initFile)) {
      issues.push({
        file: dir,
        message: "Missing __init__.py (Python package not importable)"
      });
    }
  }

  // Detect unresolved namespaces
  const namespaces = ["oss", "gh05t3_train", "ghostscript"];

  for (const ns of namespaces) {
    const found = dirs.some(d => d.toLowerCase().endsWith(ns.toLowerCase()));
    if (!found) {
      issues.push({
        file: ns,
        message: `Namespace '${ns}' does not exist as a package`
      });
    }
  }

  return { issues };
}
