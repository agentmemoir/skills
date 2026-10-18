"""Tests for `exec_dir`. Run with `python -m pytest`.

Every test passes on a host that starts files from scratch and on a host
that refuses. No test skips. No test asserts a directory name.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import exec_dir as exec_dir_module
from exec_dir import NoExecDirectory, candidates, exec_dir, probe, run_script


def _scratch(path, monkeypatch):
    """Make `path` the scratch root for this test."""
    monkeypatch.setenv("TMPDIR", str(path))
    monkeypatch.setattr(tempfile, "tempdir", None)


def test_probe_reports_a_known_state(tmp_path):
    result = probe(str(tmp_path))
    assert result.state in {"runs", "refused"}
    assert result.runs is (result.state == "runs")
    assert result.refused is (result.state == "refused")


def test_probe_never_claims_runs_for_an_uncreatable_path():
    result = probe("/proc/no-such-directory/x")
    assert result.state == "unprobed"
    assert not result.runs
    assert not result.refused


def test_candidates_order_is_env_then_project_then_temp(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setenv("EXEC_DIR", str(tmp_path / "override"))
    monkeypatch.setenv("BUILD_DIR", str(tmp_path / "build"))
    found = candidates()
    assert found[0] == os.path.realpath(str(tmp_path / "override"))
    assert found[1] == os.path.realpath(str(tmp_path / "build"))
    assert found[-1] == os.path.realpath(str(tmp_path))
    assert any(item.endswith(os.path.join(".build", "exec")) for item in found)


def test_a_scratch_candidate_is_kept_and_probed(tmp_path, monkeypatch):
    """A host may mount its temp storage executable, so it is not rejected."""
    _scratch(tmp_path, monkeypatch)
    assert os.path.realpath(str(tmp_path)) in candidates()


def test_exec_dir_with_no_env_returns_a_working_directory(monkeypatch):
    """The blocker: an ordinary host must get a usable path, not an error.

    The working directory is created inside the project, not under
    `tmp_path`. On a noexec host the project tree is executable storage
    (pytest itself runs from it), while `tmp_path` is exactly the scratch
    location this skill says not to put a program in.
    """
    project = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(dir=project) as work:
        monkeypatch.chdir(work)
        monkeypatch.delenv("EXEC_DIR", raising=False)
        monkeypatch.delenv("BUILD_DIR", raising=False)
        directory = exec_dir("a test helper")
        assert probe(directory).runs
        # The project build dir is preferred when it runs.
        build = Path(work) / ".build" / "exec"
        if probe(str(build)).runs:
            assert os.path.realpath(directory) == os.path.realpath(str(build))


def test_exec_dir_skips_a_refused_candidate_and_falls_through(monkeypatch):
    """A failing first candidate must not stop the search."""
    project = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(dir=project) as work:
        monkeypatch.setenv("EXEC_DIR", "/proc/no-such-directory/x")
        monkeypatch.setenv("BUILD_DIR", str(Path(work) / "build"))
        directory = exec_dir("a test helper")
        assert os.path.realpath(directory) != os.path.realpath(
            "/proc/no-such-directory/x"
        )
        assert probe(directory).runs


def test_error_names_each_candidate_and_state(tmp_path, monkeypatch):
    """Every candidate is named, even when none can run."""
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setenv("EXEC_DIR", "/proc/no-such-directory/x")
    monkeypatch.delenv("BUILD_DIR", raising=False)

    def always_unprobed(directory, timeout=None):
        return exec_dir_module.Probe(directory, "unprobed", "cannot create")

    monkeypatch.setattr(exec_dir_module, "probe", always_unprobed)
    with pytest.raises(NoExecDirectory) as caught:
        exec_dir("a test helper")
    message = str(caught.value)
    assert "/proc/no-such-directory/x" in message
    assert "unprobed" in message
    assert "every candidate failed" in message


def test_refused_scratch_candidate_is_reported_not_silently_dropped(
    tmp_path, monkeypatch
):
    """A refused candidate must appear in the error, not vanish from it."""
    monkeypatch.setenv("EXEC_DIR", str(tmp_path / "scratch"))
    monkeypatch.delenv("BUILD_DIR", raising=False)
    seen = []

    def refuses(directory, timeout=None):
        seen.append(directory)
        return exec_dir_module.Probe(directory, "refused", "kernel refused")

    monkeypatch.setattr(exec_dir_module, "probe", refuses)
    with pytest.raises(NoExecDirectory) as caught:
        exec_dir("a test helper")
    assert os.path.realpath(str(tmp_path / "scratch")) in seen
    assert "refused" in str(caught.value)


def test_run_script_runs_a_scratch_file_through_the_interpreter(tmp_path):
    script = tmp_path / "gen.py"
    # A bogus shebang proves the file itself is never started.
    script.write_text(
        "#!/nonexistent/interpreter\nprint('ok')\n", encoding="utf-8"
    )
    script.chmod(0o755)
    assert run_script(str(script)).stdout.strip() == "ok"


def test_run_script_needs_no_execute_bit(tmp_path):
    script = tmp_path / "plain.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    assert not os.access(str(script), os.X_OK)
    assert run_script(str(script)).stdout.strip() == "ok"


def test_direct_start_follows_the_measured_mount(tmp_path):
    """The mount state decides. Both branches assert something true."""
    path = tmp_path / "helper.py"
    path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    path.chmod(0o755)
    state = probe(str(tmp_path))
    assert state.state in {"runs", "refused"}
    if state.refused:
        with pytest.raises(PermissionError):
            subprocess.run([str(path)], check=True, capture_output=True)
    else:
        done = subprocess.run(
            [str(path)], check=True, capture_output=True, text=True
        )
        assert done.stdout.strip() == "ok"


def test_scratch_program_guard_detects_an_executable(tmp_path):
    """The guard used by the negative test must see a real program.

    The guard reads mode bits on purpose. It asks "did a program land
    here", not "will this start". A placement guard may use mode bits;
    an execution check may not.
    """
    helper = tmp_path / "helper"
    helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    helper.chmod(0o755)
    offending = [p for p in tmp_path.iterdir() if p.stat().st_mode & 0o111]
    assert offending == [helper]
    assert sys.executable
