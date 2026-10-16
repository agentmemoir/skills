# Async Test Deep Dive

Everything about testing code that runs on the Tokio runtime: choosing a runtime, controlling time, waiting correctly, and cleaning up background work.

## Runtime choice

`#[tokio::test]` builds a **current-thread** runtime by default. That is the right default: a single-threaded runtime schedules predictably, which removes a whole category of nondeterminism.

```rust
#[tokio::test]                              // current-thread, the default
async fn my_test() { /* ... */ }

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn my_concurrent_test() { /* ... */ }  // opt in deliberately
```

Rules:

- Do not reach for `multi_thread` because the production code uses it. You are testing logic, not the scheduler. Most logic tests are more reliable single-threaded.
- If you do need multiple threads, set `worker_threads` explicitly. The default scales with the machine, so the same test gets different parallelism on a laptop and on a CI runner — and a race that needs exactly 4 threads to appear will hide on your 16-core desktop.
- `start_paused = true` requires the current-thread runtime. Combining it with `flavor = "multi_thread"` panics at runtime with a message about `time::pause()` requiring a current-thread runtime.

## Feature setup

```toml
[dev-dependencies]
tokio = { version = "1", features = ["macros", "rt", "time", "sync", "test-util"] }
```

`test-util` is what makes `start_paused`, `tokio::time::pause()`, and `tokio::time::advance()` available. Without it the test panics on startup with a feature-flag message rather than anything resembling a useful error.

## Paused time

### The core behaviour

When time is paused and the runtime has no work to do, it jumps the clock forward to the next scheduled timer. The condition for jumping is that no other future can make progress. So a `sleep` in a paused test costs essentially no wall-clock time and cannot expire early.

```rust
#[tokio::test(start_paused = true)]
async fn expires_after_ttl() {
    let item = Cache::new();
    item.insert("k", "v", ttl: Duration::from_secs(60));

    tokio::time::sleep(Duration::from_secs(59)).await;
    assert!(item.get("k").is_some());

    tokio::time::sleep(Duration::from_secs(2)).await;
    assert!(item.get("k").is_none());
}
```

Both sleeps return immediately. The test asserts real TTL behaviour in microseconds of real time.

### `advance` versus `sleep`

This trips people up, and the official guidance is specific:

**Use `sleep` for almost everything.** Auto-advance processes timers in order and waits for them, so it is reliable.

**`tokio::time::advance(d)` is for jumping the clock without waiting.** It moves the instant forward in one jump, so every timer with a deadline before the new time becomes ready *at the same time*, and the runtime is free to poll them in any order. It does not wait for them to complete.

Consequences:

- To reliably trigger a timeout, use `sleep` and let auto-advance do the work — not `advance`. A test that uses `advance` to force a timeout can run before the timeout task has actually been polled.
- To simulate a pause and resume, `advance` is wrong: all timers expiring during the jump fire simultaneously, which is not what a freeze looks like.
- `advance` panics on a very large duration due to overflow. Keep durations realistic.

```rust
// Reliable: sleep, let auto-advance fire timers in order
#[tokio::test(start_paused = true)]
async fn timeout_fires() {
    time::sleep(Duration::from_secs(5)).await;
    // all timers scheduled within 5s have now been processed
}

// Use advance only when you deliberately want an instant jump
#[tokio::test(start_paused = true)]
async fn jumps_past_deadline() {
    time::advance(Duration::from_secs(3600)).await;
    assert!(clock.now() >= deadline);
}
```

### Keeping the clock still during real I/O

Auto-advance stops while a `spawn_blocking` task runs, which is what you want when the test does genuine I/O and you do not want the clock racing ahead.

```rust
#[tokio::test(start_paused = true)]
async fn writes_to_disk() {
    let start = Instant::now();
    // clock does NOT auto-advance while this blocking task runs
    task::spawn_blocking(|| real_file_write()).await.unwrap();
    assert_eq!(start.elapsed(), Duration::ZERO);
}
```

**The trap that costs people hours:** a long-lived `spawn_blocking` task — a background database handle, an infinite worker — makes the runtime believe it always has work, so it never auto-advances and every timer in the test hangs forever. If paused time mysteriously stops working, look for a `spawn_blocking` task that never finishes. Moving that work to `std::thread::spawn` resolves it.

## Never block the executor

A synchronous call inside an async task stops the whole runtime, and on the default current-thread runtime that means the only thread. Timers stop firing, the I/O driver stops polling, and every other task in the test stops making progress. `std`'s documentation is blunt about the canonical case: `thread::sleep` "is blocking, and should not be used in async functions".

```rust
// BAD - on a current-thread runtime this freezes everything for 100ms,
// including the timers and the I/O driver you are waiting on
std::thread::sleep(Duration::from_millis(100));
let data = std::fs::read_to_string(path)?;      // same problem, unbounded duration
let mut stream = std::net::TcpStream::connect(addr)?;

// GOOD - await points instead of blocking calls
tokio::time::sleep(Duration::from_millis(100)).await;
let data = tokio::fs::read_to_string(path).await?;
let mut stream = tokio::net::TcpStream::connect(addr).await?;
```

The blocking members of the standard library have async counterparts: `tokio::time::sleep`, `tokio::fs`, `tokio::net`, `tokio::process::Command`, and `tokio::sync::Mutex` (a `std::sync::Mutex` held across an `.await` blocks the whole runtime and can deadlock it against itself).

When the work genuinely cannot be async — a synchronous SQLite call, an FFI boundary, a CPU-bound loop — move it to the blocking pool and await it:

```rust
// GOOD - the offload is bounded and awaited, so the runtime keeps running
let rows = tokio::task::spawn_blocking(move || query_blocking(&path)).await??;
```

Two constraints on `spawn_blocking`, both of which bite in tests:

- It **cannot be cancelled**. Dropping the `JoinHandle` does not stop the work; it keeps running and holding whatever it holds.
- While a blocking task is alive, the runtime believes it has work, so **paused time stops auto-advancing** and every timer in a `start_paused` test hangs. If paused time mysteriously stops working, look for a `spawn_blocking` that never returns. For a long-lived background handle, `std::thread::spawn` is the right tool.

A lint pass is worth it: `clippy::await_holding_lock`, plus a grep for `thread::sleep` and `std::fs::` inside `async fn`, finds most of these before review does.

## Waiting correctly

### Good: signals

```rust
// Notify - one waiter
let notify = Arc::new(Notify::new());
notify.notified().await;

// Channel - one value, natural ownership transfer
let (tx, rx) = mpsc::channel(1);
rx.recv().await;

// Broadcast - many waiters
let (tx, mut rx) = tokio::sync::broadcast::channel(16);
rx.recv().await;
```

### Bad: `yield_now()` as synchronization

```rust
// WRONG - this is a busy-wait wearing a disguise
while !ready.load(Ordering::Relaxed) {
    tokio::task::yield_now().await;
}
```

`yield_now` hands control back to the scheduler without waiting for anything. In a single-threaded test it often appears to work. Under a full parallel suite, the task that would set `ready` may not be scheduled before your test's own timeout expires, and you get a failure that depends on machine load.

### Acceptable: bounded polling

When there is genuinely no signal to wait on, poll a condition against a generous deadline.

```rust
async fn wait_for<F, T>(mut cond: F) -> T
where
    F: FnMut() -> Option<T>,
{
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        if let Some(v) = cond() {
            return v;
        }
        assert!(Instant::now() < deadline, "condition not met within 10s");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}
```

Under `start_paused = true` this still costs no real time, because auto-advance jumps between polls. The deadline is what makes it safe rather than an infinite hang.

## Background tasks

### Every spawn needs an owner

```rust
// BAD - detached. The task is killed when the runtime drops at test end,
// possibly mid-write or holding a lock.
tokio::spawn(background_loop());

// GOOD - owned and awaited
let handle = tokio::spawn(background_loop());
// ... exercise the code ...
handle.await.expect("background task panicked");
```

### Long-lived tasks: cancel, then join

```rust
let cancel = CancellationToken::new();
let task = tokio::spawn({
    let cancel = cancel.clone();
    async move {
        loop {
            tokio::select! {
                _ = cancel.cancelled() => break,
                _ = tick() => do_work(),
            }
        }
    }
});

do_work_that_needs_the_loop().await;
cancel.cancel();
task.await.expect("shutdown failed");
```

The `cancel()` followed by `await` pair is the whole pattern. Cancelling without awaiting leaves the task running; awaiting without cancelling hangs.

A guard type whose `Drop` does both is the robust form when many tests need the same setup.

### Symptom to recognise

If a test passes alone but breaks a *later* test, suspect an unowned spawn. Under `cargo test` all tests share a process, so the damage spreads visibly. Under nextest each test is its own process, so the same bug shows up as that single test failing mysteriously or as a `LEAK` status.

## Cancellation safety

`tokio::select!` drops every future that does not win the race. If a dropped future was halfway through a mutation, its state is inconsistent unless it is explicitly cancellation-safe.

```rust
// The send branch may have partially written before being dropped.
tokio::select! {
    _ = write_to_disk(&mut buf) => {}
    _ = cancel.cancelled() => return,
}
```

Guidance:

- Make the state transition atomic and idempotent, so an interrupted attempt can simply be retried. This is usually the cheapest fix.
- Avoid mutating shared state across an await point inside a `select!` branch. Do the mutation after the await.
- Check the documented cancellation safety of any library method you use in a `select!`. Tokio documents it per method; assume nothing about your own futures.

To force the branches to win in different orders and expose the bug, add a yield or a small sleep into each branch in turn, then loop the test. If the outcome changes with which branch wins, you have found a cancellation-safety defect.

## Diagnosing a hang

When an async test hangs rather than fails:

1. Decide *never finished* versus *took too long*. `tokio-console` shows every task, its state, and its poll count. A task whose poll count is frozen while everything else is idle is blocked, not starved — that is a blocking call on the executor. A task whose busy count climbs while its poll count stalls is spinning without progress, the `yield_now()` signature.
2. Check for a `spawn_blocking` task that never returns. It blocks auto-advance and looks exactly like a hang.
3. Check for a subprocess whose output nobody reads. A parent that waits without draining the child's pipe deadlocks once the child produces more than the pipe buffer holds — see `isolation-and-resources.md`.
4. Set an explicit `timeout` around the body so a hang becomes a failure with a message.
5. Under nextest, `slow-timeout` with `terminate-after` bounds it from the outside.
