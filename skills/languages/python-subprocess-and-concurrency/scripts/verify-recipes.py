#!/usr/bin/env python3
"""verify-recipes.py - executable verification for the recipes and version
claims in skills/languages/python-subprocess-and-concurrency.

Repo tooling, not runtime behaviour of the vendored skill. It exists for the
same reason as scripts/verify-rust-skill-commands.cjs: a skill whose value is
recipe accuracy must not be the thing that ships a broken recipe. Every check
names the rule id it backs, so a failure points at the rule to correct.

Usage:
    python3 skills/languages/python-subprocess-and-concurrency/scripts/verify-recipes.py
    python3 skills/languages/python-subprocess-and-concurrency/scripts/verify-recipes.py --quiet
    python3 skills/languages/python-subprocess-and-concurrency/scripts/verify-recipes.py --self-check

Exit 0 = every check passed (skips are allowed and reported).
Exit 1 = at least one check failed.

Portability and determinism:
  * Process-tree checks need POSIX process groups plus pgrep(1); they are
    skipped elsewhere and the skip is printed. Windows claims are asserted
    only when the suite actually runs on Windows.
  * Version-gated checks assert the documented API floor for the interpreter
    running them, so the same file is honest on 3.11 through 3.14.
  * No sleep is used as synchronisation. Process facts are polled with a
    deadline (the alternative python-pytest/determinism-sync-not-sleep allows
    when no event exists to wait on), and timing assertions are lower bounds
    only, so a loaded CI runner cannot make them red.
  * The process marker is unique and self-limiting: a stray marker exits on its
    own in five minutes instead of outliving the run.
"""

import argparse
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

POSIX = os.name == "posix"
WINDOWS = os.name == "nt"
VERSION = sys.version_info

# Unique, self-limiting marker for the child and its descendant. Fractional
# seconds keep the pattern from colliding with another sleep, and the bound
# means a leaked marker dies by itself.
MARK = "sleep 300.8675309"
MARK_RE = "sleep 300.867530[9]"  # regex form, so the checker cannot match itself

QUIET = False
RESULTS = []


def record(kind, name, detail=""):
    RESULTS.append((kind, name, detail))
    if QUIET and kind == "ok":
        return
    label = {"ok": "ok  ", "fail": "FAIL", "skip": "skip"}[kind]
    # detail is context for a decision, so it only helps when something did not pass
    show = detail if kind != "ok" else ""
    print(f"{label} - {name}" + (f"\n       {show}" if show else ""), flush=True)


def check(name, ok, detail=""):
    record("ok" if ok else "fail", name, detail)


def skip(name, why):
    record("skip", name, f"({why})")


def pids():
    """PIDs currently matching the marker process."""
    out = subprocess.run(["pgrep", "-f", MARK_RE], capture_output=True, text=True)
    return sorted(int(p) for p in out.stdout.split())


def wait_until(predicate, *, timeout=5.0, interval=0.02):
    """Poll an observable OS fact with a deadline. Never a fixed sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def reap():
    """Kill any marker process left alive, so one failure cannot cascade."""
    for pid in pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def kill_group(pid, sig=signal.SIGKILL):
    """Signal a whole process group. Only reaches a tree whose leader is `pid`.

    A child started without start_new_session lives in the caller's group, so
    this is the wrong tool for it - use proc.kill() there.
    """
    if not POSIX:
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def python_child(code):
    """A child command line that needs no shell, so it runs anywhere."""
    return [sys.executable, "-c", code]


# ---------------------------------------------------------------------------
# sp- rules that hold on every platform
# ---------------------------------------------------------------------------
def check_portable_subprocess():
    # sp-check-and-capture: check=True raises and carries the exit status
    try:
        subprocess.run(python_child("raise SystemExit(3)"), check=True)
        check("sp-check-and-capture: check=True raises CalledProcessError", False, "no exception")
    except subprocess.CalledProcessError as exc:
        check("sp-check-and-capture: check=True raises CalledProcessError",
              exc.returncode == 3, f"returncode={exc.returncode}")

    # sp-check-and-capture: the default is check=False, so failure is silent
    done = subprocess.run(python_child("raise SystemExit(3)"), capture_output=True, text=True)
    check("sp-check-and-capture: check=False returns without raising, returncode visible",
          done.returncode == 3, f"returncode={done.returncode}")

    # sp-argv-not-shell: with no shell, metacharacters are data, not syntax
    done = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "a; b && rm -rf /"],
        check=True, capture_output=True, text=True,
    )
    check("sp-argv-not-shell: shell=False passes metacharacters as data",
          done.stdout == "a; b && rm -rf /\n", f"stdout={done.stdout!r}")

    # sp-close-stdin: DEVNULL gives the child an immediate EOF instead of a tty
    done = subprocess.run(
        python_child("import sys; print(len(sys.stdin.read()))"),
        stdin=subprocess.DEVNULL, check=True, capture_output=True, text=True,
    )
    check("sp-close-stdin: stdin=DEVNULL yields an empty, non-blocking stdin",
          done.stdout.strip() == "0", f"stdout={done.stdout!r}")

    # sp-timeout-always / sp-communicate-not-wait: the exception carries partial output
    child = python_child("print('partial', flush=True); import time; time.sleep(300.8675309)")
    try:
        subprocess.run(child, timeout=1, capture_output=True, text=True)
        check("sp-timeout-always: run(timeout=) raises TimeoutExpired", False, "no exception")
    except subprocess.TimeoutExpired as exc:
        check("sp-timeout-always: run(timeout=) raises TimeoutExpired", True)
        # documented: always bytes regardless of text=True, and may be None
        check("sp-communicate-not-wait: TimeoutExpired.output is bytes despite text=True",
              isinstance(exc.stdout, bytes), f"type={type(exc.stdout).__name__}")
        raw = exc.stdout or b""
        partial = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        check("sp-communicate-not-wait: the documented decode recipe recovers partial output",
              partial.strip() == "partial", f"partial={partial!r}")

    # sp-communicate-not-wait: kill, then communicate() again (never wait())
    proc = subprocess.Popen(child, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(timeout=1)
        check("sp-communicate-not-wait: communicate(timeout=) raises TimeoutExpired", False, "returned")
    except subprocess.TimeoutExpired:
        check("sp-communicate-not-wait: communicate(timeout=) raises TimeoutExpired", True)
        proc.kill()  # no descendant here, so the direct child is the whole tree
        out, _ = proc.communicate()
        check("sp-communicate-not-wait: second communicate() recovers output and returncode",
              out.strip() == "partial" and proc.returncode is not None,
              f"out={out!r} returncode={proc.returncode}")

    # sp-popen-only-when-needed: the context manager waits, it does not kill
    short = subprocess.Popen(python_child("import time; time.sleep(0.6)"))
    started = time.monotonic()
    with short:
        pass
    elapsed = time.monotonic() - started
    # lower bound only: an upper bound would be a claim about host speed
    check("sp-popen-only-when-needed: `with Popen(...)` waits for exit",
          elapsed >= 0.3, f"elapsed={elapsed:.2f}s for a 0.6s child")
    check("sp-popen-only-when-needed: `with Popen(...)` does not kill the child",
          short.returncode == 0, f"returncode={short.returncode}")



# ---------------------------------------------------------------------------
# sp-kill-the-process-tree: POSIX process-group behaviour
# ---------------------------------------------------------------------------
POSIX_ONLY = [
    "sp-kill-the-process-tree: PREMISE - a descendant survives run(timeout=)",
    "sp-kill-the-process-tree: start_new_session makes the child a group leader",
    "sp-kill-the-process-tree: killpg stops the child and every descendant",
    "sp-kill-the-process-tree: the killed tree is reaped, leaving no zombie",
    "sp-communicate-not-wait: a surviving descendant keeps the pipe open, so EOF never arrives",
]


def check_process_groups():
    if not POSIX:
        for name in POSIX_ONLY:
            skip(name, "needs POSIX process groups and pgrep(1)")
        return

    tree = ["sh", "-c", f"{MARK} & wait"]
    try:
        reap()

        # PREMISE: run(timeout=) kills the direct child only; its descendant lives on
        try:
            subprocess.run(tree, timeout=1)
            check(POSIX_ONLY[0], False, "run(timeout=) did not raise")
        except subprocess.TimeoutExpired:
            survived = wait_until(lambda: pids() != [])
            check(POSIX_ONLY[0], survived, f"survivors after the timeout were {pids() or 'none'}")

        # the cleanup helper this suite relies on actually cleans up
        reap()
        check("verify-recipes self-check: reap() leaves no marker processes",
              wait_until(lambda: pids() == []), f"left {pids()}")

        # start_new_session -> the child leads its own process group
        proc = subprocess.Popen(tree, start_new_session=True)
        check(POSIX_ONLY[1], os.getpgid(proc.pid) == proc.pid,
              f"pgid={os.getpgid(proc.pid)} pid={proc.pid}")
        check("sp-kill-the-process-tree: the tree is visible before the kill",
              wait_until(lambda: len(pids()) >= 2), f"pids={pids()}")

        try:
            proc.wait(timeout=1)
            check("verify-recipes self-check: wait(timeout=) times out on a live tree",
                  False, "wait returned")
        except subprocess.TimeoutExpired:
            check("verify-recipes self-check: wait(timeout=) times out on a live tree", True)
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()

        # a group signal reaches descendants, and a reaped tree stops matching pgrep
        gone = wait_until(lambda: pids() == [])
        check(POSIX_ONLY[2], gone, f"still alive: {pids()}")
        check(POSIX_ONLY[3], gone and proc.returncode is not None and proc.returncode < 0,
              f"returncode={proc.returncode} (negative means terminated by a signal)")

        # A descendant that inherited the pipe holds it open after the child dies,
        # so the drain must wait for the whole group, not just the direct child.
        proc = subprocess.Popen(tree, start_new_session=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        proc.kill()  # direct child only: the sleep still holds the write end
        blocked = False
        try:
            proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            blocked = True
        check(POSIX_ONLY[4], blocked,
              "communicate() reached EOF after killing only the child; the descendant was gone")
        kill_group(proc.pid)  # the direct child is reaped; its descendant still holds the pipe
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    finally:
        reap()

    check("sp-kill-the-process-tree: suite leaves no stray processes",
          wait_until(lambda: pids() == []), f"left {pids()}")



# ---------------------------------------------------------------------------
# Version claims the rules make about the interpreter
# ---------------------------------------------------------------------------
def check_version_claims():
    import asyncio
    import faulthandler
    import inspect

    # thread-size-and-bound: the documented default differs by version
    with ThreadPoolExecutor() as executor:
        workers = executor._max_workers
    if hasattr(os, "process_cpu_count"):
        expected = min(32, (os.process_cpu_count() or 1) + 4)
        formula = "min(32, (process_cpu_count or 1) + 4) [3.13+]"
    else:
        expected = min(32, (os.cpu_count() or 1) + 4)
        formula = "min(32, cpu_count + 4) [3.8-3.12]"
    check(f"thread-size-and-bound: default max_workers matches the docs ({formula})",
          workers == expected, f"workers={workers} expected={expected}")

    # thread-size-and-bound: process_cpu_count is the 3.13 addition the rule cites
    has_pcc = hasattr(os, "process_cpu_count")
    check("thread-size-and-bound: os.process_cpu_count exists at the documented floor (3.13+)",
          has_pcc == (VERSION >= (3, 13)),
          f"python={VERSION.major}.{VERSION.minor} has_process_cpu_count={has_pcc}")

    # thread-explicit-shutdown: cancel_futures is 3.9+, inside the 3.11 floor
    params = inspect.signature(ThreadPoolExecutor.shutdown).parameters
    check("thread-explicit-shutdown: shutdown(cancel_futures=...) is available (3.9+)",
          "cancel_futures" in params, f"params={list(params)}")

    # proc-bound-and-chunk: buffersize is the 3.14 addition the rule cites
    has_buffer = "buffersize" in inspect.signature(ThreadPoolExecutor.map).parameters
    check("proc-bound-and-chunk: Executor.map(buffersize=...) at the documented floor (3.14+)",
          has_buffer == (VERSION >= (3, 14)),
          f"python={VERSION.major}.{VERSION.minor} has_buffersize={has_buffer}")

    # proc-stop-cooperatively: Process.interrupt is 3.14+
    has_interrupt = hasattr(multiprocessing.Process, "interrupt")
    check("proc-stop-cooperatively: Process.interrupt exists at the documented floor (3.14+)",
          has_interrupt == (VERSION >= (3, 14)),
          f"python={VERSION.major}.{VERSION.minor} has_interrupt={has_interrupt}")

    # debugging-hangs.md: dump_c_stack is the 3.14 addition the file cites
    has_c_stack = hasattr(faulthandler, "dump_c_stack")
    check("debugging-hangs: faulthandler.dump_c_stack at the documented floor (3.14+)",
          has_c_stack == (VERSION >= (3, 14)),
          f"python={VERSION.major}.{VERSION.minor} has_dump_c_stack={has_c_stack}")

    # sp-async-children: asyncio.timeout is the 3.11 API the rule uses
    check("sp-async-children: asyncio.timeout exists at the 3.11 floor",
          hasattr(asyncio, "timeout"), f"python={VERSION.major}.{VERSION.minor}")

    # sp-kill-the-process-tree: Windows-only claims, asserted where they can be
    if WINDOWS:
        check("sp-kill-the-process-tree: CREATE_NEW_PROCESS_GROUP exists on Windows",
              hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"))
        check("sp-kill-the-process-tree: Windows terminate() is TerminateProcess, kill() is its alias",
              subprocess.Popen.kill.__doc__ == subprocess.Popen.terminate.__doc__)
    else:
        skip("sp-kill-the-process-tree: Windows terminate()/creation-flag claims",
             "only assertable on a Windows runner; add one to CI to close this")


def main():
    global QUIET
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true",
                        help="print failures and skips only")
    parser.add_argument("--self-check", action="store_true",
                        help="alias kept for consistency with the repo's other test:* entries")
    args = parser.parse_args()
    QUIET = args.quiet

    print(f"python {VERSION.major}.{VERSION.minor}.{VERSION.micro} on {sys.platform}", flush=True)
    check_portable_subprocess()
    check_process_groups()
    check_version_claims()

    passed = sum(1 for kind, _, _ in RESULTS if kind == "ok")
    failed = [(name, detail) for kind, name, detail in RESULTS if kind == "fail"]
    skipped = sum(1 for kind, _, _ in RESULTS if kind == "skip")
    print()
    for name, detail in failed:
        print(f"FAIL - {name}\n       {detail}")
    print(f"{passed}/{len(RESULTS)} checks passed"
          + (f", {skipped} skipped" if skipped else "")
          + (" - FAILURES ABOVE" if failed else ""), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
