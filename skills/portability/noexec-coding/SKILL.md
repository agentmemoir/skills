---
name: noexec-coding
description: "Write and test code that must run on hosts where scratch directories are mounted noexec, so executing a file from a temporary path is refused. Use when: (1) code creates temporary files or directories, (2) code spawns a helper binary or script, (3) code sets a build or target directory, (4) a check or program fails with Permission denied or exit code 126 while starting a process from a temp path, (5) code uses os.access, test -x, shutil.which, or mode bits to decide whether a file can run, (6) a test skips or early-returns because storage may refuse execution."
category: portability
title: Noexec coding
summary: >-
  Code and tests that work where scratch storage is mounted `noexec`. The mount blocks starting any
  file from a temporary path, so scripts run through an interpreter, executables live in a probed
  directory, and tests cannot skip around the defect. Covers what the mount blocks, why shebangs and
  mode bits do not help, the three-way execution probe, where executables belong, test design that
  cannot skip, and the anti-patterns that hide the
  defect.
say: >-
  "My tests fail with Permission denied from /tmp — make this code work on a noexec
  host."
---

# Code that works where scratch storage is `noexec`

## 1. The invariant

Assume every scratch and temporary directory is mounted `noexec`.

This covers `$TMPDIR`, `/tmp`, `/dev/shm`, and any directory the code creates for short-lived work.

Your change must pass with that mount in place. No exception. No skip. No "remount and rerun" step in the instructions.

Write the code so the host never has to change.

## 2. What `noexec` blocks, and what it does not

| Action | Result on a `noexec` mount | Rule for you |
| --- | --- | --- |
| `execve` of an ELF binary on the mount | Fails with `EACCES` | Never start a process from a scratch path. |
| Direct run of a `#!/usr/bin/env python3` script | Fails; the kernel opens the script itself with `MAY_EXEC` | A shebang does not route around the mount. |
| Shell reports the failure | `Permission denied`, exit code 126 | Treat 126 as "wrong location", not "wrong mode". |
| Read a file from the mount | Works | Fixtures, data, config, and source may live in scratch. |
| `sh file`, `python3 file`, `node file` | Works: the interpreter runs from an executable mount and only reads the file | Run generated scripts through their interpreter. |
| `python -c`, `python -m pkg` | Works | Use these instead of a console script in scratch. |
| Importing a `.pyc` from the mount | Works: bytecode is read, not started | `__pycache__` in scratch is fine. |
| `dlopen` a `.so` from the mount | Fails; the loader needs `mmap(PROT_EXEC)` | Native libraries need executable storage too. |
| `mmap(PROT_EXEC)` of a file on the mount | Fails with `EPERM` | JIT and native loaders need executable storage. |
| `chmod +x` and `stat` mode bits | Accepted; mode still reads `0755` | Mode bits do not predict execution. |
| `os.access(path, X_OK)` or `test -x` | Returns false | Never use this as an execution probe. |
| `shutil.which(name, path=dir)` | Returns `None` | Do not put a scratch directory on `PATH`. |

The only reliable answer comes from trying to start a process from that path.

Language and platform notes:

- Python: a `venv` under scratch works because `bin/python` is a symlink, but `bin/pip` and `bin/pytest` are scripts and are refused. Use `python -m pip` and `python -m pytest`.
- Go: `go run` and `go test` fail with `fork/exec /tmp/go-build.../exe: permission denied`. Set `GOTMPDIR` to executable storage; `GOCACHE` alone did not help.
- macOS: a `noexec` APFS volume reproduces the same refusal as Linux. The default `TMPDIR` sits on the executable Data volume, so a Linux-only bug hides there.

## 3. Where code goes

Put every file that must be started as a process in executable storage, and put every file that is only read in scratch.

Decide with one question: will some process call `execve` on this path? If yes, it is executable storage. If no, scratch is fine.

Executable storage is a directory that the host proves can run a file: a build output tree, the directory of the current binary, or another path the program already resolved as executable.

## 4. The three-way probe

Classify a path with three actions, in this order:

1. Can the process create a file there? A write test.
2. Can an already-running interpreter run that file? Run `sh <file>`.
3. Is direct execution refused? Run the file itself.

Only the third answer tells you whether the mount is `noexec`. A successful create proves nothing about execution. A successful `sh <file>` proves nothing either, because the interpreter reads the file as data.

```sh
d=${1:-${TMPDIR:-/tmp}}
f="$d/noexec-probe-$$"
printf '#!/bin/sh\nexit 0\n' > "$f" || { echo "UNPROBED: cannot create"; exit 2; }
chmod 755 "$f"

"$f" >/dev/null 2>&1
direct=$?

sh "$f" >/dev/null 2>&1
interp=$?

rm -f "$f"

echo "create=ok direct=$direct interpreter=$interp"
case "$direct" in
  0)   echo "RUNS: this path may hold executables" ;;
  126) echo "REFUSED: noexec mount, do not put executables here"; exit 1 ;;
  *)   echo "UNPROBED: direct run failed for another reason"; exit 2 ;;
esac
[ "$interp" -eq 0 ] || echo "WARN: interpreter could not read the file"
```

Keep the three outcomes separate. `REFUSED` means the mount said no. `UNPROBED` means the test itself did not run. Merging the two hides a real defect and produces a false pass.

If every candidate path is `REFUSED`, fail loudly. Do not fall back to scratch.

## 5. Design patterns

### Keep the build output directory and the test scratch directory separate

Reason: build output is executed; scratch is not.

Failure it prevents: a build tree pointed at `$TMPDIR` produces binaries the host refuses to run, and the error looks like a permissions bug.

### Never put a scratch path on `PATH`

Reason: `PATH` lookup ends in `execve`, so a hit in scratch becomes a refusal at the call site.

Failure it prevents: a tool found in scratch fails with 126, usually deep inside a subprocess, far from the code that set `PATH`.

### Do not write a launcher script into scratch and invoke it

Reason: the wrapper is a file that must be started, so it needs executable storage.

Failure it prevents: the actual work is fine but the shim around it is refused.

### Do not use mode bits to decide whether execution will work

Reason: the mount option outranks the mode, and `chmod +x` succeeds on a `noexec` mount.

Failure it prevents: code is marked "executable", the check is skipped, and the real host fails later.

### Prefer the already-loaded runtime over a new binary

Reason: a running interpreter can read any file; a new process must be started from an executable path.

Failure it prevents: downloading or generating a helper binary into scratch, then failing to run it. Use `python -c`, an in-process call, or the library API instead.

### Ask the environment for an executable location, and fail loudly if there is none

Reason: only the host knows which paths allow execution.

Failure it prevents: silent fallback to scratch, or a hard-coded path that works on one machine only.

### Clean up by path ownership

Reason: executable storage is often shared by several test processes.

Failure it prevents: one test deleting a directory another test still uses, and one test deleting files it did not create.

Remove only the paths you created. Record the owner when the helper makes the directory for another process.

## 6. Test design

Write tests that pass on a host that allows execution in scratch and also prove the property on a host that does not.

- Assert behavior, not location. Check that the program ran and produced the expected result. Do not assert a specific directory string.
- Assert that the code asked for executable storage. If the code has a resolver, spy on it or check that the returned path is the one the resolver chose.
- Add a negative case: force the resolver to return a scratch path and assert the code refuses it or reports a clear error. This case fails if the code writes an executable into scratch.
- Keep `REFUSED` and `UNPROBED` as separate outcomes, and test each one.
- Do not mark the check `skipif` on `noexec`. A skip turns a real defect into a pass, and a skipped run verifies nothing.
- Do not remount, bind-mount, or change mount options inside a test.

Write the test so it fails on a defect, not on a host type. If the host truly has no executable location, fail with a clear message and do not return success.

## 7. Anti-patterns

| Pattern | Why it fails on `noexec` | Correct alternative |
| --- | --- | --- |
| `tempfile.TemporaryDirectory()` holds a program or script | The directory is on scratch; starting the file is refused | Create executables in a resolved executable directory; use scratch only for data |
| `CARGO_TARGET_DIR` (or any build output dir) pointed at scratch | The test binary cannot start | Keep build output in the project tree or another executable path |
| `PATH` prefixed with a scratch directory | Lookup finds a file that cannot start | Add only executable directories to `PATH` |
| Writing a `#!/bin/sh` wrapper into scratch and calling it | The wrapper itself is refused | Put the wrapper in executable storage, or call the interpreter on the script |
| Asserting `os.access(path, os.X_OK)` or `test -x` | Both return false on a `noexec` mount, though the mode is `0755` | Run a probe file and read the exit code |
| Checking `mount` output at runtime | String parsing is fragile and host-specific; some tools disagree | Probe by running a file |
| Remounting `exec` in a test or setup script | Hides the defect and needs privileges | Make the code use executable storage |
| `chmod +x` as the fix for `Permission denied` | The mode is already correct; the mount refuses execution | Move the file to executable storage |
| Downloading a helper binary into a temp dir | The download succeeds, the run is refused | Use the current runtime, or install into executable storage |
| Silently skipping when no executable path is found | A skip is reported as a pass | Fail with a clear message |

## 8. Verification checklist

Answer these from the diff, before you say the work is done.

1. Does any new or changed file get started as a process? If yes, is it written to executable storage?
2. Does any changed default, config key, or test fixture point a build or output directory at a temporary path?
3. Does any code add a scratch path to `PATH`?
4. Does any check use a mode bit, `test -x`, `os.access`, or `mount` output to decide execution?
5. Does any test skip because storage may be `noexec`?
6. Does the resolver fail loudly when no executable path exists?
7. Does cleanup remove only paths the code created?
8. Is there a negative test that would fail if an executable landed in scratch?

Any "yes" to questions 2 to 5 is a defect. Fix it before finishing.

## 9. When the local proof is enough

The diff and the checklist above settle the question. Do not start a container, a VM, or a mount step to check `noexec`.

If the host itself refuses execution in scratch, run the three-way probe against the directory the code chose, and report `runs`, `refused`, or `unprobed`. That is the smallest honest proof. If the host allows execution in scratch, test the guard directly: force the resolver to a refusing path, and assert the clear error instead of a fallback.

Re-run the check only when the code changes the executable path, the resolver, or the build directory. A repeated run on unchanged code proves nothing new.

## 10. Companions

`noexec-python` and `noexec-rust` carry the language-specific mechanics, tested reference code, and the same three-way probe.

