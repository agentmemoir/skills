#!/usr/bin/env bash
# Compile-check and run the noexec-rust reference programs.
#
# The build output goes to .build/ in the project tree, not to TMPDIR: this
# skill's own rule is that a file must be started from executable storage.
# Skips (exit 0) when rustc is not installed, so the Node-only CI still passes.
#
# Usage: bash skills/portability/noexec-rust/scripts/self-check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
REFS="$ROOT/skills/portability/noexec-rust/references"
BUILD="$ROOT/.build/noexec-rust-self-check.$$"

if ! command -v rustc >/dev/null 2>&1; then
  echo "skip - noexec-rust self-check (rustc not installed)"
  exit 0
fi

cleanup() {
  rm -rf "$BUILD"
  # Remove the shared parent only when this run left it empty.
  rmdir "$ROOT/.build" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$BUILD"

probe_dir() {
  local d="$1" f rc
  f="$d/.exec-probe-$$"
  printf '#!/bin/sh\nexit 0\n' > "$f" || { echo "UNPROBED: cannot write $f" >&2; return 2; }
  chmod 755 "$f"
  rc=0
  "$f" >/dev/null 2>&1 || rc=$?
  rm -f "$f"
  case $rc in
    0) return 0 ;;
    126) echo "REFUSED: $d is on a noexec mount; the self-check needs executable storage" >&2; return 1 ;;
    *) echo "UNPROBED: direct run failed with $rc" >&2; return 2 ;;
  esac
}

probe_dir "$BUILD" || exit 1

rustc --edition 2021 --crate-type lib "$REFS/exec-dir.rs" -o "$BUILD/libexec_dir.rlib"
echo "ok   - exec-dir.rs compiles as a library"

rustc --edition 2021 --test "$REFS/exec-dir.rs" -o "$BUILD/exec-dir-tests"
"$BUILD/exec-dir-tests"
echo "ok   - exec-dir.rs tests pass"

rustc --edition 2021 --test "$REFS/spawn-helper.rs" -o "$BUILD/spawn-helper-tests"
# The wrong_* test is a deliberate defect demonstration and fails where
# scratch storage refuses execution. Run only the right_* examples.
"$BUILD/spawn-helper-tests" right_
echo "ok   - spawn-helper.rs right_ tests pass"

echo "OK noexec-rust self-check"
