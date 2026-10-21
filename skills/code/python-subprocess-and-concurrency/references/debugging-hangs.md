# Debugging a hang, a deadlock, an orphan, or a zombie

A hang is almost always one of three things, in this order of likelihood: **a wait with no timeout**, **a full pipe nobody drains**, **a lock someone else holds**. Identify which before reaching for a debugger — two of the three are preventable by construction rather than diagnosable after the fact.

## Get a stack out of a live, stuck process

`faulthandler` is in the standard library, implemented in C, and still reports when the interpreter is deadlocked in Python code.

```python
import faulthandler
faulthandler.enable()                      # SIGSEGV, SIGFPE, SIGABRT, SIGBUS, SIGILL

# A watchdog: dump every thread's stack if we are still running in 60 seconds
faulthandler.dump_traceback_later(60, repeat=True, exit=True)
```

Or without touching the code:

```bash
python -X faulthandler -m myapp          # -X dev also enables it, plus extra warnings
PYTHONFAULTHANDLER=1 python -m myapp     # same, for anything you cannot edit
python -m myapp &
kill -ABRT <pid>                         # triggers the fatal-error dump
```

Key facts from the docs:

- `dump_traceback_later(timeout, repeat=False, file=sys.stderr, exit=False)` dumps all threads after a timeout, or every `timeout` seconds when `repeat=True`; it "is implemented using a watchdog thread", so it fires while the main thread is blocked. `exit=True` calls `_exit(1)` right after dumping.
- `faulthandler.register(signum, file=sys.stderr, all_threads=True, chain=False)` dumps on demand (for example `SIGUSR1`) without killing the process. Not available on Windows.
- `faulthandler.dump_traceback(all_threads=True)` can be called from anywhere, including a signal handler or a watchdog thread.
- Dumps are minimal by design: filename, function, line number, no source, ASCII only, capped at 100 frames and 100 threads. That is plenty to see *which* wait is stuck.
- The `file` you pass must stay open until the dump happens, or until `cancel_dump_traceback_later()` / `unregister()` is called.
- 3.14 adds `faulthandler.dump_c_stack()`, which shows the C stack of the current thread when the Python stack is not the interesting one.

## Sample a live process without restarting it

`py-spy` reads another process's interpreter state from outside, which is what you want on production or on a process you cannot relaunch:

```bash
pip install py-spy        # or: brew install py-spy

py-spy dump --pid 12345                    # every thread's stack now — the "where is it stuck" tool
py-spy top --pid 12345                     # live view of what is burning CPU
py-spy record -o profile.svg --pid 12345   # flame graph; or `-- python app.py` to launch and profile
```

- `dump` is the tool for a hang; `top` answers "spinning or blocked?"; `record --format speedscope` gives you a shareable artifact.
- `--locals` adds local variables to the dump. It is the most intrusive option: use it deliberately, not by default.
- `--nonblocking` avoids pausing the target, at the cost of occasional partial frames.
- In containers it needs `SYS_PTRACE`; in Kubernetes, add the capability or use `kubectl debug --profile=general` in an ephemeral container.

## Inventory the threads

```python
import sys
import threading

for thread in threading.enumerate():
    frame = sys._current_frames().get(thread.ident)
    print(thread.name, thread.daemon, thread.is_alive(), frame.f_lineno if frame else None)
```

`threading.enumerate()` "returns a list of all alive threads", and `sys._current_frames()` maps a thread id to the frame it is executing. A thread that is alive with a frame parked in `lock.acquire`, `queue.get`, or `future.result()` is your culprit. Note that under the GIL one thread runs while the others wait, so "all threads look idle" usually means "one thread holds something".

To make a deadlock name its own participants, use a bounded acquire while diagnosing:

```python
if not lock.acquire(timeout=5):
    logger.error("lock %r not acquired in 5s; another thread holds it", lock)
```

That log line is worth more than any tool, because it is present in production when the hang happens.

## Orphans and zombies

These are opposites, and the fix for each is different.

| Symptom | What happened | Fix |
|---|---|---|
| Children keep running after your program exits, or after a timeout | You killed the direct child rather than its process group, or never signaled it at all | `sp-kill-the-process-tree`: `start_new_session=True` + `os.killpg`, SIGTERM then SIGKILL |
| Processes in `Z` (zombie) state | A child exited and nobody called `wait()`/`join()` on it | Join every child; `multiprocessing.active_children()` and starting a new process reap as a side effect, but do not rely on it |
| A worker vanishes mid-batch and futures raise `BrokenExecutor` | The worker was killed: OOM, segfault in a C extension, external `SIGKILL` | `proc-expect-a-broken-pool`; consider `max_tasks_per_child` for leaky workers |
| A thread or process is still alive after `shutdown()` | A daemon thread, or a pool task that ignores the stop flag | `thread-cannot-be-killed`, `proc-stop-cooperatively` |
| A child holds a lock file, port, or temp directory you thought you released | Same as the first row: descendants that were never killed | Kill the group, then clean up state on startup instead of assuming teardown worked |

```bash
# Who is whose child, and who is a zombie?
ps -o pid,ppid,stat,etime,command -p "$(pgrep -d, -f myapp)"

# What is that child holding open?
lsof -p 12345 | head
ls -l /proc/12345/fd 2>/dev/null | head
```

`STAT` starting with `Z` is a zombie; a child whose `PPID` is 1 has been reparented after its parent died. Both mean somebody is not joining what they started.

## Pipes and buffers

A child that never exits is often a child that cannot write any more output. Check for an unread `PIPE`:

- Is anything reading `proc.stdout`? `communicate()` is the only safe pattern (`sp-communicate-not-wait`).
- Did `communicate()` time out and the code then call `wait()`? That is the documented mistake; kill, then call `communicate()` again.
- Is the child a shell pipeline whose downstream process already exited? A `SIGPIPE` may have been swallowed by a restored signal disposition (`restore_signals` defaults to `True`, which resets `SIGPIPE`, `SIGXFZ`, and `SIGXFSZ` to `SIG_DFL` in the child — the opposite case is a child that inherited an ignored `SIGPIPE`).
- Is the output unbounded? `communicate()` buffers in memory, so a huge output hangs on memory rather than on the pipe.
- Did you kill only the direct child while a descendant inherited the pipe? The write end stays open, so `communicate()` waits for an EOF that never comes. Kill the process group, then drain (`sp-kill-the-process-tree`).

## Make hangs impossible instead of debugging them

The cheapest fix is structural, and it is the point of the rules in this skill:

1. Every wait has a timeout: `Popen.wait`, `communicate`, `run`, `Future.result(timeout=...)`, `Queue.get(timeout=...)`, `Lock.acquire(timeout=...)`.
2. Every timeout has a cleanup path that terminates the child, the group, or the pool.
3. Every thread and process is joined or shut down, so "still alive" is never an expected end state.
4. Fan-out is bounded, so a slow downstream becomes backpressure instead of a pile of stuck workers.

Then a hang turns into a timeout error with a stack trace attached: a bug report instead of an incident.

## For async code

Event-loop stalls, orphaned tasks, and cancellation problems have their own diagnosis path (`asyncio` debug mode, task introspection) and are owned by `python-async-best-practices`. This file covers the process and thread boundary; use both when an async service shells out.

