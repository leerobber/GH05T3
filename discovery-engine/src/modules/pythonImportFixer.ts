/**
 * Python Import Fix-Suggestion Engine
 * -----------------------------------
 * Generates suggested fixes for missing GH05T3 modules.
 *
 * For each missing module:
 *   - Suggests creating a file
 *   - Suggests the correct directory
 *   - Suggests the correct import path
 */

export function suggestPythonImportFixes(pythonImports: {
  issues: { file: string; message: string }[];
}) {
  const suggestions: { file: string; create: string; reason: string }[] = [];

  for (const issue of pythonImports.issues) {
    const missing = issue.message.replace("Missing GH05T3 module: ", "").trim();

    if (!missing) continue;

    const suggestedPath = `C:/Users/leer4/GH05T3/${missing}/${missing}.py`;

    suggestions.push({
      file: issue.file,
      create: suggestedPath,
      reason: `Module '${missing}' is imported but does not exist. Create '${missing}.py' to satisfy imports.`
    });
  }

  return { suggestions };
}
