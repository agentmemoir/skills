# Rust Flaky Test Root-Cause Taxonomy

Fifteen families of nondeterminism in Rust test suites. Each entry gives the failure signature you would actually see in output, the experiment that confirms it, and where the fix belongs.

Use this after the discrimination matrix in `SKILL.md` Phase 3 has narrowed the space. The matrix tells you whether the problem is internal to the test or caused by the environment; this file tells you which mechanism. Match on values, not only shapes — decode the error's own codes with `error-triage.md` first, because "fails with extended code 776" identifies a family that "fails sometimes after teardown" does not.

Families 1 to 10 cover the mechanisms that dominate storage, replication, and async-service codebases, because that is where the flakiness literature and the source case study concentrate. Families 11 to 14 were added to cover gaps that show up in other kinds of Rust project — CLI tools, memory-heavy services, and suites whose CI configuration itself is the problem. If your project is not storage-shaped, start reading at 11. Families 15 to 19 cover a test that damages the state it observes, the two ways an async or subprocess test deadlocks rather than fails, numeric comparison, and platform filesystem semantics — mechanisms that belong to every kind of project and that the async-service literature does not name.

Where a family here names a literature category, the citation is in the entry. Luo et al. (ICSE 2014) and Lam et al. (FaTB, MSR/MTD 2020) classified flaky-test fixes into a standard set of root causes — async wait, concurrency, test-order dependency, resource leak, network, time, I/O, randomness, floating-point operations, unordered collections, and platform dependency. Families 1 to 14 and 18 to 19 map onto that set; families 15 to 17 are the Rust-specific mechanisms the taxonomy grew from real investigations.

## How to use this file

1. Decode the failure first — every code, errno, status, and signal in the output, resolved against its documentation. See `error-triage.md`.
2. Start from the decoded values and the symptom, not from the code. Find the row whose signature matches your output.
3. Run that row's confirming experiment. If it comes back negative, move to the next row.
4. Do not skip to the fix. A fix applied to the wrong family looks like it works and leaves the real defect in place.

---

## 1. Wall-clock timing dependence

**Signature.** Intermittent timeout. `tokio::time::timeout` or a harness `slow-timeout` fires. Fails on CI and on loaded machines, passes on an idle laptop. Duration is suspiciously close to a round number, because someone wrote a deadline, not a synchronization.

**First question for any timeout.** Did the test take too long, or did it never finish? A deadline that expired because the work was slow is this family; a test that never completes is family 16 (blocking call on the executor) or family 17 (undrained child pipe). The status line distinguishes them, and the fix is unrelated.

**Mechanism.** The test assumes a bounded execution time. Under CPU throttling, container CPU limits, or a loaded disk, the real time exceeds the assumed time. Nothing is broken except the assumption.

**Confirming experiment.** Squeeze the machine and watch the failure rate rise: `stress-ng --cpu $(nproc) --timeout 60s` alongside the loop. Or convert the wait to paused time and re-run. If the rate scales with load, it is timing.

**Fix.** Replace the wall-clock wait with a real synchronization signal: a channel receive, `tokio::sync::Notify`, a broadcast, or polling a condition with a generous timeout. If the code under test is genuinely time-driven, use `#[tokio::test(start_paused = true)]` and advance time explicitly. Keep timeouts as a safety net, generous enough that they never fire in normal operation.

**Trap.** Do not fix by lengthening the timeout. That raises the threshold without removing the race, and the test gets slower every time someone does it again.

---

## 2. Scheduling starvation

**Signature.** A polling loop that never observes its condition. The test hangs or times out while doing nothing. Common in loops built on `tokio::task::yield_now()`.

**Mechanism.** `yield_now()` returns control to the runtime but does not wait for anything. Under heavy parallel load, the task that would satisfy the condition may not be scheduled before the test's own deadline expires. The loop is correct in isolation and starved in a full suite.

**Confirming experiment.** Reproduce under parallel load and with reduced worker count. If single-threaded runs never fail and highly parallel runs fail often, it is starvation, not logic.

**Fix.** Replace the polling loop with a real notification. If you must poll, poll a condition with a bounded deadline and backoff, and make the deadline generous. `yield_now()` as a synchronization mechanism is always a bug.

---

## 3. Orphan background work

**Signature.** The test passes alone but breaks, hangs, or corrupts whatever runs after it. `dispatch task is gone`, abruptly closed connections, truncated files, or a lock held by a task that no longer exists. Sometimes the symptom appears in a completely different test.

**Mechanism.** A `tokio::spawn` result is dropped. The test body returns, `#[tokio::test]` tears down the runtime, and the background task is killed mid-operation — possibly holding a lock, halfway through a write, or with a half-open connection. Under `cargo test` all tests share one process, so the damage reaches its neighbours. Under nextest the damage is usually confined to the single test process, which makes it look like a mystery.

**Confirming experiment.** Count spawns against joins. If any `tokio::spawn` has no retained `JoinHandle`, you have found it. Confirm by awaiting the handle and re-running the suite.

**Fix.** Retain every `JoinHandle` and await it, or manage the task with a `CancellationToken` and await its completion during teardown. For long-lived background loops, a guard type whose `Drop` cancels and joins is the robust pattern.

**This is often a production bug.** A component that does not shut down cleanly when its runtime dies is defective outside tests. Say so in the report.

---

## 4. Cancellation-safety violation

**Signature.** Intermittent corruption, deadlock, or half-written state. Frequently a record that is missing a field it should have, or an index that disagrees with its payload. Only under concurrency.

**Mechanism.** `tokio::select!` drops every future that does not win the race. If a dropped future was mid-mutation, its state is left inconsistent unless it is cancellation-safe. Tokio documents cancellation safety per method; custom futures usually are not safe by default.

**Confirming experiment.** Add a yield or a small delay into each `select!` branch in turn, forcing the branches to win in different orders across runs. If the outcome changes with which branch wins, it is a cancellation-safety defect.

**Fix.** Make the state transition atomic and idempotent so an interrupted attempt can be retried safely, or restructure so the mutation is not split across an await point. Where a library method is involved, check its documented cancellation safety before assuming.

---

## 5. Global or process-wide state mutation

**Signature.** A test fails only in combination with others, and the offending partner changes between runs. Path errors, missing environment variables, unexpected locale or timezone.

**Mechanism.** `std::env::set_var`, `std::env::set_current_dir`, mutable statics, `OnceLock`/`OnceCell` initialized once, or a lazy singleton retain state across test boundaries. Under `cargo test` all tests are threads in one process, so this is a genuine data race. `set_var` is `unsafe` in Rust 2024 for exactly this reason.

**Confirming experiment.** Run the suite single-threaded with a varying order. If the failing partner changes run to run, it is global state, not a fixed dependency. Note that nextest's process-per-test model masks this, so a suite can be green under nextest and broken under `cargo test` — check both if the project supports both.

**Fix.** Pass configuration as parameters or through a fixture instead of mutating globals. Where a global is unavoidable, initialize it once to a fixed value in a `OnceLock` rather than reassigning it per test. Under nextest, a test group with `max-threads = 1` is containment, not a fix.

---

## 6. Resource contention

**Signature.** `Address already in use` (EADDRINUSE), `Permission denied` on a file lock, "text file busy", or a bind failure during setup. The single most common cause in Rust suites.

**Mechanism.** Two tests bind the same hardcoded port, write the same fixed path, or fight over the same disk. Parallel execution makes them overlap.

**Confirming experiment.** Change the port or path to a unique per-iteration value and re-run. If the failures disappear, it is collision. `-j 1` also makes it vanish, which confirms collision but does not tell you which resource.

**Fix.** Bind port `0` and read back the assigned port from the listener, so the OS picks a free one. Use `tempfile::tempdir()` for files and directories, which gives a unique path and cleans up on drop. Never hardcode a port or a path under a shared root in a test.

**Trap.** A random-but-unseeded port or path is still nondeterministic. Use OS-assigned or fixture-assigned values, not `rand()`.

---

## 7. Order dependence and state leak

**Signature.** The suite fails only in specific orders. Shuffling the order changes which tests fail, or makes them pass.

**Mechanism.** A test leaves something behind: a file in a shared directory, a row in a shared database, a bucket or key prefix, a background process, a mutated static. The next test reads it and mis-asserts.

**Confirming experiment.** Run the suspected predecessor immediately before the victim, repeatedly. Then reverse the order. If the failure follows the predecessor, you have the dependency. With `cargo test` on nightly, `cargo +nightly test -- -Z unstable-options --test-threads 1 --shuffle` surfaces order dependence directly and prints a seed you can replay with `--shuffle-seed`.

**Fix.** Make every test create and own its own state, and clean up in teardown via `Drop`. A test that requires a predecessor to have run first is a design defect regardless of whether it is flaky.

---

## 8. Nondeterministic data or ordering

**Signature.** Assertion failures where the same inputs produced a different result. Diff shows the same elements in a different order.

**Mechanism.** Four usual sources. `HashMap` and `HashSet` use a randomly seeded hasher, so iteration order changes every process. Unseeded RNG produces different data each run. `SystemTime::now()` and locale or timezone differ by machine. And `read_dir` order is unspecified by every filesystem, with APFS returning hash order rather than lexicographic — so an *unsorted* listing assertion can pass on one filesystem and fail on another (see family 19 for the rest of that family's mechanism).

**Confirming experiment.** Re-run the same binary twice and compare iteration order of the same input. If it differs, the hasher seed is the cause. For RNG, seed it explicitly and re-run — the failure should become deterministic.

**Fix.** Sort before asserting, or compare as sets. Use `BTreeMap`/`BTreeSet` where order is semantically meaningful. Seed any RNG explicitly so a failure is replayable. Inject a clock instead of reading the system clock.

---

## 9. Background I/O contention

**Signature.** Timeouts and high iowait on a test that starts right after a heavy one. Benchmarks record implausible throughput. Fails on HDD or rate-limited cloud storage, passes on local SSD.

**Mechanism.** A previous test finished logically but left background work running — asynchronous deletion, compaction, cache flush, replication. That work saturates the disk, and the next test's I/O-backed timing assumptions break.

**Confirming experiment.** Insert a delay or a different heavy test before the victim. If the victim's failure rate tracks the predecessor's I/O weight, this is it. Check disk utilization during the run.

**Fix.** Make the background work observable and awaitable so the test does not finish until it is actually done. If the production code offers a synchronous or test-mode path, use it in tests. If it cannot be made awaitable, put the heavy-I/O tests in a nextest test group with `max-threads = 1`.

**Note.** This often means the test lies about completion. That is a test bug, and worth saying plainly.

---

## 10. Cleanup and resource leaks

**Signature.** A test that passes but leaves a subprocess running. Later tests fail with a port already in use or a file locked. Over a long run, file-descriptor exhaustion.

**Mechanism.** A test spawns a server or helper process and does not kill it. `std::process::Child` does **not** kill its child on drop. If the test panics before cleanup, an RAII guard is the only thing that saves you. `tokio::process::Command` can be configured with `kill_on_drop(true)`.

**Confirming experiment.** Let nextest detect it. nextest marks a test `LEAK` when standard output or error stay open past the configured `leak-timeout`, which is the signature of a surviving child. Set `leak-timeout = { period = "500ms", result = "fail" }` to make it a hard failure — and set it explicitly, since nextest's docs disagree on the default (200ms in its config reference, 100ms on its leaky-tests page). Confirm by listing processes after the run.

**Caveat.** nextest only detects children that inherit stdout or stderr. A subprocess with `Stdio::null()` is not detected today, and that limitation is not covered by nextest's stability guarantees.

**Fix.** Use `kill_on_drop(true)` for `tokio::process::Command`, or a guard type that kills and waits in `Drop`. Close listeners explicitly. Delete temp trees in teardown. Treat a `LEAK` status as a real defect, not noise.

---

## 11. Memory and allocator pressure

**Signature.** Out-of-memory abort, allocator failure, or a slowdown that only appears on a constrained runner. Sometimes a hard crash with no panic message at all — the process just dies. Common in tests that build large buffers, deserialize big fixtures, or run many subtests in one process.

**Mechanism.** A test's peak memory depends on the machine. Under a container memory limit, a test that allocates 400MB locally gets OOM-killed on a 512MB runner. It can also be an allocator interaction: a custom global allocator, a jemalloc/mimalloc configuration, or `MALLOC_ARENA_MAX` differing between environments, all of which change fragmentation and peak usage.

**Confirming experiment.** Cap memory and re-run. `cargo nextest run -E 'test(=name)' --stress-count 20` inside a constrained container, or set a low `ulimit -v`. If the failure only appears under a cap, it is memory, not logic. Also check whether the test leaks across iterations — a leak shows up as a rising failure rate over the run rather than a flat one.

**Fix.** Reduce the test's peak allocation: stream instead of buffering, shrink the fixture, drop caches between phases. For a genuine leak, that is a production defect the test exposed. Where a limit is legitimate, make the test skip cleanly when it cannot get the resources rather than aborting.

---

## 12. Test-group and runner misconfiguration

**Signature.** A test is protected by `#[serial]` or an assumed ordering and still fails under CI. Or a suite is green locally and red in one specific lane. Or a test nobody remembers adding now runs in a lane that has no network or no disk.

**Mechanism.** The runner configuration and the test's assumption have drifted apart. The usual culprit is `#[serial]` under nextest, which is a no-op because nextest is process-per-test — the test believes it is protected and is not. Others: a per-test `slow-timeout` override that is shorter than the test needs; a test moved into a test group it does not belong in; a lane whose filter selects a test whose fixture requires a capability that lane does not provide.

**Confirming experiment.** Run the test under the exact profile the failing lane uses, and diff the effective configuration against the profile you develop with. `cargo nextest run --profile <lane> -E 'test(name)'` and then check the test's attributes and any `[test-groups]` membership by hand. If it fails under one profile and not another, the configuration is the cause, not the test.

**Fix.** Move the test to a group with `max-threads = 1`, or use `serial_test`'s `file_serial` if the constraint is genuinely cross-process. Raise the per-test `slow-timeout` to fit the slowest legitimate run. If a lane lacks a capability the test needs, either exclude the test from that lane or make the test skip when the capability is absent.

---

## 13. DNS, hostname, and network identity

**Signature.** Failures in tests that resolve a hostname, connect to a named host, or assert on a self-identity. Often only in CI, and often clustered in one time window. `Temporary failure in name resolution`, `Name or service not known`, or a surprising remote address.

**Mechanism.** Anything that depends on a name resolving to a specific address is nondeterministic. A hosts-file entry differs between a laptop and a container. Corporate or CI DNS returns a load-balanced address, so consecutive connections land on different backends. IPv6 versus IPv4 preference changes which address is used. Certificate validation additionally depends on the system trust store and the clock.

**Confirming experiment.** Resolve the name repeatedly and watch the answers change: `for i in $(seq 20); do getent hosts <name>; done`. If the address varies, that is it. Also check whether the test bypasses DNS by connecting to `127.0.0.1`, and whether it does so inconsistently.

**Fix.** Do not resolve names in tests. Bind the listener to `127.0.0.1:0`, read the assigned address back, and pass it to the client as an address rather than a name. If a name is genuinely under test, inject a resolver. Make TLS tests use a pinned test certificate rather than the system trust store.

---

## 14. Test data derived from the environment

**Signature.** A test passes on one machine and fails on another with a diff that looks like random data. Different row counts, different IDs, different generated names. Common in projects seeded from a template, a fixture directory, or a query over live data.

**Mechanism.** The test's input is not fixed. It reads a fixture that differs per environment, a config file that a developer has edited, a directory that accumulates files across runs, or an auto-increment sequence whose starting value depends on what ran before. A test that globs a directory and asserts on the result changes every time someone adds a file. **Case:** an e2e assertion passed on most runners and failed on one because production truncated a device number; the environment supplied the large device number and the code handled it wrongly.

**Confirming experiment.** Run the test twice in a row on a clean checkout. If the second run differs, something is accumulating. Then diff the input: print or hash the generated data on each run and compare. `git status --porcelain` after a run reveals a test that writes into the working tree.

**Fix.** Pin the input: check fixtures into version control, generate data from a fixed seed, and assert on a sorted projection rather than on collection size. For anything discovered by globbing, assert that the expected entries are *present* rather than that the set is *exactly* equal, or scope the glob to a dedicated subdirectory nothing else writes to.

---

## 15. Self-inflicted resource damage

**Signature.** The test's own teardown causes its own failure. A store that will not open (`SQLITE_READONLY_ROLLBACK`, `SQLITE_CORRUPT`), `Text file busy`, a truncated file, a stale lock, or a checksum mismatch — all read by the *same* test that killed the writer, usually in an assertion helper. Often visible only in a full run, because only a full run has children dying mid-write. The failing frame is the test's cleanup or its own read-back helper, not the code under test.

**Mechanism.** The test spawns a writer (a child process, a helper binary, a background task), kills or drops it in `Drop`, and then reads what that writer wrote. A killed process never runs its cleanup, so a rollback journal, WAL sidecar, or temp file is left behind — and the crash artifact is what the assertion inspects. This is the mirror of family 10: family 10 is a handle that should have been released, this is damage that was deliberately caused. The distinguishing signature is that the *same* test fails, immediately, from its own cleanup, rather than a later test failing.

With an embedded database the failure stops being a race and becomes arithmetic: a connection opened `SQLITE_OPEN_READ_ONLY` cannot perform crash recovery, so a hot journal left by a dead writer makes the file *unreadable* to it, while a read-write connection with `PRAGMA query_only = ON` recovers the file and refuses writes at the statement level. A harness that chose the read-only flag precisely so its assertions could not change anything is the one that cannot read the damage.

**Confirming experiment.** Make the teardown graceful — a one-line change, and the cheapest experiment in this file: `child.wait()` instead of `child.kill()`, or drop the guard before asserting. If the failure disappears, the test was asserting on a crash artifact. Run the *shape* of the failing workload (many tests spawning children at once) rather than a heavier machine, and check whether the runner serialises concurrent invocations first, because "run it eight times concurrently" silently becomes "run it once" and zero failures then reads as a pass.

**Fix.** Never let the thing that observes state be the thing that corrupted it. Either wait for a clean writer exit before asserting, or assert on a copy taken after the writer finished. For SQLite specifically: a read-only *assertion* should be a read-write connection with `query_only`, or a `VACUUM INTO` copy made after the writer exited; `SQLITE_OPEN_READ_ONLY` reads as safer and is the opposite. For any killed child, treat what remains on disk as crash state and do not assert on it.

**Trap.** Killing the child is correct hygiene — `std::process::Child` does not kill on drop — so the fix is not "stop killing it". The fix is the ordering: kill, then stop observing. And a helper whose entire job is to read state should be able to recover that state rather than refuse to look at it.

**This is sometimes a production bug.** A component that can only be shut down by `SIGKILL` leaves durable debris for whoever runs it next. If the writer is production code, say so in the report: the fix owner changes.

---

## 16. Blocking work on the async executor

**Signature.** A timeout or a hang rather than an assertion failure, and it is worst on the default current-thread runtime. Paused time stops advancing. `tokio-console` shows one task with a long poll gap and everything else idle. Often "passes alone, times out in the suite", because in a suite the runtime has other work that the blocked thread cannot reach.

**Mechanism.** A synchronous call runs inside an async task: `std::thread::sleep`, `std::fs::*`, `std::net::TcpStream`, `Command::status()`, a synchronous SQLite or FFI call, or a CPU-bound loop. On a current-thread runtime the executor *is* that thread, so a blocking call stops everything — no timers, no I/O driver, no other tasks. `std`'s own documentation says `thread::sleep` "is blocking, and should not be used in async functions", and Tokio's answer is `tokio::time::sleep`, `tokio::fs`, `spawn_blocking`, or `tokio::process::Command`.

This is not family 2. Starvation is a task that keeps polling and never sees its condition; this is a task that stopped polling altogether, and the tell is that nothing in the runtime progresses.

**Confirming experiment.** Grep the failing path for blocking calls inside `async fn` or `tokio::spawn` bodies — `rg -n 'thread::sleep|std::fs::|std::net::|Command::new|\.wait\(\)|block_on' -g '*.rs'`. Then swap one for its async equivalent and re-run under the same conditions. Cheaper first: run with `--test-threads=1` and a deliberately small `slow-timeout`; a blocking call reproduces far sooner than a starvation race does.

**Fix.** Use the async API for every await point: `tokio::time::sleep` for delays, `tokio::fs` for files, `tokio::process::Command` for children, `tokio::net` for sockets. For genuinely blocking work, wrap it in `spawn_blocking` — and remember `spawn_blocking` cannot be cancelled and keeps the runtime busy, which is why a long-lived one stops paused time from auto-advancing and looks like a hang.

---

## 17. Subprocess pipe deadlock

**Signature.** A hang or timeout that depends on how much the child prints. Passes when the child's output is small, hangs when it is large, and the timeout duration tracks the output volume. The child is alive, not crashed, and is usually blocked in `write`.

**Mechanism.** `Stdio::piped()` hands the child a pipe with a finite buffer. If the parent waits for exit without reading the pipe — `child.wait()`, or `Command::status()` — the child fills the buffer, blocks in `write`, and never exits, so the parent waits forever. The `std::process` docs call this out directly: "If the child process fills its stdout buffer, it may end up waiting until the parent reads the stdout ... causing a deadlock." The buffer is finite, platform-dependent, and has moved across Rust versions — Linux pipes hold 64 KiB by default (rust-lang/rust#27152), and Windows anonymous pipes were 4 KiB until rust-lang/rust#95782 raised them (#45572) — so the same test can pass on one platform and hang on another.

**Confirming experiment.** Halve or double the child's output and see whether the failure tracks it. Then replace the wait with `wait_with_output()` — which drains the pipe while it waits — or set `Stdio::null()`, and re-run. If the hang disappears, it is this. On Linux, `strace -f -e trace=write -p <child-pid>` shows the child parked in `write`, which distinguishes it from family 16's blocked executor in seconds.

**Fix.** Drain or discard. `wait_with_output()` for captured output, `Stdio::null()` or `Stdio::inherit()` when the test does not read it, `tokio::process::Command` with `.kill_on_drop(true)` and a concurrent read for async tests. For very chatty children, redirect to a file and assert on the file.

**Trap.** `Command::status()` spawns the program again rather than reporting on a previous run, so `output()` followed by `status()` executes the child twice. Use `output()` once and read `Output::status`.

---

## 18. Floating-point and numeric comparison

**Signature.** An assertion failure whose two values differ by a few ULPs or by a tiny absolute amount. Passes on one machine, fails on another; passes in one build profile and fails in the other; a sum or average that is off in the last digits. Diff output full of near-identical decimals.

**Mechanism.** `assert_eq!` on floats is exact comparison. The computed value depends on the platform's math library, the optimisation level, and the target's instruction selection — `sqrt`, `exp`, `ln`, `powf`, decimal parsing, and accumulation all differ slightly between a developer machine and a CI runner. Parallel work changes accumulation order, so a sum differs when the same inputs are split across a different number of threads. Floating-point operations are one of the standard root-cause categories in the flaky-test literature (Luo et al., ICSE 2014; Lam et al., FaTB 2020), and not a rare one.

**Confirming experiment.** Print both values at full precision and the distance between them in ULPs — a distance of a few ULPs means this family, not a logic bug. Then run the test in release and debug, and with `worker_threads = 1` versus the default: if the failure correlates with profile or thread count, the comparison is the problem, not the arithmetic.

**Fix.** Assert with a tolerance rather than for equality: `(got - want).abs() <= want.abs() * 1e-9`, or use a crate built for it (`approx`'s `assert_relative_eq!`, `float_eq`'s `assert_float_eq!`). Where the exact digits do not matter, compare a quantized value — `(x * 100.0).round() / 100.0` — or compare a checksum over the rounded stream. Where they do matter, assert on the *invariant* (monotonic, within range, correctly ordered) rather than on a literal.

**Trap.** An absolute epsilon is wrong at the ends of the range: `f64::EPSILON` rejects legitimate large values, and a fixed absolute tolerance passes far too much at small magnitudes. Prefer relative or ULP-based comparison.

---

## 19. Platform filesystem semantics

**Signature.** Green on the developer's platform, red in CI, or the reverse, with an error that makes no sense: `No such file or directory` for a path that exists, two fixture files that collide, an assertion that depends on `read_dir` order, or `File name too long`. Frequently only in a Linux container.

**Mechanism.** Filesystems differ in ways a test silently depends on. **Case:** APFS and HFS+ are case-insensitive by default on macOS; ext4 is case-sensitive, so `Report.txt` and `report.txt` are one file on a laptop and two in CI. **Normalization:** macOS volumes are normalization-insensitive and return whichever form was stored, so a Unicode path can come back byte-different from what you wrote (Apple's APFS FAQ). **Order:** `readdir` order is unspecified everywhere, and Apple's APFS FAQ is explicit that APFS returns filenames in *hash* order rather than lexicographic, so an *unsorted* listing assertion can appear to pass on a filesystem whose `readdir` happens to come out in a convenient order and fail on another. Sort before asserting. **Limits:** `NAME_MAX` is 255 bytes, `PATH_MAX` differs per platform (and Windows caps far lower, with reserved device names like `CON` and `NUL`). **Symlinks:** `/tmp` is a symlink to `/private/tmp` on macOS, so a path comparison on the literal string fails.

**Confirming experiment.** Run the same test on the other platform, or in a container, and diff the filesystem state rather than the assertion: print `fs::read_dir` output before sorting, print the exact bytes of the paths involved, and try creating both `a.txt` and `A.txt` to see whether the second overwrites the first.

**Fix.** Do not use case or Unicode normalization to distinguish paths — use a content difference or a distinct prefix that cannot be folded. Sort every directory listing before asserting on it. Keep fixture and temp paths short, ASCII, and well under the name limit. Build fixture paths from `env!("CARGO_MANIFEST_DIR")` or `Path::join`, never from the process working directory or a hand-concatenated string, and compare canonicalized paths when comparing path values.

**Trap.** This reads like path contention (family 6) or order dependence (family 7) and gets "fixed" with a unique temp dir or a test group, neither of which helps. The defect is in the test's assumption about the filesystem, not in a collision.

---

## Environment-only causes

Not a numbered family, but the one you should rule in or out early, because it changes the whole investigation.

**Signature.** Passes locally every time, fails in CI. Consistent on one runner image and not another.

**Likely causes:** fewer cores or less memory on the runner, container CPU quotas, a different filesystem (overlayfs vs. ext4, tmpfs vs. disk), no outbound network, expired or absent certificates, a different locale or timezone, a cold filesystem cache.

**How to confirm.** Reproduce locally under constrained resources, or run the exact CI image in a container. Compare `nproc`, available memory, and mount types between local and CI.

**How to fix.** Do not tune timeouts to your laptop. Either remove the environment dependency (mock the network, inject the clock, use an in-memory implementation) or size the timeouts for the constrained runner, not the fast one.

---

## Precedence

When several families fit, check in this order. It follows how often each is the real answer and how cheap each is to rule out:

1. Resource contention (6) — hardcoded port or path. Most common, cheapest to confirm.
2. Self-inflicted resource damage (15) — the test killed or dropped the writer of the state it reads. Cheap to confirm (make the teardown graceful) and invisible to the axes, because nothing external is involved.
3. The two deadlock families (16 and 17) — a blocking call inside an async task, or a parent that waits without draining the child's pipe. A hang rather than a failure, and both are settled by one `rg` over the failing path.
4. Wall-clock timing (1) — any `sleep`, timeout, or fixed deadline in the path.
5. Orphan background work (3) — any dropped `JoinHandle`.
6. Order dependence and state leak (7).
7. Global state (5).
8. Scheduling starvation (2) and cancellation safety (4).
9. Nondeterministic data (8), including directory iteration order — see also 19.
10. Background I/O contention (9).
11. Cleanup leaks (10) — the same mechanism as 15, but the other direction: a handle that outlived the test instead of damage the test caused itself.
12. Runner misconfiguration (12) — cheap to check and explains "green locally, red in one lane".
13. Environment-derived test data (14).
14. Floating-point comparison (18) — only once the value is known to be a number rather than a string or a struct.
15. Memory pressure (11) and DNS or hostname identity (13).
16. Platform filesystem semantics (19) — promote it near the top if the suite runs on more than one filesystem, because every one of its symptoms looks like a different family.

If your project is not storage- or service-shaped, promote 12, 13, 15, and 16 higher: they are the families the async-service literature under-documents, and they are the ones most likely to be sitting in your suite unexamined. Families 15 and 16 stay high for every project shape, because the mechanism is a property of tests rather than of the code they test.

Timeouts and hangs deserve their own note: a failure that says `TIMEOUT`, `slow-timeout`, or a hang is not yet a diagnosis. Read it as "the test did not finish", then split the space into *took too long* (families 1, 2, 9, 11), *never finished* (families 16, 17, and a lock held by family 3), and *was killed* (a `slow-timeout` termination policy, or the runner). The error line tells you which: a `TIMEOUT` status is a slow test, a `SIGKILL` status is usually the runner or the OOM killer, and a test that hangs only under the current-thread runtime is family 16.

A single test can have more than one cause. When a fix removes only part of the failure rate, that is the signal: you have found a contributing cause, not the cause. Report both the confirmed and the residual.
