#!/usr/bin/env node
/**
 * Smoke test for the plain-Vite SSR starter files shipped in
 * skills/web/svelte5-ssr-runes/assets/.
 *
 * It copies the shipped assets into tests/plain-ssr, builds a real client and
 * server bundle, then asserts that the production HTML links the built JS/CSS
 * and that renderPage() escapes props. Fixture dependency ranges intentionally
 * float so this test notices upstream breakage of the template contract.
 *
 * Usage: npm run test:plain-ssr
 */
"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const ROOT = path.resolve(__dirname, "..");
const FIXTURE = path.join(ROOT, "tests/plain-ssr");
const ASSETS = path.join(ROOT, "skills/web/svelte5-ssr-runes/assets");
const VITE_BIN = path.join(
  FIXTURE,
  "node_modules/.bin/vite" + (process.platform === "win32" ? ".cmd" : "")
);

function run(command, args) {
  execFileSync(process.platform === "win32" && command === "npm" ? "npm.cmd" : command, args, {
    cwd: FIXTURE,
    stdio: "inherit"
  });
}

function copyAssets() {
  fs.mkdirSync(path.join(FIXTURE, "src"), { recursive: true });
  for (const file of ["index.html", "entry-client.js", "entry-server.js"]) {
    fs.copyFileSync(path.join(ASSETS, file), path.join(FIXTURE, file === "index.html" ? file : `src/${file}`));
  }
}

async function main() {
  copyAssets();

  if (!fs.existsSync(VITE_BIN)) {
    console.log("installing fixture dependencies (first run only, needs network)...");
    run("npm", ["install", "--no-audit", "--no-fund", "--loglevel=error"]);
  }

  run(VITE_BIN, ["build", "--outDir", "dist/client"]);
  run(VITE_BIN, ["build", "--outDir", "dist/server", "--ssr", "src/entry-server.js"]);

  const template = fs.readFileSync(path.join(FIXTURE, "dist/client/index.html"), "utf8");
  const script = template.match(/<script[^>]+src="(\/assets\/[^"]+\.js)"/);
  assert.ok(script, "client build must link a hashed JS entry in dist/client/index.html");
  const css = template.match(/<link[^>]+href="(\/assets\/[^"]+\.css)"/);
  assert.ok(css, "client build must link the emitted CSS in dist/client/index.html");

  const { renderPage } = await import(pathToFileURL(path.join(FIXTURE, "dist/server/entry-server.js")).href);
  const props = { title: "SSR smoke test", injection: "</script><script>alert(1)</script>" };
  const html = await renderPage(template, props);
  const text = html.replace(/<!--[\s\S]*?-->/g, "");

  assert.ok(text.includes("SSR smoke test"), "renderPage must render props server-side");
  assert.ok(text.includes("count: 0 / 0"), "renderPage must evaluate runes server-side");
  assert.ok(html.includes(script[1]), "rendered HTML must keep the hashed client script");
  assert.ok(html.includes(css[1]), "rendered HTML must keep the built CSS link");
  assert.ok(html.includes("\\u003c/script>"), "props must be JSON-escaped for the browser");
  assert.ok(!html.includes("</script><script>alert(1)"), "raw </script> from props must not reach the page");

  console.log("OK test:plain-ssr (client + server build, renderPage, prop escaping)");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
