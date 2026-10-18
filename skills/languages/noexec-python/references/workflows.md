# Python workflows on a host that refuses execution in scratch

## 1. Proving the property without a container

Do not start a container to check this. A correct diff needs no container run. Reason from the diff, then run the smallest local check.

Ask these three questions of the diff:

1. Does every executable path come from executable storage? A path from `tempfile`, `tmp_path`, or `TMPDIR` is a defect for a program.
2. Was the preflight asked and answered? `exec_dir()` must return a probed directory, or raise `NoExecDirectory` with each candidate named.
3. Does any test skip or return early because storage may refuse execution? A skip is a defect.

The smallest local proof, with no Docker and no root:

```sh
python - <<'PY'
from exec_dir import exec_dir, probe
directory = exec_dir("a test helper")
print(directory, probe(directory).state)
PY
python -m pytest -q tests/
```

`exec_dir()` probes each candidate. `probe()` reports `runs`, `refused`, or `unprobed`. If the host itself refuses execution in scratch, the resolver returns the project build dir or raises. Both are honest results. Report which one you got.

If the resolver returns a directory whose state is `runs`, the preflight was asked and answered. Do not repeat the check on unchanged code. Do not add a container job or a mount step.

## 2. pytest configuration

Keep the temp root on scratch. It is correct for data, and moving it would hide a program written there.

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

Give the program directory to the suite through the environment, once per run:

```sh
export EXEC_DIR="$PWD/.build/exec"
mkdir -p "$EXEC_DIR"
python -m pytest -q
```

If a session fixture needs a program, resolve it once:

```python
# conftest.py
import pytest
from exec_dir import exec_dir

@pytest.fixture(scope="session")
def program_dir():
    return exec_dir("a test program")
```

That import needs `exec_dir.py` on `sys.path`. Copy it into the project root, beside `conftest.py`, or into a package that `conftest.py` imports. Pytest adds the rootdir to `sys.path` when the project uses rootdir-based imports.

Do not set `--basetemp` to an executable directory to "make the suite pass". That hides every program written to `tmp_path`, which is the defect you want the suite to catch.

## 3. Reading the failure

| What you see | What it means | What to change |
| --- | --- | --- |
| `PermissionError` on `subprocess.run([path])` | direct start of a scratch file | use `sys.executable` |
| `PermissionError` on `/tmp/venv/bin/pip` | console script on scratch | `python -m pip` |
| `PermissionError` on `os.execv` | same `execve` rule | `os.execv(sys.executable, ...)` |
| `shutil.which(...) is None` | `X_OK` says no | search `PATH` without scratch |
| exit code `126` from a shell | the kernel refused | move the file |
| `FileNotFoundError` from `spawn` helpers | a bootstrap file vanished | check `TMPDIR` is writable |
| a test skipped with `reason="noexec"` | no check ran | delete the skip |

## 4. Migration checklist

1. Search for `subprocess`, `os.exec`, `os.system`, `os.posix_spawn`, `which`, and `Popen`.
2. For each hit, find where the first argument was written.
3. If that path came from `tempfile`, `tmp_path`, or `TMPDIR`, change it.
4. Add `probe()` or `exec_dir()` in one module.
5. Replace `os.access(_, os.X_OK)` and mode-bit checks with a probe.
6. Delete every skip that exists for this mount flag.
7. Add the negative test.
8. Run the smallest affected test and report the preflight state: runs, refused, or unprobed.
