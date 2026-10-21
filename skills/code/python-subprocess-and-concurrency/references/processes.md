# Process rules (`proc-`)

Verified against the CPython 3.14 `multiprocessing` and `concurrent.futures` documentation, plus `os.fork`. Rule IDs match the quick reference in `SKILL.md`.

## proc-choose-start-method

**Prevents:** code that forks a threaded process (unsafe), and code whose behavior changes when the default changes.

`multiprocessing` supports three start methods, and the default moved in 3.14:

| Method | What the child gets | Default on |
|---|---|---|
| `spawn` | A fresh interpreter: only what `run()` needs, no inherited descriptors | Windows, macOS |
| `forkserver` | A single-threaded server process forks on request; no unnecessary resources inherited | POSIX platforms that pass fds over Unix pipes (Linux) — **became the default in 3.14** |
| `fork` | A copy of the whole parent, including every lock, thread, and descriptor | **Nowhere**: "This is no longer the default start method on any platform" (3.14) |

Forking a multithreaded process is unsafe, and it has been formally flagged since 3.12: "If Python is able to detect that your process has multiple threads, the `os.fork()` function that this start method calls internally will raise a `DeprecationWarning`. Use a different start method." The `os.fork` docs are blunter — the child inherits locks and allocator state from threads that do not exist in it, so "it has never been safe to mix threading with `os.fork()` on POSIX platforms", and deadlock is the usual symptom.

```python
# BAD: relies on whatever the interpreter picks, and breaks when that changes
with ProcessPoolExecutor() as executor: ...

# BAD: forks a process that has threads (a web server, a logging thread, a metrics thread)
with ProcessPoolExecutor(mp_context=multiprocessing.get_context("fork")) as executor: ...

# GOOD: name the method; spawn and forkserver are safe in threaded processes
ctx = multiprocessing.get_context("spawn")            # or "forkserver"
with ProcessPoolExecutor(mp_context=ctx) as executor: ...
```

Migration notes for the 3.14 change (from the release notes):

- If you *need* `fork`, request it explicitly via `get_context()` (preferred) or `set_start_method()`. Naming it is the point; inheriting it is not.
- `forkserver` and `spawn` require everything the child touches to be picklable and importable. Module-level mutable globals that `fork` used to copy now have to be passed or re-created — see `proc-inherit-dont-ship`.
- 3.14 also authenticated the forkserver's control socket, so filesystem permissions are no longer the only thing restricting who can ask it to spawn workers (gh-97514).
- `InterpreterPoolExecutor` (3.14+) sidesteps the question: separate interpreters with separate GILs, sharing no mutable state, inside one process.

## proc-main-guard

**Prevents:** recursively spawning processes until the machine gives up, and import-time side effects in every worker.

With `spawn` and `forkserver` the child imports your module to find the target, so module-level code runs again in every worker. The docs are explicit that the `if __name__ == "__main__":` part is "necessary", with the explanation in the programming guidelines.

```python
# BAD: this runs again at import time in each child, spawning more workers, forever
with ProcessPoolExecutor() as executor:
    results = list(executor.map(work, items))

# GOOD
def main() -> None:
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(work, items))

if __name__ == "__main__":             # the guard is the fix, not a formality
    multiprocessing.freeze_support()   # required for frozen executables (PyInstaller, cx_Freeze)
    raise SystemExit(main())
```

The same guard applies to raw `Process(...)`, `Pool(...)`, and any library call that starts processes for you. A library that spawns processes must not do it at import time — that is `imports-no-side-effects` from `python-best-practices`, with teeth.

## proc-top-level-and-picklable

**Prevents:** a `PicklingError`, or a mysterious `AttributeError: Can't get attribute`, that appears only after switching to processes.

Arguments and return values cross a process boundary, so they are pickled. "The arguments to `Process` usually need to be picklable so they can be passed to the child process." That excludes more than people expect:

| Works | Fails |
|---|---|
| Module-level functions | Lambdas, nested functions, closures |
| Plain data: `int`, `str`, `bytes`, `list`, `dict`, `dataclass` instances | Open sockets/files, DB connections, thread locks, generators |
| Classes importable by name in the worker | Classes defined inside a function, or in `__main__` of a script |
| Results returned as data | Live objects you expected to stay shared |

```python
# BAD: a lambda and a closure-returning factory are both unpicklable
executor.submit(lambda row: score(row, weight), row)
executor.submit(make_scorer(weight), row)

# GOOD: a module-level function plus explicit arguments
def score(row_id: int, weight: float) -> float: ...

executor.submit(score, row_id, weight)
```

Return plain data. A worker that returns a connection, a client, or a large object graph is asking you to serialize it — sometimes successfully, always expensively. Note the `__main__` case the docs call out: pasting a `Process` example into a REPL "could lead to an `AttributeError` in the child process trying to locate the `f` function in the `__main__` module." If something works under `fork` and fails under `spawn`, pickling is the reason.

## proc-inherit-dont-ship

**Prevents:** paying serialization cost per task, and rebuilding an expensive resource in every task instead of once per worker.

The docs' guidance is to avoid moving data between processes and, where a child needs a resource, to arrange for it to "inherit it from an ancestor process". In practice: use `initializer`/`initargs` for per-worker setup, and keep the hot loop free of setup work.

```python
# BAD: the object is unpicklable, and even if it were not, it would be shipped per task
with ProcessPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda rid: Client(dsn).fetch(rid), ids))

# GOOD: one client per worker process, created once at worker start
def init_worker(dsn: str) -> None:
    global _client
    _client = Client(dsn)

def fetch(row_id: int) -> Row:
    return _client.fetch(row_id)

if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=8, initializer=init_worker, initargs=(dsn,)) as executor:
        results = list(executor.map(fetch, ids, chunksize=200))
```

`initializer` "is an optional callable that is called at the start of each worker process". If it raises, "all currently pending jobs will raise a `BrokenProcessPool`, as well as any attempt to submit more jobs to the pool" — so a bad DSN fails loudly and immediately rather than intermittently.

**Scope:** under `fork`, a worker inherits the parent's memory, so a connection opened before the pool exists can appear to work. It is also a known way to corrupt data (several processes writing through one inherited socket). Treat inherited handles as shared-by-accident and open per-worker resources explicitly.

## proc-message-pass

**Prevents:** shared-state bugs that only appear once work moves into another process, and surprises about what is actually shared.

"When using multiple processes, one generally uses message passing for communication between processes and avoids having to use any synchronization primitives like locks." Pick the mechanism deliberately:

| Mechanism | Use for | Cost / caveat |
|---|---|---|
| `Queue` / `SimpleQueue` | Many producers and consumers | Everything is pickled; a background feeder thread flushes to a pipe |
| `JoinableQueue` | Work queues with completion tracking | You must call `task_done()` per item, or the internal semaphore eventually overflows |
| `Pipe` | A one-to-one connection between two processes | Not safe for multiple readers/writers at once |
| `Manager` proxies (`dict`, `list`, `set`, locks) | Shared mutable state across processes | Every access is a remote call through a manager process: much slower |
| `shared_memory` / shared ctypes | Large arrays read or written by several processes | You own the lifetime and the synchronization; needs a lock to be safe |
| `initializer` args / returned values | Per-worker setup and results | Pickled once, which is usually what you want |

Two documented traps worth pinning to the wall:

- "If a process is killed using `Process.terminate()` or `os.kill()` while it is trying to use a `Queue`, then the data in the queue is likely to become corrupted." This is `proc-stop-cooperatively`.
- A process that put items on a queue will not exit until the feeder thread has flushed them, so a consumer that stops reading can keep a producer alive forever. That is a deadlock built out of a shutdown ordering mistake.
- Avoid shared state entirely where you can: "As far as possible one should try to avoid shifting large amounts of data between processes."

```python
# BAD: shared dict mutated from several workers, no synchronization
shared = {}                               # a plain dict is a *copy* in each process

# GOOD: results come back as data; the parent owns the aggregate
with ProcessPoolExecutor() as executor:
    for row in executor.map(score, ids):
        aggregate.merge(row)
```

## proc-expect-a-broken-pool

**Prevents:** a single bad task silently taking down a whole pool, and a hang with no error.

From 3.3, "when one of the worker processes terminates abruptly, a `BrokenProcessPool` error is now raised. Previously, behaviour was undefined but operations on the executor or its futures would often freeze or deadlock." The same applies to a worker that fails to start with a bad `initializer` (`BrokenProcessPool`), or a thread worker that fails to initialize (`BrokenThreadPool`). All of them derive from `BrokenExecutor`, "raised when an executor is broken for some reason, and cannot be used to submit or execute new tasks."

A worker dies for reasons you cannot catch in Python: OOM killer, a segfault in a C extension, a `sys.exit()` in library code, a SIGKILL from an operator. Handle it as an expected operational event:

```python
from concurrent.futures import BrokenExecutor

try:
    with ProcessPoolExecutor(max_workers=8, initializer=init_worker, initargs=(dsn,)) as executor:
        results = list(executor.map(work, items, chunksize=100))
except BrokenExecutor as exc:
    logger.error("worker pool died; %d items unprocessed", len(items), exc_info=exc)
    raise
```

Mitigations for a worker that leaks or degrades over time: `max_tasks_per_child` (3.11+) "specifies the maximum number of tasks a single process can execute before it will exit and be replaced with a fresh worker process". Note the documented interaction: when it is set, the `spawn` start method is used by default in the absence of `mp_context`, and the feature "is incompatible with the `fork` start method."

**Scope:** a pool whose work is idempotent and restartable can retry a `BrokenExecutor` from a fresh pool. A pool halfway through a non-idempotent batch cannot; there, size the blast radius instead (small batches, checkpoints) so a dead worker costs you a batch, not the run.


## proc-stop-cooperatively

**Prevents:** corrupted shared queues, half-written output, and a shutdown path that only works on the happy path.

The docs warn that terminating a worker breaks everything it was holding: "Using the `Process.terminate` method to stop a process is liable to cause any shared resources (such as locks, semaphores, pipes and queues) currently being used by the process to become broken or unavailable to other processes. Therefore it is probably best to only consider using `Process.terminate` on processes which never use any shared resources." The queue warning is more specific: killing a process mid-`Queue` use "is likely to" corrupt the queue for everyone else.

So: give workers a cooperative stop, exactly like threads (`thread-cannot-be-killed`).

```python
import multiprocessing

def worker(work: multiprocessing.Queue, stop: multiprocessing.Event) -> None:
    while not stop.is_set():
        try:
            item = work.get(timeout=0.25)     # bounded get: re-check the flag between items
        except queue.Empty:
            continue
        handle(item)                          # finishes the current item, then exits cleanly
    # any flush/close belongs here, and it only runs because we did not terminate

if __name__ == "__main__":
    stop = multiprocessing.Event()
    proc = multiprocessing.Process(target=worker, args=(work, stop))
    proc.start()
    ...
    stop.set()
    proc.join(timeout=10)
    if proc.is_alive():
        proc.kill()                           # last resort: the worker is already unreachable
```

Two more constraints on the shutdown path:

- **Signals cannot be sent to a child's cooperative handler from arbitrary places.** Signal handlers can only be installed in the main thread of the main interpreter, so `Event` (or a queue message) is the portable stop channel. `Popen.send_signal`-style control does not exist for `multiprocessing.Process` beyond `terminate()`/`kill()`.
- **`Process.terminate()` skips `finally` blocks.** 3.14 added `Process.interrupt()`, which sends `SIGINT` instead, "which terminates the child process by sending SIGINT. This enables `finally` clauses to print a stack trace for the terminated process." If you must be abrupt and still want tracebacks, that is the tool. 3.14 also added `ProcessPoolExecutor.terminate_workers()` and `kill_workers()` to stop every live worker in a pool.
- **Zombie processes.** "On POSIX when a process finishes but has not been joined it becomes a zombie." Anything that starts children must join them — `active_children()` and starting a new process both reap finished ones as a side effect, but relying on that is not a plan.

## proc-bound-and-chunk

**Prevents:** a pool sized to the machine rather than to the work, and a `map` that materializes the entire input plus every result in memory.

`ProcessPoolExecutor(max_workers=None)` defaults to `os.process_cpu_count()`, and it raises `ValueError` for `max_workers <= 0` (on Windows it must be ≤ 61). Defaults are a starting point, not a decision: a memory-hungry worker needs fewer, an I/O-touching worker may want more.

```python
import os
from concurrent.futures import ProcessPoolExecutor

# BAD: os.cpu_count() is machine-wide and can be None; and chunking is left at 1
with ProcessPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
    results = list(executor.map(work, ids))

# GOOD: affinity-aware sizing, explicit chunking for a long iterable
with ProcessPoolExecutor(max_workers=os.process_cpu_count() or 1) as executor:
    results = list(executor.map(work, ids, chunksize=500))
```

Chunking is a first-class performance knob for processes, not a micro-optimization: "When using `ProcessPoolExecutor`, this method chops iterables into a number of chunks which it submits to the pool as separate tasks... For very long iterables, using a large value for `chunksize` can significantly improve performance compared to the default size of 1." Each chunk is one round trip through a pipe, so chunking amortizes IPC instead of payload. With `ThreadPoolExecutor` and `InterpreterPoolExecutor`, `chunksize` has no effect.

Two more memory notes:

- `map` "collected immediately rather than lazily" unless you pass `buffersize` (3.14+), which limits "the number of submitted tasks whose results have not yet been yielded" and pauses iteration when the buffer is full. Without it, `executor.map` over a huge iterable is the same unbounded-fan-out mistake as `submit` in a loop (`async-bound-concurrency`).
- Results are pickled back to the parent, so returning a 200 MB array per task costs two copies. Pass identifiers rather than payloads, and write large outputs to disk or `shared_memory` and return the handle.

```python
# Streaming results with a bound, instead of materializing everything
with ProcessPoolExecutor(max_workers=8) as executor:
    for row in executor.map(work, ids, chunksize=500, buffersize=64):  # buffersize: 3.14+
        consume(row)
```

**Scope:** the pool size for CPU-bound work should roughly match real usable cores, because oversubscribing adds context switching and memory pressure without adding throughput. For work that blocks on I/O inside the worker, a larger pool can be justified — the constrainer is the downstream service, not the CPU count.

