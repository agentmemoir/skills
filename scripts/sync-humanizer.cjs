#!/usr/bin/env node
/**
 * Keep the humanizer catalog vendored inside wordsmith in sync with upstream.
 *
 *   node scripts/sync-humanizer.cjs            static check: generated region matches the pinned snapshot
 *   node scripts/sync-humanizer.cjs --write    regenerate the vendored region from the pinned snapshot
 *   node scripts/sync-humanizer.cjs --update [ref]
 *                                              fetch upstream (default main), re-pin, refresh the snapshot,
 *                                              regenerate the region, print what changed upstream
 *   node scripts/sync-humanizer.cjs --live     ask upstream whether our pin is stale (needs network)
 *
 * Exit codes: 0 ok · 1 local inconsistency (fix our copy) · 10 upstream drift (a newer humanizer exists).
 *
 * Layout it maintains:
 *   references/upstream/humanizer.json            the pin: repo, version, commit, sha256, sync date
 *   references/upstream/humanizer-<ver>.SKILL.md  verbatim upstream SKILL.md we vendored from
 *   references/upstream/humanizer-LICENSE.txt     verbatim upstream MIT license (attribution)
 *   references/voice-and-tells.md                 holds the generated region, between the markers below
 *
 * The region is generated from the snapshot, never edited by hand. The prose around it
 * (crosswalk to the S rules, docs exemptions, delivery rules) is ours and is never clobbered.
 */
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const REPO = "blader/humanizer";
const SKILL_DIR = path.join(ROOT, "skills/writing/wordsmith");
const UPSTREAM_DIR = path.join(SKILL_DIR, "references/upstream");
const PIN_FILE = path.join(UPSTREAM_DIR, "humanizer.json");
const LICENSE_FILE = path.join(UPSTREAM_DIR, "humanizer-LICENSE.txt");
const TARGET = path.join(SKILL_DIR, "references/voice-and-tells.md");

const BEGIN = "<!-- BEGIN GENERATED: humanizer catalog";
const END = "<!-- END GENERATED -->";

const args = process.argv.slice(2);
const WRITE = args.includes("--write");
const UPDATE = args.includes("--update");
const LIVE = args.includes("--live");
const REF = (() => {
  const i = args.indexOf("--update");
  const next = i === -1 ? undefined : args[i + 1];
  return next && !next.startsWith("--") ? next : "main";
})();

const rawUrl = (ref, file) => `https://raw.githubusercontent.com/${REPO}/${ref}/${file}`;
const short = (sha) => (sha ? sha.slice(0, 7) : "unknown");
const sha256 = (buf) => crypto.createHash("sha256").update(buf).digest("hex");

/** "3.1.0" -> [3, 1, 0], for ordering pins. */
function parseVersion(text) {
  const fm = text.startsWith("---") ? text.slice(3, text.indexOf("\n---", 3)) : text;
  const m = /version:\s*"?([0-9]+(?:\.[0-9]+)*)"?/.exec(fm);
  if (!m) return null;
  return { raw: m[1], parts: m[1].split(".").map(Number) };
}

function compareVersions(a, b) {
  const n = Math.max(a.parts.length, b.parts.length);
  for (let i = 0; i < n; i += 1) {
    const d = (a.parts[i] || 0) - (b.parts[i] || 0);
    if (d !== 0) return d < 0 ? -1 : 1;
  }
  return 0;
}

/** Every numbered pattern heading, for diffing two snapshots. */
function listPatterns(skillMd) {
  return [...skillMd.matchAll(/^### (\d+)\. (.+)$/gm)].map((m) => ({ n: Number(m[1]), title: m[2].trim() }));
}

async function get(url, { json = false } = {}) {
  const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  return json ? res.json() : res.text();
}

/**
 * The vendored region: everything upstream says after the opening sections, heading
 * levels demoted one notch so the file keeps our outline. Verbatim otherwise — no
 * rephrasing means no drift and nothing to port by hand.
 */
function extractCatalog(skillMd) {
  const lines = skillMd.split("\n");
  const start = lines.findIndex((l) => /^## Why AI text sounds the way it does\s*$/.test(l));
  const end = lines.findIndex((l) => /^## Source\s*$/.test(l));
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("upstream layout changed: could not find the catalog boundaries (expected '## Why AI text…' … '## Source')");
  }
  const body = lines
    .slice(start, end)
    .map((l) => (l.startsWith("### ") || l.startsWith("## ") ? `#${l}` : l))
    .join("\n")
    .replace(/\n+$/, "");
  return body;
}

function region(pin, catalog) {
  const note = `<!-- BEGIN GENERATED: humanizer catalog — ${REPO} v${pin.version} (commit ${short(pin.commit)}, sha256 ${pin.sha256.slice(0, 12)}) · run \`npm run sync:humanizer\` to refresh, do not edit by hand -->`;
  return `${note}\n\n${catalog}\n\n${END}`;
}

function spliceRegion(fileText, newRegion) {
  const from = fileText.indexOf(BEGIN);
  const to = fileText.indexOf(END);
  if (from === -1 || to === -1 || to < from) {
    throw new Error(`${path.relative(ROOT, TARGET)} is missing the ${BEGIN} … ${END} markers`);
  }
  return `${fileText.slice(0, from)}${newRegion}${fileText.slice(to + END.length)}`;
}

function readPin() {
  if (!fs.existsSync(PIN_FILE)) {
    throw new Error(`missing pin ${path.relative(ROOT, PIN_FILE)} — run: npm run sync:humanizer -- --update`);
  }
  return JSON.parse(fs.readFileSync(PIN_FILE, "utf8"));
}

function snapshotFor(pin) {
  const file = path.join(UPSTREAM_DIR, `humanizer-${pin.version}.SKILL.md`);
  if (!fs.existsSync(file)) throw new Error(`missing snapshot ${path.relative(ROOT, file)}`);
  return { file, text: fs.readFileSync(file, "utf8") };
}

/** Rebuild the region from the pin and report whether the file already matches. */
function check() {
  const pin = readPin();
  const { file, text } = snapshotFor(pin);
  const digest = sha256(text);
  if (digest !== pin.sha256) {
    console.error(`FAIL humanizer pin: sha256 of ${path.relative(ROOT, file)} does not match ${path.relative(ROOT, PIN_FILE)}`);
    return 1;
  }
  const current = fs.readFileSync(TARGET, "utf8");
  const want = region(pin, extractCatalog(text));
  const has = spliceRegion(current, want);
  if (has === current) {
    console.log(`OK humanizer vendored region (${REPO} v${pin.version}, ${listPatterns(text).length} patterns)`);
    return 0;
  }
  if (WRITE) {
    fs.writeFileSync(TARGET, has);
    console.log(`wrote ${path.relative(ROOT, TARGET)} from v${pin.version}`);
    return 0;
  }
  console.error(`FAIL humanizer vendored region: ${path.relative(ROOT, TARGET)} is stale or hand-edited`);
  console.error("  fix: npm run sync:humanizer   (regenerates the region from the pinned snapshot)");
  return 1;
}

/** Version headings in upstream's CHANGELOG that are newer than where we were pinned. */
function changelogSince(changelog, fromRaw) {
  if (!changelog || !fromRaw) return [];
  const from = parseVersion(`version: ${fromRaw}`);
  if (!from) return [];
  return [...changelog.matchAll(/^## (.+)$/gm)]
    .map((m) => m[1].trim())
    .filter((v) => {
      const parsed = parseVersion(`version: ${v}`);
      return parsed && compareVersions(parsed, from) > 0;
    });
}

/** Which patterns appeared, vanished, or were retitled between two snapshots. */
function patternDiff(before, after) {
  const b = new Map(before.map((p) => [p.n, p.title]));
  const a = new Map(after.map((p) => [p.n, p.title]));
  return {
    added: [...a].filter(([n]) => !b.has(n)),
    removed: [...b].filter(([n]) => !a.has(n)),
    retitled: [...a].filter(([n, t]) => b.has(n) && b.get(n) !== t),
  };
}

/** Fetch upstream, re-pin, refresh the snapshot + license, regenerate the region. */
async function update() {
  const prev = fs.existsSync(PIN_FILE) ? JSON.parse(fs.readFileSync(PIN_FILE, "utf8")) : null;
  const prevPatterns = (() => {
    if (!prev) return [];
    const f = path.join(UPSTREAM_DIR, `humanizer-${prev.version}.SKILL.md`);
    return fs.existsSync(f) ? listPatterns(fs.readFileSync(f, "utf8")) : [];
  })();

  const [skillMd, license, changelog] = await Promise.all([
    get(rawUrl(REF, "SKILL.md")),
    get(rawUrl(REF, "LICENSE")),
    get(rawUrl(REF, "CHANGELOG.md")).catch(() => ""),
  ]);
  const version = parseVersion(skillMd);
  if (!version) throw new Error("upstream SKILL.md has no metadata.version");

  let commit = null;
  try {
    commit = (await get(`https://api.github.com/repos/${REPO}/commits/${REF}`, { json: true })).sha;
  } catch {
    commit = null; // API rate limit or offline: version + content digest still pin the bytes
  }

  fs.mkdirSync(UPSTREAM_DIR, { recursive: true });
  const snapshot = path.join(UPSTREAM_DIR, `humanizer-${version.raw}.SKILL.md`);
  fs.writeFileSync(snapshot, skillMd);
  fs.writeFileSync(LICENSE_FILE, license);

  const pin = {
    repo: REPO,
    ref: REF,
    version: version.raw,
    commit,
    sha256: sha256(skillMd),
    synced: new Date().toISOString().slice(0, 10),
  };
  fs.writeFileSync(PIN_FILE, `${JSON.stringify(pin, null, 2)}\n`);
  fs.writeFileSync(TARGET, spliceRegion(fs.readFileSync(TARGET, "utf8"), region(pin, extractCatalog(skillMd))));

  const patterns = listPatterns(skillMd);
  console.log(
    `pinned ${REPO} v${version.raw} (commit ${short(commit)}, sha256 ${pin.sha256.slice(0, 12)}, ${patterns.length} patterns)`
  );
  console.log(`  snapshot  ${path.relative(ROOT, snapshot)}`);
  console.log(`  license   ${path.relative(ROOT, LICENSE_FILE)}`);
  if (!prev) return 0;

  if (prev.version !== version.raw) console.log(`  was       v${prev.version} (commit ${short(prev.commit)})`);
  const d = patternDiff(prevPatterns, patterns);
  const line = (label, list) =>
    list.length
      ? `  ${label} ${list.map(([n, t]) => `H${n}${label.startsWith("retitled") ? ` "${t}"` : ` ${t}`}`).join(", ")}`
      : `  ${label} (none)`;
  if (prev.version !== version.raw) {
    console.log("  pattern diff:");
    console.log(line("added:   ", d.added));
    console.log(line("removed: ", d.removed));
    console.log(line("retitled:", d.retitled));
  }
  const releases = changelogSince(changelog, prev.version);
  console.log(`  upstream releases since the old pin: ${releases.length ? releases.join(", ") : "none listed"}`);
  console.log("  review now: the crosswalk, the docs-exemption table, and the H-number citations in");
  console.log("              skills/writing/wordsmith/references/voice-and-tells.md");
  return 0;
}

/** Ask upstream whether our pin is stale. Offline is a warning, not a failure. */
async function live() {
  const pin = readPin();
  let skillMd;
  try {
    skillMd = await get(rawUrl("main", "SKILL.md"));
  } catch (err) {
    console.warn(`WARN humanizer live check skipped: ${err.message}`);
    return 0;
  }
  const upstream = parseVersion(skillMd);
  if (!upstream) throw new Error("upstream SKILL.md has no metadata.version");
  if (compareVersions(upstream, parseVersion(`version: ${pin.version}`)) > 0) {
    const changelog = await get(rawUrl("main", "CHANGELOG.md")).catch(() => "");
    console.error(`DRIFT humanizer upstream is v${upstream.raw}; we pin v${pin.version}`);
    for (const v of changelogSince(changelog, pin.version)) console.error(`  release since our pin: ${v}`);
    console.error("  fix: npm run sync:humanizer -- --update");
    return 10;
  }
  console.log(`OK humanizer pin v${pin.version} is current (upstream main v${upstream.raw})`);
  return 0;
}

(async () => {
  try {
    if (UPDATE && (await update()) !== 0) process.exit(1);
    const rc = check();
    if (rc !== 0) process.exit(rc);
    process.exit(LIVE ? await live() : 0);
  } catch (err) {
    console.error(`FAIL humanizer sync: ${err.message}`);
    process.exit(1);
  }
})();

