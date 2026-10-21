# Subprocess rules (`sp-`)

Every claim here is verified against the CPython 3.14 `subprocess` documentation. Rule IDs match the quick reference in `SKILL.md`.

## sp-argv-not-shell

**Prevents:** command injection, and the class of bug where a value containing a space or a quote becomes two arguments or a different command.

`subprocess` "will not implicitly choose to call a system shell. This means that all characters, including shell metacharacters, can safely be passed to child processes." With `shell=True`, quoting becomes your job: the docs put the responsibility for escaping every metacharacter on the application, and name `shlex.quote()` as an option.

```python
# BAD: filename controls the command line
subprocess.run(f"pdfinfo {filename}", shell=True)

# BAD: same injection, plus a pipeline
subprocess.run(f"gzip {filename} | wc -c", shell=True)

# GOOD: one argv element per argument, no shell involved
subprocess.run(["/usr/bin/pdfinfo", filename], check=True)

# GOOD: if a shell must be involved, quote for that shell and know which shell it is
subprocess.run(f"gzip -- {shlex.quote(filename)} | wc -c", shell=True)
```

Three traps that survive "just quote it":

- `shlex.quote()` implements POSIX shell quoting only. It is not safe for `cmd.exe` or PowerShell; PEP 787 (safer subprocess via t-strings) was deferred partly because that gap is not solvable in stdlib.
- On Windows, batch files (`*.bat`, `*.cmd`) "may be launched by the operating system in a system shell regardless of the arguments passed to this library", so arguments can be re-parsed by shell rules without Python escaping them (gh-114539). If you must launch a batch file with untrusted arguments, the docs suggest `shell=True` so Python escapes them.
- 3.12 changed the Windows shell search order for `shell=True` to `%COMSPEC%` and `%SystemRoot%\System32\cmd.exe`, so `shell=True` does not mean the same thing across versions.

**Scope:** `shell=True` with a fully literal, self-authored command and no interpolation is not what this rule is about. If you were handed a trusted command *string*, `shlex.split(cmd)` turns it into argv.

## sp-check-and-capture

**Prevents:** a failing command that reports success.

`check` defaults to `False`, so `run()` returns a `CompletedProcess` whose `returncode` is non-zero and your code carries on. `returncode` semantics: `0` is success, and a negative `-N` means the child was terminated by signal `N` (POSIX only).

```python
# BAD: failure is invisible, and stdout is None because nothing was captured
subprocess.run(["tar", "-czf", out, src])

# GOOD: raises CalledProcessError, which carries returncode, cmd, stdout, stderr
subprocess.run(["tar", "-czf", out, src], capture_output=True, text=True, check=True)

# GOOD: or handle codes yourself when non-zero is an expected outcome
done = subprocess.run(["diff", a, b], capture_output=True, text=True)
if done.returncode not in (0, 1):
    raise RuntimeError(f"diff failed ({done.returncode}): {done.stderr}")
```

With `shell=True`, an `OSError` is raised only when the shell itself is missing; a shell that cannot find your program just exits non-zero. One more reason the exit code must be checked.

## sp-timeout-always

**Prevents:** an unbounded wait on a child that will never finish.

Every `wait`, `communicate`, and `run` call here is unbounded without `timeout`. With `run(timeout=n)`, "if the timeout expires, the child process will be killed and waited for", and `TimeoutExpired` is re-raised after the child has terminated.

Two documented caveats that shape the value you pick:

- Process creation cannot be interrupted on many platforms, so "you are not guaranteed to see a timeout exception until at least after however long process creation takes."
- Very small timeouts "may result in almost immediate `TimeoutExpired` exceptions because process creation and system scheduling inherently require time."

The timeout is a stuck-child guard, not a deadline. Set it generously enough to survive a loaded machine (seconds to minutes) and keep the business deadline somewhere you control.

## sp-kill-the-process-tree

**Prevents:** orphaned grandchildren that keep holding ports, lock files, temp directories, and CPU after you believe you stopped them.

`run(timeout=...)` kills the direct child via the internal `Popen.kill()`, which sends `SIGKILL` on POSIX. Grandchildren the child spawned live in the child's process group and are never signaled. `Popen.wait(timeout=...)` does not kill anything at all: "the child process is not killed if the timeout expires."

The fix is to give the child its own process group and signal the group:

```python
import os
import signal
import subprocess

proc = subprocess.Popen(
    argv,
    # setsid() in the child: its own session, so its process group id == its pid
    start_new_session=True,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
)
try:
    out, _ = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired:
    os.killpg(proc.pid, signal.SIGTERM)   # the whole group, not just the child
    try:
        proc.wait(timeout=5)              # give it a chance to exit cleanly
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()                       # always reap
    raise
```

Notes:

- `start_new_session=True` is POSIX-only and is the documented replacement for `preexec_fn=os.setsid`, which is thread-unsafe. `process_group=<id>` (3.11+, POSIX) joins an existing group instead.
- `os.killpg(proc.pid, ...)` is correct here only because `start_new_session=True` made the child a group leader. Otherwise resolve the group with `os.getpgid` and handle `ProcessLookupError` for a child that already exited.
- Always reap. A killed child that is never waited on stays a zombie until your process exits.
- Windows has no signals and no process groups. `terminate()` calls `TerminateProcess` (no graceful shutdown) and `kill()` is an alias for it; Ctrl events need `CREATE_NEW_PROCESS_GROUP` plus `CTRL_BREAK_EVENT`. Killing a whole tree on Windows needs a Win32 Job Object, which the standard library does not expose.

## sp-communicate-not-wait

**Prevents:** the classic pipe deadlock, where your process waits for the child while the child waits for you to drain a full pipe.

The docs are explicit: use `communicate()` rather than `proc.stdin.write()`, `proc.stdout.read()`, or `proc.stderr.read()`, to "avoid deadlocks due to streams pausing reading or writing and blocking the child process." `Popen.wait()` carries the same hazard with `PIPE`, because the child blocks writing into a full OS pipe buffer.

```python
# BAD: deadlocks once the child writes more than the pipe buffer (often 64 KiB)
proc = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True)
proc.wait()
output = proc.stdout.read()

# GOOD: communicate() drains the pipes while it waits
done = subprocess.run(argv, capture_output=True, text=True, check=True)
print(done.stdout)
```

After `communicate()` raises `TimeoutExpired`, do not call `wait()`. The documented recovery is to kill and call `communicate()` again to finish the pipes and populate `returncode`:

```python
try:
    out, err = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired:
    proc.kill()
    out, err = proc.communicate()   # not wait()
```

**Killing the child is not always enough to end the read.** A descendant of the child inherits its stdout/stderr, so if the child spawned something, the write end of your pipe is still open after the child dies and `communicate()` waits for an EOF that will never arrive. That is the second, subtler reason to signal the whole process group before draining:

```python
proc = subprocess.Popen(["sh", "-c", "some-tool & wait"], start_new_session=True,
                        stdout=subprocess.PIPE, text=True)
try:
    out, _ = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired:
    os.killpg(proc.pid, signal.SIGKILL)   # group, so no descendant keeps the pipe open
    out, _ = proc.communicate()           # now this can reach EOF
    raise
```

**Scope:** `communicate()` buffers output in memory, so it is the wrong tool for unbounded output. Stream deliberately instead: read incrementally from `proc.stdout` in a thread or with `select`, or send output straight to a file with `stdout=open(..., "wb")`.

**One decoding surprise:** `TimeoutExpired.output` (and its `stdout`/`stderr` aliases) "is always bytes when any output was captured regardless of the `text=True` setting", and "may remain `None` instead of `b''` when no output was observed". So the partial output attached to a timeout is not text just because you asked for text:

```python
try:
    out, _ = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired as exc:
    raw = exc.stdout or b""
    partial = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
```

## sp-popen-only-when-needed

**Prevents:** hand-rolled process management that leaks children and file descriptors.

"The recommended approach to invoking subprocesses is to use the `run()` function for all use cases it can handle. For more advanced use cases, the underlying `Popen` interface can be used directly." Reach for `Popen` when you genuinely need incremental streaming, interactive stdin, signal-the-group cleanup on timeout, or a long-lived child. Otherwise `run()` does the whole job.

The context manager is narrower than it looks: "on exit, standard file descriptors are closed, and the process is waited for." It does **not** kill. A `with` block that raises leaves the child running and your code thinking it is managed.

```python
# BAD: `with` gives a false sense of cleanup; the child survives an exception here
with subprocess.Popen(argv) as proc:
    if not ready(proc):
        raise RuntimeError("not ready")   # child keeps running

# GOOD: every path ends in a decision about the child
proc = subprocess.Popen(argv)
try:
    ...
finally:
    if proc.poll() is None:
        proc.kill()
        proc.wait()
```

Since 3.6 the `Popen` destructor emits a `ResourceWarning` when the child is still running. If you see that warning, something above skipped its cleanup.

## sp-close-stdin

**Prevents:** a child that blocks forever waiting for input, or that eats input meant for your program.

A child inherits your stdin by default. In an interactive shell or a pipeline, that means a prompt, a pager, or a "read the password" step can hang your program or consume the wrong stream. Hand it nothing:

```python
# BAD: inherits the terminal (or the upstream pipe) and may block on read
subprocess.run(["ssh", host, "uptime"], check=True)

# GOOD: no stdin at all
subprocess.run(["ssh", host, "uptime"], stdin=subprocess.DEVNULL, check=True)

# GOOD: exactly the input it should get
subprocess.run(["ssh", host, "uptime"], input="", text=True, check=True)
```

Valid values are `None` (inherit), `PIPE`, `DEVNULL`, an open file descriptor, or a file object. `input=` implies `stdin=PIPE` and cannot be combined with `stdin=`.


## sp-explicit-env-and-cwd

**Prevents:** a command that works on your machine and resolves a different binary, or no binary, in CI, a container, or a service.

The docs: "For maximum reliability, use a fully qualified path for the executable", because path resolution is platform-dependent — on POSIX `cwd` overrides the working directory and `env` can override `PATH`; on Windows with `shell=False`, `cwd` does *not* override the working directory and `env` cannot override `PATH`. "Using a full path avoids all of these variations."

```python
# BAD: which "ffmpeg" runs depends on the caller's PATH
subprocess.run(["ffmpeg", "-i", src, dst], check=True)

# GOOD: absolute path, explicit working directory, and an environment you chose
env = {**os.environ, "LC_ALL": "C", "HOME": str(home)}
subprocess.run(
    ["/usr/bin/ffmpeg", "-i", src, dst],
    cwd=str(workdir),
    env=env,
    check=True,
)
```

`env` **replaces** the child's environment rather than merging into it, so copy `os.environ` when you only want to add or override a few variables. A deliberately short `PATH` is also the cheap defense against PATH hijacking: a relative program name resolved through an attacker-writable `PATH` entry runs attacker code.

## sp-explicit-text-encoding

**Prevents:** mojibake and `UnicodeDecodeError` that appear only in some environments.

`text=True` (or `universal_newlines=True`) decodes with the locale encoding, `locale.getpreferredencoding(False)`. That value differs between a developer shell, a container with no `LANG`, and Windows. When you want text, name the encoding and pick a failure policy:

```python
# BAD: decoding depends on the ambient locale
subprocess.run(argv, capture_output=True, text=True, check=True)

# GOOD: deterministic decode, replacement instead of a crash on odd bytes
subprocess.run(
    argv,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=True,
)
```

`errors="replace"` is the right default for human or log output you must not crash on; use `errors="strict"` when the bytes are a contract. If the output is genuinely binary, do not use text mode at all.

## sp-no-preexec-fn

**Prevents:** a child that deadlocks before `exec` — intermittent and near-impossible to reproduce.

The docs warn in capitals: "The `preexec_fn` parameter is NOT SAFE to use in the presence of threads in your application. The child process could deadlock before `exec` is called." A forked child inherits locks that may be held by threads that do not exist in the child.

There are supported replacements for the things people use it for:

```python
# BAD: the classic pair
subprocess.Popen(argv, preexec_fn=os.setsid)                   # use start_new_session
subprocess.Popen(argv, preexec_fn=lambda: os.setpgid(0, 0))    # use process_group
subprocess.Popen(argv, preexec_fn=lambda: os.putenv("K", "v")) # use env

# GOOD
subprocess.Popen(argv, start_new_session=True)
subprocess.Popen(argv, process_group=0)
subprocess.Popen(argv, env={**os.environ, "K": "v"})
```

`preexec_fn` also raises `RuntimeError` in subinterpreters since 3.8, which is how this pattern breaks in embedded deployments (mod_wsgi, uWSGI).

## sp-bound-child-fanout

**Prevents:** the incident `async-bound-concurrency` describes, with a heavier unit of work — one child per input item means N processes, N pairs of pipes, and N times the memory, all demanded at once.

```python
# BAD: 10,000 inputs means 10,000 concurrent children
for argv in work:
    subprocess.Popen(argv)

# BAD: "parallelism" by loop, still unbounded, and failures go unchecked
for argv in work:
    subprocess.run(argv, check=True)

# GOOD: a bounded number of children in flight
with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(one, work))   # one() runs subprocess.run(..., check=True)
```

Pick the bound from a real constraint — logical CPUs for CPU-heavy commands, memory per child, a downstream rate or license limit — and expose it as a parameter rather than hardcoding it at the call site. If the work arrives over time, front the workers with a bounded `queue.Queue(maxsize=...)` so the producer waits instead of piling up.

## sp-drop-legacy-apis

**Prevents:** losing the security and error-handling guarantees this module exists to provide.

The `subprocess` module "intends to replace several older modules and functions: `os.system`, `os.spawn*`." It also still ships two legacy helpers, and its own documentation disclaims them: they "implicitly invoke the system shell and none of the guarantees described above regarding security and exception handling consistency are valid for these functions."

| Do not use | Use instead |
|---|---|
| `os.system(cmd)` | `subprocess.run(argv, check=True)` |
| `os.popen(cmd)`, `os.spawn*` | `subprocess.run(...)` / `Popen` |
| `subprocess.getstatusoutput(cmd)` | `subprocess.run(argv, capture_output=True)` |
| `subprocess.getoutput(cmd)` | `subprocess.run(argv, capture_output=True, text=True).stdout` |
| `commands.*` (Python 2) | `subprocess` |

`os.system` also ignores `SIGINT` and `SIGQUIT` while the command runs, whereas with `subprocess` the caller must manage that deliberately. The replacements above are the ones listed in the docs' "Replacing Older Functions with the subprocess Module".


## sp-async-children

**Prevents:** blocking the event loop with a synchronous child, and leaving a child running when its coroutine is cancelled.

In `async def` code, `subprocess.run()` blocks every task on the loop. Use the asyncio subprocess API instead:

```python
import asyncio

async def rev_parse(path: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/git", "-C", path, "rev-parse", "HEAD",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(30):          # 3.11+
            out, err = await proc.communicate()
    except (TimeoutError, asyncio.CancelledError):
        proc.kill()                               # a cancelled await does not signal the child
        await proc.wait()
        raise
    if proc.returncode != 0:
        raise RuntimeError(err.decode("utf-8", "replace"))
    return out.decode("utf-8").strip()
```

- `create_subprocess_shell` exists and carries the same injection responsibility as `shell=True`: the docs put quoting on the application and recommend `shlex.quote()`. Prefer `create_subprocess_exec`.
- `Process.wait()` "can deadlock when using `stdout=PIPE` or `stderr=PIPE` and the child process generates so much output that it blocks waiting for the OS pipe buffer to accept more data." Use `communicate()`.
- If the `Process` object is garbage collected while the child is still running, the child is killed. Holding no reference is not "fire and forget" — it is an unpredictable kill. Own the reference.
- `create_subprocess_exec(..., limit=...)` defaults to 65536 bytes on `StreamReader` lines; one long line raises `LimitOverrunError`, so raise the limit for chatty programs.
- On Windows, subprocesses require a `ProactorEventLoop` (the default there); `SelectorEventLoop` has no subprocess support.
- Event-loop discipline — `TaskGroup`, blocking calls, cancellation, bounded fan-out via semaphore — belongs to `python-async-best-practices`. This rule covers only the process boundary.

## Platform differences that change the code

| Concern | POSIX | Windows |
|---|---|---|
| Killing a tree | `start_new_session=True` + `os.killpg` | Needs a Win32 Job Object; stdlib gives only `terminate()`/`kill()` |
| Graceful stop | `SIGTERM`, then `SIGKILL` | `terminate()` is `TerminateProcess`: immediate, no cleanup |
| Ctrl events | Signals to the group | `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` |
| `cwd` vs executable lookup | `cwd` affects lookup; `env` can override `PATH` | With `shell=False`, neither affects lookup |
| Explicit shell | `shlex.quote()` is valid | `shlex.quote()` is not sufficient; avoid shell strings |
| Shell search for `shell=True` | `PATH`, plus `/bin/sh` | 3.12+: `%COMSPEC%` / `%SystemRoot%\System32\cmd.exe` |
| Exit status | Negative `-N` means killed by signal `N` | Always a non-negative exit code |
| `Process.returncode` under asyncio | Negative on signal | Shell may map signals to `128+N` |

