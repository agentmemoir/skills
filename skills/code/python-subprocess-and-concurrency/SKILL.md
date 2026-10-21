---
name: python-subprocess-and-concurrency
description: >-
  Subprocess and concurrency discipline for Python: how to run external programs
  safely, and how to pick the right concurrency model instead of the habitual
  one. Use when spawning processes with subprocess or asyncio subprocesses,
  writing threading or ThreadPoolExecutor code, using multiprocessing or
  ProcessPoolExecutor, sizing worker pools, bounding fan-out, or diagnosing
  deadlocks, hangs, orphaned children, and zombie processes. Covers argv vs
  shell, timeouts that kill the whole process tree, pipe deadlocks, start
  methods (spawn/forkserver/fork), pickling limits, GIL and free-threading, and
  cancellation. For event-loop and coroutine rules (TaskGroup, blocking calls,
  cancellation), use python-async-best-practices instead.
category: code
title: Python subprocess and concurrency
summary: >-
  Runs external programs safely and picks the right concurrency model instead of the habitual one.
  Covers argv vs `shell=True`, timeouts that kill the whole process tree, pipe deadlocks,
  `ThreadPoolExecutor` sizing, GIL and free-threading, multiprocessing start methods
  (spawn/forkserver/fork), pickling limits, and inter-process messaging, plus hang, orphan, and zombie
  diagnosis.
say: >-
  "Review this subprocess and threading code" or "Why is this Python script
  hanging?"
---

# Python Subprocess & Concurrency

Two topics that produce the same class of bug — a program that passes every smoke test and then hangs, leaks children, or silently drops failures under load. 29 rules in 3 categories.

A rule match is a signal, not a verdict. Concurrency advice is context-dependent: a fixed handful of tasks needs no ceremony, and a `fork` pool is still fine in a single-threaded program. Check the rule's scope line before flagging or refactoring.

## Scope: what this skill owns, and what it defers

| Topic | Owner |
|---|---|
| `subprocess`: argv, timeouts, killing trees, pipes, exit codes | **this skill** (`sp-` rules) |
| `threading`, `concurrent.futures` threads | **this skill** (`thread-` rules) |
| `multiprocessing`, `ProcessPoolExecutor`, start methods, IPC | **this skill** (`proc-` rules) |
| `asyncio` event-loop discipline, tasks, cancellation, generators | `python-async-best-practices` |
| The offload decision itself: GIL vs threads vs process pool, default executor sizing, thread non-interruptibility | `python-async-best-practices`, rule `async-no-blocking-event-loop` |
| General Python style, typing, error handling, dataclasses | `python-best-practices` |
| Test determinism and synchronization | `python-pytest`, rule `determinism-sync-not-sleep` |

Do not restate the deferred skills' rules here. Where they overlap, this skill states the *same* principle in the process/thread domain and names their rule (for example `async-bound-concurrency` for bounded fan-out, `determinism-sync-not-sleep` for concurrency tests).

Read the ownership honestly before claiming a gap. `async-no-blocking-event-loop` already covers the offload decision, the `min(32, cpu + 4)` then `process_cpu_count()` executor-sizing formula, free-threaded 3.13+ builds, and the fact that a running thread cannot be interrupted. `thread-for-io-not-cpu`, `thread-size-and-bound` and `thread-cannot-be-killed` go deeper on those for code that never touches asyncio, and each names that rule as the earlier statement rather than claiming the ground.

What is genuinely uncovered upstream, and owned here: `subprocess` in full; thread ownership, join and `excepthook`; lock discipline and pool deadlocks; `ThreadPoolExecutor` exit semantics; multiprocessing start methods, pickling, IPC and pool failure; and hang, orphan and zombie diagnosis.

## Pick the model before writing code

The most expensive concurrency mistake is choosing a model out of habit. Choose by what the work waits on and whether it can run in parallel.

| The work | Model | Why |
|---|---|---|
| Nothing that can overlap | plain loop | Concurrency is pure cost: workers and failure modes for zero gain |
| Many blocking I/O calls on async-capable libraries | `asyncio` | See `python-async-best-practices`; thousands of concurrent operations, no thread per op |
| Blocking I/O with libraries that have no async equivalent | `ThreadPoolExecutor` | Simplest tool that overlaps the wait |
| Pure-Python CPU work | `ProcessPoolExecutor` / `multiprocessing` | The GIL serializes bytecode; processes do not share it |
| CPU work inside a C extension that releases the GIL | threads | The GIL is not the limit for that call |
| CPU work, free-threaded build (`Py_GIL_DISABLED=1`) | threads | No GIL to serialize them (PEP 703/779); measure, and confirm C extensions did not re-enable it |
| Thousands of small CPU tasks with little shared state | `InterpreterPoolExecutor` (3.14+) | Each interpreter has its own GIL: multicore parallelism without process startup |
| An external program, script, or CLI | `subprocess` | It is a separate process whether you like it or not |

Sizing facts worth knowing (verified against the 3.14 standard-library docs):

- `os.process_cpu_count()` (3.13+) is the count usable by *this* process — it respects CPU affinity and container limits. `os.cpu_count()` is machine-wide and can return `None`. Use the former for pool sizing.
- `ThreadPoolExecutor(max_workers=None)` defaults to `min(32, (os.process_cpu_count() or 1) + 4)`.
- `ProcessPoolExecutor(max_workers=None)` defaults to `os.process_cpu_count()`, capped at 61 on Windows.
- `InterpreterPoolExecutor` is a `ThreadPoolExecutor` subclass: one worker thread each, one interpreter each. Interpreters cannot share a mutable object, so it forces an explicit data contract.

## Quick reference

### Subprocess (`sp-`)

- `sp-argv-not-shell` — Pass an argv sequence; never interpolate values into `shell=True`
- `sp-check-and-capture` — `check=True` (or read `returncode` explicitly); `check` defaults to `False`
- `sp-timeout-always` — Every wait has a timeout; `run(timeout=)` kills only the direct child
- `sp-kill-the-process-tree` — `start_new_session=True` + `os.killpg` to actually stop descendants
- `sp-communicate-not-wait` — Use `communicate()` with pipes; `.wait()`/`.read()` deadlocks, and a surviving descendant keeps EOF from arriving
- `sp-popen-only-when-needed` — `run()` by default; `with Popen` waits, it does not kill
- `sp-close-stdin` — `stdin=DEVNULL` for non-interactive children
- `sp-explicit-env-and-cwd` — Full executable path, explicit `cwd` and `env`
- `sp-explicit-text-encoding` — `encoding="utf-8"`, never the locale by accident
- `sp-no-preexec-fn` — `preexec_fn` is thread-unsafe; use `start_new_session`/`process_group`
- `sp-bound-child-fanout` — One child per input item is unbounded fan-out
- `sp-drop-legacy-apis` — Not `os.system`, `os.popen`, `os.spawn*`, `getstatusoutput`
- `sp-async-children` — In async code use `create_subprocess_exec` + `asyncio.timeout`

### Threads (`thread-`)

- `thread-cannot-be-killed` — No stop/suspend; stop cooperatively, and not with daemon threads
- `thread-own-and-join` — Join every thread or use an executor; a failed thread prints and vanishes
- `thread-size-and-bound` — Set `max_workers`; bound submission the way `async-bound-concurrency` bounds fan-out
- `thread-never-wait-on-a-future` — A worker waiting on another future deadlocks the pool
- `thread-for-io-not-cpu` — Threads do not speed up pure-Python CPU work
- `thread-share-by-message` — Pass data, guard shared mutable state, keep locks short and ordered
- `thread-no-pool-for-long-running-work` — The exit handler joins threads before `atexit`; a pool is not a scheduler
- `thread-explicit-shutdown` — Context manager or explicit `shutdown()`; `cancel_futures` only reaches queued work

### Processes (`proc-`)

- `proc-choose-start-method` — Name the start method; `fork` is no longer a default anywhere
- `proc-main-guard` — `if __name__ == "__main__":` plus `freeze_support()`
- `proc-top-level-and-picklable` — Workers are module-level functions; args and results are pickled
- `proc-inherit-dont-ship` — Set up each worker in `initializer`; inherit resources instead of shipping them
- `proc-message-pass` — Queues for data, `Pipe` for one-to-one, proxies sparingly
- `proc-expect-a-broken-pool` — A killed worker breaks the whole pool; catch `BrokenExecutor`
- `proc-stop-cooperatively` — Terminating a worker corrupts shared queues; signals are main-thread-only
- `proc-bound-and-chunk` — Size the pool yourself; `chunksize` matters, `map` collects eagerly


## The patterns that carry most of the weight

**Every external command, in one shape.** Argv, closed stdin, explicit encoding, timeout, checked exit code:

```python
import subprocess

def git_rev(path: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", path, "rev-parse", "HEAD"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )
    return result.stdout.strip()
```

**A timeout that stops the whole tree.** `run(timeout=)` kills only the direct child; anything it spawned keeps running and keeps holding your resources.

```python
import os
import signal
import subprocess

def run_tree(argv: list[str], *, timeout: float, grace: float = 5.0) -> int:
    # start_new_session=True puts the child in its own session, so its process
    # group id equals its pid: one killpg stops the child and every descendant.
    proc = subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)      # ask the whole group to stop
        try:
            proc.wait(timeout=grace)             # give it a moment to exit cleanly
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)  # then stop asking
            proc.wait()                          # always reap
        raise
```

**Bounded child fan-out.** One child per input item is a fork bomb dressed as a loop:

```python
from concurrent.futures import ThreadPoolExecutor
import subprocess

def run_all(argv_list: list[list[str]], *, max_parallel: int = 8) -> list[str]:
    def one(argv: list[str]) -> str:
        done = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8",
            timeout=60, check=True,
        )
        return done.stdout

    # max_workers bounds how many children exist at once. Same principle as
    # async-bound-concurrency, applied to processes instead of coroutines.
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        return list(executor.map(one, argv_list))
```

**Shutdown you can predict.** A daemon thread is killed mid-work at interpreter exit; a worker pool joins what it accepted.

```python
from concurrent.futures import ThreadPoolExecutor

def handle(item: str) -> None: ...

with ThreadPoolExecutor(max_workers=4) as executor:   # shutdown(wait=True) on exit
    futures = [executor.submit(handle, item) for item in items]
    for future in futures:
        future.result()   # never let a worker's exception disappear
```

**Per-worker setup, results as plain data.** Both executors give you a one-time per-worker hook; use it instead of reopening a connection per task, and return data instead of shipping live objects:

```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

_conn = None                      # assigned once per worker by init_worker()

def init_worker(dsn: str) -> None:
    global _conn
    _conn = connect(dsn)          # opened once per worker process, not once per task

def score(row_id: int) -> float:
    return _conn.query(row_id)    # must be importable at module top level to be picklable

if __name__ == "__main__":        # required by the spawn and forkserver start methods
    ctx = multiprocessing.get_context("spawn")   # name it; never inherit the default blindly
    with ProcessPoolExecutor(max_workers=8, mp_context=ctx,
                             initializer=init_worker, initargs=(dsn,)) as executor:
        results = list(executor.map(score, row_ids, chunksize=200))
```

## Debugging a hang

A hang is a missing timeout, a full pipe, or a lock. In that order.

- Get a stack out of a live process: `faulthandler.dump_traceback_later(60, exit=True)`, or run with `python -X faulthandler`. It is implemented in C, so it still reports during a deadlock in Python code.
- `py-spy dump --pid <pid>` prints every thread's stack without restarting the process; `py-spy top --pid <pid>` shows what is burning CPU; `--locals` adds frame locals. In containers it needs the `SYS_PTRACE` capability.
- `threading.enumerate()` lists thread objects that are still alive; `multiprocessing.active_children()` does the same for children.
- Orphans and zombies point at the opposite mistakes: a child outliving its parent means the wrong thing was killed (`sp-kill-the-process-tree`), and an unreaped child means nobody joined it (`thread-own-and-join`, `proc-main-guard`).

Commands and diagnosis order: `references/debugging-hangs.md`.

## Review checklist

- [ ] Every `subprocess` call passes an argv sequence, and `shell=True` appears nowhere.
- [ ] Every call sets `check=True` or inspects `returncode` deliberately.
- [ ] Every call has a timeout, and a timed-out child cannot leave descendants running or holding its pipes open.
- [ ] No `.read()`, `.stdin.write()`, or `.wait()` against a `PIPE`; `communicate()` is used.
- [ ] `encoding` is explicit when text mode is used.
- [ ] `stdin=DEVNULL` (or explicit `input=`) for anything non-interactive.
- [ ] Executable path, `cwd`, and `env` are explicit where the result must be reproducible.
- [ ] No `preexec_fn`.
- [ ] Fan-out is bounded: at most N children or N workers, chosen from a real downstream limit.
- [ ] No `os.system`, `os.popen`, `os.spawn*`, or `subprocess.getstatusoutput`.
- [ ] Every thread is joined, or lives in an executor that is shut down.
- [ ] No daemon thread owns work whose interruption would corrupt state.
- [ ] No worker waits on another task's future.
- [ ] Shared mutable state across threads is message-passed or guarded; locks are acquired in one global order and never held across a blocking call.
- [ ] CPU-bound work in threads is justified by a free-threaded build or a GIL-releasing extension.
- [ ] Pool sizing is explicit, and uses `os.process_cpu_count()` (3.13+) rather than `os.cpu_count()`.
- [ ] The multiprocessing start method is named explicitly, and `fork` is not used in a threaded process.
- [ ] Worker functions are module-level and picklable; args and results are plain data.
- [ ] `if __name__ == "__main__":` guards the entry point of anything that spawns processes.
- [ ] `BrokenExecutor` / `BrokenProcessPool` is handled where a worker can die.
- [ ] Shutdown is cooperative for threads and processes; `terminate()` is not used on workers holding shared queues.

## References

- `references/subprocess.md` — the `sp-` rules with failure modes, code, and platform notes.
- `references/threads.md` — the `thread-` rules: GIL, free-threading, ownership, locks, pool behavior.
- `references/processes.md` — the `proc-` rules: start methods, pickling, IPC, pool lifecycle.
- `references/debugging-hangs.md` — hang, deadlock, orphan, and zombie diagnosis with commands.

Run `scripts/verify-recipes.py` to re-check this skill's recipes and version claims on the interpreter you have (repo tooling, wired into `npm test`; execute it, do not read it into context). It prints one line per check naming the rule it backs, skips POSIX-only checks off POSIX, and asserts the documented API floor for your Python version.

Standards this follows: [PEP 324](https://peps.python.org/pep-0324/) (subprocess), [PEP 703](https://peps.python.org/pep-0703/) and [PEP 779](https://peps.python.org/pep-0779/) (free-threading; officially supported in 3.14), [PEP 3148](https://peps.python.org/pep-3148/) (`concurrent.futures`), [PEP 734](https://peps.python.org/pep-0734/) (interpreters). Cross-skill: `python-async-best-practices`, `python-best-practices`, `python-pytest`.

