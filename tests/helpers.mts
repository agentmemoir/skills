// Shared helpers for the node:test suite.
//
// Runs on Node's built-in TypeScript type stripping — no `typescript`
// dependency, no build step. ESM (`.mts`), so `import`/`export` are real and
// the types line up without `export =`. Only erasable syntax is used.
// Async I/O only (node:fs/promises and a promised subprocess): never sync.

import * as path from "node:path";
import { readFile, readdir } from "node:fs/promises";
import { execFile } from "node:child_process";
import { createRequire } from "node:module";
import type { ExecFileOptions } from "node:child_process";

export type RunResult = {
  status: number;
  stdout: string;
  stderr: string;
};

export const ROOT: string = path.resolve(import.meta.dirname, "..");
export const SKILLS_DIR: string = path.join(ROOT, "skills");

/** Load a CommonJS module (the skill scripts) from ESM; the caller types it. */
export const loadCjs = createRequire(import.meta.url);

/** Run a command from the repo root; resolve with { status, stdout, stderr }. */
export function run(cmd: string, args: string[] = [], options: ExecFileOptions = {}): Promise<RunResult> {
  return new Promise<RunResult>((resolve) => {
    execFile(
      cmd,
      args,
      { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, ...options },
      (error, stdout, stderr): void => {
        const status = error ? (typeof error.code === "number" ? error.code : 1) : 0;
        resolve({ status, stdout: String(stdout ?? ""), stderr: String(stderr ?? "") });
      },
    );
  });
}

/** Sorted list of skill paths (`category/name`) with a directory under skills/. */
export async function listSkillDirs(): Promise<string[]> {
  const out: string[] = [];
  const cats = await readdir(SKILLS_DIR, { withFileTypes: true });
  for (const cat of cats) {
    if (!cat.isDirectory()) continue;
    const catDir = path.join(SKILLS_DIR, cat.name);
    const skills = await readdir(catDir, { withFileTypes: true });
    for (const skill of skills) {
      if (skill.isDirectory()) out.push(path.join(cat.name, skill.name));
    }
  }
  return out.sort();
}

/** Read a repo-relative file as UTF-8 text. */
export function readText(relPath: string): Promise<string> {
  return readFile(path.join(ROOT, relPath), "utf8");
}

/** Parse a repo-relative JSON file. */
export async function readJson<T = unknown>(relPath: string): Promise<T> {
  return JSON.parse(await readText(relPath));
}

/** Raw frontmatter text between the first pair of `---` fences, or null. */
export function frontmatter(text: string): string | null {
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  return match ? match[1] : null;
}

/** Value of a top-level `key:` line in frontmatter text, or null. */
export function frontmatterValue(frontmatterText: string, key: string): string | null {
  const lines = frontmatterText.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.startsWith(`${key}:`)) continue;
    const rest = line.slice(key.length + 1).trim();
    if (rest.startsWith(">") || rest.startsWith("|")) {
      const folded = rest.startsWith(">");
      const block: string[] = [];
      let indent: number | null = null;
      for (let j = i + 1; j < lines.length; j += 1) {
        const current = lines[j];
        if (!current.trim()) {
          block.push("");
          continue;
        }
        const currentIndent = current.length - current.trimStart().length;
        if (currentIndent === 0) break;
        if (indent === null) indent = currentIndent;
        if (currentIndent < indent) break;
        block.push(current.slice(indent));
      }
      while (block.length && block[block.length - 1] === "") block.pop();
      if (folded) {
        const paragraphs: string[] = [];
        let current: string[] = [];
        for (const piece of block) {
          if (piece === "") {
            paragraphs.push(current.join(" "));
            current = [];
          } else {
            current.push(piece);
          }
        }
        paragraphs.push(current.join(" "));
        return paragraphs.join("\n").trim();
      }
      return block.join("\n");
    }
    if (rest.length >= 2 && rest[0] === rest[1] && (rest[0] === '"' || rest[0] === "'")) {
      return rest.slice(1, -1);
    }
    return rest;
  }
  return null;
}
