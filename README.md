# agentmemoir/skills

Skills that run inside your coding agent. They work with Claude Code, Codex, Cursor, Copilot, Gemini CLI, and OpenCode. Requires Node.js 22.18+.

## Install

One command installs every skill globally, for all your agents:

```bash
npx skills add agentmemoir/skills --all --global -y
```

`--all` is shorthand for `--skill '*' --agent '*' -y`: all skills, all agents, no prompts. `--global` installs to `~/.agents/skills/` (symlinked into each agent) instead of the current project. Each skill's `Say:` line below shows how to invoke it once installed.

## Categories

| Category | Skills | Focus |
|---|---:|---|
| [Frontend](#frontend) | 3 | Build and review Svelte 5 apps |
| [Languages](#languages) | 7 | Language, data-store, and host-portability craft |
| [Quality](#quality) | 5 | Review, red-team, and verify finished work |
| [Writing](#writing) | 1 | Write and improve prose |

## Skill Index

### Frontend

`skills/frontend/`

| Skill | Description |
|---|---|
| [`paraglide-svelte5-best-practices`](skills/frontend/paraglide-svelte5-best-practices/SKILL.md) | Type-safe, tree-shakable i18n for Svelte 5 and SvelteKit with Paraglide JS 2.x. |
| [`svelte5-ssr-runes`](skills/frontend/svelte5-ssr-runes/SKILL.md) | Server-rendered Svelte 5 with runes, SvelteKit SSR, or plain Vite SSR. |
| [`svelte5-static-runes`](skills/frontend/svelte5-static-runes/SKILL.md) | Static (no server) Svelte 5 apps with runes and adapter-static. |

#### Paraglide Svelte5 best practices

```
npx skills add agentmemoir/skills --skill paraglide-svelte5-best-practices --global -y
```

Type-safe, tree-shakable i18n for Svelte 5 and SvelteKit with Paraglide JS 2.x: compiler-based messages, locale strategies, localized URLs, SSR/SSG setup, rich-text markup with Svelte 5 snippets, testing, and common pitfalls.

Say: "Set up Paraglide i18n in my SvelteKit app with localized URLs."

#### Svelte5 SSR runes

```
npx skills add agentmemoir/skills --skill svelte5-ssr-runes --global -y
```

Build, migrate, or review server-rendered Svelte 5 apps using runes with SvelteKit SSR or plain Vite SSR: request-scoped state, hydration-safe rendering, streaming loads, CSP nonces, and an SSR security checklist.

Say: "Build my Svelte 5 app with SSR and runes."

#### Svelte5 static runes

```
npx skills add agentmemoir/skills --skill svelte5-static-runes --global -y
```

Build, migrate, or review static (no server) Svelte 5 apps using runes ($state, $derived, $effect, $props, $bindable) instead of legacy Svelte 4 reactivity, with SvelteKit adapter-static setup and an XSS/CSP/secrets security checklist.

Say: "Build my Svelte 5 static site with runes."

### Languages

`skills/languages/`

| Skill | Description |
|---|---|
| [`noexec-coding`](skills/languages/noexec-coding/SKILL.md) | Code and tests that work where scratch storage is mounted `noexec`. |
| [`noexec-python`](skills/languages/noexec-python/SKILL.md) | Python under a `noexec` mount: run scripts through the interpreter, keep temp paths for data. |
| [`noexec-rust`](skills/languages/noexec-rust/SKILL.md) | Rust under a `noexec` mount: probe and relocate the cargo target dir. |
| [`python-subprocess-and-concurrency`](skills/languages/python-subprocess-and-concurrency/SKILL.md) | Runs external programs safely and picks the right concurrency model. |
| [`rust-flaky-test-investigator`](skills/languages/rust-flaky-test-investigator/SKILL.md) | Finds why a Rust test fails intermittently and files it with a measured flake rate. |
| [`rust-test-best-practices`](skills/languages/rust-test-best-practices/SKILL.md) | Guidelines for writing Rust tests that stay reliable in CI. |
| [`sql-guidelines`](skills/languages/sql-guidelines/SKILL.md) | Postgres formatting conventions for case, layout, naming, and types. |

#### Noexec coding

```
npx skills add agentmemoir/skills --skill noexec-coding --global -y
```

Write and test code for hosts where every scratch directory is mounted `noexec`, so starting a file from a temporary path is refused with `Permission denied` or exit code 126. Covers what the mount blocks, why shebangs and mode bits do not help, the three-way execution probe, where executables belong, test design that cannot skip, and the anti-patterns that hide the defect.

Say: "My tests fail with Permission denied from /tmp — make this code work on a noexec host."

#### Noexec python

```
npx skills add agentmemoir/skills --skill noexec-python --global -y
```

Write and test Python on hosts where scratch storage is mounted `noexec`. Run scripts through `sys.executable` instead of starting them, keep `tempfile` and `tmp_path` for data, resolve a proven executable directory with a three-state probe, and replace skip-based tests with one negative test that fails when a program lands in scratch. Includes a tested resolver, twelve reference tests, and a migration workflow.

Say: "Why does subprocess raise PermissionError for a helper script in tmp_path?"

#### Noexec rust

```
npx skills add agentmemoir/skills --skill noexec-rust --global -y
```

Build and test Rust on hosts where scratch storage is mounted `noexec`, where `cargo test` fails with `Permission denied (os error 13)`. Probe the cargo target directory before a cold build, move it to executable storage, cover doctests and build scripts, and spawn helper programs from a resolved directory while keeping `TempDir` for data. Includes compile-checked resolver and spawn examples.

Say: "cargo test fails with Permission denied on a temp target dir — fix the setup."

#### Python subprocess and concurrency

```
npx skills add agentmemoir/skills --skill python-subprocess-and-concurrency --global -y
```

Subprocess and concurrency discipline for Python: how to run external programs safely, and how to pick the right concurrency model instead of the habitual one. Covers argv vs `shell=True`, timeouts that kill the whole process tree, pipe deadlocks, `ThreadPoolExecutor` sizing, GIL and free-threading, multiprocessing start methods (spawn/forkserver/fork), pickling limits, and inter-process messaging, plus hang, orphan, and zombie diagnosis.

Say: "Review this subprocess and threading code" or "Why is this Python script hanging?"

#### Rust flaky test investigator

```
npx skills add agentmemoir/skills --skill rust-flaky-test-investigator --global -y
```

Finds out why a Rust test fails intermittently and files it as a bug with a measured flake rate, a reproduced failure, and a root cause backed by a controlled experiment. Decodes the error's own codes before forming any hypothesis, then uses cargo-nextest stress runs, an eight-axis discrimination matrix, and a nineteen-family root-cause taxonomy. Never concludes a cause from reading test code alone.

Say: "Investigate why `replication_convergence` is flaky in this Rust repo."

#### Rust test best practices

```
npx skills add agentmemoir/skills --skill rust-test-best-practices --global -y
```

Guidelines for writing Rust tests that stay reliable in CI. Covers test layer choice, async tests with Tokio paused time, isolating ports and temp dirs, resource cleanup across processes, determinism against clocks, hash order and floating point, blocking the async executor, filesystem semantics across platforms, timeouts, property-based tests, and cargo-nextest configuration.

Say: "Write this Rust test following rust-test-best-practices" or "Review my Rust tests against the guidelines."

#### SQL guidelines

```
npx skills add agentmemoir/skills --skill sql-guidelines --global -y
```

Postgres formatting conventions for case, layout, naming, and types. Keywords uppercase, type names lowercase (except `TIMESTAMP WITH TIME ZONE`), snake_case identifiers, 2-space indent, types at column 96, plus naming, type, table, function, and index rules. Applies to every SQL change.

Say: "Write (or review) this SQL using sql-guidelines."

### Quality

`skills/quality/`

| Skill | Description |
|---|---|
| [`autopsy`](skills/quality/autopsy/SKILL.md) | Second pass on finished work; returns one HTML audit report and changes nothing until you pick fixes. |
| [`debloat`](skills/quality/debloat/SKILL.md) | Forces lean code in any language; caps every file it creates or modifies at 450 lines. |
| [`review`](skills/quality/review/SKILL.md) | Three-pass bug hunt that keeps only the bugs that survive refutation. |
| [`tracer`](skills/quality/tracer/SKILL.md) | Evidence-based, read-only security audit with severity-rated findings. |
| [`verification-antipattern`](skills/quality/verification-antipattern/SKILL.md) | Finds verification gates that block people or agents for over 5 minutes, names the cause, and ranks fixes. |

#### Autopsy

```
npx skills add agentmemoir/skills --skill autopsy --global -y
```

A second pass on finished work. It checks docs, plans, or code against what you asked for, verifies checkable claims with web search, and returns a single HTML report with a verdict, missing requirements, and fixes ordered by priority. It changes nothing until you pick what to fix.

Say: "Run an autopsy on docs/plan.md and show me the report."

#### Debloat

```
npx skills add agentmemoir/skills --skill debloat --global -y
```

Enforce lean code in any language: confirm requirements, research current best practices, then write the smallest implementation that works. Caps every file it creates or modifies at 450 lines.

Say: "Add the endpoint, but keep it debloated."

#### Review

```
npx skills add agentmemoir/skills --skill review --global -y
```

A three-pass bug hunt on a codebase. The first pass lists as many bugs as it can find, the second argues against each one, and the third keeps only the ones that hold up. Each phase writes a dated file and every bug keeps one ID (BUG-001, BUG-002) with file and line across all three. Point it at one folder when the repo is large, since it does better work on a small scope than on everything at once.

Say: "Run a review on ./src/auth."

#### Tracer

```
npx skills add agentmemoir/skills --skill tracer --global -y
```

Evidence-based security audit of a local codebase. It maps the attack surface, investigates reachable vulnerabilities, reproduces them safely, challenges each hypothesis independently, and reports severity-rated findings with honest limits. Read-only by default.

Say: "Audit this repo for security vulnerabilities and show me the confirmed findings."

#### Verification antipattern

```
npx skills add agentmemoir/skills --skill verification-antipattern --global -y
```

Detects hostile verification gates — lint, format, typecheck, build, test, coverage, mutation, or security checks that block a person or agent for more than five minutes — and returns a short report naming the cause from a catalog of eleven antipatterns, with fixes ranked by expected wait saved. It reports and plans; it changes gates only when the task asks.

Say: "CI blocks every merge for 20 minutes. Find where the time goes and fix it."

### Writing

`skills/writing/`

| Skill | Description |
|---|---|
| [`wordsmith`](skills/writing/wordsmith/SKILL.md) | Writes, audits, and rewrites developer documentation with page typing, 28 style rules, a 26-pattern AI-tell catalog, and rule-traced change logs. |

#### Wordsmith

```
npx skills add agentmemoir/skills --skill wordsmith --global -y
```

Write, audit, and rewrite developer documentation using the Wordsmith method — page typing, 28 numbered style rules, a 26-pattern AI-tell catalog, and rule-traced change logs. Its voice pass strips machine-written tells (not-X-but-Y contrasts, one-line closers, forced triads, stock words, decorative bold) from docs prose without touching facts, code samples, or reference neutrality. The catalog is vendored verbatim from [blader/humanizer](https://github.com/blader/humanizer) at a pinned release and checked in CI, so a hand-edit to the vendored text fails the build.

Say: "Rewrite this README with wordsmith" or "These docs read like AI wrote them — de-slop them."

## CLI tools

This repo ships two binaries, `pb` and `sqlm`. Since there is more than one `bin` entry, call them with the explicit `--package` form.

```
npx --package github:agentmemoir/skills pb <inputFile> [outputFile]
npx --package github:agentmemoir/skills sqlm <input_directory> [output_file]
```

- `pb` expands `{{file:...}}`, `{{raw:...}}`, and `{{folder:...}}` placeholders relative to the current directory. With no `[outputFile]` it writes `.<name>.processed<ext>` next to the input.
- `sqlm` merges every `.sql` file under `<input_directory>` in alphabetical order. With no `[output_file]` it writes `<input_directory>.sql`.

## Next steps

- Add a skill: copy `template/SKILL.md`, then follow the index-sync checklist in `AGENTS.md`.
- Verify a change: run `npm test` (needs Node.js 22.18+).

[MIT](LICENSE) — use freely, attribution appreciated.
