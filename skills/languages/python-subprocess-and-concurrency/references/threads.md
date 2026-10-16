# Thread rules (`thread-`)

Verified against the CPython 3.14 `threading`, `concurrent.futures`, and free-threading documentation. Rule IDs match the quick reference in `SKILL.md`.

## thread-cannot-be-killed

**Prevents:** a teardown that silently destroys in-flight work, and a hang that nothing can interrupt.

Python's `Thread` "supports a subset of the behavior of Java's `Thread` class; currently, there are no priorities, no thread groups, and threads **cannot be destroyed, stopped, suspended, resumed, or interrupted**." There is no `kill()`. A thread ends by returning from its target, raising out of it, or the process exiting.

That makes daemon threads a trap. From the docs: "Daemon threads are abruptly stopped at shutdown. Their resources (such as open files, database transactions, etc.) may not be released properly. If you want your threads to stop gracefully, make them non-daemonic and use a suitable signalling mechanism such as an `Event`."

```python
# BAD: the transaction is abandoned mid-flight at exit, with no rollback
threading.Thread(target=writer_loop, daemon=True).start()

# GOOD: the thread owns its own shutdown and gets a chance to finish cleanly
stop = threading.Event()

def writer_loop(out: Path, stop: threading.Event) -> None:
    with out.open("a", encoding="utf-8") as handle:
        while not stop.is_set():
            item = work.get(timeout=0.25)      # wake regularly to re-check the flag
            handle.write(f"{item}\n")
            handle.flush()                     # a clean stop is a durable stop

worker = threading.Thread(target=writer_loop, args=(out, stop), name="writer")
worker.start()
...
stop.set()
worker.join(timeout=5)                         # bounded, but always joined
```

**Scope:** a daemon thread is defensible when losing its work at exit is genuinely harmless — a metrics flusher, a cache warmer, a sampler. The rule targets work whose interruption would corrupt state: transactions, partially written files, held locks, protocol streams.

**Overlap with `async-no-blocking-event-loop`:** that rule states the same fact for offloaded async work ("A running thread can't be interrupted... the thread itself always runs to completion"). It owns the statement in the asyncio context; this rule owns the lifecycle consequences — ownership, joining, cooperative stop, and what a daemon thread costs at shutdown.

## thread-own-and-join

**Prevents:** the most expensive thread bug there is — a worker that fails and takes its exception with it.

`threading.excepthook` is the only default reporting path for an uncaught exception raised by `Thread.run()`: the exception prints to `sys.stderr` and the thread is gone. Your program keeps running. Nothing you awaited learns about it, and a `stderr` dump is easy to miss in a service log.

```python
# BAD: if validate() raises, nobody hears about it; the "results" are just missing
threads = [threading.Thread(target=validate, args=(row,)) for row in rows]
for thread in threads:
    thread.start()
# no join(), and no error channel at all

# GOOD: results and exceptions come back through a future
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(validate, row) for row in rows]
    results = [f.result() for f in futures]     # the first real exception surfaces here
```

If you keep raw threads, join them and collect the outcome yourself, or install a hook that reports:

```python
def hook(args: threading.ExceptHookArgs) -> None:
    logger.error("thread %s failed", args.thread.name, exc_info=args.exc_value)

threading.excepthook = hook
```

Name your threads (`name=`; from 3.14 `Thread.start()` also sets the OS thread name) so a log line identifies the worker.

## thread-size-and-bound

**Prevents:** a pool sized by accident, and a task queue that grows without limit.

`max_workers=None` has real defaults — `min(32, (os.process_cpu_count() or 1) + 4)` since 3.13, and `min(32, os.cpu_count() + 4)` in 3.8-3.12 — but they are tuned for overlapping I/O, not for your downstream service. Say what you mean, and size from `os.process_cpu_count()` (affinity- and cgroup-aware, 3.13+) rather than `os.cpu_count()` (machine-wide, may be `None`).

Submission, not just worker count, needs a bound. `submit()` in a loop over unbounded input queues every task and retains every argument and result: the thread-side version of the `async-bound-concurrency` failure. Three shapes, depending on the source:

```python
# 1. Known finite input: bound the workers; the queue is finite by construction
with ThreadPoolExecutor(max_workers=max_parallel) as executor:
    results = list(executor.map(fetch, urls))

# 2. Very long or streaming input: window the submission so only ~N tasks exist
#    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
with ThreadPoolExecutor(max_workers=max_parallel) as executor:
    pending: set[Future[str]] = set()
    for url in url_stream:
        while len(pending) >= max_parallel * 2:            # backpressure
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                results.append(future.result())
        pending.add(executor.submit(fetch, url))

# 3. Producer/consumer: a bounded queue makes the producer wait, which is the point
work: queue.Queue[Item] = queue.Queue(maxsize=max_parallel * 4)
```

**Scope:** a fixed handful of tasks — three health checks — needs no ceremony. The rule triggers when fan-out scales with input the program did not author.

**Overlap with `async-no-blocking-event-loop`:** that rule states the default sizing formula (`min(32, cpu + 4)`, then the affinity-aware `process_cpu_count()` on 3.13+) for the executor behind `asyncio.to_thread`. The same numbers govern a pool you construct yourself, which is what this rule is about: the facts are theirs, the application to an explicitly configured pool is this rule's.

## thread-never-wait-on-a-future

**Prevents:** a self-inflicted pool deadlock that looks like a hang with no cause.

The docs document it directly. With `max_workers=1`:

```python
def wait_on_future() -> None:
    f = executor.submit(pow, 5, 2)   # queued behind the only worker: this one
    print(f.result())                # never returns

executor = ThreadPoolExecutor(max_workers=1)
future = executor.submit(wait_on_future)
future.result()                      # also deadlocks: the worker is busy waiting
```

With two workers, a symmetric pair deadlocks just as reliably: `a` waits on `b` while `b` waits on `a`. The general shape is *a worker waiting for work that needs a worker*. In real code it appears as a helper that calls back into the same executor, a nested `executor.map` inside a worker, or a retry wrapper that re-submits to the pool it is already running on.

```python
# BAD: process() executes inside a worker and submits back to the same pool
def process(item: Item) -> Result:
    return executor.submit(parse, item).result()

# GOOD: call the function directly inside the worker
def process(item: Item) -> Result:
    return parse(item)
```

If you need nested concurrency, use a separate executor you own, or restructure so the fan-out happens at a single level. A semaphore does not fix this; it only makes the deadlock smaller and less frequent.

## thread-for-io-not-cpu

**Prevents:** a "parallelized" CPU loop that runs no faster than the serial version, or slower.

Under the default build the GIL lets one thread execute Python bytecode at a time, so threads overlap *waiting*, not computing. Threads are the right tool when time goes into a blocking call that releases the GIL — sockets, file I/O, `time.sleep`, database drivers, and many C extensions. They are the wrong tool for pure-Python number crunching or data transformation.

```python
# BAD: no speedup; context switching can even make it slower than the loop
with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(parse_and_score, big_rows))

# GOOD: a process pool, where each worker has its own interpreter
with ProcessPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(parse_and_score, big_rows, chunksize=500))
```

Since 3.13 CPython also ships a **free-threaded build** (PEP 703), officially supported from 3.14 (PEP 779 phase II). There the GIL is gone and threads can scale CPU-bound Python. Detect rather than assume:

```python
import sys
import sysconfig

def threads_can_scale_cpu() -> bool:
    if sysconfig.get_config_var("Py_GIL_DISABLED") != 1:
        return False                       # with-GIL build: threads will not scale CPU work
    return sys._is_gil_enabled() is False  # runtime: the GIL can be re-enabled (PYTHON_GIL, -X gil)
```

A free-threaded interpreter runs with the GIL enabled if a C extension that is not marked free-threading-safe is imported — it warns when that happens. The build also carries overhead (roughly 10% single-threaded and 15-20% memory per the PEP 779 discussion). Measure before switching a workload.

**Scope:** the GIL is irrelevant to a thread that spends its life blocked in a GIL-releasing C call. "Threads don't scale CPU work" is about executing Python bytecode.

**Overlap with `async-no-blocking-event-loop`:** that rule reaches the same conclusion for offloaded work — pure-Python CPU-bound work gains nothing from a thread, so reach for a process pool, while GIL-releasing extensions and free-threaded 3.13+ builds do parallelize in threads. It owns the claim for the asyncio offload path; this rule owns it for code that uses threads directly, and adds what the async context does not need: detection (`Py_GIL_DISABLED`, `sys._is_gil_enabled()`).

## thread-share-by-message

**Prevents:** race conditions and torn reads that pass on a laptop and appear on an 8-core server.

Threads share the interpreter's memory, so every mutable object touched by two threads is potential shared state — including containers you never thought of that way (a module-level dict cache, a counter, a list you append to). Two rules cover most cases:

1. **Transfer ownership instead of sharing it.** Put data on a `queue.Queue` (thread-safe, and `maxsize` gives backpressure) and let one thread own it at a time.
2. **Guard it, narrowly.** If a structure must be shared and mutated, protect every access with the same lock, prefer cheap immutable swaps, and keep critical sections free of blocking calls.

```python
# BAD: read-modify-write with no lock; increments are lost nondeterministically
counts[key] = counts.get(key, 0) + 1

# GOOD: one owner, messages in; or guard every access consistently
with lock:                             # a plain threading.Lock is enough for one dict
    counts[key] = counts.get(key, 0) + 1
```

Locks add failure modes of their own:

- **Deadlock by ordering.** Two locks acquired in different orders will eventually deadlock. Pick a global order (by name, by id) and never violate it.
- **Holding a lock across unknown code.** Never call user code, I/O, or `Future.result()` while holding a lock: the callee may need the same lock. Prefer `with lock:` over manual `acquire()`/`release()` so an exception cannot leak the lock.

Per-thread state belongs in `threading.local()` (or `contextvars`, which also survives `asyncio.to_thread`), not in a dict keyed by `threading.get_ident()`.


## thread-no-pool-for-long-running-work

**Prevents:** a program that will not exit, or one that exits while abandoning work it refused to stop.

Two documented behaviors make a pool unsuitable as an application scheduler:

- "All threads enqueued to `ThreadPoolExecutor` will be joined before the interpreter can exit. Note that the exit handler which does this is executed **before** any exit handlers added using `atexit`. This means exceptions in the main thread must be caught and handled in order to signal threads to exit gracefully. For this reason, it is recommended that `ThreadPoolExecutor` **not be used for long-running tasks**."
- "Regardless of the value of `wait`, the entire Python program will not exit until all pending futures are done executing."

So a pool running long-lived tasks turns shutdown into a hang, and a pool whose tasks never finish keeps the process alive regardless of `shutdown(wait=False)`. For long-running workers, own plain threads with an `Event`, or hand supervision to something built for it.

```python
# BAD: the process cannot exit until every queue item is drained
with ThreadPoolExecutor(max_workers=4) as executor:
    for item in infinite_stream:
        executor.submit(handle, item)

# GOOD: threads the program controls, with a stop signal it can set
stop = threading.Event()
workers = [
    threading.Thread(target=handle_loop, args=(stop,), name=f"worker-{i}")
    for i in range(4)
]
for worker in workers:
    worker.start()
...
stop.set()
for worker in workers:
    worker.join(timeout=10)
```

**Scope:** for a batch job with a known end — a bounded set of tasks that must all complete before exit — the pool's join-on-exit behavior is exactly what you want. This rule is about long-running or unbounded work.

## thread-explicit-shutdown

**Prevents:** work that is silently cancelled, or a pool that is never released.

Use the executor as a context manager, or call `shutdown()` on every path. "Calls to `Executor.submit()` and `Executor.map()` made after `shutdown` will raise `RuntimeError`." The context manager runs `shutdown(wait=True)` on exit, which also means an exception inside the block waits for already-submitted work before it propagates.

```python
with ThreadPoolExecutor(max_workers=4) as executor:      # shutdown(wait=True) on exit
    futures = [executor.submit(job, i) for i in range(100)]
    for future in futures:
        future.result()
```

`cancel_futures=True` (3.9+) is narrower than it reads: "this method will cancel all pending futures that the executor has not started running. Any futures that are completed or running won't be cancelled". `Future.cancel()` behaves the same way and returns `False` once the work has started. There is no cancellation for a running thread — that is `thread-cannot-be-killed` again.

```python
# stop accepting work, then drop whatever never started
executor.shutdown(wait=False, cancel_futures=True)
```

**Scope:** library code should not own a module-level executor. Accept one as a parameter (dependency injection) so the application decides the pool's size and lifetime, and so tests can inject `max_workers=1` to serialize work deterministically.

