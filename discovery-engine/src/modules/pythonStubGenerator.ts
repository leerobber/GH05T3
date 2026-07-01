import fs from "fs";
import path from "path";

/**
 * Automatic Python Stub Generator
 * -------------------------------
 * Creates missing GH05T3 modules automatically.
 */

export function generatePythonStubs(suggestions: {
  suggestions: { create: string; file: string; reason: string }[];
}) {
  const created: string[] = [];

  for (const s of suggestions.suggestions) {
    const filePath = s.create;

    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, "# auto-generated stub\n");
      created.push(filePath);
    }
  }

  return { created };
}
