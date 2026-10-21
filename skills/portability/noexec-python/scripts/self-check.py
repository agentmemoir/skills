#!/usr/bin/env python3
"""self-check.py - verify the noexec-python reference helper.

Repo tooling, not runtime behaviour of the skill. It loads
``references/exec_dir.py`` with the standard library only, so the skill's
claims are checked on a machine without pytest. When pytest is installed, the
twelve reference tests in ``references/test_exec_dir.py`` also run.

Usage:
    python3 skills/portability/noexec-python/scripts/self-check.py
    python3 skills/portability/noexec-python/scripts/self-check.py --quiet

Exit 0 = every check passed (a missing pytest is reported as a skip).
Exit 1 = at least one check failed.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HELPER_PATH = SKILL / "references" / "exec_dir.py"
REFERENCE_TESTS = SKILL / "references" / "test_exec_dir.py"
QUIET = "--quiet" in sys.argv[1:]

RESULTS: list[bool] = []


def check(name: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - one failure must not stop the run
        RESULTS.append(False)
        print(f"FAIL - {name}\n       {type(exc).__name__}: {exc}", flush=True)
    else:
        RESULTS.append(True)
        if not QUIET:
            print(f"ok   - {name}", flush=True)


def load_helper():
    """Import references/exec_dir.py without writing bytecode into the skill."""
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("noexec_exec_dir", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


helper = load_helper()


def save_env(*names: str) -> dict[str, str | None]:
    return {name: os.environ.get(name) for name in names}


def restore_env(saved: dict[str, str | None]) -> None:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_probe_reports_three_states() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = helper.probe(tmp)
        assert result.state in {"runs", "refused"}, result
        assert result.runs is (result.state == "runs"), result
        assert result.refused is (result.state == "refused"), result

        blocker = Path(tmp) / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        broken = helper.probe(str(blocker / "child"))
        assert broken.state == "unprobed", broken
        assert not broken.runs and not broken.refused, broken


def test_candidates_order_is_env_then_project_then_temp() -> None:
    saved = save_env("EXEC_DIR", "BUILD_DIR", "TMPDIR")
    saved_tempdir = tempfile.tempdir
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EXEC_DIR"] = str(Path(tmp) / "override")
            os.environ["BUILD_DIR"] = str(Path(tmp) / "build")
            os.environ["TMPDIR"] = tmp
            tempfile.tempdir = None

            found = helper.candidates()
            assert found[0] == os.path.realpath(str(Path(tmp) / "override")), found
            assert found[1] == os.path.realpath(str(Path(tmp) / "build")), found
            assert found[-1] == os.path.realpath(tmp), found
            assert any(
                item.endswith(os.path.join(".build", "exec")) for item in found
            ), found
    finally:
        restore_env(saved)
        tempfile.tempdir = saved_tempdir


def test_exec_dir_skips_an_unusable_candidate() -> None:
    saved = save_env("EXEC_DIR", "BUILD_DIR")
    try:
        # A project-local workspace keeps the candidate on executable storage
        # and lets TemporaryDirectory remove everything this check creates.
        with tempfile.TemporaryDirectory(dir=SKILL) as work:
            blocker = Path(work) / "blocker"
            blocker.write_text("x", encoding="utf-8")
            os.environ["EXEC_DIR"] = str(blocker / "child")
            os.environ["BUILD_DIR"] = str(Path(work) / "build")

            directory = helper.exec_dir("the self-check")
            assert helper.probe(directory).runs, directory
            assert os.path.realpath(directory) == os.path.realpath(
                os.environ["BUILD_DIR"]
            ), directory
    finally:
        restore_env(saved)


def test_error_names_each_candidate_and_state() -> None:
    saved = save_env("EXEC_DIR", "BUILD_DIR")
    real_probe = helper.probe
    try:
        os.environ["EXEC_DIR"] = "/nonexistent/noexec-self-check"
        os.environ.pop("BUILD_DIR", None)

        def always_unprobed(directory, timeout=None):
            return helper.Probe(directory, "unprobed", "cannot create")

        helper.probe = always_unprobed
        try:
            helper.exec_dir("the self-check")
        except helper.NoExecDirectory as exc:
            message = str(exc)
        else:
            raise AssertionError("exec_dir must raise when every candidate is unprobed")

        assert "/nonexistent/noexec-self-check" in message, message
        assert "unprobed" in message, message
        assert "every candidate failed" in message, message
    finally:
        helper.probe = real_probe
        restore_env(saved)


def test_run_script_needs_no_execute_bit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "plain.py"
        # A bogus shebang proves the file itself is never started.
        script.write_text(
            "#!/nonexistent/interpreter\nprint('ok')\n", encoding="utf-8"
        )
        assert not os.access(script, os.X_OK), script
        done = helper.run_script(str(script))
        assert done.stdout.strip() == "ok", done


def test_placement_guard_sees_a_program() -> None:
    """The negative-test guard reads mode bits on purpose.

    It asks "did a program land here", not "will this start".
    """
    with tempfile.TemporaryDirectory() as tmp:
        program = Path(tmp) / "helper"
        program.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        program.chmod(0o755)

        offending = [
            item for item in Path(tmp).iterdir() if item.stat().st_mode & 0o111
        ]
        assert offending == [program], offending


def test_reference_pytest_suite() -> None:
    try:
        import pytest  # noqa: F401
    except ImportError:
        if not QUIET:
            print("skip - reference pytest suite (pytest not installed)", flush=True)
        return

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            REFERENCE_TESTS.name,
        ],
        cwd=str(REFERENCE_TESTS.parent),
        capture_output=True,
        text=True,
        env=env,
    )
    if done.returncode != 0:
        raise AssertionError((done.stdout + done.stderr).strip()[-4000:])


def main() -> int:
    check("probe keeps runs, refused, and unprobed apart", test_probe_reports_three_states)
    check("candidates are env, then project, then temp", test_candidates_order_is_env_then_project_then_temp)
    check("exec_dir skips an unusable candidate", test_exec_dir_skips_an_unusable_candidate)
    check("the error names each candidate and state", test_error_names_each_candidate_and_state)
    check("run_script needs no execute bit", test_run_script_needs_no_execute_bit)
    check("the placement guard sees a program", test_placement_guard_sees_a_program)
    check("the reference pytest suite passes", test_reference_pytest_suite)

    failed = RESULTS.count(False)
    if failed:
        print(f"FAIL noexec-python self-check ({failed} failed)", flush=True)
        return 1
    print("OK noexec-python self-check", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

