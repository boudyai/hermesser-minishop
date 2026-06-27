import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const rootDir = path.resolve(import.meta.dirname, "../src");
const checkedExtensions = new Set([".js", ".mjs", ".svelte", ".ts"]);
const ignoredFiles = new Set(["openapi.generated.ts"]);

const checks = [
  { label: "legacy prop declaration", pattern: /\bexport\s+let\b/ },
  { label: "legacy reactive statement", pattern: /(^|[^\w$])\$:\s/m },
  { label: "legacy $$props", pattern: /\$\$props\b/ },
  { label: "legacy $$restProps", pattern: /\$\$restProps\b/ },
  { label: "legacy slot element", pattern: /<slot\b/ },
  { label: "legacy dynamic component", pattern: /<svelte:component\b/ },
  { label: "legacy event dispatcher", pattern: /\bcreateEventDispatcher\b/ },
  { label: "legacy helper import", pattern: /["']svelte\/legacy["']/ },
  { label: "class component $set API", pattern: /\.\$set\s*\(/ },
];

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (checkedExtensions.has(path.extname(entry.name)) && !ignoredFiles.has(entry.name)) {
      yield fullPath;
    }
  }
}

function lineNumber(source, index) {
  return source.slice(0, index).split("\n").length;
}

const failures = [];

for await (const filePath of walk(rootDir)) {
  const source = await readFile(filePath, "utf8");
  for (const check of checks) {
    const match = check.pattern.exec(source);
    if (match) {
      failures.push({
        filePath: path.relative(rootDir, filePath).replaceAll(path.sep, "/"),
        line: lineNumber(source, match.index),
        label: check.label,
      });
    }
  }
}

if (failures.length > 0) {
  console.error("Svelte 5 runes-only check failed:");
  for (const failure of failures) {
    console.error(`- src/${failure.filePath}:${failure.line} ${failure.label}`);
  }
  process.exit(1);
}
