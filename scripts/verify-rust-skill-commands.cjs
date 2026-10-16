#!/usr/bin/env node
// verify-rust-skill-commands.cjs - static checks that the Rust skills' documented
// commands and snippets are internally consistent and match a known-good list.
//
// This exists because both skills were shipped with commands that fail on first
// use: `cargo nextest show-config profiles` and `cargo nextest build` do not
// exist, and `shuttle::check_random` was called with the wrong arity. A skill
// whose value is command accuracy cannot be the thing that ships broken commands.
//
// Two layers, because a fully dynamic check needs the target toolchain:
//
//   1. Always-on static checks (this file). No Rust toolchain required, so it
//      runs in CI on any machine.
//   2. Optional live checks, run only when cargo/nextest are present:
//         node scripts/verify-rust-skill-commands.cjs --live
//
// Usage:
//   node scripts/verify-rust-skill-commands.cjs [--live] [--quiet]
//
// Exit 0 = all checks passed. Exit 1 = at least one failed.

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const SKILLS = ["skills/languages/rust-flaky-test-investigator", "skills/languages/rust-test-best-practices"];
const LIVE = process.argv.includes("--live");
const QUIET = process.argv.includes("--quiet");

let failures = 0;
let checks = 0;

function check(name, ok, detail) {
  checks += 1;
  if (ok) {
    if (!QUIET) console.log(`ok   - ${name}`);
  } else {
    failures += 1;
    console.log(`FAIL - ${name}${detail ? `\n       ${detail}` : ""}`);
  }
}

function walk(dir, exts, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, exts, out);
    else if (exts.some((e) => entry.name.endsWith(e))) out.push(full);
  }
  return out;
}

const docFiles = SKILLS.flatMap((s) => walk(path.join(ROOT, s), [".md"]));
const rel = (f) => path.relative(ROOT, f);
const corpus = docFiles.map((f) => ({ file: rel(f), text: fs.readFileSync(f, "utf8") }));

// ---------------------------------------------------------------------------
// 1. Banned commands. These do not exist; naming them in prose is fine, calling
//    them is not. Comment lines and inline code spans are stripped first so the
//    explanatory text that mentions them does not trip the check.
// ---------------------------------------------------------------------------
const BANNED = [
  { cmd: "cargo nextest build", why: "no such subcommand; real ones are list, run, bench, archive, show-config, self" },
  { cmd: "cargo nextest show-config profiles", why: "show-config has only 'version' and 'test-groups'" },
  { cmd: "RUST_TEST_SEED", why: "not a libtest variable; the real ones are RUST_TEST_SHUFFLE / RUST_TEST_SHUFFLE_SEED" },
];

for (const { file, text } of corpus) {
  // Remove fenced code blocks? No - we WANT to catch commands in code blocks.
  // Remove full-line comments and inline backtick spans instead.
  const codeish = text
    .split("\n")
    .filter((l) => !/^\s*<!--/.test(l))
    .map((l) => l.replace(/`[^`]*`/g, "``"))
    .join("\n");

  for (const { cmd, why } of BANNED) {
    check(
      `${file}: does not invoke "${cmd}"`,
      !codeish.includes(cmd),
      `found outside backticks. ${why}`
    );
  }
}

// ---------------------------------------------------------------------------
// 2. crate::fn arity. A wrong-arity snippet is a compile error for the reader.
// ---------------------------------------------------------------------------
const ARITY = [
  {
    fn: "shuttle::check_random",
    minArgs: 2,
    usage: /shuttle::check_random\s*\(\s*(\|\|[^|]*\|\|)\s*(,|\))/g,
  },
];

for (const { file, text } of corpus) {
  for (const { fn, minArgs, usage } of ARITY) {
    const re = new RegExp(usage.source, "g");
    let m;
    while ((m = re.exec(text)) !== null) {
      // Snippets written across lines put the second arg after a comma; count
      // top-level commas instead of trusting the regex tail.
      const start = m.index + m[0].length - (m[2] === "," ? 1 : 0);
      const snippet = text.slice(start, start + 240);
      const hasSecondArg = /,\s*[0-9_]+[,\s)]/.test(snippet.slice(0, 120));
      check(
        `${file}: ${fn} has an iteration count`,
        m[2] === "," || hasSecondArg,
        `call site looks single-argument; real signature is ${fn}(f, iterations)`
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 3. TSan must use -Zbuild-std. Without an instrumented std it reports false
//    races from std internals, which is worse than not documenting it at all.
// ---------------------------------------------------------------------------
for (const { file, text } of corpus) {
  const usesTsan = /-Zsanitizer=thread/.test(text);
  if (!usesTsan) continue;
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    if (!/-Zsanitizer=thread/.test(line)) return;
    // The flag may be on its own line above the cargo invocation; look at a
    // small window around it.
    const window = lines.slice(Math.max(0, i - 3), i + 4).join("\n");
    check(
      `${file}:${i + 1}: TSan command uses -Zbuild-std`,
      /-Zbuild-std/.test(window),
      "instrumented std is required or TSan emits false positives from std internals"
    );
  });
}

// ---------------------------------------------------------------------------
// 4. ThreadSanitizer block must mention the rust-src component.
// ---------------------------------------------------------------------------
for (const { file, text } of corpus) {
  if (!/-Zsanitizer=thread/.test(text)) continue;
  if (!/-Zbuild-std/.test(text)) continue;
  check(
    `${file}: mentions the rust-src component for -Zbuild-std`,
    /rust-src/.test(text),
    "-Zbuild-std needs `rustup component add rust-src`"
  );
}

// ---------------------------------------------------------------------------
// 5. Cross-skill claim consistency. The install model duplicates shared content
//    on purpose (installers do not preserve cross-skill symlinks), so duplicated
//    claims must not drift apart.
//
//    Scoped deliberately: only docs that make the *substantive claim* are
//    required to carry the caveat, not every doc that mentions the topic in
//    passing. Requiring it everywhere produced false failures on passing
//    mentions and would train the reader to ignore the check.
// ---------------------------------------------------------------------------
const SHARED_CLAIMS = [
  {
    label: "a numeric leak-timeout default",
    // Only a doc that asserts what the default IS can rot. Recommending an
    // explicit value ("leak-timeout = 500ms") is good practice, not a claim.
    claims: (text) => /leak-timeout[^\n]{0,80}?default[^\n]{0,40}?\d+\s*ms|default[^\n]{0,40}?leak-timeout[^\n]{0,40}?\d+\s*ms/i.test(text),
    caveat: (text) => /inconsistent|disagree/.test(text),
  },
  {
    label: '"#[serial] is a no-op under nextest"',
    claims: (text) => /#\[serial\][^\n]*?(no-op|no op|is a no-op)/i.test(text) || /in-process (mutex|attribute)/i.test(text),
    caveat: (text) => /file_serial/.test(text),
  },
];

for (const { label, claims, caveat } of SHARED_CLAIMS) {
  const claiming = corpus.filter((c) => claims(c.text));
  if (claiming.length === 0) {
    if (!QUIET) console.log(`note - no doc asserts ${label}; nothing to cross-check`);
    continue;
  }
  const withCaveat = claiming.filter((c) => caveat(c.text));
  check(
    `cross-skill: every doc asserting ${label} carries the caveat`,
    withCaveat.length === claiming.length,
    `${withCaveat.length}/${claiming.length} carry it; missing in: ${claiming.filter((c) => !caveat(c.text)).map((c) => c.file).join(", ")}`
  );
}

// ---------------------------------------------------------------------------
// 6. Statistical thresholds. A wrong bound changes a branching decision, so
//    assert the arithmetic rather than trusting the prose.
// ---------------------------------------------------------------------------
function upperBoundZeroFailures(n) {
  // 95% upper confidence bound on p given 0 failures in n trials: 1 - 0.05^(1/n)
  return 1 - Math.pow(0.05, 1 / n);
}

for (const { file, text } of corpus) {
  // Any claim that 50 clean iterations bound the rate at some percentage.
  const m = text.match(/50 iterations[^.]*?below[^.]*?(\d+(?:\.\d+)?)\s*%/i);
  if (!m) continue;
  const claimed = Number(m[1]);
  const actual = upperBoundZeroFailures(50) * 100; // 5.8
  check(
    `${file}: 50-iteration bound is arithmetically correct`,
    Math.abs(claimed - actual) < 1.0,
    `claims ${claimed}%, correct 95% upper bound for 0/50 is ${actual.toFixed(1)}%`
  );
}

// ---------------------------------------------------------------------------
// 7. Every referenced reference/ and scripts/ path exists.
//    Paths are written relative to the skill root (the directory holding
//    SKILL.md), which is how the agent reads them.
// ---------------------------------------------------------------------------
const skillRootOf = (file) => {
  const dir = path.dirname(path.join(ROOT, file));
  return path.basename(dir) === "references" || path.basename(dir) === "scripts"
    ? path.resolve(dir, "..")
    : dir;
};

for (const { file, text } of corpus) {
  const refs = text.match(/(?:references|scripts)\/[A-Za-z0-9._-]+/g) || [];
  for (const r of new Set(refs)) {
    const target = path.join(skillRootOf(file), r);
    check(`${file}: reference ${r} exists`, fs.existsSync(target), `looked in ${target}`);
  }
}

// ---------------------------------------------------------------------------
// 8. Schema and example agree, and the example actually validates.
// ---------------------------------------------------------------------------
const schemaPath = path.join(ROOT, "skills/languages/rust-flaky-test-investigator/references/flaky-finding.schema.json");
const examplePath = path.join(ROOT, "skills/languages/rust-flaky-test-investigator/references/flaky-finding.example.json");
const taxonomyPath = path.join(ROOT, "skills/languages/rust-flaky-test-investigator/references/flaky-taxonomy.md");
if (fs.existsSync(schemaPath) && fs.existsSync(examplePath)) {
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const example = JSON.parse(fs.readFileSync(examplePath, "utf8"));
  const required = schema.required || [];
  const missing = required.filter((k) => !(k in example));
  check("flaky-finding.example.json has every schema-required key", missing.length === 0, `missing: ${missing.join(", ")}`);

  // Enum conformance for the fields most likely to drift.
  const enums = [
    ["root_cause_family", schema.properties.root_cause_family.enum],
    ["severity", schema.properties.severity.enum],
    ["confidence", schema.properties.confidence.enum],
    ["defect_location", schema.properties.defect_location.enum],
  ];
  for (const [key, values] of enums) {
    check(`example ${key} is a valid enum value`, values.includes(example[key]), `got ${JSON.stringify(example[key])}`);
  }
  const reproStatus = schema.properties.reproduction.properties.status.enum;
  check("example reproduction.status is valid", reproStatus.includes(example.reproduction.status));

  // A confirmed finding must carry a non-empty not_verified list per the schema
  // description; also assert the discipline the skill preaches.
  check(
    "example has a non-empty not_verified list",
    Array.isArray(example.not_verified) && example.not_verified.length > 0,
    "the skill requires honest gaps; the example must model that"
  );
  check(
    "example confirmed finding has a confirming_experiment",
    example.confidence !== "confirmed" || Boolean(example.confirming_experiment),
    "confidence=confirmed requires a completed experiment"
  );

  // The schema's discrimination axes must match the matrix in SKILL.md, or a
  // reported finding can name an axis the workflow never runs. Matrix row
  // labels are human-facing ("Build") so normalise before comparing.
  const matrix = fs.readFileSync(path.join(ROOT, "skills/languages/rust-flaky-test-investigator/SKILL.md"), "utf8");
  const normalise = (s) => s.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const matrixAxes = new Set(
    (matrix.match(/^\| \d+ \| ([A-Za-z ]+) \|/gm) || []).map((l) => normalise(l.split("|")[2]))
  );
  const schemaAxes = new Set(schema.properties.discrimination.items.properties.axis.enum);
  const axesMissingFromSchema = [...schemaAxes].filter((a) => !matrixAxes.has(a));
  check(
    "every schema discrimination axis appears in the SKILL.md matrix",
    axesMissingFromSchema.length === 0,
    `not in the matrix: ${axesMissingFromSchema.join(", ")}; matrix has: ${[...matrixAxes].join(", ")}`
  );
  const axesMissingFromMatrix = [...matrixAxes].filter((a) => !schemaAxes.has(a));
  check(
    "every SKILL.md matrix axis is representable in the schema",
    axesMissingFromMatrix.length === 0,
    `not in the schema enum: ${axesMissingFromMatrix.join(", ")}`
  );

  // The taxonomy and the schema must describe the same number of families. This
  // is the drift that happened when four families were added to the taxonomy
  // without touching the schema or the "ten families" prose.
  if (fs.existsSync(taxonomyPath)) {
    const taxonomy = fs.readFileSync(taxonomyPath, "utf8");
    const numbered = (taxonomy.match(/^## \d+\. /gm) || []).length;
    const meta = schema.properties.root_cause_family.enum.length - 2; // minus environment_only, unclassified
    check(
      "taxonomy family count matches the schema enum",
      numbered === meta,
      `taxonomy has ${numbered} numbered families, schema enum has ${meta} (excluding environment_only and unclassified)`
    );

    // And the prose count in SKILL.md must match too.
    const claimed = [...matrix.matchAll(/one of the (\w+) cause families/g)].map((m) => m[1]);
    const words = {
      ten: 10,
      eleven: 11,
      twelve: 12,
      thirteen: 13,
      fourteen: 14,
      fifteen: 15,
      sixteen: 16,
      seventeen: 17,
      eighteen: 18,
      nineteen: 19,
    };
    for (const w of claimed) {
      const n = words[w.toLowerCase()];
      check(
        `SKILL.md family count word ("${w}") matches the taxonomy`,
        n === numbered,
        `prose says ${w} (${n}), taxonomy has ${numbered}`
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 9. Optional live checks against the real toolchain.
// ---------------------------------------------------------------------------
function has(cmd, args = ["--version"]) {
  try {
    execFileSync(cmd, args, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

if (LIVE) {
  if (!has("cargo", ["--version"])) {
    console.log("skip - live checks: cargo not available");
  } else if (!has("cargo-nextest", ["--version"])) {
    console.log("skip - live checks: cargo-nextest not available");
  } else {
    // Real subcommand list. `cargo nextest --help` prints them indented by two
    // spaces, e.g. "  list         List tests in workspace".
    let subcommands = "";
    try {
      subcommands = execFileSync("cargo", ["nextest", "--help"], { encoding: "utf8" });
    } catch (e) {
      subcommands = e.stdout || "";
    }
    const isSubcommand = (name) => new RegExp(`^ {2,6}${name}\\s{2,}\\S`, "m").test(subcommands);
    for (const banned of ["build"]) {
      check(`live: "cargo nextest ${banned}" is not a real subcommand`, !isSubcommand(banned), "found in `cargo nextest --help`");
    }
    for (const real of ["list", "run", "archive", "show-config"]) {
      check(`live: "cargo nextest ${real}" exists`, isSubcommand(real), "not found in `cargo nextest --help`");
    }
    // show-config must NOT have a profiles subcommand.
    let showConfigHelp = "";
    try {
      showConfigHelp = execFileSync("cargo", ["nextest", "show-config", "--help"], { encoding: "utf8" });
    } catch (e) {
      showConfigHelp = e.stdout || "";
    }
    check(
      "live: `cargo nextest show-config profiles` is not a real subcommand",
      !/^ {2,6}profiles\s{2,}\S/m.test(showConfigHelp),
      "found in `cargo nextest show-config --help`"
    );
    for (const sc of ["version", "test-groups"]) {
      check(
        `live: "cargo nextest show-config ${sc}" exists`,
        new RegExp(`^ {2,6}${sc}\\s{2,}\\S`, "m").test(showConfigHelp),
        "not found in `cargo nextest show-config --help`"
      );
    }
    // Flags the skills rely on.
    let runHelp = "";
    try {
      runHelp = execFileSync("cargo", ["nextest", "run", "--help"], { encoding: "utf8", maxBuffer: 1 << 24 });
    } catch (e) {
      runHelp = e.stdout || "";
    }
    for (const flag of ["--stress-count", "--no-fail-fast", "--retries", "--flaky-result", "--profile"]) {
      check(`live: "cargo nextest run ${flag}" exists`, runHelp.includes(flag), "not found in `cargo nextest run --help`");
    }
  }
} else {
  if (!QUIET) console.log("note - live toolchain checks skipped; pass --live to run them");
}

console.log("");
console.log(`${checks - failures}/${checks} checks passed${LIVE ? " (including live)" : " (static only)"}`);
process.exit(failures === 0 ? 0 : 1);
