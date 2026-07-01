import fs from "fs";
import path from "path";

export async function analyzeDeps(structure: { files: string[] }) {
  const edges: { from: string; to: string; error?: string }[] = [];

  for (const file of structure.files) {
    if (
      !file.endsWith(".js") &&
      !file.endsWith(".ts") &&
      !file.endsWith(".jsx") &&
      !file.endsWith(".tsx")
    ) {
      continue;
    }

    let src: string;
    try {
      src = fs.readFileSync(file, "utf8");
    } catch {
      continue;
    }

    const importRegex =
      /import\s+.*?from\s+["'](.+?)["']|require\(["'](.+?)["']\)/g;

    let match: RegExpExecArray | null;
    while ((match = importRegex.exec(src))) {
      const target = match[1] || match[2];
      edges.push({ from: file, to: target });
    }
  }

  // naive missing-target detection (relative imports only)
  for (const edge of edges) {
    if (edge.to.startsWith(".")) {
      const baseDir = path.dirname(edge.from);
      const resolved = path.resolve(baseDir, edge.to);
      const candidates = [
        resolved,
        resolved + ".js",
        resolved + ".ts",
        resolved + ".jsx",
        resolved + ".tsx",
      ];
      const exists = candidates.some(p => fs.existsSync(p));
      if (!exists) {
        edge.error = `Missing import target: ${edge.to}`;
      }
    }
  }

  return { edges };
}
