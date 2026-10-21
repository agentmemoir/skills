#!/usr/bin/env node
/**
 * Format / format-check shared JSON + JS for the repo tooling.
 * --check: verify files are already normalized (CI).
 * default: rewrite JSON with stable 2-space indent; JS left as-is after syntax check.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const checkOnly = process.argv.includes("--check");

const JSON_FILES = [
  "skills/review/autopsy/references/findings.schema.json",
  "skills/review/autopsy/references/findings.example.json",
  "skills/code/rust-flaky-test-investigator/references/flaky-finding.schema.json",
  "skills/code/rust-flaky-test-investigator/references/flaky-finding.example.json",
  "skills/docs/wordsmith/references/upstream/humanizer.json",
  "package.json",
  ".claude-plugin/marketplace.json",
  "tsconfig.json",
];

const JS_FILES = [
  "scripts/install-hooks.cjs",
  "scripts/format.cjs",
  "scripts/verify-rust-skill-commands.cjs",
  "scripts/test-plain-ssr.cjs",
  "skills/review/autopsy/scripts/generate-report.cjs",
];

// Test files are TypeScript and run through Node's type stripping; `node
// --check` cannot parse TypeScript, so they are validated by `npm test`.

let failed = 0;

for (const rel of JSON_FILES) {
  const full = path.join(ROOT, rel);
  if (!fs.existsSync(full)) {
    console.error(`format: missing ${rel}`);
    failed++;
    continue;
  }
  const raw = fs.readFileSync(full, "utf8");
  let obj;
  try {
    obj = JSON.parse(raw);
  } catch (e) {
    console.error(`format: invalid JSON ${rel}: ${e.message}`);
    failed++;
    continue;
  }
  const normalized = `${JSON.stringify(obj, null, 2)}\n`;
  if (checkOnly) {
    if (raw !== normalized) {
      console.error(`format: needs formatting: ${rel}`);
      failed++;
    } else {
      console.log(`OK format ${rel}`);
    }
  } else if (raw !== normalized) {
    fs.writeFileSync(full, normalized);
    console.log(`formatted ${rel}`);
  } else {
    console.log(`OK format ${rel}`);
  }
}

for (const rel of JS_FILES) {
  const full = path.join(ROOT, rel);
  if (!fs.existsSync(full)) continue;
  try {
    execFileSync(process.execPath, ["--check", full], { stdio: "pipe" });
    console.log(`OK syntax ${rel}`);
  } catch {
    console.error(`format: syntax error ${rel}`);
    failed++;
  }
}

if (failed) process.exit(1);
console.log(checkOnly ? "OK format --check" : "OK format");
