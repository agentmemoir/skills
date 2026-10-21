# cargo-nextest Configuration

`cargo nextest` runs each test in its own process. That single design choice removes an entire class of Rust test bugs — global state, environment mutation, and cross-test contamination — and it is why it is the right default for any suite that can adopt it.

## Baseline config

```toml
# .config/nextest.toml
[profile.default]
retries = 0                              # never hide a flake locally
fail-fast = true
slow-timeout = { period = "60s", on-timeout = "fail" }
leak-timeout = "500ms"                   # flag subprocesses that outlive the test
test-threads = "num-cpus"

[profile.ci]
inherits = "default"
fail-fast = false                        # let the whole run report
retries = 0                              # retries are opt-in per test, never global
```

The file lives at `.config/nextest.toml` from the workspace root. It is checked into version control, so it is shared by everyone and by CI.

Confirm what the installed version supports and see effective test-group membership:

```bash
cargo nextest --version
cargo nextest show-config test-groups
cargo nextest run --help
```

`show-config` has only `version` and `test-groups` subcommands — there is no profile dump, so read profile values from the TOML. Use `--help` to confirm a flag exists before relying on it; the flag set grows across releases. Verified against 0.9.146.

## Test groups: the only real serialization

`serial_test`'s `#[serial]` takes an in-process mutex. nextest runs each test in a separate OS process, so that mutex cannot serialize anything — `#[serial]` is a **no-op under nextest**. It only affects a plain `cargo test` fallback.

There is one exception: `serial_test`'s `file_serial` serializes with file locks rather than an in-process mutex, so it *does* work across nextest processes. A test group is still the better default, because it does not require annotating every participant and cannot rot when someone adds an unmarked test later.

To actually serialize under nextest, use a test group:

```toml
[test-groups]
serial-integration = { max-threads = 1 }
resource-limited  = { max-threads = 4 }

[[profile.ci.overrides]]
filter = 'test(/^needs_fixed_port::/)'
test-group = 'serial-integration'

[[profile.ci.overrides]]
filter = 'package(heavy-io-tests)'
test-group = 'resource-limited'
```

A group is a logical semaphore: at most `max-threads` tests from that group run concurrently, while everything else proceeds at full parallelism. This is much better than `-j 1` for the whole suite.

Tests report their own group at runtime via the `NEXTEST_TEST_GROUP` environment variable, which is useful for diagnostics.

**Prefer isolation over serialization.** A group makes the suite slower and leaves the underlying coupling in place. Before adding one, check whether the test could instead bind port `0` or use its own `tempdir`. Add the group when the resource genuinely cannot be made per-test — a fixed device node, a fixed kernel setting, a real disk mount.

When you do add one, comment why. A group with no explanation becomes permanent cargo cult.

## Retries and quarantine

A test that passes on retry is flaky. By default nextest treats that as success and exits 0, which is exactly wrong for a gate.

```bash
# see retries as failures
cargo nextest run --retries 3 --flaky-result fail
```

For a suite, grant retries per test and never globally:

```toml
[profile.ci]
retries = 0

# Known-flaky test, contained. Link exactly one open issue.
[[profile.ci.overrides]]
filter = 'test(/^known_flaky::replication_convergence/)'
retries = 2
```

Rules that keep quarantine from becoming permanent:

- Every retry override names a responsible owner and links one open issue in a comment.
- Every quarantine has a deadline. A test is either fixed or deleted by then.
- An override whose issue is closed is a policy violation, not a technical state.
- `retries` in config supports backoff, which matters for genuinely transient external failures:

```toml
retries = { backoff = "exponential", count = 3, delay = "1s", max-delay = "10s", jitter = true }
```

Note that `--retries` on the command line and the `NEXTEST_RETRIES` environment variable both **override and disable** per-test retry settings for that run. Convenient for a uniform investigation, but you are no longer seeing the project's configured policy.

## Timeouts

```toml
[profile.default]
slow-timeout = { period = "60s", on-timeout = "fail" }
```

- `period` marks a test slow and, with `on-timeout = "fail"`, fails it.
- `terminate-after = N` tolerates N slow periods before killing the test. `terminate-after = 2` with `period = "15s"` means a test has 30 seconds before it is killed.
- `grace-period` controls how long a terminated test gets to clean up.
- `global-timeout` bounds the entire run.
- `leak-timeout` catches subprocesses that outlive the test; `{ period = "500ms", result = "fail" }` makes it a hard failure.

Timeouts are a safety net that converts a hang into a failure. They are not a synchronization mechanism. If a test only passes because a timeout was raised, the race is still there.

## JUnit output and flaky detection

```toml
[profile.ci.junit]
path = "junit.xml"
```

The path is relative to `store.dir`, which defaults to `target/nextest`. Unrelated to `cargo nextest archive`, which is for build artifacts.

What to look for:

- A test that **passed on retry** is tagged with a `flakyFailure` element. That tag, not a green check, is how a live flake stays visible.
- A test that **failed on every retry** gets `failure` and `flakyFailure`.
- `store-success-output = true` keeps output for passing tests too — useful when you suspect a passing test is passing for the wrong reason.
- `junit.flaky-fail-status = "success"` reports flaky-fail tests as passes in the XML. It changes the report only; the runner still fails them.

For a suite-wide sweep, enable JUnit, run with retries and `--flaky-result fail`, then collect every `flakyFailure`. That gives you a candidate list. It does not give you flake rates — for those, stress each candidate individually.

## Stress runs

```bash
cargo nextest run -E 'test(my_test)' --stress-count 200 --no-fail-fast
```

Needs nextest 0.9.103 or newer. `--stress-duration 30m` bounds it by wall clock instead.

**`--no-fail-fast` is mandatory when measuring a rate.** The default profile has `fail-fast = true` and a stress run inherits it, so the loop stops at the first failure. You get a truncated sample dressed up as a result: `3/10 stress run iterations: 2 passed, 1 failed` is an aborted run, not a 33% flake. The real rate is higher.

Per-iteration output lets you see which iterations failed and compare them. With JUnit enabled, each iteration becomes its own `<testsuite>` annotated `@stress-N`.

## Profile design

A workable layout for a growing project:

| Profile | Purpose |
|---|---|
| `default` | local runs, never retries |
| `ci` | PR gate, `fail-fast = false`, per-test quarantine only |
| `e2e-smoke` | small PR subset of the slow suite |
| `e2e-full` | merge queue and main |
| `nightly-*` | slow, cross-process, or platform-specific lanes |

Lanes are selected by filterset in per-test overrides. If the project pins lane membership with a digest of the selected test list, know that a rename or a new test can change membership and trip that check.

Keeping slow suites out of the PR gate is the highest-leverage CI change available: most flaky-test reports come from heavy e2e lanes that do not need to block a pull request.

## CI wiring

```yaml
- name: Test
  run: cargo nextest run --profile ci --workspace
- name: Upload results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: nextest-report
    path: target/nextest/ci/junit.xml
```

Use `if: always()` so the report uploads even when tests fail — that JUnit file is the evidence for every flake report that follows.

For CI-only flakes, add a bounded debug loop that runs the test repeatedly under CI's actual resource limits:

```yaml
- name: Debug flake
  run: |
    for i in $(seq 1 50); do
      if ! cargo nextest run -E 'test(my_test)' --no-fail-fast; then
        echo "FAILED on iteration $i"
        exit 1
      fi
    done
```

Reproduce the conditions, not just the command. CPU limits, memory, filesystem, and network on the runner are usually the actual variable.

## Name-based gates

Some projects select tests by name substring and enforce a floor on how many must match, so a rename cannot silently thin a safety net. Reserved substrings typically mark cross-pool data movement, rebalance, decommission, source cleanup, and delete-marker handling.

If you rename a test, check whether its name is in that list. Changing a floor and a test name belong in the same change, and the floor change needs an explanation.

## Reading the output

| Signal | Meaning |
|---|---|
| `TRY 2 PASS` | passed on a retry — a flake, not a pass |
| `FLAKY` in the summary | passed on retry; run still succeeded |
| `SLOW` | exceeded `slow-timeout` |
| `LEAK` | subprocess outlived the test holding stdout/stderr |
| `LEAK-FAIL` | same, configured as a failure |
| `TIMEOUT` | exceeded the slow-timeout termination policy |
| `0 tests run` | the filter matched nothing — check the selector |
| exit code 4 | advisory: no tests ran |
| exit code 5 | advisory: rerun has outstanding previously-failing tests |

## Selecting tests

`test()` matches the Rust test path — `module::test_name` — **not** the binary name.

| Form | Meaning |
|---|---|
| `test(works)` | substring; the safe default |
| `test(=tests::thing::works)` | exact; needs the full module path |
| `test(/^tests::thing::/)` | anchored regex |

`test(=bare_name)` matches **nothing** and reports `0 tests run`, which reads as a pass. Find the real name with `cargo nextest list`, or just use the substring form.
