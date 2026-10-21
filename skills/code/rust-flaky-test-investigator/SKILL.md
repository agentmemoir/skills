---
name: rust-flaky-test-investigator
description: >-
  Investigates a flaky Rust test and reports it as a filed bug with a measured
  flake rate, a reproduced failure, and a proven root cause. Use when a Rust test
  passes intermittently, CI is red without a code change, a test is suspected of
  being order-dependent or timing-sensitive, a test needs quarantining, or the
  I say "flaky test", "intermittent failure", "passes on retry", "works on my
  machine", or asks to find which tests in a Rust suite are unreliable. Built
  around error-code triage, cargo-nextest stress runs, and controlled
  experiments. Execution-driven: never concludes a root cause from reading test
  code alone.
---

# Rust Flaky Test Investigator

Turns "this test is flaky" into a filed bug: a measured failure rate or an explicit, evidenced `not_reproduced` finding, a captured failing run, one root cause backed by a discriminating experiment, and a minimal fix proposal.

## When to use

Use this skill when a Rust test fails intermittently, CI is red with no matching code change, a test is suspected of being order-dependent, timing-bound, or resource-colliding, or a test is being considered for quarantine. Also use it to sweep a suite for unreliable tests.

Do not use it for: a test that fails every time (that is a plain bug — use `review`), a genuine regression after a known code change, or non-Rust suites (the taxonomy is Rust-specific).

## The one rule that matters

**You cannot find a flaky test's cause by reading its code.** Berndt et al. (SANER 2026, "Can We Classify Flaky Tests Using Only Test Code?") evaluated three LLMs on flaky-test classification from test source alone and found the best prompt/model combination "only marginally better than random guessing" (best-case MCC 0.27); their manual analysis of 50 samples found the test code "does not necessarily contain sufficient information". The complementary argument for execution data comes from deflake.rs (Magill & McMinn, JOSS 2025), which detects flakiness from per-test coverage plus diff rather than from source inspection.

The defect lives in the interaction between the test, the scheduler, the network, the clock, and the disk — none of which is visible in the source. Every conclusion in this skill must come from a command you ran and output you read.

This is a hard gate. If you did not execute it, you do not know it. A plausible-sounding root cause with no reproduction behind it is a hypothesis, and the report must label it as one.

## The mirror of that rule

**The error's own payload is data, and it is often the whole answer.** You cannot diagnose from source alone — and you cannot diagnose from the *shape* of the failure alone either. The failing run already printed a code, a status, a signal, or a value that names the mechanism, and one lookup against that library's documentation ends the investigation. Decode it before you generate a hypothesis, and before you read a single file of the code under test. See `references/error-triage.md`.

Both halves fail the same way. Three wrong mechanisms in one investigation came from reading code and ignoring the panic; the right one came from decoding it.

## Non-negotiables

1. **No flake claim without a rate.** Measure failures over N iterations with the code unchanged. "It failed once last night" is not a flake report; it is an anecdote. State the sample size. A test you never reproduced has no rate: file it as `reproduction.status = not_reproduced` with `cause_basis = inferred`, which is a legitimate finding, and say so in the report rather than borrowing a number.
2. **No root cause without a discriminating experiment.** For each candidate cause, name the one experiment whose outcome differs depending on whether the cause is real. If you cannot design that experiment, you have a hypothesis, not a root cause.
3. **Separate flake from non-flake first.** A test that always fails is a bug. A test that started failing after a specific commit is a regression. Confirm which one before anything else.
4. **Never resolve with a retry.** Bumping `retries`, adding a sleep, or widening a timeout hides the defect. Containment is allowed only alongside a tracked bug with an owner and a deadline.
5. **Read-only by default.** Investigate, capture, and propose. Do not edit production or test code, change runner config, or alter CI without a separate explicit request. Proposed fixes ship as diffs.
6. **Report only what ran.** If a tool was missing, a step was skipped, a loop was cut short, or a command cache replayed a stored verdict instead of executing, say so in the report. Never present a planned step as a completed one, and never a cached result as a measurement.
7. **Bound the cost.** Stress loops are wall-clock expensive. Default to 50 iterations, raise only with evidence that the rate is below detection at 50, and always tell me the expected runtime before starting a long one. Never saturate my machine without asking: confirm it is not a battery-powered host I am working on, and prefer a smaller run of the failing workload's *shape* over a heavier run of the same tests.
8. **A hypothesis is not a finding until you have read the code that emits the error.** You can satisfy non-negotiable 2 with a well-designed experiment about the wrong mechanism, and then file a confident, well-structured, wrong bug. If you cannot point at the line that produced the error value, the cause is `hypothesis` in the report — not `confirmed`.

## Workflow

Run the steps in order. Step 0 and Phases 1 to 3 are cheap and mandatory. Phase 4 and 5 are where the answer comes from. Do not skip to a fix.

### Step 0 — Decode the failure

The failing run already printed the mechanism. Read it before reading code, because a wrong first hypothesis costs more than every other mistake in this skill combined.

Take the first line that names an error and enumerate every value it carries: primary and extended codes, `errno`, HTTP or gRPC status, SQLSTATE, exit signal, and the asserted values. Resolve each one against that library's own documentation, then read the code path that emits it. A resolved code is a named hypothesis; confirm it against the emitting branch before you build anything on it.

Details, the code tables, and a worked example are in `references/error-triage.md`. Do this even when the failure looks like a plain timeout: the code under the timeout is usually more specific than the symptom.

### Phase 1 — Intake and repo policy

Establish these five things before running anything.

**The target.** Get the exact test identifier in nextest form (`binary::module::test_name`) and the exact command that observes the failure, including the CI profile. A flake report without the reproducing command is not reproducible.

**The project's own rules.** Read the repo's test policy before forming any opinion. Most Rust projects already encode anti-flake rules, and violating one is itself the finding. Look for:

- `.config/nextest.toml` — profiles, `retries`, `slow-timeout`, `leak-timeout`, `[test-groups]`, quarantine overrides.
- A testing doc (`docs/testing/`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`).
- Existing flake or quarantine tracking, and any name-substring gates that select tests by name.

**Tooling available.** Record present vs. missing: `cargo-nextest`, nightly toolchain, `tokio-console`, `loom`, `shuttle`, `proptest`, ThreadSanitizer, `stress-ng`, container runtime. Degrade gracefully and log the gap. Record the nextest version (`cargo nextest --version`) — several behaviours below are version-sensitive. To see effective test groups, run `cargo nextest show-config test-groups`; note that `show-config` has no profile-dump subcommand, so read profile values from `.config/nextest.toml` directly.

**Tooling that lies: command caches.** Plenty of repos wrap test commands in a content-addressed cache, a Makefile target, `cargo-nextest` behind a wrapper, or a CI action with `cache-hit` output. On an unchanged tree, the second identical command may replay a stored verdict instead of running. That is the most expensive possible failure during a flake investigation, because a replayed **pass** deletes the failure you are trying to measure. Find out before you trust the first number: `rg -n 'cache|force|restage|mtime' Makefile justfile .just/ .config/ .github/workflows/ 2>/dev/null`, and check whether any wrapper prints a `cache hit` line. If it does, vary the command between iterations or perturb the tree so each run is distinct, and record `runs_distinct: false` if you could not. See the playbook section on replayed verdicts.

**Baseline the test exists.** Run it once, normally. If it fails every single time, stop — that is a deterministic bug, not a flake.

### Phase 2 — Prove it flakes and measure the rate

Confirm nondeterminism before investigating it. A test that passed every single iteration is not flaky, and chasing it wastes the run.

Prefer `cargo nextest run --stress-count=N --no-fail-fast` over a shell loop: nextest runs the selection N times, annotates each iteration, and reports a per-iteration summary. It needs nextest 0.9.103 or newer.

```bash
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
```

`--no-fail-fast` is mandatory. Without it the loop stops at the first failure, and the truncated sample masquerades as a rate — a summary reading `3/10 iterations: 2 passed, 1 failed` is an aborted run, not a 33% flake.

Two selector traps: `test(name)` is a substring match against the module path, so a bare name is fine, while `test(=name)` is an exact match that needs the full `module::path`. An exact match on a bare name selects nothing and reports `0 tests run`, which reads as a pass. Confirm the selector with `cargo nextest list` before trusting a zero.

Read the `Summary` line. It gives iterations run, tests passed, and failures. That is your flake rate. **Take the rate from that line, never from the exit code** — measured on nextest 0.9.146, a stress run with `6 failed` exited `0` in five runs out of six.

Escalate deliberately:

- Fails early and often — the rate is high, 50 iterations is plenty. Move on.
- Passes everything at 50 — the rate is below about **6%** at 95% confidence. Zero failures in 50 trials only bounds the rate at `1 - 0.05^(1/50)` ≈ 5.8%; reaching a 2% bound needs roughly 150 iterations. Either raise the count, or lower the effective threshold by adding load (Phase 3, load axis), or conclude the cause is environmental and will not reproduce locally. Say which.
- Never ran — the test was filtered, ignored, or the selector is wrong. Fix the selector. A run reporting `0 tests run` is a usage error, not a pass.

**"Reproduced zero times locally" is a named terminal state, not a failure to keep pushing.** Two real failures in a whole-workspace run, and nothing local, is a common and legitimate outcome — but it is also the point where a confident report gets written on no evidence. When you land here, file it, with `reproduction.status = not_reproduced` and `cause_basis = inferred`, and include:

- The exact command and workload the failures were seen under, from the original failing job, not a local substitute.
- Every reproduction attempt with its command and result, including the ones that passed. Never round "20 of 20 passed" up to a rate without saying how many of those 20 actually executed.
- The mechanism narrowed to a specific code path **by reading**, with the error code that named it and the file and line that emits it. This is the only evidence you have, so it has to be quotable.
- An explicit sentence saying the cause is inferred, not measured, and naming the single cheap experiment that would confirm it on a machine that can reproduce the workload.

An inferred cause with a named code path and a named next experiment is a strong finding. The same cause presented as `confirmed` with no local reproduction is the failure mode this skill exists to prevent.

Record the exact command, iteration count, failure count, and the failing run's full output. If retries are enabled in the profile, note them: a test that "passes" may have passed on attempt 3. Add `--flaky-result fail` so flaky tests cannot silently report success.

### Phase 3 — Run the discrimination matrix

This is the highest-value phase. Each axis is a controlled experiment that eliminates a whole family of causes. Run them in this order; stop as soon as one axis isolates the failure.

For the full command set and axis-by-axis interpretation, read `references/reproduction-playbook.md`.

| # | Axis | Vary | If the failure vanishes | Implicates |
|---|------|------|-------------------------|-----------|
| 1 | Isolation | test alone vs. full suite | Passes alone | cross-test interference, leaked state or process |
| 2 | Serialization | `-j 1` / `--test-threads=1` vs. parallel | Passes serially | shared resource, contention, starvation |
| 3 | Ordering | the suspected predecessor, in that order | Only fails after it | order dependence, state leak |
| 4 | Load | under CPU and I/O pressure | Fails only under load | sleep-based wait, `yield_now` polling, short server lifetime |
| 5 | Build profile | debug vs. release | Fails only in debug | timing sensitivity exposed by slower unoptimized code |
| 6 | Environment | host vs. CI container / constrained runner | Fails only in CI | infra limits, missing network, certs, locale, disk speed |
| 7 | Cleanup | watch for `LEAK` status, orphaned processes | LEAK present | child process holding a port, fd, or file lock |
| 8 | Resources | unique temp dir and port per iteration | Stops failing | hardcoded path or port collision |

Axis 1 is the highest-information split. It cleanly separates "the test is internally nondeterministic" from "something else in the suite interferes with it", and every later axis is interpreted differently depending on which side you land on.

Axis 8 deserves emphasis: hardcoded ports and fixed temp paths are the most common single cause, and they are trivially confirmable by changing one thing and re-running.

Axis 4 has preconditions, because saturating a machine is a cost paid by me. Ask before you stress a host you do not own, confirm it is not a battery-powered machine I am working on, and state the expected runtime first. Then prefer **shape over cost**: a smaller run of the same workload shape — many tests spawning children at once — usually beats a busier machine running the same tests, and it is the cheap option that respects my time. Note also that a test-runner gate serialises concurrent invocations, so "run it eight times concurrently" silently becomes "run it once" and the resulting zero failures read as a pass. Check for that before trusting a load-axis result, and record the axis honestly when load produced no signal.

**A host-dependent failure can be a defect in the code, not the test.** A value can be decoded, truncated, or formatted differently on some hosts. When the failure payload shows production output missing an expected element, follow the production path before proposing any test change, and never weaken the assertion to get green.

**Where to spend effort.** The axes are not equally broad, and knowing this saves time:

- **Broad** (each rules out several families): Isolation, Serialization, Ordering, Load, Environment. These five do most of the narrowing.
- **Narrow** (each confirms one specific family): Cleanup only distinguishes a subprocess leak, and Resources only confirms *which* resource collided. Neither narrows the space on its own, but both turn a suspicion into a confirmed cause cheaply.

Every family in the taxonomy has at least one decisive experiment, though three of them are not matrix axes: family 15's is a one-line teardown change, and families 16 and 17 are settled by an `rg` over the failing path plus the child's process state — see the playbook's hang section. Families 18 and 19 do map onto existing axes, build profile and environment respectively. So a test that resists all eight axes is a signal in itself: either the cause is environmental and needs the CI image reproduced, or the taxonomy is missing a family. Report that outcome rather than forcing a match.

### Phase 4 — Localize to a cause family

With the matrix results in hand, read `references/flaky-taxonomy.md` and match the failure signature to one of the nineteen cause families. Each family in that file lists its signature, the experiment that confirms it, and the fix direction. Families 1 to 10 cover async and storage-shaped codebases; 11 to 14 cover memory pressure, runner misconfiguration, DNS/hostname identity, and environment-derived test data, which the async-service literature tends to under-document; 15 to 19 cover the mechanisms that arrive from real Rust investigations — a test that corrupts the state it reads, the two deadlocks that hang instead of fail, floating-point comparison, and platform filesystem semantics.

Match on the decoded values from Step 0, not on the shape alone. A signature like "fails with a read-only error after a child exits" is a family; a family like self-inflicted resource damage has a one-line confirming experiment that nobody would think of from the symptom alone.

Three families dominate Rust suites and are worth checking first:

- **Wall-clock dependence.** A `sleep`, a short fixed timeout, or a mock server with a hardcoded idle shutdown. Under CPU throttling the deadline expires before the code runs. The test is not slow, it is a race with the clock.
- **Orphan background work.** A `tokio::spawn` whose `JoinHandle` is dropped. The test returns, the runtime is torn down, and the background task dies mid-write or is killed holding a lock. Symptom: the test passes alone but corrupts or breaks whatever runs next.
- **Self-inflicted resource damage.** The *same* test kills, drops, or interrupts the writer of the state it then reads, so its own teardown produces the artifact its assertion inspects. Family 10's neighbours are all about work outliving a test; this one is about a test destroying its own evidence, which is why it never shows up as "later tests fail". Confirm it by making the teardown graceful — wait for a clean exit instead of killing — and see whether the failure disappears.

A fourth is cheap and worth checking on any hang or timeout: **a blocking call inside an async task**, or **a parent that waits for a child without draining its pipe**. Those two families are settled by one `rg` over the failing path, and they are the most commonly misdiagnosed as a timing problem. Read "did not finish" separately from "took too long" before you spend an iteration on load.

Instrumentation, cheapest first:

- `RUST_LOG=debug` plus a `tracing` subscriber for chronological async events.
- `#[tracing_test::traced_test]` to capture only this test's logs, without parallel-run noise.
- `tokio-console` when the failure is a hang: it shows which tasks are pending, and which are busy-polling without making progress.
- `leak-timeout` in nextest config to catch subprocesses that outlive the test.

### Phase 5 — Prove it, then propose the fix

**Design the confirming experiment.** State it in one sentence: "If I remove the hardcoded port and bind ephemeral instead, the flake rate at 50 iterations goes to zero, and restoring the hardcoded port brings it back." Then actually run it both ways if you have the budget. A fix that was never seen to fail is not verified.

**Propose the minimal structural fix.** Match the fix to the family: ephemeral port and per-test temp dir for contention; `#[tokio::test(start_paused = true)]` plus explicit synchronization for timing; awaited `JoinHandle` or `CancellationToken` for orphan work; `tempfile::tempdir()` for shared paths; for self-inflicted damage, a clean writer exit or a post-exit copy, plus `query_only` instead of a read-only open where the assertion reads a store someone else writes. Avoid three non-fixes: adding a retry, adding a longer sleep, widening a timeout. They convert a real defect into a slower, rarer, and harder-to-diagnose one.

**Check whether the fix belongs in the test or in production code.** Sometimes the test is right and the code is wrong — a background task that does not shut down cleanly is a production defect that the test merely exposed. Flag that distinction; it changes who owns the bug.

### Phase 6 — File the report

Write the report to the output directory (default `./flaky-reports/`), one file per finding:

- `flaky-report.md` — the human-readable bug report, from `references/bug-report-template.md`.
- `flaky-findings.json` — the same findings, validated against `references/flaky-finding.schema.json`.

`references/bug-report.example.md` and `references/flaky-finding.example.json` are the same finding in both output shapes — a confirmed port collision with a filled discrimination matrix, a two-direction confirming experiment, rejected alternatives, and a non-empty `not_verified` list. Read them before writing your first report; the optional blocks are easy to get wrong or omit.

Validate the JSON against the schema before declaring done. Then present the findings in chat, ranked by flake rate and blast radius, and stop. Do not apply fixes unless asked.

Each finding must carry: the exact test id, the reproducing command, the measured rate with sample size, the failure signature, the decoded error values with their documented meanings, the root cause, the code path that emits the error value, the discriminating experiment and its result, the proposed fix, the confidence level, and an explicit list of what you did not verify.

When the cause rests on reading rather than on a local reproduction, that difference is the report's most important field. Set `cause_basis` to `measured` only when an experiment confirmed the cause here, `inferred` when the mechanism is established by the error code and by reading, and `environmental` when nothing could be attributed to a mechanism at all — and then write the report so a reader can act on it anyway: the exact workload, the attempts with their results, the code path, and the one experiment that would settle it.

## Sweeping a whole suite

When asked which tests in a suite are unreliable, or when a single flake is suspected to be one of many:

1. Run the suite with retries enabled and `--flaky-result fail`, so anything that only passes on a retry is visible rather than green.
2. Read the JUnit report and collect every test carrying a `flakyFailure` element. Enable it with a `[profile.<name>.junit]` block in `.config/nextest.toml`; the path is relative to `store.dir`, which defaults to `target/nextest`.
3. Stress each candidate individually to get a real rate. A retry-based detection gives you a candidate list, never a rate.
4. Group findings by cause family. Several tests sharing one cause is one bug with N symptoms, and fixing the shared cause is the real deliverable.

## References

- `references/error-triage.md` — decode the codes, statuses, signals, and asserted values in a failing run before forming a hypothesis. Step 0 reads this first.
- `references/flaky-taxonomy.md` — nineteen root-cause families with signature, confirming experiment, and fix direction.
- `references/reproduction-playbook.md` — verified command cookbook for nextest, cargo test, stress load, and CI reproduction.
- `references/repo-test-policy.md` — how to read a Rust project's testing conventions, profiles, test groups, quarantine, and the `#[serial]` trap.
- `references/bug-report-template.md` — the report format.
- `references/bug-report.example.md` — a complete worked report, showing what fully filled looks like. Read it before writing your first one.
- `references/flaky-finding.schema.json` — machine-readable finding schema.
- `references/flaky-finding.example.json` — the same finding as valid JSON.
- `scripts/flake-loop.sh` — bounded stress loop that works with or without cargo-nextest, records per-iteration logs, and prints a flake rate parsed from nextest's summary rather than its exit code.

## Out of scope

- Fixing the flake. This skill diagnoses and files. Hand the fix to a normal editing task.
- Non-Rust suites. The taxonomy assumes Tokio, nextest, and Rust's process model.
- Performance benchmarking of tests. Slow is not flaky; they have different root causes and different fixes.

## Version notes

Several behaviours here are version-sensitive and were verified against the versions below. Re-check them if the reader's toolchain differs, and say so in the report when it does.

| Claim | Verified against | Note |
|---|---|---|
| `--stress-count` exists | nextest 0.9.103+ | Older versions need the shell loop |
| Stress-run exit code is unreliable; parse `Summary` | nextest 0.9.146 | Measured: a run with 6 failures exited 0 in 5 of 6 runs |
| `test()` matches the module path, not the binary name | nextest 0.9.146 | `test(=bare_name)` silently matches nothing |
| `show-config` has only `version` and `test-groups` | nextest 0.9.146 | There is no profile dump |
| `leak-timeout` default | **contradictory upstream** | Config reference says 200ms, leaky-tests page says 100ms — set it explicitly |
| SQLite result codes and meanings | sqlite.org/rescode.html (page dated 2026-02-18) | `776` = `SQLITE_READONLY_ROLLBACK`; low 8 bits are the primary code |
| `rusqlite` splits code from extended code | libsqlite3-sys `error.rs`, `Error::new` | `result_code & 0xff` becomes `code`, the whole value becomes `extended_code` |
| Extended result codes are off per connection by default | sqlite.org/c3ref/extended_result_codes.html; rusqlite `OpenFlags` docs | Enable with `sqlite3_extended_result_codes()` or `SQLITE_OPEN_EXRESCODE` (3.37.0+); **not** in rusqlite's default flags |
| `thread::sleep` is unsafe in async | `std::thread::sleep` docs | "blocking, and should not be used in async functions" |
| Child pipe buffer sizes | rust-lang/rust#27152 (Linux 64 KiB), #45572 and #95782 (Windows) | Finite, platform-dependent, and it has moved across Rust versions, so a hang can be platform-specific |
| `readdir` order on APFS is hash order | Apple APFS FAQ | Also case-insensitive by default and normalization-insensitive |
| libtest `--shuffle` / `--shuffle-seed` | nightly only | Needs `-Z unstable-options`; `RUST_TEST_SEED` does not exist |
| Paused time needs `test-util` and a current-thread runtime | tokio 1.x | Panics with `start_paused` on a multi-thread runtime |
| `shuttle::check_random(f, iterations)` | shuttle 0.9.x | Two arguments; randomized and **not sound** |
| TSan needs `-Zbuild-std` and the `rust-src` component | nightly | Without it, false races from uninstrumented `std` |

In the agentmemoir/skills repo, two guards keep the tool-facing parts of this table honest: `skills/code/rust-flaky-test-investigator/scripts/flake-loop.sh --self-check` and the repo-root `verify-rust-skill-commands.cjs` (pass `--live` to check commands against an installed nextest). Both run in CI.
