# Fix Playbook

Recipes for measuring gates and for each fix class. Order fixes by expected wait saved over risk and effort. Take the person off the hook first; delete duplicated work second; then bound, select, cache, and shard. State what each fix gives up.

## Measure without paying twice

Find the gates: list CI workflow files, task-runner files, hook configs, required checks, and merge queue rules, as in the SKILL.md inventory step.

Time them from data that already exists:
- CI run pages and APIs show per-step durations. Prefer a week of runs; the median hides a bad tail, so look at the 95th percentile too.
- JUnit XML carries a `time` attribute per test case; sum and sort it to find the slow tail.
- Runner timing reports: pytest `--durations=0`, Jest `--verbose`, Go `-v`, nextest's timing output, Gradle build scans.
- If only one run is available, use it and say so.

When nothing exists, time the smallest representative invocation and say what it covers. Example: run one test file with the same flags rather than the whole suite.

Price each gate in the report: wall time, what it blocks, runs per day, people affected. Wait tax = wall time × runs per day × blocked people; for one person it is wall time × runs per day. For parallel stages, use the critical path, not the sum.

Failure mode: measuring a slow gate by re-running it. Use recorded durations first; run only what is needed to fill a gap, and never to confirm a number you already have.

## Take the person off the hook

Goal: nobody waits on the slow gate. The full gate still runs before merge.

- Keep the commit path fast: a hook should run changed-file checks in seconds, not minutes. pre-commit supports changed-file runs; lint-staged runs only staged files.
- Move slow checks to CI, push-time, or a scheduled stage. A nightly full suite is a normal home for slow work.
- Make long runs resumable: skip already-passed work on the next attempt where the runner supports it.
- For merge races, use a merge queue so the platform tests the queued head once; authors stop rebasing to re-trigger checks.
- Where the team prefers mainline purity, use speculative merging (Zuul, bors, merge queues). It serializes merges so the mainline stays green.
- For long, non-blocking checks, require an owner and a deadline. GitHub's own fix kept slow jobs but stopped them blocking merges, with a 72-hour remediation timer.

Failure modes: the fast local subset becomes the only gate (lossy); merge queues multiply CI load; nightly failures arrive after merge, so they need a rollback or fix path.

## Delete duplicate work

Goal: no check runs twice without adding a signal.

- Define each check once. Locally run the changed-files scope; in CI run the full scope of the same check.
- Drop whole-repo lint on small changes; run lint on changed files with a content-keyed cache. Keep the full lint on a schedule.
- Combine coverage with the test run instead of a second pass.
- Consolidate overlapping tools after comparing their rule sets and output.
- Build once, publish the artifact, and let test, lint, and package jobs reuse it.
- Keep defense-in-depth only where it is deliberate; remove accidental mirrors.

Failure modes: lint caches that ignore cross-file rules can miss findings (lossy); coverage instrumentation can push the fast gate over budget, in which case move coverage to a slower stage; tool consolidation can change formatting or message output on the margins.

## Bound the run

Goal: no gate runs unbounded; every failure is fast and clear.

- Set a per-gate wall budget and a per-test timeout from a measured baseline, for example p95 plus a margin.
- Enforce at multiple levels: job timeout, step timeout, test-level timeout. Many platforms default far too high (a common CI job default is 360 minutes).
- Fail fast in the interactive gate: exit on first failure, and order tests by likely failure, with the last failure first or a stepwise resume.
- In sharded runs, decide explicitly between collecting all results and cancelling early; platform defaults often cancel sibling jobs and hide failures.
- Keep one scheduled non-fail-fast run that shows all failures at once.

Failure modes: tight caps flake under load; a cap can hide a genuine slowdown instead of exposing it; per-test timeouts do not bound the sum of many slow tests; automatic build deadlines derived from a baseline proved flaky in one real tool (cargo-mutants 24.7.1), so treat build and test bounds separately.

## Select the scope

Goal: per-change cost tracks change size, not repository size, with a known backstop.

- Prefer declared dependency graphs when the build tool has them: run targets that depend on changed files (affected-target features in Nx, Turborepo, Pants, Bazel with a target determinator).
- File-diff selection is cheaper to adopt and weaker: run tests related to changed files (`--changedSince`, testmon). Coverage-based selection needs a mapping built once.
- Treat learned or predictive selection as the highest-risk tier; it needs retraining, a flake filter, and a fallback.
- Always keep a full-run backstop: nightly or post-submit, plus a fallback to all tests when the selector cannot understand a change.
- When a change touches shared code, interfaces, or generated code, widen or skip selection for that change.

Failure modes: selection rots silently; undeclared dependencies and dynamic code are missed; a wrong selection is a false green; selection frameworks may not see third-party dependency changes. Record what the selector does not model, and keep the full run.

## Reuse results

Goal: work already done is not repeated, and each cache key covers its inputs.

- Cache dependency downloads with keys on lockfiles.
- Cache compilation with a compiler cache or a task-level build cache (ccache, sccache, Gradle build cache, Bazel action cache).
- Cache test results keyed on source, flags, and toolchain (Go test cache, Jest cache, task-runner remote caches).
- Include the toolchain, compiler flags, lockfiles, and config in keys. Prefer content hashes over timestamps.
- Share caches across machines with a remote cache where the team has one.
- Provide a force-full switch and a periodic full run.

Failure modes: a key missing an input yields a stale green; same-key writes overwrite each other (GitLab); caches expire (GitHub removes entries untouched for 7 days); fork caches cross trust boundaries; hash instability defeats the cache silently.

## Shard and parallelize

Goal: wall-clock falls while every test still runs in exactly one shard.

- Split by historical timing, not alphabet or file size. First runs are unbalanced; remeasure and rebalance.
- Prefer fewer, balanced shards over many tiny ones. Fixed overhead per shard grows with shard count.
- Share one build or one prepared environment across shards where the tool allows it.
- Parallelize inside one machine as well (worker pools and parallel test runners), then cap concurrency to protect shared infrastructure.
- Merge coverage and results across shards; do not read a single shard's coverage as the suite's coverage.

Failure modes: sharding does not reduce total work and can increase it through per-shard builds; one slow shard dominates (rebuild the split from fresh timings); fail-fast cancellation hides sibling results; port or state collisions appear under parallelism.

## Fix slow tests by design

Goal: the fast gate contains only tests that are fast by construction.

- Classify tests by size and resource budget. Small tests avoid network, database, sleeps, and real clocks; sizes carry time limits.
- Replace sleeps with condition-based synchronization.
- Inject fake clocks and fake I/O for time- and service-dependent logic. Accept that fakes are lossy: keep some real-integration coverage in a slower stage, and watch for fake drift.
- Make tests hermetic: no dependency on external state, ordering, or the machine clock.
- Keep end-to-end and performance tests in a slower stage that still runs; split by size rather than deleting.
- When a later-stage failure escapes, add a fast test that would have caught it, so the fast gate strengthens over time.

Failure modes: fakes hide race conditions and timing bugs; a hermetic test that no longer runs anywhere silently removes coverage; the test pyramid is a heuristic, not a ratio to enforce blindly.

## Deflake

Goal: a red build means a real defect.

- Measure per-test flake rates from ordinary runs; one-off failures are not enough to quarantine.
- Prefer fixing the cause: time, ordering, shared state, ports, network, resource limits.
- Quarantine only with an owner, a bug link, and an expiry date. Revisit at expiry; do not let quarantine become a graveyard.
- Keep retries bounded and visible; report "passed on retry" instead of green.
- Exclude badly flaky tests from selection-based gates until they are fixed, so they cannot poison both the result and the selector.
- Track flake rate as a gate metric: it predicts wait time and trust.

Failure modes: retries convert real intermittent bugs to green; quarantine removes coverage while it lasts; flake detection needs history and a stable runner environment.

## Price and budget

Goal: verification cost is visible, owned, and capped per stage.

- Assign each gate a wall-clock budget and, where compute is billed, a money budget. Name an owner.
- Alert or fail when a gate breaches its budget; review the slowest gates on a schedule.
- Cap concurrency where a matrix or merge queue can flood runners.
- Separate budgets per stage: seconds on the commit path, minutes before merge, hours on the schedule.
- For agent-authored or bot-authored checks, require a cost estimate before the check lands, and prefer extending an existing gate.
- Make cost visible with platform accounting (compute minutes or credits per pipeline).

Failure modes: caps without a full-run backstop starve coverage; cost pressure on runner size can increase flake; budgets without owners drift; prices and quotas change, so re-check numbers before quoting them.

## Subject sweeps (mutation, fault injection, loops over examples)

Goal: cost tracks the change and the subject, not subjects × suite. Apply in this order.

1. Build a coverage or dependency map once. Run only tests that reach the subject. Uncovered subjects cost nothing.
2. Cache verdicts under content hashes of the subject, the covering tests, and a declared environment fingerprint. Invalidate when test files change. Keep a force-full switch, and list what is not in the key.
3. Scope to the diff (changed subjects only) and keep a periodic full sweep. Watch the trap: diff filtering can select subjects while still running all tests, and test-only changes can match nothing.
4. Prepare once and select the subject at run time where the platform allows it, instead of rebuilding per subject.
5. Clamp each subject run at a multiple of its measured baseline; injected faults can hang.
6. Run off the blocking path with resumable partial results; deliver findings into review with a per-change cap.
7. Suppress subjects that never produce actionable findings; measure the productive share and tune.
8. Require a green unmutated baseline before any subject result counts.

Failure modes: selection can miss kills (all major tools document this; PIT labels its incremental mode experimental); cached verdicts can go stale; cheap mitigations like depth limits are lossy; one central subject reached by nearly every test reduces selection to the full suite, so budget that case explicitly.

## Verify a fix and keep proof

- Re-measure the changed path once and compare before and after. Report both numbers.
- Confirm the check still detects a deliberate failure: break something small that the gate should catch, run the changed gate's scope, and confirm red, then revert. Skip this when it would be expensive; say so.
- Keep the backstop: full run on main or nightly, fallback to all tests, and invalidation on test-file changes.
- Name what the fix gives up, in the report, before claiming success.
- Watch for false green after each fix: selection misses, stale caches, retries hiding flakes, quarantine without expiry, and timeouts that mask hangs as passes.
