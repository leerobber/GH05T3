import { execSync } from "child_process";

export async function analyzeStatic(rootDir: string) {
  const issues: string[] = [];

  // JS/TS lint (if eslint is present)
  try {
    execSync("npx eslint .", {
      cwd: rootDir,
      stdio: "pipe",
    });
  } catch (err: any) {
    const out =
      (err.stdout && err.stdout.toString()) ||
      (err.stderr && err.stderr.toString()) ||
      err.message;
    issues.push(out);
  }

  // You can add more (tsc, pylint, etc.) here later.

  return { issues };
}
