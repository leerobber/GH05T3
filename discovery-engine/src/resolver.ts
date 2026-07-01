// === GH05T3 DISCOVERY-ENGINE IMPORT RESOLVER PATCH ===
// Completely blocks .venv and site-packages from being scanned.
// Forces all imports to resolve ONLY inside GH05T3_NO_VENV.

import path from "path";
import fs from "fs";

const GH05T3_ROOT = "C:\\Users\\leer4\\GH05T3_NO_VENV";

// Normalize a path safely
function safeResolve(base: string, target: string): string {
    return path.resolve(base, target).replace(/\\/g, "/");
}

// Check if a path should be ignored
function isBlocked(p: string): boolean {
    return (
        p.includes(".venv") ||
        p.includes("site-packages") ||
        p.includes("Lib/site-packages") ||
        p.includes("Lib\\site-packages") ||
        p.includes("__pycache__") ||
        p.includes("dist-packages")
    );
}

// Main resolver
export function resolveImport(baseDir: string, importPath: string): string | null {
    // Block anything pointing to .venv or site-packages
    if (isBlocked(importPath)) {
        return null;
    }

    // Relative import: ./something or ../something
    if (importPath.startsWith(".")) {
        const resolved = safeResolve(baseDir, importPath);
        return isBlocked(resolved) ? null : resolved;
    }

    // Absolute import: fastapi → GH05T3_NO_VENV/fastapi/fastapi.py
    const mapped = importPath.replace(/\./g, "/");
    const candidateDir = safeResolve(GH05T3_ROOT, mapped);
    const candidateFile = candidateDir + ".py";

    // Prefer file if exists
    if (fs.existsSync(candidateFile)) {
        return candidateFile;
    }

    // Otherwise return directory if exists
    if (fs.existsSync(candidateDir)) {
        return candidateDir;
    }

    // If nothing exists, block it (do NOT fall back to .venv)
    return null;
}

