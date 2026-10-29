# Worked Example — FLAKY-001

A complete filled report, shown against a real-shaped case. Read this alongside `bug-report-template.md` to see what "fully filled" looks like. The machine-readable twin of this finding is `flaky-finding.example.json`.

This is the example the adversarial review asked for: the report shape is easy to state and easy to under-fill. Note in particular that the **Not verified** section is the longest part, and that the confidence is `confirmed` only because a two-direction experiment was run.

---

# [FLAKY-001] object_put_converges_on_remote_target fails ~8% of runs with EADDRINUSE: fake target binds a hardcoded port

- **Severity:** high
- **Confidence:** confirmed
- **Cause basis:** measured — the two-direction experiment below ran locally
- **Flake rate:** 4 failures in 50 iterations (8%)
- **Layer:** e2e

## Summary

The replication convergence test fails roughly one run in twelve with `Address already in use`, always while binding its fake remote target and never at the convergence assertion. It passes 50 out of 50 when run alone and fails when a sibling test in the same module runs concurrently. The failure signature points at replication; the cause is a port collision in the test fixture.

## Test under investigation

- **Identifier (nextest form):** `e2e_test replication_target_matrix_test::object_put_converges_on_remote_target`
- **File:** `crates/e2e_test/src/replication_target_matrix_test.rs`
- **Runner and profile:** `cargo nextest run --profile e2e-repl-nightly`
- **Gating:** nightly lane, not a PR gate. Report-only for PRs.

## Reproduction

```
cargo nextest run -E 'test(replication_target_matrix_test::object_put_converges_on_remote_target)' --stress-count 50 --no-fail-fast
```

Environment: Linux, 4 cores, debug build, no added load, not containerized. nextest 0.9.146.

Read the rate from the `Summary` line, not the exit code — in stress mode nextest's exit code does not reliably reflect per-iteration failures.

## Measured behaviour

| Condition | Iterations | Failures | Rate |
|---|---|---|---|
| Baseline, alone | 50 | 0 | 0% |
| Paired with `delete_marker_replication` | 20 | 7 | 35% |
| Paired, after fix applied | 20 | 0 | 0% |
| Paired, after fix reverted | 20 | 6 | 30% |
| Full suite, `-j 1` | 5 runs | 0 | 0% |

Every row is a command that was run. The last two rows are the two directions of the confirming experiment.

## Failure signature

```
thread 'object_put_converges_on_remote_target' panicked at
crates/e2e_test/src/replication_target_matrix_test.rs:212:14:
  called `Result::unwrap()` on an `Err` value: Address already in use (os error 98)
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

The failure is always at mock-target bind, never at the convergence assertion. That detail is what redirected the investigation away from replication logic.

## Error decode

| Value | Kind | Documented meaning | Source | Emitted by |
|---|---|---|---|---|
| `os error 98` | `errno` | `EADDRINUSE` — the address is already in use. 98 on Linux, 48 on macOS | `python3 -c 'import os; print(os.strerror(98))'` on the runner; `asm-generic/errno-base.h` | `replication_target_matrix_test.rs:212`, the fixture's `TcpListener::bind` unwrap |
| `...rs:212:14` | `panic_message` | the unwrap is in the fixture's bind, so the failure is in setup, not in the replication logic | `RUST_BACKTRACE=1` run of a failing iteration | same line; the backtrace has no frames below it |

The decoded value says a bind collided and nothing more. Which test collided with which came later, from the matrix.

## Discrimination results

- **Isolation:** 0 failures in 50 runs alone. The test is internally deterministic, which eliminates async scheduling, wall-clock timing, orphan background work, and cancellation safety as causes.
- **Serialization:** full suite passed 5 consecutive iterations under `-j 1`. The failure requires concurrency, narrowing to resource contention or shared global state.
- **Ordering:** running the suspected sibling immediately before the victim produced 7 failures in 20, all in the victim. The failure follows a specific partner, so this is a concurrent collision rather than state left behind by a prior run.
- **Resources:** binding an ephemeral port removed the failure; restoring the hardcoded port brought it back. This is the confirming experiment, below.
- **Load:** not run. The failure rate at rest was already 8%, well above the noise floor, so load was unnecessary. Recorded as unverified rather than assumed.

## Root cause

`start_fake_target` binds `127.0.0.1:9411` instead of an ephemeral port. Two tests in `replication_target_matrix_test` call it, and under process-per-test execution their lifetimes overlap, so whichever loses the bind panics at setup. The convergence logic under test is never reached on a failing run.

**In test code or production code?** Test code. The production replication client correctly handles an unavailable endpoint; nothing is wrong with it.

## Confirming experiment

- **Hypothesis:** if the hardcoded port is the cause, binding an ephemeral port removes the failure and restoring the hardcoded port brings it back.
- **Experiment:** patched the fixture to bind `127.0.0.1:0` and pass `listener.local_addr()` to the client; ran the failing pair for 20 iterations; reverted the patch; ran the same pair for 20 iterations.
- **Result:** patched 0/20, reverted 6/20 with EADDRINUSE at the same line. Both directions observed, so the cause is confirmed rather than merely consistent.

## Policy context

- No existing quarantine entry for this test.
- Violates a written project rule: `docs/testing/README.md` requires per-test random ports and isolated temp directories.
- The outbound target matrix expectation table pins known-red cells to an open issue. This failure is not one of those cells, so no expectation-table change is needed.
- The fix must not add the test to a `max-threads = 1` group, because the project rule is isolation over serialization.

## Proposed fix

```
--- a/crates/e2e_test/src/replication_target_matrix_test.rs
+++ b/crates/e2e_test/src/replication_target_matrix_test.rs
@@ -198,9 +198,11 @@ async fn start_fake_target() -> FakeTarget {
-    let listener = TcpListener::bind("127.0.0.1:9411").await.unwrap();
-    let addr = SocketAddr::from(([127, 0, 0, 1], 9411));
+    // Bind 0 so the OS assigns a free port. A hardcoded port collides with
+    // any sibling test that starts a fake target concurrently.
+    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
+    let addr = listener.local_addr().unwrap();
     FakeTarget { listener, addr }
 }
```

**Explicitly rejected alternatives:**

- **Add `retries = 2` for this test.** The project flake policy requires a linked open issue and a fix-or-delete deadline, and this is a two-line fix with a confirmed cause. A retry would hide a fixture bug that every future test in the module inherits.
- **Add a `[test-groups]` entry with `max-threads = 1`.** Slower, and it leaves the collision in place for anyone who adds a third sibling later.
- **Widen the mock target startup timeout.** The failure is a bind error, not a timeout, so no timeout change affects it.

## Blast radius

`delete_marker_replication` in the same module binds the same port and is the observed collision partner. Any future test calling `start_fake_target` inherits the same collision, so the fix removes a recurring class rather than one instance.

## Not verified

- The fix was not applied, so the 0% rate is predicted from the two-direction experiment rather than measured on a full 50-iteration run of the patched module.
- Not tested on macOS or ARM; the lane is Linux-only.
- Did not check whether other e2e modules hardcode ports, so the blast radius outside this module is unquantified.
- Did not run the load axis, so it is unconfirmed whether the rate also rises under CPU pressure.
- Did not verify the quarantine-policy claim against `.config/nextest.toml`; it comes from `docs/testing/README.md`.

## Suggested next step

Apply the two-line port fix, run the full module for 50 iterations to confirm 0%, then open an issue referencing FLAKY-001 and attach the stress output as evidence.
