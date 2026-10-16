# Isolation and Resource Cleanup

How to keep a test's resources to itself, and how to guarantee they are released. Most Rust test flakiness reduces to three mistakes here: two tests sharing a resource, a test leaving a resource behind, and a test destroying a resource it then goes on to read.

## Ports

**Always bind `0`.** The OS assigns a free port and nothing else can collide with it.

```rust
use tokio::net::TcpListener;

let listener = TcpListener::bind("127.0.0.1:0").await?;
let addr = listener.local_addr()?;   // read back the assigned port
```

For a server under test, pass the assigned address into the client code rather than letting the client re-derive it. A common flake is a server that binds `0` and a client that still hardcodes `9000` — the fix is incomplete and the test still collides.

Never generate a port with `rand()`. That is still a guess, and a guess can collide. `0` is not a guess.

Dropping a `TcpListener` closes the socket. In most cases that is enough. Under nextest, where each test is its own process, a lingering socket is not a problem; under `cargo test`, an unclosed listener in one test can collide with another in the same process.

## Files and directories

**Use `tempfile`.** It gives a unique path and removes it on drop, including during a panic unwind.

```rust
// BAD
let dir = PathBuf::from("/tmp/my_test_data");

// GOOD
let dir = tempfile::tempdir()?;         // unique, auto-cleaned
let path = dir.path().join("data.bin"); // path is inside the unique dir
```

Two details that matter:

- Put **all** of a test's files under one `tempdir()`, not several loose `tempfile::NamedTempFile`s scattered across the filesystem. One directory is one thing to reason about and one thing to clean up.
- If the code under test needs the directory to outlive the test — a background task still writing to it — do not let `tempdir()` drop early. That reintroduces exactly the cross-test I/O contention you were avoiding. Either await the background work, or move it to a `TempDir` you control explicitly.

**Never write to a fixed path under a shared root.** `/tmp/my_test_data` is a global. Two tests, two runs, two machines on the same NFS mount.

## Environment variables

`std::env::set_var` mutates process-wide state. Under `cargo test`, where all tests are threads in one process, that is a genuine data race with every other test. It is `unsafe` in Rust 2024 for exactly this reason.

```rust
// BAD
std::env::set_var("RUST_LOG", "debug");

// GOOD - explicit dependency, no global mutation
fn new_client(log_filter: LogFilter) -> Client;

// GOOD - for a dev-dependency setup only
let _guard = EnvGuard::set("RUST_LOG", "debug");  // restores on drop, and only in a serial test
```

The same applies to `std::env::set_current_dir`, which is process-wide and even worse because it invalidates every relative path in the process.

If a test must set an env var, put it in a nextest test group with `max-threads = 1` so it cannot race, and comment why. That is containment, and it is honest about being containment.

## Static and lazy state

`static mut`, `OnceLock`, `OnceCell`, and `lazy_static` all retain state for the life of the process.

- Under nextest, each test is a fresh process, so a poisoned static cannot leak between tests. This is the main reason nextest eliminates a large class of Rust test bugs.
- Under `cargo test`, it can. A test that initializes a `OnceLock` has changed the state of every test that runs after it, in an order that depends on scheduling.

If a project supports both runners, that difference is worth stating in its test docs, because it means a suite can be green under one and broken under the other.

Prefer passing configuration explicitly. Where a global is genuinely unavoidable, initialize it once to a fixed value rather than reassigning it per test.

## Subprocesses

**`std::process::Child` does not kill its child on drop.** A test that panics before cleanup leaves the process running, holding its port, its file locks, and its memory.

```rust
// BAD - leaks on panic
let mut child = Command::new("my-server").spawn()?;

// GOOD for tokio
let child = tokio::process::Command::new("my-server")
    .kill_on_drop(true)
    .spawn()?;

// GOOD for std - a guard that kills and reaps in Drop
struct ChildGuard(std::process::Child);
impl Drop for ChildGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
```

**Let nextest catch the ones you miss.** It marks a test `LEAK` when a subprocess keeps stdout or stderr open past the configured `leak-timeout`, which is the signature of a surviving child. Make it a hard failure:

```toml
[profile.default]
leak-timeout = { period = "500ms", result = "fail" }
```

Set it explicitly rather than relying on the default. nextest's own documentation is inconsistent about that default — its configuration reference embeds 200ms while the leaky-tests page says 100 milliseconds — so pick a value comfortably above your slowest legitimate child shutdown and assert it in config.

Limitations worth knowing:

- Only children that **inherit stdout or stderr** are detected. A subprocess spawned with `Stdio::null()` is not detected today, and that gap is explicitly outside nextest's stability guarantees — it may be closed later.
- Detection is a heuristic with a timeout. A child that exits slightly after the test does may or may not be flagged depending on timing.

Do not suppress a `LEAK` status. It is real information about a resource your test did not release.

## Always drain or discard a child's output

`Stdio::piped()` gives the child a pipe with a finite buffer. If the test waits for the child to exit without reading that pipe, the child fills the buffer, blocks in `write`, and never exits — so the wait never returns. The standard library documents it: "If the child process fills its stdout buffer, it may end up waiting until the parent reads the stdout, and not be able to read stdin in the meantime, causing a deadlock."

```rust
// BAD - fine for a child that prints two lines, a hang for one that prints 100k
let mut child = Command::new("generate-fixtures").stdout(Stdio::piped()).spawn()?;
child.wait()?;                       // never reads the pipe

// GOOD - drains the pipe while it waits
let out = child.wait_with_output()?;

// GOOD - the test does not need the output, so do not create a pipe to fill
let mut child = Command::new("migrate-db").stdout(Stdio::null()).spawn()?;
child.wait()?;

// GOOD - chatty child, read it concurrently, and keep it killable on panic
let mut child = tokio::process::Command::new("reindex")
    .kill_on_drop(true)
    .stdout(tokio::process::Stdio::piped())
    .spawn()?;
let out = child.wait_with_output().await?;
```

Two details worth knowing. The buffer is finite, platform-dependent, and has moved across Rust versions — Linux pipes hold 64 KiB by default (rust-lang/rust#27152), and Windows anonymous pipes were smaller until rust-lang/rust#95782 raised them (#45572) — so the same test can pass on one platform and hang on another. And `Command::status()` spawns the program again rather than reporting on an earlier run, so calling `output()` and then `status()` executes the child twice; use `output()` once and read `Output::status`.

For a very chatty child, redirect to a file under the test's `tempdir()` and assert on the file. That also gives you the output when the child misbehaves.

## What a killed child leaves behind

Releasing a child and cleaning up after it are different things. `Child::kill` sends `SIGKILL` on Unix, which the child cannot catch, so nothing in its shutdown path runs: no final flush, no commit, no journal deletion, no lock release. What survives is durable and on disk — a rollback journal, a WAL or `-shm` sidecar, a half-written output file, an fsync that never happened.

The consequence for tests is narrow and sharp: **a test that kills a child and then reads what that child wrote is asserting on a crash artifact.** The failure it sees is about the kill, not about the writer's logic, and it is usually intermittent because it depends on whether the kill landed mid-write.

Two ways out, both cheap:

- **Wait for a clean exit.** Have the child exit on its own (`child.wait()`), and treat a hang as a hang. This is the better default, and when a child genuinely needs killing, do it in teardown after the assertions.
- **Assert on a copy.** Take the snapshot after the writer has exited — a file copy, or SQLite's `VACUUM INTO` — and assert on the copy. Now the assertion is about what the writer committed.

Neither requires giving up the kill. The rule is ordering: kill, then stop observing. Put the guard's `Drop` after the assertions, or scope it so it drops when the test body ends rather than before the reads.

## Databases another process writes

A test that reads an embedded database while a child process, a background task, or another test writes it adds a recovery problem on top of the contention problem.

**`SQLITE_OPEN_READ_ONLY` is a trap for assertions.** It reads as strictly safer than a read-write open — the connection cannot change anything — and it is the opposite. SQLite performs crash recovery by writing, so a read-only connection cannot roll back a hot journal. A store left in that state by a writer that died mid-transaction is not merely unwritable, it is *unreadable*, and the failure says so precisely: `SQLITE_READONLY_ROLLBACK`, extended result code `776` — "a database cannot be opened because it has a hot journal that needs to be rolled back but cannot because the database is readonly". The harness that chose the read-only flag so its assertions could not change anything is the one that cannot read the damage.

```rust
// BAD - cannot recover a hot journal, so it fails exactly when there is
// something interesting to look at
let conn = Connection::open_with_flags(&path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;

// GOOD - read-only by construction, recoverable when needed
let conn = Connection::open(&path)?;
conn.execute_batch("PRAGMA query_only = ON")?;

// GOOD - observe a committed snapshot, taken after the writer exited
child.wait()?;
let conn = Connection::open(snapshot_path)?;   // file copy or `VACUUM INTO`
```

Rules, for SQLite and for any store with a journal:

- **A read-only assertion should be a read-write connection with `query_only`**, or a copy taken after the writer exited. Never a read-only *open* on a store that anything might have left unrecovered.
- **A read after a kill is a read of crash state.** Either eliminate the crash state by waiting for a clean exit, or assert on something that does not depend on recovering it.
- **A helper built to observe state should be able to recover that state.** If the read path refuses to look at a dirty store, its whole purpose fails open.
- **Pin the classified code in the failure message.** `SQLITE_READONLY_ROLLBACK (776)` tells the next reader what happened without a documentation lookup; a rendered `readonly rollback` string does not.

The same shape applies to any store with a recovery journal, and to a WAL sidecar in particular: a `-shm` or `-wal` file that outlived its writer is what makes the failure look intermittent and cross-test.

## Filesystem semantics differ by platform

A test that passes on your machine and fails in CI is often assuming something about the filesystem rather than colliding with another test. The assumptions that break:

- **Case sensitivity.** APFS and HFS+ are case-insensitive by default on macOS; ext4 is case-sensitive. `Report.txt` and `report.txt` are one file on a Mac and two in Linux CI. Never use case, or Unicode normalization, to tell two paths apart — use a content difference, or a prefix that cannot be folded.
- **Unicode normalization.** macOS volumes are normalization-insensitive and return whichever form was stored, so a path with accents can come back byte-different from what you wrote. Assert on a path you control, or compare canonicalized forms.
- **Directory iteration order.** `read_dir` order is unspecified everywhere, and Apple's APFS FAQ is explicit that APFS returns filenames in hash order rather than lexicographic. Sort before asserting.
- **Name and path limits.** `NAME_MAX` is 255 bytes, `PATH_MAX` differs per platform, and Windows is lower again with reserved device names like `CON` and `NUL`. Keep fixture and temp paths short and ASCII; a long `tempfile` path plus a descriptive filename is how a test starts failing with `File name too long`.
- **Symlinked directories.** `/tmp` is a symlink to `/private/tmp` on macOS, so comparing a path as a string can fail while the file is right there. Canonicalize before comparing paths.

Fixture paths belong to the crate, not to the working directory. Build them with `Path::join` from `env!("CARGO_MANIFEST_DIR")`, never by concatenating strings and never from `std::env::current_dir()`:

```rust
// BAD - relative to whatever directory the runner happened to use
let fixture = PathBuf::from("tests/data/case.json");

// GOOD - resolved from the crate root, and joined rather than pasted
let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/data/case.json");
assert!(fixture.is_file(), "missing fixture: {}", fixture.display());
```

## Threads

`std::thread::spawn` also detaches on drop of the `JoinHandle`.

```rust
// BAD
std::thread::spawn(worker);

// GOOD
let handle = std::thread::spawn(worker);
// ... assertions ...
handle.join().expect("worker thread panicked");
```

In a nextest process-per-test world this matters less, because the process exit cleans up. It matters a great deal under `cargo test`, and for any thread holding a file lock or a port.

## Background work outliving the test

This is the subtle one, and it is a common cause of flakiness in storage and replication codebases.

A test can be logically finished while the system under test is still working: deletion is asynchronous, compaction is still flushing, replication is still streaming, a cache is still writing back. The test passes, the next test starts, and now two tests are competing for the same disk or network. The next test's timing assumptions break, and the failure looks unrelated.

Three options, in order of preference:

1. **Make the work awaitable** and await it before the test ends. Best, and often the correct production fix: a delete that has not completed should not report success.
2. **Use a test-mode path** that performs the work synchronously. Common for background reclaimers. Document why it is safe to do so in tests.
3. **Serialize with a test group.** Put the heavy-I/O tests in a group with `max-threads = 1`. This is containment; it makes the suite slower and leaves the real issue in place. Say so in a comment.

## Checklist

- [ ] Ports bound to `0`, and the assigned address passed to the client.
- [ ] All files under one `tempfile::tempdir()`.
- [ ] No `std::env::set_var` or `set_current_dir`, or contained in a serial test group with a comment.
- [ ] Subprocesses killed on drop; `kill_on_drop(true)` for tokio.
- [ ] Every piped child stream is drained (`wait_with_output`) or discarded (`Stdio::null()`); no parent waits on a child whose pipe nobody reads.
- [ ] Nothing this test kills leaves durable state that this test then reads — clean exit, or assert on a post-exit copy.
- [ ] No assumption that a filesystem is case-sensitive, normalization-preserving, or lexicographic; directory listings are sorted, fixture paths are short and built from `CARGO_MANIFEST_DIR`.
- [ ] A store this test reads but does not own is opened read-write with `query_only`, or read from a snapshot; never with a read-only open flag.
- [ ] `JoinHandle`s for every spawned thread and task, awaited before the test ends.
- [ ] `leak-timeout` configured to fail the build.
- [ ] Background work awaited, made synchronous, or explicitly grouped.
- [ ] Nothing written to a fixed shared path.
