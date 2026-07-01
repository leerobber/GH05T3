#!/usr/bin/env node

import { scanStructure } from "./modules/structure";
import { analyzeDeps } from "./modules/deps";
import { analyzeLogs } from "./modules/logs";
import { analyzeStatic } from "./modules/static";
import { analyzePythonTracebacks } from "./modules/pythonTrace";
import { filterPythonIssues } from "./modules/pythonFilter";
import { analyzePythonImports } from "./modules/pythonImports";
import { normalizePythonPackages } from "./modules/pythonPackageNormalizer";
import { suggestPythonImportFixes } from "./modules/pythonImportFixer";
import { rankIssues } from "./modules/ranker";

async function main() {
  const rootDir = process.argv[2] || process.cwd();

  console.log("[discovery-engine] rootDir:", rootDir);

  const structure = await scanStructure(rootDir);
  console.log("[discovery-engine] files scanned:", structure.files.length);

  const deps = await analyzeDeps(structure);
  console.log("[discovery-engine] dependency edges:", deps.edges.length);

  const runtime = await analyzeLogs(rootDir);
  console.log("[discovery-engine] runtime issues:", runtime.issues.length);

  const pythonRaw = await analyzePythonTracebacks(rootDir);
  const python = { issues: filterPythonIssues(pythonRaw.issues) };
  console.log("[discovery-engine] python traceback issues:", python.issues.length);

  const pyImports = await analyzePythonImports(rootDir);
  console.log("[discovery-engine] python import issues:", pyImports.issues.length);

  const pkgFix = await normalizePythonPackages(rootDir);
  console.log("[discovery-engine] created __init__.py:", pkgFix.created.length);

  // ⭐ STEP 2 + STEP 3 — generate import fix suggestions
  const pyFix = suggestPythonImportFixes(pyImports);
  console.log("[discovery-engine] import fix suggestions:", pyFix.suggestions.length);

  const staticIssues = await analyzeStatic(rootDir);
  console.log("[discovery-engine] static issues (raw):", staticIssues.issues.length);

  const ranked = rankIssues({
    structure,
    deps,
    runtime,
    staticIssues,
    python,
    pythonImports: pyImports,
    pythonPackages: pkgFix
  });

  console.log("");
  console.log("=== Files to fix first ===");
  for (const issue of ranked.slice(0, 50)) {
    console.log(
      `${issue.severity.toUpperCase()}  ${issue.path}`,
      JSON.stringify(issue.signals)
    );
  }

  console.log("");
  console.log("=== Suggested Python Import Fixes ===");
  for (const fix of pyFix.suggestions.slice(0, 50)) {
    console.log(
      `Create: ${fix.create}  (needed by ${fix.file})`
    );
  }
}

main().catch(err => {
  console.error("Discovery engine failed:", err);
  process.exit(1);
});
