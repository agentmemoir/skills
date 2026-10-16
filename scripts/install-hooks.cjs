#!/usr/bin/env node
/** Point this repo's git hooksPath at ./githooks (local config only). */
"use strict";

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
if (!fs.existsSync(path.join(root, ".git"))) {
  console.log("install-hooks: skip (not a git checkout)");
  process.exit(0);
}

try {
  execFileSync("git", ["config", "core.hooksPath", "githooks"], {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const value = execFileSync("git", ["config", "--get", "core.hooksPath"], {
    cwd: root,
    encoding: "utf8",
  }).trim();
  console.log(`install-hooks: core.hooksPath=${value}`);
} catch (err) {
  const detail = err && err.stderr ? String(err.stderr).trim() : String(err.message || err);
  console.error(`install-hooks: WARNING failed to set core.hooksPath (${detail || "unknown error"})`);
  console.error("install-hooks: run manually: git config core.hooksPath githooks");
  // Still exit 0 so npm install works from non-interactive / restricted environments.
  process.exit(0);
}
