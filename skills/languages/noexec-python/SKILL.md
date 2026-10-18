---
name: noexec-python
description: "Write and test Python on hosts where scratch storage is mounted noexec, so starting a file from a temporary path raises PermissionError. Use when: (1) a test spawns a helper script written to tmp_path, tempfile, or TMPDIR and fails with Permission denied, (2) code calls subprocess with a path under a temp directory, (3) a console script, entry point, or venv lives on scratch storage, (4) code uses os.access, os.X_OK, shutil.which, or mode bits to decide whether a file can run, (5) multiprocessing or build tooling writes helper state to a temp directory, (6) a test skips or early-returns because storage may refuse execution."
---

# Python where scratch storage is `noexec`

## Overview

`noexec` is a mount flag. It blocks `execve` of a file on that mount. It does not block read, write, `chmod`, or import. The rule is one sentence: **run scripts with the interpreter, never execute them**.

A Python file in scratch is data. The interpreter that reads it lives on an executable mount. So `python3 /tmp/x.py` works and `subprocess.run([sys.executable, path])` works. Starting the file itself fails, and the failure looks like a permissions bug. The mode is `0755`, `chmod +x` succeeds, and the mount still refuses the start. A shell reports exit code `126`. The `noexec-coding` skill covers the mount rules and the three-way probe.

## Process

- [ ] 1. Find every process start. Search `subprocess`, `os.exec`, `os.system`, `os.posix_spawn`, `shutil.which`, `Popen`.
- [ ] 2. Ask of each: is the first argument a Python script or a program? A script goes through `sys.executable`. A program must sit on executable storage. Delete every `chmod(0o755)` that only makes a temp file runnable.
- [ ] 3. Replace every `os.access(_, os.X_OK)`, `shutil.which`, and mode-bit check used as "can it run" with a real probe.
- [ ] 4. Keep `tempfile`, `tmp_path`, and `tmpdir` for data. Write programs only to a probed directory.
- [ ] 5. Add the preflight helper once, in one module. Resolve once per run, not per call.
- [ ] 6. Remove every `skipif`, `importorskip`, and runtime early return for `noexec`. Add one negative test that fails if a program lands in scratch.
- [ ] 7. Run the smallest affected test. Report the preflight state: runs, refused, or unprobed.

### The `TMPDIR` rule

A data-only `TMPDIR` is acceptable. Anything that must execute must not live on `noexec` scratch: cargo and rustc artifacts, doctests, helper binaries, and spawn helpers.

In Python, a script runs through the interpreter, so a data-only `TMPDIR` is fine. A helper program, console script, or venv launcher must go elsewhere.

In Rust, `TMPDIR` must be on executable storage, because doctests and `cargo install` build scripts run from it. Never move `TMPDIR` to hide a defect. Move only the programs.

### Checklist before saying done

Answer these from the diff.

1. Where does every executable path come from? The environment or a probe, never `tempfile.gettempdir()`.
2. What happens on a `noexec` host? No program goes to scratch, or the code raises a clear error.
3. Does any test skip, `xfail`, or return early because storage might refuse execution? A yes is a defect, and so is an executable path taken from `tempfile`.
4. Was the preflight asked once and answered? Name the state it returned: runs, refused, or unprobed.

## Quick Reference

Measured on a Linux host with `/tmp` mounted `noexec`.

| Action | Result | Use it? |
| --- | --- | --- |
| `python3 /tmp/x.py`, `python -c`, `python -m pkg` | works | yes |
| `sh /tmp/x.sh` | works | yes |
| `import` a `.py` or `.pyc` from scratch | works | yes |
| `subprocess.run([sys.executable, p])` | works | yes |
| Direct run of `/tmp/x.py` | `PermissionError` | never |
| `os.execv` / `execve` / `execvp` / `execvpe`, `os.posix_spawn` on scratch | `PermissionError` | never |
| Console script at `/tmp/venv/bin/tool` | `PermissionError` | never |
| `bin/python` of a scratch venv | works, it is a symlink | yes |
| `python -m pip` inside a scratch venv | works | yes |
| `os.access(p, os.X_OK)`, `test -x` | `False`, though the mode is `0755` | not as a check |
| `shutil.which("t", path=tmp)` | `None` | not as a check |
| `chmod 0o755` | succeeds, changes nothing | not as a fix |

The last three rows report the mount, not the file. Measured on a `noexec` mount: mode `0o100755`, `os.access` `False`, `shutil.which` `None`, `test -x` exit `1`. A `stat` of the same file returns the same `0755` as on an exec mount, so neither call can tell the two apart. Only a started file answers the question.

```python
def can_run(directory):
    path = os.path.join(directory, f".probe-{os.getpid()}")
    with open(path, "w") as handle:
        handle.write("#!/bin/sh\nexit 0\n")
    os.chmod(path, 0o700)
    try:
        return subprocess.run([path], capture_output=True).returncode == 0
    except PermissionError:
        return False
    finally:
        os.unlink(path)
```

That returns one boolean: enough to pick the next candidate, not to say why a path failed. Use `probe()` in `references/exec_dir.py` for the three states.

### Where scratch comes from

`tempfile.gettempdir()` takes the first usable entry from `TMPDIR`, `TEMP`, `TMP`, then `/tmp`. `TemporaryDirectory()`, `mkdtemp()`, `NamedTemporaryFile()`, pytest `tmp_path` / `tmpdir` / `--basetemp`, and the `multiprocessing` bootstrap files follow it. All are right for data and wrong for programs.

```python
data_dir = Path(tempfile.mkdtemp())       # fixtures, logs, output files
program_dir = exec_dir("a test helper")   # only after a probe says "runs"
subprocess.run([sys.executable, str(data_dir / "work.py")], check=True)
```

### Anti-patterns

| Trap | Why it fails | Safe form |
| --- | --- | --- |
| `subprocess.run([tmp_path / "h.py"])` | the kernel must `execve` the script | `[sys.executable, h]` |
| A generated `#!/usr/bin/env python3` wrapper | the kernel reads the shebang, then `execve`s the wrapper | `import` the body, or use `sys.executable` |
| `console_scripts` entry point in a scratch venv | pip writes a real launcher into `bin/` | `python -m pkg`, or keep the venv off scratch |
| `os.exec*` on a scratch path | same `execve` rule | `os.execv(sys.executable, [sys.executable, script])` |
| A `PATH` entry on scratch | lookup ends in `execve` at the call site | put only executable directories on `PATH` |
| `shutil.which("t", path=tmp)` | uses `X_OK`, returns `None` | search `PATH` without scratch entries |
| `os.access(p, X_OK)` | `False` while the mode stays `0755` | run a probe file |
| `chmod(0o755)` as the fix | mode bits never override the mount | move the file, or use the interpreter |

### Build tooling and `multiprocessing`

| Tool | On a `noexec` `TMPDIR` | Note |
| --- | --- | --- |
| `pip install .`, `pip wheel .`, `python -m build` | works | the backend runs as `python -m` |
| `setuptools` / `hatchling` writing `bin/tool` | writes fine | the launcher cannot run |
| `pip install` into a scratch venv | works | `bin/python` is a symlink; `bin/pip` fails |
| `__pycache__` in scratch | works | bytecode is read, not executed |
| `PYTHONPYCACHEPREFIX=/exec/path` | works | moves the cache off scratch |

Build isolation is safe because `pip` starts its backend through the interpreter. An `entry_points` launcher is a file with a shebang, so it is not.

`multiprocessing` `spawn` works with `TMPDIR` on `noexec`, because the child re-executes `sys.executable`, which is on an executable mount. `forkserver` needs a writable temp dir and falls back to `spawn` when it cannot get one. `fork` starts no interpreter. Measured result: `spawn` works. This flag needs no change. Do not switch to `fork` to dodge `noexec`; it is unsafe with threads and on macOS. If a scratch `TMPDIR` is unavoidable, pass `env=dict(os.environ, TMPDIR=exec_dir())` to the child, use `mp.get_context("spawn")`, and guard the entry point with `if __name__ == "__main__":`.

### Test design

Assert the behavior, not the location. Fail loudly. `skipif`, `importorskip`, and a bare `return` all turn a defect into a pass:

```python
def test_helper_runs():
    directory = exec_dir("a test helper")     # raises with each candidate's state
    helper = Path(directory) / f"h-{os.getpid()}.py"
    helper.write_text("print('ready')\n", encoding="utf-8")
    out = subprocess.run([sys.executable, str(helper)], check=True,
                         capture_output=True, text=True)
    assert out.stdout.strip() == "ready"

def test_no_program_lands_in_scratch(tmp_path):
    before = set(tmp_path.iterdir())
    install_helper(tmp_path)                 # the code under test
    new = set(tmp_path.iterdir()) - before
    assert not [p for p in new if p.stat().st_mode & 0o111]
```

That last check reads mode bits on purpose. It asks "did a program land here", not "will this start". A placement guard may use mode bits. An execution check may not.

### Worked examples

**(a) A helper script invoked directly.** Wrong, then right:

```python
path = tmp_path / "helper.py"
path.write_text("#!/usr/bin/env python3\nprint('ready')\n")
path.chmod(0o755)
subprocess.run([str(path)], check=True)                      # PermissionError

out = subprocess.run([sys.executable, str(path)],            # right
                     capture_output=True, text=True, check=True)
assert out.stdout.strip() == "ready"
```

**(b) A pytest fixture split two ways.**

```python
@pytest.fixture
def data_dir(tmp_path):
    return tmp_path                       # scratch: fixtures and source

@pytest.fixture(scope="session")
def program_dir():
    return exec_dir("a test program")     # proven once per session
```

**(c) The preflight in use.**

```python
from exec_dir import NoExecDirectory, exec_dir

try:
    directory = exec_dir("the acme helper")
except NoExecDirectory as exc:
    raise SystemExit(f"cannot install the acme helper: {exc}\n"
                     "Set EXEC_DIR to a directory on an executable mount.") from exc
```

Copy `references/exec_dir.py` into the project first, beside the module that imports it. The example assumes it is importable on `sys.path`.

`exec_dir` lists each candidate and its state in the message. Full helper: `references/exec_dir.py`.

## Security

`noexec` stops direct execution only. An interpreter on an executable mount can read and run any script on a `noexec` mount. This is not a sandbox and not a trust boundary.

Do not remount, bind-mount, or raise privileges to make a check pass. That needs root, hides the defect, and changes the host. Do not treat a successful `import` or `sh script` as proof that a file can run; both read the file as data.

## Reference Files

- `references/exec_dir.py` — the probe, the resolver, and `run_script`. Standard library only. Tested.
- `references/test_exec_dir.py` — twelve tests, all passing on an exec host. The refused branch was measured on a `noexec` tmpfs.
- `references/workflows.md` — a local proof without a container, pytest setup, and a migration checklist.

The `noexec-coding` skill covers the mount rules and the three-way probe.

## Key Rules

- ALWAYS run a Python script through `sys.executable`, never by starting the file.
- ALWAYS take a program's directory from the environment or a probe, never from `tempfile`.
- ALWAYS keep three outcomes apart: runs, refused, unprobed. A write failure or a timeout is unprobed. Name each candidate and its state when no directory works.
- ALWAYS keep `tempfile`, `tmp_path`, and `tmpdir` for data. They are correct there. A program, launcher, or console script goes elsewhere.
- NEVER use `os.access(_, os.X_OK)`, `chmod`, mode bits, `test -x`, `shutil.which`, or `mount` output as an execution check.
- NEVER add a scratch directory to `PATH`, or skip, `xfail`, or early-return a test because storage might refuse execution.
- NEVER treat `noexec` as a sandbox. It stops `execve`, nothing else.
- PREFER `python -m pkg` over a console script, and the already-running interpreter over a new process.
- PREFER one negative test that fails when a program lands in scratch.

## Ground Rules

- A file mode is not a mount option. Read the mount only by trying to start a file.
- A skip is not a pass. Say "no check ran" when a check did not run.
- Test the behavior, not the path. A test that asserts `/tmp/...` breaks on the next host.
- macOS allows execution in its default temp directory, so a Linux-only defect hides there. Run the affected check on a `noexec` mount before you claim a fix, and report the outcome as runs, refused, or unprobed.
