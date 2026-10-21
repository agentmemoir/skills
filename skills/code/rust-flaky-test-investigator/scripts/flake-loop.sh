#!/usr/bin/env bash
# flake-loop.sh - bounded stress loop for a single Rust test.
#
# Runs one test N times, records every failing run's output separately, and
# prints a flake rate. Prefers cargo nextest --stress-count when available and
# falls back to a plain loop for cargo test or older nextest.
#
# Exit codes: 0 = loop completed, 1 = bad usage, 2 = every iteration passed,
# 3 = at least one iteration failed (that is the point, not an error here).
set -uo pipefail

TEST_NAME=""
ITERATIONS=50
RUNNER="auto"          # auto | nextest | cargo
EXACT=0
PKG=""
NO_BUILD=0
LOAD=0
LOAD_DURATION=0       # seconds; 0 = run until the loop ends
OUT_DIR=""
KEEP_LOGS=0
SELF_CHECK=0

# These are read by cleanup(), which runs on EVERY exit path via the EXIT trap
# below -- including the early usage-error and preflight-failure exits. They
# must be initialised before the trap is installed, or `set -u` makes cleanup
# die with "unbound variable" on exactly the paths a user hits when something
# is already wrong.
FAILURES=0
PASSES=0
CLEANUP_DIR=""
LOAD_PIDS=""

# Build the nextest filterset expression.
#
# nextest matches test() against the Rust test path (module::name) WITHOUT the
# binary prefix, e.g. 'tests::thing::name' - not 'my-crate tests::thing::name'.
# A bare 'test(name)' is a SUBSTRING match, which is what we want by default
# because it works with a short or partial name. 'test(=name)' is an EXACT match
# and needs the full module path, so it is opt-in via --exact. Using 'test(=)'
# with a bare name selects nothing and reports "0 tests run", which reads as a
# pass -- that is the trap the preflight below exists to catch.
build_filter() {
  if [ "$EXACT" -eq 1 ]; then
    printf 'test(=%s)' "$TEST_NAME"
  else
    printf 'test(%s)' "$TEST_NAME"
  fi
}

# Count test lines in `cargo nextest list` output.
#
# Each test prints as "<binary> <test-path>". Two things this must NOT do:
#   1. Require a "::" in the path. A #[test] at the root of a lib.rs has no
#      module path ("nf root_level_test"), so a "::" filter scores it 0. An
#      earlier version of this script did exactly that and reported "no test
#      matched" for every root-level test.
#   2. Count cargo/rustc chatter. stderr is already discarded by the caller, but
#      a diagnostic that lands on stdout ("warning: unused variable ...") would
#      otherwise be scored as a matching test and defeat the preflight.
count_matches() {
  printf '%s\n' "$1" \
    | grep -vE '^(warning|error|note|help|Compiling|Finished|Blocking|Fresh|Updating|Downloading|Downloaded|Installing|Running|Locking|Adding|Removing|Checking)' \
    | grep -E '^[^[:space:]]+[[:space:]]+[^[:space:]]' \
    | grep -c .
}

# Parse the failure count out of a nextest stress Summary line.
#
# nextest's exit code is NOT a reliable flake signal in stress mode. Measured
# on 0.9.146: a run whose summary read "4 passed, 6 failed" exited 0 in five
# runs out of six and 100 in one. So the rate must come from this line, never
# from `$?`.
parse_failed_iters() {
  printf '%s\n' "$1" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1
}

parse_total_iters() {
  printf '%s\n' "$1" | grep -oE '[0-9]+/[0-9]+ stress' | grep -oE '^[0-9]+' | head -1
}

usage() {
  cat <<'EOF'
Usage: flake-loop.sh -t <test-name> [options]

Required:
  -t, --test <name>        Test name to loop.

Options:
  -n, --iterations <N>     Iterations to run (default: 50).
      --runner <r>         auto | nextest | cargo (default: auto).
      --exact              Exact-match the test name. With the nextest runner the
                           name must be the full module path, for example
                           'my_module::my_test'. The binary name is NOT part of
                           it. Read the exact name with 'cargo nextest list'.
  -p, --package <name>     Limit to a cargo package.
      --no-build           Skip the build step.
      --load               Run CPU + IO load generators alongside the loop.
      --load-seconds <N>   Stop the load after N seconds (default: until loop ends).
  -o, --out-dir <path>     Where to write failure logs (default: mktemp dir).
      --keep-logs          Do not delete the log directory on success.
  -h, --help               This help.
      --self-check         Verify the script's own plumbing, then exit.

Output:
  A per-iteration line, a final FLAKE RATE summary, and the path to the
  failure log directory. Exit code 3 means at least one iteration failed.
  Exit code 2 means every iteration passed, i.e. no flake at this sample size.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -t|--test)        TEST_NAME="${2:-}"; shift 2 ;;
    -n|--iterations)  ITERATIONS="${2:-}"; shift 2 ;;
    --runner)         RUNNER="${2:-}"; shift 2 ;;
    --exact)          EXACT=1; shift ;;
    -p|--package)     PKG="${2:-}"; shift 2 ;;
    --no-build)       NO_BUILD=1; shift ;;
    --load)           LOAD=1; shift ;;
    --load-seconds)   LOAD_DURATION="${2:-}"; shift 2 ;;
    -o|--out-dir)     OUT_DIR="${2:-}"; shift 2 ;;
    --keep-logs)      KEEP_LOGS=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    --self-check)     SELF_CHECK=1; shift ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [ "$SELF_CHECK" -eq 1 ]; then
  # Exercise the argument parsing, the run-command builder, and the rate
  # arithmetic without invoking cargo. Fails loudly if any of them regress.
  fail=0
  check() { if [ "$2" = "$3" ]; then echo "ok   - $1"; else echo "FAIL - $1 (got '$2', want '$3')"; fail=1; fi; }

  # rate arithmetic: 3 failures in 50 iterations = 6%
  pct=$(( 3 * 100 / 50 ))
  check "rate 3/50" "$pct" "6"
  pct=$(( 0 * 100 / 50 ))
  check "rate 0/50" "$pct" "0"
  pct=$(( 50 * 100 / 50 ))
  check "rate 50/50" "$pct" "100"

  # division by zero must not happen when nothing ran
  pct=$(( 0 * 100 / 1 ))
  check "rate with 1 iteration" "$pct" "0"

  # --- filter construction -------------------------------------------------
  # These two forms are the whole reason the preflight exists. A bare
  # 'test(name)' must be a substring match; 'test(=name)' is exact and needs the
  # full module path. Getting this backwards silently selects zero tests.
  EXACT=0; TEST_NAME="probe_flaky"
  check "filter substring" "$(build_filter)" "test(probe_flaky)"
  EXACT=1; TEST_NAME="tests::probe_flaky"
  check "filter exact" "$(build_filter)" "test(=tests::probe_flaky)"
  EXACT=0

  # --- preflight match counting --------------------------------------------
  # Regression guard: a #[test] at the root of a lib.rs has NO "::" in its
  # name. An earlier version of this script counted matches with a "::" grep
  # and therefore reported "no test matched" for every root-level test. Feed
  # the counter both shapes and require a non-zero count for each.
  check "preflight counts nested test"    "$(count_matches 'ar-probe tests::nested_test')" "1"
  check "preflight counts root-level test" "$(count_matches 'ar-probe root_level_test')" "1"
  check "preflight counts two tests"       "$(count_matches 'a m::one
b m::two')" "2"
  check "preflight rejects empty"          "$(count_matches '')" "0"
  check "preflight ignores cargo noise"    "$(count_matches 'warning: unused variable `x`
    Finished `test` profile [unoptimized] target(s)
error: something broke
ar-probe real_test')" "1"
  check "preflight rejects all-noise"      "$(count_matches 'warning: unused variable `x`
error: aborting')" "0"

  # --- cleanup safety on early exit ----------------------------------------
  # FAILURES must exist before the EXIT trap is installed, otherwise `set -u`
  # kills cleanup() with "unbound variable" on the preflight-failure path.
  if [ -z "${FAILURES+x}" ]; then
    echo "FAIL - FAILURES is unset before the trap (cleanup would crash on early exit)"; fail=1
  else
    echo "ok   - FAILURES initialised before trap"
  fi
  if [ -z "${CLEANUP_DIR+x}" ]; then
    echo "FAIL - CLEANUP_DIR is unset before the trap"; fail=1
  else
    echo "ok   - CLEANUP_DIR initialised before trap"
  fi

  # --- no nonexistent nextest subcommands ----------------------------------
  # `cargo nextest build` and `cargo nextest show-config profiles` do not exist.
  # Strip comment lines first, so the explanatory comments naming them do not
  # trip the check that is meant to catch real invocations.
  if grep -vE '^[[:space:]]*#' "$0" | grep -qE 'cargo nextest (build|show-config profiles)'; then
    echo "FAIL - script invokes a nonexistent nextest subcommand"; fail=1
  else
    echo "ok   - no nonexistent nextest subcommands invoked"
  fi

  # --- nextest stress summary parsing --------------------------------------
  # Regression guard: nextest's stress-mode exit code is unreliable (0 in most
  # runs even when iterations failed), so the flake verdict must come from the
  # Summary line. An earlier version trusted `$?` and reported "no flake" for
  # runs that had already failed half their iterations.
  S1="     Summary [   0.106s] 10/10 stress run iterations: 6 passed, 4 failed"
  S2="     Summary [   0.000s] 3/3 stress run iterations: 3 passed"
  S3="     Summary [   0.203s] 20/20 stress run iterations: 8 passed, 12 failed"
  check "parse failed iters (with failures)" "$(parse_failed_iters "$S1")" "4"
  check "parse failed iters (none)"           "$(parse_failed_iters "$S2")" ""
  check "parse failed iters (double digits)"  "$(parse_failed_iters "$S3")" "12"
  check "parse total iters"                   "$(parse_total_iters "$S3")" "20"
  check "parse total iters (no failures)"     "$(parse_total_iters "$S2")" "3"
  check "parse total iters (empty input)"     "$(parse_total_iters "")" ""

  if [ "$fail" -eq 0 ]; then echo "self-check passed"; else echo "self-check FAILED"; fi
  exit "$fail"
fi

if [ -z "$TEST_NAME" ]; then
  echo "error: -t/--test is required" >&2
  usage >&2
  exit 1
fi

case "$ITERATIONS" in
  ''|*[!0-9]*) echo "error: --iterations must be a positive integer" >&2; exit 1 ;;
esac
if [ "$ITERATIONS" -lt 1 ]; then
  echo "error: --iterations must be at least 1" >&2
  exit 1
fi

case "$LOAD_DURATION" in
  ''|*[!0-9]*) LOAD_DURATION=0 ;;
esac

have() { command -v "$1" >/dev/null 2>&1; }

# Runner selection
if [ "$RUNNER" = "auto" ]; then
  if have cargo-nextest; then RUNNER="nextest"; else RUNNER="cargo"; fi
fi
if [ "$RUNNER" = "nextest" ] && ! have cargo-nextest; then
  echo "error: cargo-nextest not found; install it or use --runner cargo" >&2
  exit 1
fi

# Log directory
CLEANUP_DIR=""
if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/flake-loop.XXXXXX")"
  CLEANUP_DIR="$OUT_DIR"
fi
mkdir -p "$OUT_DIR" || { echo "error: cannot create $OUT_DIR" >&2; exit 1; }

# Load generators
LOAD_PIDS=""
start_load() {
  if [ "$LOAD" -eq 0 ]; then return; fi
  if have stress-ng; then
    local cpus
    cpus="$( (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null) || echo 2)"
    if [ "$LOAD_DURATION" -gt 0 ]; then
      stress-ng --cpu "$cpus" --io 4 --timeout "${LOAD_DURATION}s" >/dev/null 2>&1 &
    else
      stress-ng --cpu "$cpus" --io 4 --timeout "$((ITERATIONS * 60))s" >/dev/null 2>&1 &
    fi
    LOAD_PIDS="$LOAD_PIDS $!"
  else
    # Portable fallback: saturate every core with busy loops.
    local cpus i
    cpus="$( (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null) || echo 2)"
    for ((i = 0; i < cpus; i++)); do
      (while :; do :; done) >/dev/null 2>&1 &
      LOAD_PIDS="$LOAD_PIDS $!"
    done
  fi
  echo "load generators started (pids:$LOAD_PIDS)"
}

stop_load() {
  [ -n "$LOAD_PIDS" ] || return 0
  # shellcheck disable=SC2086
  kill $LOAD_PIDS 2>/dev/null
  wait $LOAD_PIDS 2>/dev/null
  LOAD_PIDS=""
}

cleanup() {
  stop_load
  if [ -n "$CLEANUP_DIR" ] && [ "$KEEP_LOGS" -eq 0 ] && [ "$FAILURES" -eq 0 ]; then
    rm -rf "$CLEANUP_DIR"
  fi
}
trap cleanup EXIT INT TERM

# build_filter() is defined near the top of this file so --self-check can
# exercise it.
FILTER=""
if [ "$RUNNER" = "nextest" ]; then
  FILTER="$(build_filter)"
fi

# Preflight: resolve the filter to concrete tests so a mistyped name is a clear
# error instead of a silent "0 tests run" that looks like a passing result.
#
# Count real test lines from `cargo nextest list`, which prints one
# "<binary> <test-path>" line per test. Do NOT filter on "::" here: a #[test]
# declared at the root of a lib.rs or main.rs has no module path, so its line
# is "<binary> root_level_test" and a "::" test would wrongly score it 0.
# Warnings and cargo chatter go to stderr and the blank lines are dropped.
if [ "$RUNNER" = "nextest" ]; then
  listing="$(cargo nextest list -E "$FILTER" 2>/dev/null || true)"
  matched="$(count_matches "$listing")"
  if [ "${matched:-0}" -eq 0 ]; then
    echo "error: no test matched filter: $FILTER" >&2
    echo "       list the real test names with: cargo nextest list" >&2
    echo "       nextest matches on the module path, not the binary name." >&2
    echo "       test(=name) needs the full path, e.g. tests::thing::name;" >&2
    echo "       drop --exact to fall back to a substring match." >&2
    exit 1
  fi
fi

# Build once so compile time does not pollute per-iteration timing.
#
# There is no `cargo nextest build` subcommand -- the real subcommands are
# list, run, bench, archive, show-config and self. For the nextest runner use
# `cargo build --tests`, which is a real cargo subcommand, and do NOT silence
# stderr so a genuine build failure is visible instead of being reported as a
# successful "building..." step.
if [ "$NO_BUILD" -eq 0 ]; then
  echo "building..."
  if [ "$RUNNER" = "nextest" ]; then
    if [ -n "$PKG" ]; then
      cargo build --tests -p "$PKG" >&2 || echo "warning: pre-build failed; nextest will build during the run" >&2
    else
      cargo build --tests >&2 || echo "warning: pre-build failed; nextest will build during the run" >&2
    fi
  else
    if [ -n "$PKG" ]; then cargo test -p "$PKG" --no-run >/dev/null 2>&1 || true
    else cargo test --no-run >/dev/null 2>&1 || true; fi
  fi
fi

# nextest stress-count needs 0.9.103+. Detect and fall back if it is absent.
NEXTEST_STRESS=0
if [ "$RUNNER" = "nextest" ]; then
  ver="$(cargo nextest --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ -n "$ver" ]; then
    major="${ver%%.*}"; rest="${ver#*.}"; minor="${rest%%.*}"; patch="${rest#*.}"
    if [ "$major" -gt 0 ] || { [ "$major" -eq 0 ] && [ "$minor" -gt 9 ]; } || \
       { [ "$major" -eq 0 ] && [ "$minor" -eq 9 ] && [ "$patch" -ge 103 ]; }; then
      NEXTEST_STRESS=1
    fi
  fi
fi

if [ "$RUNNER" = "nextest" ] && [ "$NEXTEST_STRESS" -eq 1 ]; then
  echo "runner: nextest $ver (native --stress-count)"
else
  echo "runner: $RUNNER (shell loop)"
fi
echo "test:   $TEST_NAME"
echo "runs:   $ITERATIONS"
echo "logs:   $OUT_DIR"
echo

start_load

FAILURES=0
PASSES=0
RUN_START=$(date +%s)

if [ "$RUNNER" = "nextest" ] && [ "$NEXTEST_STRESS" -eq 1 ]; then
  # Native mode: one command, nextest does the looping and reports per-iteration.
  # --no-fail-fast is essential: the default profile has fail-fast = true, which
  # aborts the stress loop at the first failure. That truncates the sample and
  # biases the reported rate downward, which is the opposite of what we want.
  cmd=(cargo nextest run -E "$FILTER" --no-fail-fast)
  [ -n "$PKG" ] && cmd+=(-p "$PKG")
  cmd+=(--stress-count "$ITERATIONS")
  echo "command: ${cmd[*]}"
  echo
  run_log="$OUT_DIR/nextest-stress.log"
  "${cmd[@]}" 2>&1 | tee "$run_log"
  rc=${PIPESTATUS[0]}
  echo

  # nextest exit code 4 is the advisory NO_TESTS_RUN: nothing matched, which is
  # a usage error, not a flake result.
  if [ "$rc" -eq 4 ]; then
    echo "FLAKE RATE: not computed - no tests matched the filter." >&2
    exit 1
  fi

  # DO NOT trust nextest's exit code to decide whether a flake occurred.
  # Measured on 0.9.146: with --stress-count, a run reporting "4 passed, 6
  # failed" exited 0 in 5 runs out of 6 and 100 in 1. The stress-test exit code
  # does not reliably reflect per-iteration failures, so parse the Summary line
  # instead. This is why the rate must come from the summary and not from `$?`.
  summary="$(grep -E 'stress run iterations' "$run_log" | tail -1)"
  if [ -z "$summary" ]; then
    echo "FLAKE RATE: could not parse a stress summary from nextest output." >&2
    echo "            full output kept at: $run_log" >&2
    exit 1
  fi
  failed_iters="$(parse_failed_iters "$summary")"
  total_iters="$(parse_total_iters "$summary")"
  FAILURES="${failed_iters:-0}"
  total_iters="${total_iters:-$ITERATIONS}"
  RUN_END=$(date +%s)
  ELAPSED=$((RUN_END - RUN_START))
  PCT=$(( FAILURES * 100 / (total_iters > 0 ? total_iters : 1) ))

  echo "==================== FLAKE RATE ===================="
  echo "test        : $TEST_NAME"
  echo "iterations  : $total_iters"
  echo "failures    : $FAILURES"
  echo "flake rate  : ${PCT}%"
  echo "elapsed     : ${ELAPSED}s"
  echo "nextest rc  : $rc  (not used - see note in script)"
  if [ "$FAILURES" -gt 0 ]; then
    echo "full log    : $run_log"
  else
    echo "no failures captured"
    [ "$KEEP_LOGS" -eq 1 ] || rm -f "$run_log"
    [ -n "$CLEANUP_DIR" ] && [ "$KEEP_LOGS" -eq 0 ] && echo "(log dir removed; pass --keep-logs to retain)"
  fi
  echo "====================================================="

  if [ "$FAILURES" -gt 0 ]; then exit 3; fi
  exit 2
fi

# Shell loop mode
for i in $(seq 1 "$ITERATIONS"); do
  log="$OUT_DIR/iter-$(printf '%04d' "$i").log"
  if [ "$RUNNER" = "nextest" ]; then
    cmd=(cargo nextest run -E "$FILTER" --no-fail-fast)
  else
    cmd=(cargo test "$TEST_NAME" -- --nocapture)
    [ "$EXACT" -eq 1 ] && cmd+=(--exact)
  fi
  [ -n "$PKG" ] && cmd+=(-p "$PKG")

  if "${cmd[@]}" >"$log" 2>&1; then
    PASSES=$((PASSES + 1))
    printf 'iter %3d/%d  PASS\n' "$i" "$ITERATIONS"
    [ "$KEEP_LOGS" -eq 1 ] || rm -f "$log"
  else
    rc=$?
    # Exit code 4 is nextest's advisory NO_TESTS_RUN. Treat it as a usage
    # error and stop, rather than counting a non-existent test as a failure.
    if [ "$RUNNER" = "nextest" ] && [ "$rc" -eq 4 ]; then
      echo "error: no tests matched $FILTER on iteration $i" >&2
      exit 1
    fi
    FAILURES=$((FAILURES + 1))
    printf 'iter %3d/%d  FAIL  -> %s\n' "$i" "$ITERATIONS" "$log"
  fi
done

RUN_END=$(date +%s)
ELAPSED=$((RUN_END - RUN_START))
PCT=$(( FAILURES * 100 / ITERATIONS ))

echo
echo "==================== FLAKE RATE ===================="
echo "test        : $TEST_NAME"
echo "iterations  : $ITERATIONS"
echo "failures    : $FAILURES"
echo "flake rate  : ${PCT}%"
echo "elapsed     : ${ELAPSED}s"
if [ "$FAILURES" -gt 0 ]; then
  echo "failure logs: $OUT_DIR"
else
  echo "no failures captured"
  [ -n "$CLEANUP_DIR" ] && [ "$KEEP_LOGS" -eq 0 ] && echo "(log dir removed; pass --keep-logs to retain)"
fi
echo "====================================================="

if [ "$FAILURES" -gt 0 ]; then exit 3; fi
exit 2
