---
name: rust-test-best-practices
description: >-
  Guidelines for writing Rust tests that stay reliable in CI. Use when adding,
  reviewing, or refactoring tests in a Rust project, or when I ask
  whether a test is well written. Covers test layer choice, async tests with
  Tokio paused time, isolation of ports and temp dirs, resource cleanup across
  processes, reading an embedded database a child process writes, determinism
  against clocks, hash order and floating point, blocking the async executor,
  filesystem semantics across platforms, timeouts, property-based tests, and
  cargo-nextest configuration. Every rule states the failure it prevents and
  shows the pattern to use instead. Use it before writing a test, not after one
  has already gone flaky.
category: code
title: Rust test best practices
summary: >-
  Guidelines for writing Rust tests that stay reliable in CI. Covers test layer choice, async tests
  with Tokio paused time, isolating ports and temp dirs, resource cleanup across processes,
  determinism against clocks, hash order and floating point, blocking the async executor, filesystem
  semantics across platforms, timeouts, property-based tests, and cargo-nextest
  configuration.
say: >-
  "Write this Rust test following rust-test-best-practices" or "Review my Rust tests against the
  guidelines."
---

# Rust Test Best Practices

How to write Rust tests that pass every time, on your machine and on a loaded CI runner. Each rule names the flake it prevents, because a rule without a consequence gets ignored the first time it is inconvenient.

## When to use

Use this when writing a new Rust test, reviewing someone else's, or deciding whether a test needs to change. Use `rust-flaky-test-investigator` instead when a test is *already* failing intermittently and you need a diagnosis.

## The default that prevents most problems

Write every test so it can run **in any order, in parallel, on any machine, at any time of day**, and pass. When that is genuinely impossible, say so in a comment and contain the test explicitly — do not leave the coupling implicit.

Six rules carry most of the weight:

1. **Own your resources.** Every port, path, file, and process belongs to one test and is released when it ends.
2. **Never wait on the wall clock.** Synchronize on a signal, not a duration.
3. **Await everything you spawn.** A dropped `JoinHandle` is a latent defect.
4. **Inject the clock and the RNG.** Never read them from the system.
5. **Assert on sorted, deterministic data.** Never on hash iteration order.
6. **Never be the thing that corrupts what you observe.** A test that kills, drops, or interrupts the writer of the state it asserts on is reading a crash artifact — wait for a clean exit, or read a copy taken after the writer finished.

## Choosing a test layer

Pick the lowest layer that can prove the change. Add a higher layer only when the behaviour is genuinely not observable below it.

| Layer | Proves | Cost | Use for |
|---|---|---|---|
| Unit | a function's logic in isolation | milliseconds | pure logic, edge cases, error paths |
| Crate integration | the crate's public API | seconds | cross-module behaviour, wiring |
| End-to-end | a real binary over a real protocol | minutes | protocol conformance, deployment shape |

A slow end-to-end test that could have been a unit test is not thorough, it is a tax on everyone who waits for CI. If you find yourself writing an e2e test for logic a unit test can reach, stop and write the unit test.

## Isolation

**Ports: bind `0` and read back.** A hardcoded port is a collision waiting to happen.

```rust
// BAD - collides with any parallel sibling
let listener = TcpListener::bind("127.0.0.1:9000")?;

// GOOD - the OS assigns a free port
let listener = TcpListener::bind("127.0.0.1:0")?;
let addr = listener.local_addr()?;
```

Never "randomize" a port with `rand()`. That is still nondeterministic. Let the OS assign it.

**Paths: use `tempfile`.** `tempfile::tempdir()` gives a unique directory and deletes it on drop, including on panic.

```rust
// BAD - shared across tests and across runs
let dir = PathBuf::from("/tmp/my_test_data");

// GOOD - unique per test, cleaned up automatically
let dir = tempfile::tempdir()?;
```

**Environment variables: do not mutate them.** `std::env::set_var` races with every other thread in the process, and is `unsafe` in Rust 2024 for exactly that reason. Pass configuration as parameters or through a fixture.

```rust
// BAD - process-wide, races with parallel tests
std::env::set_var("LANG", "C");

// GOOD - explicit dependency
fn parse_date(input: &str, locale: Locale) -> Result<Date, Error>;
```

**Never depend on test order.** A test that needs a predecessor to have run first is broken regardless of whether it is flaky. Each test sets up everything it needs and tears down everything it created.

**Do not rely on `#[serial]` to save you.** `cargo nextest` runs each test in its own process, so `serial_test`'s in-process `#[serial]` mutex cannot serialize anything — it is a no-op. If a test is genuinely unsafe to run alongside others, express that in `.config/nextest.toml` with a test group, and say why in a comment.

`serial_test`'s `file_serial` is the one exception: it serializes across processes with file locks, so it does work under nextest. A test group is still usually preferable, because it does not require annotating every participant and cannot silently rot when someone adds an unmarked test.

## Async tests

**Start paused and control time explicitly.** This is the single highest-value rule in async testing.

```rust
// BAD - a race with the clock. On a loaded CI runner the deadline can expire
// before the work finishes, and the test fails for no real reason.
#[tokio::test]
async fn retries_after_backoff() {
    do_thing().await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    assert_eq!(state(), Done);
}

// GOOD - no wall-clock dependency at all
#[tokio::test(start_paused = true)]
async fn retries_after_backoff() {
    do_thing().await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    assert_eq!(state(), Done);
}
```

With the clock paused, the runtime fast-forwards to the next timer the moment nothing else can make progress, so the sleep costs no real time and cannot expire early.

Three constraints on paused time, all of which will bite you:

- It requires the `test-util` feature on tokio, normally enabled under `[dev-dependencies]`.
- It requires the current-thread runtime, which is the `#[tokio::test]` default. It does not work with `flavor = "multi_thread"`.
- Prefer `sleep` over `advance`. `advance` jumps the clock without waiting for the timers it passed to be processed, so it is unreliable for forcing a timeout. Use `sleep` and let auto-advance do the work.

```toml
[dev-dependencies]
tokio = { version = "1", features = ["macros", "rt", "time", "test-util"] }
```

**Await everything you spawn.** `tokio::spawn` returns a `JoinHandle`; dropping it detaches the task. The test returns, the runtime is torn down, and the task dies mid-operation — possibly holding a lock or halfway through a write.

```rust
// BAD - the replication loop is still running when the test ends
#[tokio::test]
async fn writes_replicate() {
    tokio::spawn(replication_loop());
    put("key", "value").await;
    assert_eq!(get("key").await, Some("value"));
}

// GOOD - clean shutdown, and a spawn failure surfaces as a test failure
#[tokio::test]
async fn writes_replicate() {
    let cancel = CancellationToken::new();
    let loop_task = tokio::spawn(replication_loop(cancel.clone()));
    put("key", "value").await;
    assert_eq!(get("key").await, Some("value"));
    cancel.cancel();
    loop_task.await.expect("replication task panicked");
}
```

**Never block the executor.** A synchronous call inside an async task stops the whole runtime, and on the default current-thread runtime that means the only thread — timers, the I/O driver, and every other task stop together. `std::thread::sleep` is the classic, and `std`'s own docs say it "should not be used in async functions".

```rust
// BAD - freezes everything for 100ms, including what you are waiting on
std::thread::sleep(Duration::from_millis(100));
let data = std::fs::read_to_string(path)?;

// GOOD
tokio::time::sleep(Duration::from_millis(100)).await;
let data = tokio::fs::read_to_string(path).await?;
```

Blocking work that cannot be made async goes to `tokio::task::spawn_blocking`. Two constraints: it cannot be cancelled, and while one is alive the runtime never auto-advances paused time, so a `spawn_blocking` that never returns looks exactly like a hang. A `std::sync::Mutex` held across an `.await` is the same defect wearing a lock.

**Do not synchronize with `yield_now()`.** It returns control to the runtime without waiting for anything, so under load the task you are waiting for may never be scheduled before your own deadline.

```rust
// BAD - starvation: the other task may never get CPU time
while !flag.load(Ordering::Relaxed) {
    tokio::task::yield_now().await;
}

// GOOD - a real signal, with a deadline as a safety net
tokio::time::timeout(Duration::from_secs(5), notify.notified())
    .await
    .expect("worker did not signal within 5s");
```

**Prefer `Notify`, channels, or broadcasts over polling.** All three wake the waiter directly. If you must poll, poll a condition against a generous deadline.

**Be careful inside `select!`.** It drops every future that does not win. A future that was mid-mutation leaves inconsistent state unless it is cancellation-safe. Do not mutate shared state across an await point inside a `select!` branch; make the transition atomic and idempotent so an interrupted attempt can be retried.

**Prefer the single-threaded runtime.** It is the `#[tokio::test]` default and it schedules predictably. Specify `worker_threads` explicitly when you genuinely need multiple threads, and know that you have opted into nondeterministic ordering.

## Timeouts

Every unbounded wait is a hang waiting for a loaded CI runner.

- Set an explicit timeout on anything that waits for external work, and make it generous enough that it never fires in normal operation.
- A timeout is a safety net that turns a hang into a failure. It is not a synchronization mechanism, and lengthening one to "fix" a flake raises the threshold without removing the race.
- Under nextest, set `slow-timeout` so a hang is bounded, and use `terminate-after` if a stuck test should be killed rather than waited on.

## Resource cleanup

**A test that leaves a process running is a defect, not a nuisance.** `std::process::Child` does **not** kill its child when dropped, so a test that panics before cleanup leaks it.

```rust
// BAD - a panic before this line leaks the child, which holds its port
let mut child = Command::new("my-server").spawn()?;

// GOOD - killed and reaped even on panic
let mut child = Command::new("my-server").kill_on_drop(true).spawn()?;
```

For `std::process::Command`, wrap the child in a guard type whose `Drop` kills and waits.

**Drain or discard the child's output.** `Stdio::piped()` gives the child a pipe with a finite buffer. If the test waits for the child to exit without reading that pipe, the child blocks in `write` and never exits, so the wait never returns — the failure looks like a hang, and it only appears once the child prints more than the buffer holds.

```rust
// BAD - fine for two lines of output, a deadlock for 100k
let mut child = Command::new("reindex").stdout(Stdio::piped()).spawn()?;
child.wait()?;

// GOOD
let out = child.wait_with_output()?;                  // drains while it waits
let mut child = Command::new("reindex").stdout(Stdio::null()).spawn()?;   // no pipe to fill
```

The pipe buffer is finite and platform-dependent — 64 KiB by default on Linux (rust-lang/rust#27152), and Windows anonymous pipes were smaller until rust-lang/rust#95782 raised them — so the same test can pass on one platform and hang on another.

Let nextest help you catch these. It marks a test `LEAK` when a subprocess keeps stdout or stderr open past `leak-timeout`, and you can make that a hard failure:

```toml
[profile.default]
leak-timeout = { period = "500ms", result = "fail" }
```

Detection only covers children that inherit stdout or stderr. A subprocess with `Stdio::null()` is not detected today.

**Do not let background work outlive the logical end of a test.** If the code under test does asynchronous work — deletion, compaction, replication, cache flush — and the test finishes while that work continues, the next test competes for the same disk or network. Make the work awaitable, or use a test-mode path that runs it synchronously.

**Killing a child does not just stop it, it leaves debris.** A `SIGKILL`ed process never runs its cleanup, so a rollback journal, a WAL sidecar, a half-written temp file, or an orphaned lock survives it. A test that kills a child and then reads what that child wrote is asserting on a crash artifact — the assertion measures the kill, not the writer. Either let the child exit cleanly and wait for it, or take a copy after it exited and assert on the copy. The ordering is the rule: kill, then stop observing.

**Read-only is not safer for a store someone else writes.** With an embedded database the intuitive flag is the wrong one.

```rust
// BAD - a read-only connection cannot perform crash recovery, so a store left
// with a hot journal by a killed writer is *unreadable* to it.
// Fails with SQLITE_READONLY_ROLLBACK (extended code 776), which reads as
// "something else is writing" and is actually "you cannot look at this".
let conn = Connection::open_with_flags(&path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;

// GOOD - read-only intent, enforced per statement, recovery still possible
let conn = Connection::open(&path)?;
conn.execute_batch("PRAGMA query_only = ON")?;

// GOOD - assert on a snapshot taken after the writer exited cleanly
child.wait()?;                 // exit, do not kill
let copy = snapshot(&path)?;   // file copy or `VACUUM INTO`
```

Three rules for a store a test or a child process also writes:

- A process killed or dropped mid-write leaves a journal behind, so a read after a kill is a read of crash state. Treat it as such, or eliminate it by waiting for a clean exit.
- A helper whose entire job is to observe state should be able to *recover* that state. If it opens read-only, it cannot roll back a hot journal and will fail exactly when there is something interesting to see.
- Open read-write with `query_only` when you need the reader to be incapable of changing anything. That gives you the guarantee you wanted without losing the ability to read a store that needs recovery.

## Determinism

**Inject the clock.** Read the system time only in production code, behind a trait.

```rust
// BAD - differs by machine and by when CI runs
let cutoff = SystemTime::now() - Duration::from_secs(3600);

// GOOD - the test controls time completely
let clock = FakeClock::new("2026-01-01T00:00:00Z");
let cutoff = clock.now() - Duration::from_secs(3600);
```

**Seed any RNG, and print the seed on failure.** Unseeded randomness makes a failure unreproducible, which is the one thing you need most.

```rust
let seed = std::env::var("SEED").ok().and_then(|s| s.parse().ok()).unwrap_or(0x5EED);
let mut rng = SmallRng::seed_from_u64(seed);
if result.is_err() {
    eprintln!("failed with seed {seed:#x} - replay with SEED={seed}");
}
```

**Never assert on `HashMap` or `HashSet` iteration order.** Rust randomizes the hasher seed per process, so the order differs every run.

```rust
// BAD - fails intermittently, passes locally
assert_eq!(map.keys().collect::<Vec<_>>(), vec!["a", "b", "c"]);

// GOOD
let mut keys: Vec<_> = map.keys().collect();
keys.sort_unstable();
assert_eq!(keys, vec!["a", "b", "c"]);

// or compare as sets
assert_eq!(map, HashMap::from([("a", 1), ("b", 2), ("c", 3)]));
```

Use `BTreeMap`/`BTreeSet` when order is semantically meaningful.

**Never assert on `read_dir` order.** It is unspecified on every filesystem, and macOS APFS returns hash order rather than lexicographic — so a listing assertion can pass on Linux and fail on a Mac. Sort first.

**Do not `assert_eq!` on floats.** The computed value differs by ULPs across platforms, optimisation levels, and thread counts. Use a relative or ULP tolerance, or compare a quantized value.

**Do not depend on locale, timezone, or hostname.** Pin them in the fixture, or assert on something that does not vary.

**Do not depend on filesystem semantics.** macOS volumes are case-insensitive and normalization-insensitive by default; ext4 is neither. Never distinguish two paths by case or Unicode form, keep fixture paths short and ASCII, and build them from `Path::join` on `env!("CARGO_MANIFEST_DIR")` rather than from the working directory or a pasted string.

## Assertions

- Assert on observable behaviour, not internal state. A test coupled to a private field breaks on every refactor and catches nothing.
- One logical claim per test. If the name needs "and", it is two tests.
- Include the actual value in the message when the default output would not make the failure obvious: `assert_eq!(got, want, "checksum for {key}")`.
- Pin the API's own classification on low-level failures, so the next reader does not need a lookup. `Query failed: readonly rollback` costs someone a web search; `Query failed: SQLITE_READONLY_ROLLBACK (776)` does not.
- Prefer `assert!(matches!(...))` over unwrapping a match, so a failure shows the value rather than a bare `panic!`.
- Test the error path, not just the happy path. Error handling is where defects hide.

## Naming

- Name a regression test after what it pins — the issue number, advisory, or the invariant — so `rg` finds the guard for a past bug later.
- Do not rename a test whose name a CI gate selects by substring. Some projects keep a floor on how many tests must match a reserved substring so a rename cannot silently thin a safety net. If a rename is unavoidable, change the floor in the same change.
- If the project routes suites to different CI lanes by name pattern, follow the existing marker of the suite you are extending.

## Property-based tests

Use `proptest` when the input space is too large to enumerate and an invariant is easier to state than the cases.

```rust
proptest! {
    #[test]
    fn roundtrip_preserves_input(s in any::<Vec<u8>>()) {
        let encoded = encode(&s);
        prop_assert_eq!(decode(&encoded).unwrap(), s);
    }
}
```

- Set `ProptestConfig` cases explicitly in CI; the default is low enough to miss rare interleavings.
- Use `proptest-regressions` so a found failure is persisted as a file and replayed on every future run. Without it, a shrink-found counterexample is lost.
- `proptest` shrinks on failure, which makes the reported case minimal and usually points straight at the bug.

## Concurrency primitives

For locks, channels, and state machines, random scheduling rarely explores the interleaving that breaks. Model checkers explore it systematically. The two are complements, not equivalents: **loom is exhaustive and sound** (a passing test is real evidence), while **shuttle is randomized and explicitly not sound** — a passing shuttle test does not prove correctness, but it scales to much larger state spaces and finds most non-adversarial concurrency bugs.

```rust
loom::model(|| { /* exercise a std::sync primitive */ });          // exhaustive, small state
shuttle::check_random(|| { /* explore scheduling */ }, 100);       // randomized, needs an iteration count
```

Note the second argument on `check_random` — the signature is `check_random(f, iterations)`, and the count is shuttle's main tuning knob. Shuttle also provides `check_pct` (probabilistic concurrency testing, bounded preemptions) and `check_dfs` (exhaustive, for very small primitives).

Both require rewriting the test against the tool's primitives, so keep them for the component under test. They do not belong in an integration suite.

For `unsafe` code, run ThreadSanitizer periodically rather than per-commit. It needs a nightly toolchain and the instrumented standard library, without which it reports false races from `std` internals:

```bash
rustup component add rust-src        # -Zbuild-std needs the std sources
RUSTFLAGS="-Zsanitizer=thread" \
  cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu -- --test-threads=1
```

Run it single-threaded. TSan reports on multi-threaded test execution often indicate bugs in the tests themselves.

## Runner configuration

Use `cargo nextest`. It runs each test in its own process, which removes an entire class of global-state and cross-test interference problems, and it gives you retries, timeouts, and flaky detection.

```toml
# .config/nextest.toml
[profile.default]
retries = 0                    # never hide a flake locally
fail-fast = true
slow-timeout = { period = "60s", on-timeout = "fail" }
leak-timeout = { period = "500ms", result = "fail" }

[profile.ci]
retries = 0                    # retries are opt-in per test, never global
fail-fast = false

# Serialize only what genuinely cannot run in parallel.
[test-groups]
serial-integration = { max-threads = 1 }

[[profile.ci.overrides]]
filter = 'test(/^needs_fixed_port::/)'
test-group = 'serial-integration'
```

Guidance:

- Keep `retries = 0` globally. Grant retries per test, with a comment linking an open issue. A global retry turns a flaky suite green and hides the problem permanently.
- Prefer self-isolating tests over test groups. A group is slower and leaves the coupling in place.
- Give quarantined tests a deadline. A retry with no owner and no due date is not containment, it is abandonment.
- Enable JUnit output when you need to see flakes across a suite: a test that passes on retry is tagged `flakyFailure` there, which is more reliable than reading console output.

## Review checklist

Run through this before calling a test done.

- [ ] Runs in any order, in parallel, with no dependence on another test.
- [ ] Ports bound to `0`; paths from `tempfile`; no shared fixed location.
- [ ] No `std::env::set_var` or working-directory changes.
- [ ] No `sleep` without `start_paused = true`; no `yield_now()` as synchronization.
- [ ] No blocking call inside an async task: no `std::thread::sleep`, `std::fs::`, `std::net::`, or a `std::sync` lock held across an `.await`.
- [ ] Every `tokio::spawn` result is retained and awaited, or cancelled and joined.
- [ ] Every subprocess is killed on drop; no leaked ports or listeners.
- [ ] Every piped child stream is drained or discarded; no wait on a child whose pipe nobody reads.
- [ ] Every process this test kills has left nothing durable that this test then reads — a clean exit or a post-exit copy instead.
- [ ] A store this test reads but does not own is opened read-write with `query_only` (or read after a snapshot), never with a read-only open flag.
- [ ] Clock and RNG are injected or seeded, and the seed is printed on failure.
- [ ] No assertion on `HashMap`/`HashSet` order; data is sorted first.
- [ ] No `assert_eq!` on floats, and no assertion on `read_dir` order.
- [ ] No assumption that a filesystem is case-sensitive or normalization-preserving; fixture paths are short and resolved from `CARGO_MANIFEST_DIR`.
- [ ] Every unbounded wait has a generous, explicit timeout.
- [ ] No reliance on `#[serial]` under nextest.
- [ ] The lowest layer that can prove the behaviour is the one used.
- [ ] The name describes the invariant, and does not break a name-based CI gate.
- [ ] Failures on a low-level API assert the API's own code or classification, not just a rendered message.

## References

- [references/async-tests.md](references/async-tests.md) — Tokio runtime choice, paused time, blocking the executor, cancellation safety, and orphan tasks in depth.
- [references/isolation-and-resources.md](references/isolation-and-resources.md) — ports, temp dirs, environment, processes, draining child output, reading an embedded database a child process writes, filesystem semantics, and cleanup patterns.
- [references/determinism.md](references/determinism.md) — clocks, RNG, hash and directory ordering, floating-point comparison, and making failures replayable.
- [references/nextest-config.md](references/nextest-config.md) — annotated `nextest.toml` reference, test groups, quarantine, and CI wiring.
