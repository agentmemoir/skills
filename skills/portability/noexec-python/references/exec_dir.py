"""Prove a directory can start a file, then keep programs there.

Standard library only. Python 3.8 or newer.

Two callers exist. `probe()` classifies one path and keeps three outcomes
apart. `exec_dir()` picks the first path that ran the probe, or raises.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

PROBE_BODY = "#!/bin/sh\nexit 0\n"
PROBE_TIMEOUT = 10
CANDIDATE_ENV = ("EXEC_DIR", "BUILD_DIR")
PROJECT_BUILD_DIR = (".build", "exec")

_probe_ids = itertools.count()


class NoExecDirectory(RuntimeError):
    """No candidate directory would start a file."""

    def __init__(self, purpose: str, outcomes: dict[str, str]) -> None:
        self.purpose = purpose
        self.outcomes = outcomes
        detail = ", ".join(f"{path}: {state}" for path, state in outcomes.items())
        super().__init__(
            f"no directory allows execution for {purpose}; "
            f"every candidate failed: {detail or 'nothing'}. "
            "Set EXEC_DIR to a directory on an executable mount."
        )


@dataclass(frozen=True)
class Probe:
    """One probe result. `state` is `runs`, `refused`, or `unprobed`."""

    directory: str
    state: str
    detail: str = ""

    @property
    def runs(self) -> bool:
        return self.state == "runs"

    @property
    def refused(self) -> bool:
        return self.state == "refused"


def probe(directory: str, timeout: float = PROBE_TIMEOUT) -> Probe:
    """Start a tiny file in `directory` and report what the kernel did.

    Only a clean start proves the mount allows execution. A mode bit and
    `os.access(_, os.X_OK)` report the inode, not the mount.
    """
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        return Probe(directory, "unprobed", f"cannot create: {exc}")

    unique = f"{os.getpid()}-{next(_probe_ids)}"
    path = os.path.join(directory, f".exec-probe-{unique}")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(PROBE_BODY)
        os.chmod(path, 0o700)
    except OSError as exc:
        _remove(path)
        return Probe(directory, "unprobed", f"cannot write: {exc}")

    try:
        done = subprocess.run([path], capture_output=True, timeout=timeout)
    except PermissionError as exc:
        return Probe(directory, "refused", f"kernel refused: {exc}")
    except subprocess.TimeoutExpired:
        return Probe(directory, "unprobed", "timed out")
    except OSError as exc:
        return Probe(directory, "unprobed", f"cannot start: {exc}")
    finally:
        _remove(path)

    if done.returncode == 0:
        return Probe(directory, "runs")
    return Probe(directory, "unprobed", f"exit {done.returncode}")


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def candidates(extra: tuple[str, ...] = ()) -> list[str]:
    """Candidate directories, most preferred first.

    Order: an explicit override from the environment, a project-local
    build directory, then the system temp directory.

    A path under the scratch root stays in the list. A host may mount its
    temp storage executable, so only the probe decides. Rejecting the path
    by name would drop a valid answer and hide a refused one.
    """
    found: list[str] = []
    for name in CANDIDATE_ENV:
        value = os.environ.get(name)
        if value:
            found.append(value)
    found.extend(extra)
    found.append(os.path.join(os.getcwd(), *PROJECT_BUILD_DIR))
    found.append(tempfile.gettempdir())

    kept: list[str] = []
    for item in found:
        real = os.path.realpath(os.path.expanduser(item))
        if real not in kept:
            kept.append(real)
    return kept


def exec_dir(purpose: str = "an executable file",
             extra: tuple[str, ...] = ()) -> str:
    """Return a directory that started the probe, or raise NoExecDirectory.

    Call this once and keep the result. Probing at every use costs a fork.
    """
    outcomes: dict[str, str] = {}
    for directory in candidates(extra):
        result = probe(directory)
        outcomes[directory] = (
            result.state
            if not result.detail
            else f"{result.state} ({result.detail})"
        )
        if result.runs:
            return directory
    raise NoExecDirectory(purpose, outcomes)


def run_script(path: str, *args: str) -> subprocess.CompletedProcess:
    """Run a script through the current interpreter.

    The interpreter sits on an executable mount. It reads the script as data,
    so a script on scratch works. Starting the script file does not.
    """
    return subprocess.run(
        [sys.executable, path, *args],
        capture_output=True,
        text=True,
        check=True,
    )
