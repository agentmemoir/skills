# Reproduction Playbook

Verified commands for reproducing, measuring, and discriminating Rust test failures. Prefer nextest; the `cargo test` section exists because some projects still use it, and because the two runners behave differently in ways that matter for diagnosis.

## Contents

- [Decode the failure first](#decode-the-failure-first)
- [Tool discovery](#tool-discovery)
- [Selecting one test](#selecting-one-test)
- [Measuring the flake rate](#measuring-the-flake-rate)
- [The discrimination matrix](#the-discrimination-matrix)
- [Diagnosing a hang or timeout](#diagnosing-a-hang-or-timeout)
- [Making retries visible](#making-retries-visible)
- [Reproducing in CI](#reproducing-in-ci)
- [Command caches and replayed verdicts](#command-caches-and-replayed-verdicts)
- [Load, leak, and profile signals](#load-leak-and-profile-signals)
- [Model checking](#model-checking)
- [cargo test equivalents](#cargo-test-equivalents)
- [Reading nextest output](#reading-nextest-output)

---

## Decode the failure first

Before any hypothesis, resolve every code, errno, status, signal, and asserted value in the failing output against that library's own documentation. `references/error-triage.md` has the procedure, the code tables, and a worked example where one extended result code ended the investigation. Cheap, and it is the step most often skipped.

---

## Tool discovery

```bash
cargo nextest --version          # needs 0.9.103+ for --stress-count
cargo nextest show-config test-groups   # effective test-group membership
cargo nextest run --help          # authoritative list of run flags
rustup toolchain list             # is nightly available for --shuffle and sanitizers?
```

`show-config` has only two subcommands, `version` and `test-groups`. There is no profile dump, so read profile values (`retries`, `slow-timeout`, `leak-timeout`, per-test overrides) from `.config/nextest.toml` directly, and use `cargo nextest run --help` to confirm which flags the installed version actually supports.

Read the project's `.config/nextest.toml` for `retries`, `slow-timeout`, `leak-timeout`, `[test-groups]`, and any quarantine overrides. A test that only "passes" because the profile retries it is already a flake, whether or not anyone noticed.

---

## Selecting one test

nextest uses a filterset DSL (`-E`), not substring matching. The matching rules matter, and getting them wrong produces a silent "0 tests run" that looks like a pass.

**How `test()` matches.** It matches against the Rust test path — `module::test_name` — and **not** the binary name. So for a test in `my-crate` at `tests::thing::works`, the match target is `tests::thing::works`, not `my-crate tests::thing::works`.

| Form | Meaning |
|---|---|
| `test(works)` | substring — works with a bare or partial name. **Default choice.** |
| `test(=tests::thing::works)` | exact — needs the **full module path** |
| `test(/^tests::thing::works$/)` | anchored regex |
| `test(#*thing::works)` | glob |

```bash
# substring: the safe default
cargo nextest run -E 'test(my_test_name)'

# exact: must include the module path
cargo nextest run -E 'test(=my_module::my_test_name)'

# scoped to a module, package, or binary
cargo nextest run -E 'test(/^my_module::/)'
cargo nextest run -p my-crate
cargo nextest run --test my_test_binary

# combine predicates
cargo nextest run -E 'test(/^a::/) + test(/^b::/)'
```

**The trap.** `test(my_test_name)` with a bare name matches **nothing** and nextest exits with advisory code 4 after printing `0 tests run`. Under a stress loop that reads as a clean result. Find the real name first:

```bash
cargo nextest list | grep my_test
```

Use the substring form for anything you intend to report, then confirm the resolved test list before trusting the number. `scripts/flake-loop.sh` does this preflight for you and aborts on a zero match.

**Exit code 4 means nothing matched.** It is advisory, not a failure, which is exactly why it is easy to misread. Check it whenever a run reports zero tests.

---

## Measuring the flake rate

**Preferred: nextest stress tests.** Runs the selection N times and reports a per-iteration summary.

```bash
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
```

Output ends with a summary line like:

```
     Summary [   4.201s] 50/50 stress run iterations: 47 passed
```

47/50 is a 6% flake rate. Record the exact command, the iteration count, and the failure count.

**`--no-fail-fast` is not optional here.** The default profile ships `fail-fast = true`, and a stress run inherits it: the loop **stops at the first failure**. You then get a truncated sample that looks like a rate but is not one — a run reporting `3/10 stress run iterations: 2 passed, 1 failed` is not a 33% flake rate, it is a run that aborted. The real rate is higher. Always pass `--no-fail-fast` when measuring.

**Do not trust the exit code in stress mode.** Measured on nextest 0.9.146: a stress run whose summary read `4 passed, 6 failed` exited `0` in five runs out of six and `100` in one. The exit code does not reliably reflect per-iteration failures, so a CI step or script that branches on `$?` will report a clean run for a test that failed half its iterations. **Parse the `Summary` line for the rate, never `$?`.** `scripts/flake-loop.sh` does this and prints the raw nextest exit code alongside the parsed rate so the discrepancy stays visible.

Two more details that affect the number:

- `try` vs `pass` in the iteration lines. A test that shows `TRY 2 PASS` passed on a retry, which is a flake, not a pass. Use `--retries 0` to measure the raw first-attempt rate.
- With JUnit output enabled, each iteration becomes its own `<testsuite>` annotated `@stress-N`, so you can diff an iteration that failed against one that passed.

By duration instead of count, for a bounded wall-clock budget:

```bash
cargo nextest run -E 'test(my_test_name)' --stress-duration 10m --no-fail-fast
```

With JUnit output enabled, each iteration becomes its own `<testsuite>` annotated `@stress-N`, so you can diff an iteration that failed against one that passed.

**Fallback: the bundled script.** When nextest is unavailable, or the project uses `cargo test`:

```bash
scripts/flake-loop.sh -t my_test_name -n 50
scripts/flake-loop.sh -t my_test_name -n 50 --runner cargo
scripts/flake-loop.sh -t my_test_name -n 50 --runner cargo --exact
```

It records each failing run's output separately and prints a rate. Run `scripts/flake-loop.sh --help` for all options.

**Escalation rule.** If 50 iterations pass cleanly, the rate is below about **6%** at 95% confidence — zero failures in 50 trials bounds the rate at `1 - 0.05^(1/50)` ≈ 5.8%, and a 2% bound would need roughly 150 iterations. Do not just raise the count blindly. Either add load (the stress axis below) to push the rate up past the noise floor, or conclude the cause is environmental and will not reproduce on this host — and say which, because "could not reproduce locally" is a legitimate and common finding. When the failures were real elsewhere, that finding is filed as `reproduction.status = not_reproduced` with `cause_basis = inferred`: the mechanism comes from the decoded error and from reading, the rate is left unmeasured, and the report says both.

---

## The discrimination matrix

Run in this order. Stop when one axis isolates the failure.

### Axis 1 — Isolation

Does it fail by itself, or only with the suite?

```bash
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast  # alone
cargo nextest run --stress-count 3 --no-fail-fast                        # whole suite
```

Alone-failing means the nondeterminism is inside the test. Suite-only means something interferes. Every later axis is interpreted differently depending on which side you land on, so do not skip this one.

### Axis 2 — Serialization

```bash
cargo nextest run --stress-count 5 --no-fail-fast -j 1
```

Disappearing under `-j 1` implicates shared resources, contention, or scheduling starvation. It does not tell you which resource — that is what Axis 8 is for.

### Axis 3 — Ordering

Run the suspected predecessor immediately before the victim, repeatedly, then reverse the order.

```bash
cargo nextest run -E 'test(suspected_predecessor) + test(victim)' --stress-count 20 --no-fail-fast
cargo nextest run -E 'test(victim) + test(suspected_predecessor)' --stress-count 20 --no-fail-fast
```

If the failure follows the predecessor regardless of order, you have order dependence. If it only appears in one direction, the predecessor is leaving state the victim depends on.

Under `cargo test` on nightly you can sweep all orderings at once:

```bash
cargo +nightly test -- -Z unstable-options --test-threads 1 --shuffle
```

`--shuffle` prints a seed. Replay a specific order with `--shuffle-seed <N>`. Note that `--shuffle` does not change parallelism — combine with `--test-threads 1` for a random sequential order, which is the useful combination for order-dependence hunting.

### Axis 4 — Load

Starves the scheduler and the disk, which is how you confirm a timing hypothesis. Three preconditions first, because this axis costs the user more than any other:

1. **Ask before you saturate a host you do not own**, and say how long it will take. If the machine is a laptop someone is working on, do not run `nproc` busy loops on it without permission.
2. **Prefer shape over cost.** A smaller run of the failing workload's *shape* is usually the honest experiment: if the failure needs many tests spawning children at once, run fewer iterations with that concurrency rather than the same tests on a busier machine. CPU pressure was often never the variable.
3. **Check for a serialising gate.** A test-runner gate, Makefile lock, or CI wrapper that serialises invocations turns "run it eight times concurrently" into "run it once". The zero failures that follow read as a pass, so verify the runs were actually concurrent before trusting the result.

```bash
# Linux
stress-ng --cpu "$(nproc)" --io 4 --timeout 120s &
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
kill %1

# macOS fallback: busy loops instead
for i in 1 2 3 4; do (while :; do :; done) & done
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
kill %1 %2 %3 %4
```

A failure rate that climbs under load confirms wall-clock dependence or scheduling starvation. This is also the right way to surface a flake rarer than 6%: add load until the failure appears reliably, then investigate against that condition. If the rate does not move, say so and record the axis — a load axis that produced no signal is information, and reporting it as `skipped` or as a confirmation is not.

### Axis 5 — Build profile

```bash
cargo nextest run --release -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
```

Failing only in debug implicates timing sensitivity exposed by slower unoptimized code. Also a common source of "passes on my machine" when the developer's default differs from CI.

### Axis 6 — Environment

Compare the constrained environment against yours. In CI, cap the runner to match, or run the CI image locally:

```bash
docker run --rm --cpus 1 --memory 512m -v "$PWD":/w -w /w <ci-image> \
  cargo nextest run -E 'test(my_test_name)' --stress-count 20 --no-fail-fast
```

Record `nproc`, available memory, filesystem type of the target dir, and outbound network availability. These four explain most CI-only flakes.

### Axis 7 — Cleanup leaks

```toml
# .config/nextest.toml
[profile.default]
leak-timeout = { period = "500ms", result = "fail" }
```

A test that leaves a child process holding stdout or stderr open past the timeout is marked `LEAK-FAIL`. A passing test marked `LEAK` still leaked. Confirm by listing processes after the run.

Detection is limited to children that inherit stdout or stderr; a subprocess with `Stdio::null()` is not detected today.

### Axis 8 — Resources

Change one thing: bind an ephemeral port instead of the hardcoded one, or use a fresh temp dir per iteration. If the failures vanish, it is collision.

```bash
# baseline
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast

# after the change
cargo nextest run -E 'test(my_test_name)' --stress-count 50 --no-fail-fast
```

To localize without editing the test, run pairs of tests that look like they share a port or path:

```bash
cargo nextest run -E 'test(/^module_a::/) + test(/^module_b::/)' --stress-count 20 --no-fail-fast
```

---

## Making retries visible

By default, a test that passes on retry is treated as successful and the run exits 0. That is exactly the wrong behaviour for an investigation.

```bash
cargo nextest run --retries 3 --flaky-result fail -E 'test(my_test_name)'
```

Under a profile with retries configured, `--retries` and `NEXTEST_RETRIES` both override and disable per-test retry overrides for the run — useful for a uniform investigation, but be aware you are no longer seeing the project's configured policy.

For a suite-wide sweep, enable JUnit output and collect every `flakyFailure`:

```toml
[profile.ci.junit]
path = "junit.xml"
```

The path is relative to `store.dir`, which defaults to `target/nextest`. Note that this JUnit path is unrelated to `cargo nextest archive`, which is for build artifacts, not reports.

---

## Reproducing in CI

If it only fails in CI, reproduce the conditions rather than the machine. A bounded loop in the workflow captures the failing run's logs:

```yaml
- name: Debug flake
  run: |
    for i in $(seq 1 50); do
      if ! cargo nextest run -E 'test(my_test_name)' --no-fail-fast; then
        echo "FAILED on iteration $i"
        exit 1
      fi
      echo "iteration $i passed"
    done
```

Add `RUST_LOG=debug` and archive the target directory on failure so the failing iteration's artifacts survive. `--no-fail-fast` matters: with fail-fast on, the run stops at the first failure and you lose the rest of the signal.

---

## Diagnosing a hang or timeout

A `TIMEOUT` status is not a diagnosis. It says the test did not finish, and that splits three ways — took too long, never finished, or was killed. Two of the three are settled by one `rg`, so do that before spending an iteration on load.

```bash
# 1. blocking calls inside async tasks, and waits that ignore the child's output
rg -n 'thread::sleep|block_on\(|std::fs::|std::net::|Command::new|\.status\(\)|\.wait\(\)' -g '*.rs'

# 2. the child's own state, if it is alive (Linux/macOS)
ps -o pid,ppid,stat,wchan,etime -p <child-pid>
strace -f -e trace=write,read -p <child-pid>      # Linux: parked in write() = undrained pipe
```

| What you see | Family | One-line fix direction |
|---|---|---|
| Test ran long, then hit `slow-timeout` | 1, 2, 9, 11 | replace the wall-clock wait with a signal |
| Task with a long poll gap, nothing else progressing | 16 | async API, or `spawn_blocking` |
| Child alive, blocked in `write` | 17 | `wait_with_output()`, or `Stdio::null()` |
| Test stops at a fixed duration only when output is large | 17 | same |
| Killed with no slow-test record | runner, `terminate-after`, OOM killer | check the runner's own status line and the host's OOM log |

Bound it while you work: `slow-timeout = { period = "30s", on-timeout = "fail" }` locally turns an unbounded hang into a failure you can iterate on, and `terminate-after` stops the leftover process so it cannot perturb the next iteration.

## Command caches and replayed verdicts

Every command above assumes it executes. In any repo that wraps test commands in a content-addressed cache, a Makefile target, a `cargo` alias, or a CI action with a cache key, an identical command on an unchanged tree can replay a stored verdict instead of running. For a flake investigation this is the most costly possible failure mode, because a replayed **pass** removes the failure you are trying to measure, and a byte-identical summary line is the only evidence that anything happened.

Detect it before trusting the first number:

```bash
rg -n 'cache|force|restage|CACHE|mtime' Makefile justfile .just/ .config/ .github/workflows/ 2>/dev/null
cargo nextest run -E 'test(my_test_name)' --stress-count 2 --no-fail-fast   # twice: does the second run say it ran?
```

Tell-tales: two runs with identical wall-clock times and identical iteration counts, a `cache hit` / `CACHED` marker, a `1 passed` result on a repo where the first build of that test takes minutes, or a run whose summary is character-for-character the previous one.

Make each run distinct, in order of preference:

1. **Use the runner's bypass flag** if the wrapper has one (`--force`, `--no-cache`, `FORCE=1`, `nocache=1`).
2. **Vary the command**, not just its results: change the `--stress-count`, add a distinct `RUST_LOG=debug` filter, or pass a per-iteration `--test-threads` value, so each invocation has a different cache key.
3. **Perturb the tree** between iterations with a harmless edit — a comment, a `#[allow]`, a touched fixture — and revert it after. Confirm the repo is clean afterwards.

Two consequences for the report. A rate measured entirely from passes deserves a second look at whether the runs happened at all; and when you could not make the runs distinct, say so — set `flake_rate.runs_distinct` to `false` and list it under `not_verified` rather than quoting a clean run as evidence.

---

## Load, leak, and profile signals

**Per-test logs without parallel noise.** `#[tracing_test::traced_test]` captures only the annotated test's output.

**Task-level introspection.** `tokio-console` shows which tasks are pending, and which are busy-polling without making progress — the signature of a starved polling loop. Add `console-subscriber` and set `TOKIO_CONSOLE=1` in a temporary test binary.

**Race detection in unsafe code.** ThreadSanitizer, nightly only, and only useful with an instrumented standard library — without `-Zbuild-std` it reports false races from `std` internals rather than from the code under test. Use for periodic auditing, not routine runs:

```bash
rustup component add rust-src        # -Zbuild-std requires the std sources
RUSTFLAGS="-Zsanitizer=thread" \
  cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu -- --test-threads=1
```

Run it single-threaded. TSan reports on multi-threaded test execution often indicate bugs in the tests themselves rather than in the code under test.

**Miri** for undefined behaviour that the borrow checker cannot see. Slow; scope it to one test.

---

## Model checking

For concurrent primitives — locks, channels, state machines — interleaving exploration finds races that random scheduling will miss. These require rewriting the test against the tool's primitives, so they are for the component under test, not for an integration suite.

The two tools are complements, not equivalents. **loom is exhaustive and sound**: a passing `loom::model` is real evidence, but it only handles small state spaces. **shuttle is randomized and explicitly not sound**: a passing shuttle test does *not* prove correctness, but it scales far larger and finds most non-adversarial concurrency bugs.

```rust
// loom — exhaustive over all interleavings; sound
loom::model(|| { /* exercise the primitive */ });

// shuttle — randomized scheduling; NOT sound, needs an iteration count
shuttle::check_random(
    || { /* exercise the code */ },
    100,
);

// shuttle also offers bounded-preemption (PCT) and exhaustive (DFS) schedulers
shuttle::check_pct(|| { /* ... */ }, 1_000, 2);
```

Treat a shuttle failure as a genuine bug worth reproducing, and a shuttle pass as weak evidence rather than proof.

---

## cargo test equivalents

For projects that do not use nextest. Note that `cargo test` runs all tests as threads in **one process**, so global state races and cross-test interference are live concerns that nextest removes. A suite can be green under nextest and broken under `cargo test`; if the project supports both runners, check both.

```bash
# single test
cargo test my_test_name -- --exact --nocapture

# serial
RUST_TEST_THREADS=1 cargo test
cargo test -- --test-threads=1

# repeat (no built-in stress flag; use the bundled script or a loop)
scripts/flake-loop.sh -t my_test_name -n 50 --runner cargo
```

`--nocapture` is essential for diagnosis; libtest otherwise swallows output from passing tests, which is often where the answer is. Environment variables `RUST_TEST_THREADS`, `RUST_TEST_NOCAPTURE`, `RUST_TEST_SHUFFLE`, and `RUST_TEST_SHUFFLE_SEED` exist but are deprecated in favour of the CLI flags, and the two shuffle variables are nightly-only.

---

## Reading nextest output

| Signal | Meaning |
|---|---|
| `PASS ... [2/3]` | passed on attempt 2 of 3 — a flake, not a pass |
| `FLAKY` in the final summary | passed on a retry; the run still succeeded |
| `SLOW` | exceeded `slow-timeout`; a slow test is not a flaky test, but often a related bug |
| `LEAK` | subprocess outlived the test and held stdout or stderr open |
| `LEAK-FAIL` | same, configured as a failure |
| `TIMEOUT` | exceeded the slow-timeout termination policy |
| `SIGABRT` / signal exit | a panic that aborted, or a test killed by the runner |
| exit code 4 | advisory: no tests ran — usually a bad filter, check your selector |
| exit code 5 | advisory: rerun has outstanding previously-failing tests |

`--stress-count` and the "Stress test iteration N/M" lines give you the per-iteration breakdown needed to compute a rate.

The codes inside a failure line are data too: an extended error code, an `os error N`, or a `SIGxxx` often names the mechanism outright. Resolve them with `references/error-triage.md` before you build a theory around the shape of the failure.

A `TIMEOUT` or a bare `SIGKILL` carries no code, which is exactly why the hang section above starts from `rg` and process state instead of from the output.
