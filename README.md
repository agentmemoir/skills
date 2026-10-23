# agentmemoir/skills

Skills that run inside your coding agent. They work with Claude Code, Codex, Cursor, Copilot, Gemini CLI, and OpenCode. Requires Node.js 22.18+.

## Install

One command installs every skill globally, for all your agents:

```bash
npx skills add agentmemoir/skills --all --global -y
```

`--all` is shorthand for `--skill '*' --agent '*' -y`: all skills, all agents, no prompts. `--global` installs to `~/.agents/skills/` (symlinked into each agent) instead of the current project. Each skill's `Say:` line below shows how to invoke it once installed.

<!-- BEGIN GENERATED: skills index -->

## Categories

| Category | Skills | Focus |
|---|---:|---|
| [Code](#code) | 4 | Write, run, and test code inside one language |
| [Docs](#docs) | 2 | Write and improve documentation |
| [Engineering](#engineering) | 2 | Build lean code and keep verification gates honest |
| [Portability](#portability) | 3 | Code that runs on hosts that block execution |
| [Review](#review) | 3 | Verdicts on finished work |
| [Web](#web) | 3 | Apps that run in a browser |
| [Workflow](#workflow) | 4 | Decide, plan, and report progress with you |

## Skill Index

### Code

`skills/code/`

| Skill | Description |
|---|---|
| [`python-subprocess-and-concurrency`](skills/code/python-subprocess-and-concurrency/SKILL.md) | Runs external programs safely and picks the right concurrency model instead of the habitual one. |
| [`rust-flaky-test-investigator`](skills/code/rust-flaky-test-investigator/SKILL.md) | Finds why a Rust test fails intermittently and files it as a bug. |
| [`rust-test-best-practices`](skills/code/rust-test-best-practices/SKILL.md) | Guidelines for writing Rust tests that stay reliable in CI. |
| [`sql-guidelines`](skills/code/sql-guidelines/SKILL.md) | Postgres formatting conventions for case, layout, naming, and types. |

#### Python subprocess and concurrency

```
npx skills add agentmemoir/skills --skill python-subprocess-and-concurrency --global -y
```

Runs external programs safely and picks the right concurrency model instead of the habitual one. Covers argv vs `shell=True`, timeouts that kill the whole process tree, pipe deadlocks, `ThreadPoolExecutor` sizing, GIL and free-threading, multiprocessing start methods (spawn/forkserver/fork), pickling limits, and inter-process messaging, plus hang, orphan, and zombie diagnosis.

Say: "Review this subprocess and threading code" or "Why is this Python script hanging?"

#### Rust flaky test investigator

```
npx skills add agentmemoir/skills --skill rust-flaky-test-investigator --global -y
```

Finds why a Rust test fails intermittently and files it as a bug. Reports a measured flake rate, a reproduced failure, and a root cause backed by a controlled experiment. Decodes the error's own codes before forming any hypothesis, then uses cargo-nextest stress runs, an eight-axis discrimination matrix, and a nineteen-family root-cause taxonomy. Never concludes a cause from reading test code alone.

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

### Docs

`skills/docs/`

| Skill | Description |
|---|---|
| [`philosophy`](skills/docs/philosophy/SKILL.md) | Researches your project before the first question — product truths with evidence, hypotheses, and tensions between existing features. |
| [`wordsmith`](skills/docs/wordsmith/SKILL.md) | Writes, audits, and rewrites developer documentation with page typing, 28 style rules, and a 26-pattern AI-tell catalog. |

#### Philosophy

```
npx skills add agentmemoir/skills --skill philosophy --global -y
```

Researches your project before the first question — product truths with evidence, hypotheses, and tensions between existing features. Then interviews you one decision at a time, flags every contradiction the moment it appears, and recaps all choices so you can amend any answer. Costly forks go through prism with each option tagged as product truth or new proposal. Writes PHILOSOPHY.md only after your explicit confirmation, then refactors AGENTS.md so every rule names the belief it serves.

Say: "Write our philosophy for this repo before you touch AGENTS.md."

#### Wordsmith

```
npx skills add agentmemoir/skills --skill wordsmith --global -y
```

Writes, audits, and rewrites developer documentation with page typing, 28 style rules, and a 26-pattern AI-tell catalog. Its voice pass strips machine-written tells (not-X-but-Y contrasts, one-line closers, forced triads, stock words, decorative bold) from docs prose without touching facts, code samples, or reference neutrality. Every change is traced to the rule that caused it, and the catalog is vendored verbatim from [blader/humanizer](https://github.com/blader/humanizer) at a pinned release and checked in CI, so a hand-edit to the vendored text fails the build.

Say: "Rewrite this README with wordsmith" or "These docs read like AI wrote them — de-slop them."

### Engineering

`skills/engineering/`

| Skill | Description |
|---|---|
| [`debloat`](skills/engineering/debloat/SKILL.md) | Forces lean code in any language and caps every file it creates or modifies at 450 lines. |
| [`verification-antipattern`](skills/engineering/verification-antipattern/SKILL.md) | Finds verification gates that block people or agents for over 5 minutes, names the cause, and ranks the fixes. |

#### Debloat

```
npx skills add agentmemoir/skills --skill debloat --global -y
```

Forces lean code in any language and caps every file it creates or modifies at 450 lines. Confirms requirements, researches current best practices, then writes the smallest implementation that works.

Say: "Add the endpoint, but keep it debloated."

#### Verification antipattern

```
npx skills add agentmemoir/skills --skill verification-antipattern --global -y
```

Finds verification gates that block people or agents for over 5 minutes, names the cause, and ranks the fixes. Covers lint, format, typecheck, build, test, coverage, mutation, and security checks, and reports from a catalog of eleven antipatterns with fixes ranked by expected wait saved. It reports and plans; it changes gates only when the task asks.

Say: "CI blocks every merge for 20 minutes. Find where the time goes and fix it."

### Portability

`skills/portability/`

| Skill | Description |
|---|---|
| [`noexec-coding`](skills/portability/noexec-coding/SKILL.md) | Code and tests that work where scratch storage is mounted `noexec`. |
| [`noexec-python`](skills/portability/noexec-python/SKILL.md) | Python under a `noexec` mount: run scripts through the interpreter and keep temp paths for data. |
| [`noexec-rust`](skills/portability/noexec-rust/SKILL.md) | Rust under a `noexec` mount: probe and relocate the cargo target dir. |

#### Noexec coding

```
npx skills add agentmemoir/skills --skill noexec-coding --global -y
```

Code and tests that work where scratch storage is mounted `noexec`. The mount blocks starting any file from a temporary path, so scripts run through an interpreter, executables live in a probed directory, and tests cannot skip around the defect. Covers what the mount blocks, why shebangs and mode bits do not help, the three-way execution probe, where executables belong, test design that cannot skip, and the anti-patterns that hide the defect.

Say: "My tests fail with Permission denied from /tmp — make this code work on a noexec host."

#### Noexec python

```
npx skills add agentmemoir/skills --skill noexec-python --global -y
```

Python under a `noexec` mount: run scripts through the interpreter and keep temp paths for data. Resolve a proven executable directory with a three-state probe, and replace skip-based tests with one negative test that fails when a program lands in scratch. Includes a tested resolver, twelve reference tests, and a migration workflow.

Say: "Why does subprocess raise PermissionError for a helper script in tmp_path?"

#### Noexec rust

```
npx skills add agentmemoir/skills --skill noexec-rust --global -y
```

Rust under a `noexec` mount: probe and relocate the cargo target dir. `cargo test` fails with `Permission denied (os error 13)` on a scratch target path, so probe the directory before a cold build and move it to executable storage. Covers doctests and build scripts, and spawns helper programs from a resolved directory while keeping `TempDir` for data. Includes compile-checked resolver and spawn examples.

Say: "cargo test fails with Permission denied on a temp target dir — fix the setup."

### Review

`skills/review/`

| Skill | Description |
|---|---|
| [`autopsy`](skills/review/autopsy/SKILL.md) | Second pass on finished work: returns one HTML audit report and changes nothing until you pick fixes. |
| [`review`](skills/review/review/SKILL.md) | Three-pass bug hunt that keeps only the bugs that survive refutation. |
| [`tracer`](skills/review/tracer/SKILL.md) | Evidence-based, read-only security audit with severity-rated findings. |

#### Autopsy

```
npx skills add agentmemoir/skills --skill autopsy --global -y
```

Second pass on finished work: returns one HTML audit report and changes nothing until you pick fixes. Checks docs, plans, or code against what you asked for, verifies checkable claims with web search, and reports a verdict, missing requirements, and fixes ordered by priority.

Say: "Run an autopsy on docs/plan.md and show me the report."

#### Review

```
npx skills add agentmemoir/skills --skill review --global -y
```

Three-pass bug hunt that keeps only the bugs that survive refutation. The first pass lists as many bugs as it can find, the second argues against each one, and the third keeps only the ones that hold up. Each phase writes a dated file and every bug keeps one ID (BUG-001, BUG-002) with file and line across all three. Point it at one folder when the repo is large, since it does better work on a small scope than on everything at once.

Say: "Run a review on ./src/auth."

#### Tracer

```
npx skills add agentmemoir/skills --skill tracer --global -y
```

Evidence-based, read-only security audit with severity-rated findings. Maps the attack surface, investigates reachable vulnerabilities, reproduces them safely, challenges each hypothesis independently, and reports honest limits.

Say: "Audit this repo for security vulnerabilities and show me the confirmed findings."

### Web

`skills/web/`

| Skill | Description |
|---|---|
| [`paraglide-svelte5-best-practices`](skills/web/paraglide-svelte5-best-practices/SKILL.md) | Type-safe, tree-shakable i18n for Svelte 5 and SvelteKit with Paraglide JS 2.x. |
| [`svelte5-ssr-runes`](skills/web/svelte5-ssr-runes/SKILL.md) | Server-rendered Svelte 5 with runes, SvelteKit SSR, or plain Vite SSR. |
| [`svelte5-static-runes`](skills/web/svelte5-static-runes/SKILL.md) | Static (no server) Svelte 5 apps with runes and adapter-static. |

#### Paraglide Svelte5 best practices

```
npx skills add agentmemoir/skills --skill paraglide-svelte5-best-practices --global -y
```

Type-safe, tree-shakable i18n for Svelte 5 and SvelteKit with Paraglide JS 2.x. Covers compiler-based messages, locale strategies, localized URLs, SSR/SSG setup, rich-text markup with Svelte 5 snippets, testing, and common pitfalls.

Say: "Set up Paraglide i18n in my SvelteKit app with localized URLs."

#### Svelte5 SSR runes

```
npx skills add agentmemoir/skills --skill svelte5-ssr-runes --global -y
```

Server-rendered Svelte 5 with runes, SvelteKit SSR, or plain Vite SSR. Build, migrate, or review apps that use runes: request-scoped state, hydration-safe rendering, streaming loads, CSP nonces, and an SSR security checklist.

Say: "Build my Svelte 5 app with SSR and runes."

#### Svelte5 static runes

```
npx skills add agentmemoir/skills --skill svelte5-static-runes --global -y
```

Static (no server) Svelte 5 apps with runes and adapter-static. Build, migrate, or review apps that use runes instead of legacy Svelte 4 reactivity, with SvelteKit adapter-static setup and an XSS/CSP/secrets security checklist.

Say: "Build my Svelte 5 static site with runes."

### Workflow

`skills/workflow/`

| Skill | Description |
|---|---|
| [`prism`](skills/workflow/prism/SKILL.md) | Puts a costly, hard-to-undo decision to you as one short question, one option per lens, and a recommendation. |
| [`probe`](skills/workflow/probe/SKILL.md) | Grills you on a request before any code changes, then turns the settled decisions into a plan, a GitHub master issue, or a coding session. |
| [`progress`](skills/workflow/progress/SKILL.md) | Keeps a ledger of the large work items in a long task and sends a 12-line progress and ETA report each time one changes state. |
| [`retro`](skills/workflow/retro/SKILL.md) | Ends a session with up to three suggestions to fix your skills, agent instructions, and rules, each grounded in something that happened. |

#### Prism

```
npx skills add agentmemoir/skills --skill prism --global -y
```

Puts a costly, hard-to-undo decision to you as one short question, one option per lens, and a recommendation. Speed, Simplicity, Reliability, and Flexibility each get an option that fully solves the problem, with real pros and cons. If a choice is clear or cheap to undo, the agent makes it and tells you in one line.

Say: "Prism this: which cache fix should we ship?"

#### Probe

```
npx skills add agentmemoir/skills --skill probe --global -y
```

Grills you on a request before any code changes, then turns the settled decisions into a plan, a GitHub master issue, or a coding session. Restates your goal, researches avenues, and asks one decision at a time. Costly choices go through prism. Plans and preferences are saved outside the CLI's data folder, so session cleanup cannot delete them.

Say: "Probe me on the auth refactor before you touch any code."

#### Progress

```
npx skills add agentmemoir/skills --skill progress --global -y
```

Keeps a ledger of the large work items in a long task and sends a 12-line progress and ETA report each time one changes state. Items are never silently dropped or renamed. Scope changes are stated, and the ETA is always a range based on evidence. Works for one agent alone or for an orchestrator with subagents.

Say: "Track progress on this and give me ETAs."

#### Retro

```
npx skills add agentmemoir/skills --skill retro --global -y
```

Ends a session with up to three suggestions to fix your skills, agent instructions, and rules, each grounded in something that happened. Every suggestion names the file, quotes the instruction, and states the effect seen. One switch turns retros off for every future session.

Say: "Run a retro on this session."

<!-- END GENERATED: skills index -->

## CLI tools

This repo ships two binaries, `pb` and `sqlm`. Since there is more than one `bin` entry, call them with the explicit `--package` form.

```
npx --package github:agentmemoir/skills pb <inputFile> [outputFile]
npx --package github:agentmemoir/skills sqlm <input_directory> [output_file]
```

- `pb` expands `{{file:...}}`, `{{raw:...}}`, and `{{folder:...}}` placeholders relative to the current directory. With no `[outputFile]` it writes `.<name>.processed<ext>` next to the input.
- `sqlm` merges every `.sql` file under `<input_directory>` in alphabetical order. With no `[output_file]` it writes `<input_directory>.sql`.

## Next steps

- Add a skill: copy `template/SKILL.md`, fill in its frontmatter, then run `npm run generate:index`.
- Verify a change: run `npm test` (needs Node.js 22.18+).

[MIT](LICENSE) — use freely, attribution appreciated.
