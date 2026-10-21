# Verification Antipattern Catalog

Eleven patterns that make verification gates slow or hostile. Each entry gives what it is, how to detect it, fixes stated in tool-agnostic terms with ecosystem examples, and what the fix gives up. Lossless/lossy labels are this skill's classification of verification strength, not a source claim.

Sources were checked on 2026-10-09. URLs appear with the finding. Quotes are verbatim and short.

## Whole-suite-per-change

**What it is.** Every change runs the full test, lint, and build suite, so gate time tracks repository size and grows forever. At Google's scale this broke: one commit per second made full testing per commit impossible, so only changed, covered code is mutated during review.

**Signals.** CI triggers on `pull_request` or `push` and runs a bare whole-suite command (`pytest`, `npm test`, `go test ./...`, `./gradlew test`, `mvn verify`, `cargo test`) with no selection step. No selection configuration exists: no affected-target settings, no `--changedSince`, no testmon, no target-determinator. Gate time is roughly constant regardless of diff size, and it matches the full suite time measured locally.

**Fixes (tool-agnostic).**
- Select by build graph and reverse dependencies: run only targets that depend on changed files. Examples: Nx "affected", Pants `--changed-since`, Turborepo `--affected`.
- Select by file diff: Jest `--changedSince`, pytest-testmon, Go test caching for unchanged packages.
- Select by learned prediction: model past change and test outcomes, as Meta does. Treat this as the highest-risk selector.
- Keep a full run behind every selector: nightly or post-submit full suite, and a safe fallback to all tests when the selector cannot understand a change, as Azure DevOps Test Impact Analysis documents.

**Gives up (lossy).** Fewer tests per change means some regressions surface later. Selection needs a maintained mapping or model and can silently rot. Dynamic languages, generated code, and undeclared dependencies are hard cases. A wrong selection is a false green. Bound the loss with the full-run backstop and fallback. Build-graph selection for declared dependencies is closer to lossless than coverage or learned selection.

**Sources.**
- Google's system mutates only changed, covered code during review: "Mutation testing is done incrementally" (arXiv 2102.11378, https://arxiv.org/html/2102.11378v2).
- TAP scale context: "more than 13K code projects, requiring 800K builds and 150 Million test runs" (https://research.google.com/pubs/archive/45861.pdf).
- Nx: "Nx determines the minimum set of projects that are affected by the change" (https://nx.dev/ci/features/affected).
- Turborepo: "Filter to only packages that are affected by changes on the current branch" (https://turborepo.dev/docs/reference/run).
- Pants caveat: "Pants does not understand transitive third-party dependencies in this context" (https://www.pantsbuild.dev/docs/using-pants/advanced-target-selection).
- testmon caveat: reliability is "the same as limits of coverage.py" (https://www.testmon.org/blog/determining-affected-tests/).
- Jest: "Runs tests related to the changes since the provided branch or commit hash" (https://jestjs.io/docs/cli).
- Test Impact Analysis fallback: "it falls back to running all tests" (https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis).
- Meta predictive selection, including the flaky-test noise problem: https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/.

## Cold every run

**What it is.** Each run re-downloads dependencies, recompiles unchanged code, and repeats work whose result is already known. The same cost is paid on every invocation.

**Signals.** No cache step in CI; logs show full downloads and full compiles every run. No compiler cache wrapper (`ccache`, `sccache`). No build or task cache configured: Gradle build cache off, no Bazel disk or remote cache, Turborepo reporting all misses. Test-result caches absent: Go never prints `(cached)`, Jest runs with `--no-cache`, the pytest cache directory is deleted.

**Fixes (tool-agnostic).** Key caches on content, not timestamps. Cache dependency downloads on lockfiles. Cache compilation on compiler inputs and flags (`ccache`, `sccache`, Gradle build cache, Bazel action cache). Cache test results on source and flags (Go test cache, Jest cache, Turborepo remote cache). Share caches across the team with remote caches (Bazel, Gradle, Turborepo). Make keys include the toolchain, flags, and lockfiles, and provide fallback keys for partial reuse.

**Gives up.** A correct cache is close to lossless: the check still runs whenever inputs change. A key that misses an input is lossy and produces a false green. Watch for: same-key overwrites (GitLab documents jobs overwriting each other's cache), eviction (GitHub removes caches unused for 7 days, 10 GB per repo), cross-trust-boundary access in forks, and timestamp-based incremental checks that skip stale outputs (MSBuild). Hash instability, such as absolute paths or embedded timestamps, quietly defeats a cache.

**Sources.**
- GitHub Actions cache: eviction and isolation (https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).
- GitLab: "two jobs with different paths, but the same cache key, overwrite their cache" (https://docs.gitlab.com/ci/caching/).
- ccache: "It speeds up recompilation by caching previous compilations" (https://ccache.dev/).
- sccache: "avoids compilation when possible, storing cached results" (https://github.com/mozilla/sccache).
- Gradle: "compute a build cache key that uniquely defines the task's outputs" (https://docs.gradle.org/current/userguide/build_cache.html).
- Bazel remote cache: action cache plus content-addressable store (https://bazel.build/remote/caching).
- Go: "go test caches successful package test results" (https://pkg.go.dev/cmd/go).
- MSBuild incremental caveat: timestamp-based, "output files that are up-to-date ... aren't executed" (https://learn.microsoft.com/en-us/visualstudio/msbuild/incremental-builds).

## One serial runner

**What it is.** One executor runs the entire suite sequentially, so gate time is the sum of all test times instead of the maximum of balanced shards.

**Signals.** One test job; no matrix, no `parallel`, no `parallelism`. Single-threaded invocations: `pytest` without `-n`, single-threaded test runners, JUnit parallel execution disabled. Many cores sit idle. No timing artifacts exist, so timing-based splitting is impossible.

**Fixes (tool-agnostic).** Shard across identical jobs and balance by historical timing: CircleCI `parallelism` plus split-by-timings; GitLab `parallel` plus a partition flag such as nextest's; GitHub Actions matrix. Parallelize inside one machine too: pytest-xdist, Jest worker pools, JUnit parallel execution. Share one build across shards instead of rebuilding per shard.

**Gives up.** Sharding buys wall clock, not total work. Each shard repeats setup, checkout, and often a build, so total CPU work rises; too many shards lose to fixed overhead. Balance needs history, and the first run is unbalanced. Fail-fast defaults can cancel other shards and hide the full signal. Tests that share state or ports break under parallelism, and coverage must be merged across shards.

**Sources.**
- cargo-mutants wall-clock model: `SHARD_STARTUP + (CLEAN_BUILD + TEST) + (N_TOTAL_MUTANTS / N_SHARDS) * (INCREMENTAL_BUILD + TEST)`; CPU model multiplies per-shard setup by shard count (https://mutants.rs/shards.html).
- nextest: each job does its own build; supports build archiving (https://nexte.st/docs/ci-features/partitioning/).
- CircleCI: splits "by using historic timing data" (https://circleci.com/docs/parallelism-faster-jobs/).
- GitHub matrix and default cancellation: "cancel all in-progress and queued jobs in the matrix" (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- JUnit: "enabling this property is only the first step" (https://docs.junit.org/6.1.3/writing-tests/parallel-execution.html).

## Human on the hook

**What it is.** A long check runs synchronously while the person or agent waits at commit, push, or merge time, and every rebase re-runs it.

**Signals.** Pre-commit or pre-push hooks run full builds or full suites. Hook configs call `pre-commit run --all-files` or a full test command. Branch protection requires all checks green on the PR head and authors rebase repeatedly instead of using a merge queue. No fast local subset exists; the only gate is the slow one.

**Fixes (tool-agnostic).** Run only fast checks locally, on changed files: pre-commit on changed files, lint-staged on staged files. Move slow checks to CI or a scheduled stage. Make long runs resumable. Serialize merges with a merge queue or speculative merging instead of rebase races. Keep the full gate before merge, and the full suite on a schedule.

**Gives up.** Mostly lossless for merged-state verification when a full gate still runs before merge. It becomes lossy when the fast local subset is the only gate. Compute moves from people to runners, and merge queues multiply CI load. Nightly-only signals arrive after the change is merged.

**Sources.**
- pre-commit runs hooks "on the changed files during git hooks" (https://pre-commit.com/).
- lint-staged: "formatters and linters against staged git files" (https://github.com/lint-staged/lint-staged).
- GitHub merge queue groups changes "with the latest version of the base_branch" (https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- Zuul speculative execution: https://zuul-ci.org/docs/zuul/latest/gating.html.
- The Not Rocket Science Rule: automatically maintain a repository that passes all tests (https://graydon2.dreamwidth.org/1597.html; implementations include bors, https://bors.tech/).
- Humble & Farley: the developer who checked in "waits for the results before moving on", while later pipeline stages "are lengthy activities" (https://www.informit.com/articles/article.aspx?p=1621865&seqNum=4).

## Unbounded run

**What it is.** Gates have no time budget, so a hang or an unexpectedly slow test blocks a runner until the platform maximum, and one hung test consumes a whole shard's budget.

**Signals.** Jobs and steps without explicit timeouts (GitHub Actions defaults to 360 minutes per job). No per-test timeout: no pytest-timeout, no JUnit `@Timeout`, no CTest `TIMEOUT`, no nextest slow-timeout. Incidents where CI was canceled manually or hit the platform limit instead of failing fast with a clear message.

**Fixes (tool-agnostic).** Set a per-gate wall budget and a per-test timeout derived from a measured baseline, for example p95 plus a margin, not a round number. Enforce at job, step, and test level. Emit timing data and review the slowest gates when they cross the budget. Note that baseline-derived build deadlines were tried by cargo-mutants and then removed for flakiness; prefer to bound test runs, and treat build bounds as separate.

**Gives up.** A hang timeout is effectively lossless, since a hung test has no usable result. A cap that kills legitimate slow work is lossy. Timeouts bound one test, not the sum, so a suite of many slow tests still needs a gate budget. Tight caps interact with load and can flake.

**Sources.**
- GitHub Actions job default 360 minutes (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- Go test binary default panic at 10 minutes (https://pkg.go.dev/cmd/go).
- pytest-timeout caveat: "termination may or may not be graceful" (https://raw.githubusercontent.com/pytest-dev/pytest-timeout/master/README.rst).
- CTest `TIMEOUT` (https://cmake.org/cmake/help/latest/prop_test/TIMEOUT.html); JUnit `@Timeout` (https://docs.junit.org/6.1.3/writing-tests/timeouts.html).
- Bazel maps test size to timeout: a large test defaults to 900 seconds (https://bazel.build/reference/test-encyclopedia).
- Google test sizes include time budgets, 60 / 300 / 900+ seconds (https://testing.googleblog.com/2010/12/test-sizes.html).
- Deriving a timeout from a measured baseline is established practice (PIT's factor 1.25 plus 4000 ms constant; cargo-mutants baseline timeout) but no single source states the general rule; treat the multiplier as a local calibration.

## Run past the first red

**What it is.** A run keeps going after the first failure, so the full suite time is paid before the failure is reported, and fixed or random order finds the likely culprit late. The inverse misuse also exists: fail-fast in a sharded matrix cancels shards that would have shown the full failure picture.

**Signals.** Test commands lack bail flags (`-x`, `--maxfail`, `--bail`, `-ff`). Matrix jobs do not set `fail-fast: false` where all shard results matter. Reruns always start from the same first test, and the first failing test is a known slow one.

**Fixes (tool-agnostic).** Exit at the first failure for the fast gate: pytest `-x`, Jest `--bail`, Maven `-ff`, nextest `fail-fast`, pre-commit `fail_fast`. Order by likely failure: last failures first, stepwise resume, or historical failure ordering. In sharded runs, decide deliberately between full signal and early cancellation. Keep one non-fail-fast full run, nightly, to see all failures.

**Gives up.** Fail-fast saves wall clock but reduces diagnostic breadth per run; on a busy branch that can mean more runs. Ordering assumes test independence and can reshuffle fixture setup. Cancelling sibling shards is lossy for that run and is recoverable by re-running.

**Sources.**
- pytest `-x` and `--ff` side-effect warning (https://docs.pytest.org/en/stable/reference/reference.html).
- Jest `--bail` (https://jestjs.io/docs/cli); Maven `-ff` (https://maven.apache.org/guides/mini/guide-building-for-different-environments.html).
- GitHub matrix fail-fast default (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- nextest fail-fast and slow-timeout configuration (https://nexte.st/docs/configuration/).
- StrykerJS option to report all failing tests "instead of bailing after the first failing test" (https://stryker-mutator.io/docs/stryker-js/configuration/).

## Double-check

**What it is.** The same check runs more than once, whole-repo work runs for a small change, coverage forces a second full test pass, or several tools check overlapping rules.

**Signals.** Pre-commit hooks mirror CI lint steps. CI lint runs over all files with no cache and no changed-file filter. A dedicated coverage job re-runs the suite after the test job already ran it. Overlapping linters, formatters, or type checkers for one language run in the same gate. The same build runs once for tests and again for lint or packaging.

**Fixes (tool-agnostic).** One source of truth per gate: define the check once, run changed files locally and the full scope in CI. Lint only what changed on PRs, with content-keyed caching. Combine coverage with the test run instead of a second pass. Consolidate overlapping tools after reconciling rule sets. Build once and reuse the artifact across jobs.

**Gives up.** Removing exact duplicates is lossless. Changed-file lint caches are lossy for cross-file rules: ESLint's cache "does not track dependencies between files" and can reuse a result after a dependency changed. Combining coverage shifts time onto the critical path; if that breaks the budget, put coverage in a slower stage. Tool consolidation can change output on the margins.

**Sources.**
- ESLint cache caveat (https://eslint.org/docs/latest/use/command-line-interface).
- Ruff as a replacement: "can be used to replace Flake8"; formatting is "> 99.9% of lines ... identical" to Black (https://docs.astral.sh/ruff/faq/).
- pre-commit recommends running hooks in CI as well (https://pre-commit.com/).
- pytest-cov handles xdist and coverage in one pass (https://raw.githubusercontent.com/pytest-dev/pytest-cov/master/README.rst).
- Jest `--coverage` (https://jestjs.io/docs/cli).

## Slow by design

**What it is.** The fast gate contains sleeps, real network, database, clock, or filesystem use, and large end-to-end or performance tests. No sharding or caching can fully fix a suite that is slow by construction.

**Signals.** Sleeps in tests and fixed waits for async work. Tests hit real hosts, real databases, production-like services, or the system clock. One test directory dominates runtime and runs on every change. Performance or benchmark tests run per change. No unit/integration/e2e separation exists.

**Fixes (tool-agnostic).** Classify tests by size and resource budget, and enforce the budget: small tests avoid network, database, and sleeps; sizes carry time limits (Google's 60 / 300 / 900+ seconds; Bazel encodes size to timeout). Replace sleeps with condition-based synchronization. Inject fake clocks and I/O. Keep the test pyramid, with fast hermetic tests in the per-change gate, and move end-to-end and performance tests to a slower stage.

**Gives up.** Splitting by size is close to lossless when the same test still runs in some gate, just later. Fake clocks and mocks are lossy for real timing, network, and integration behavior, and fakes drift from the real dependency. The pyramid is a heuristic; some system-level failures are only visible end to end.

**Sources.**
- Google test sizes: network, database, and sleep forbidden in small tests; time limits 60 / 300 / 900+ seconds (https://testing.googleblog.com/2010/12/test-sizes.html).
- Bazel size to timeout and resource restrictions (https://bazel.build/reference/test-encyclopedia).
- Software Engineering at Google: "All tests should strive to be hermetic" (https://abseil.io/resources/swe-book/html/ch11.html).
- Espresso on `Thread.sleep`: "these delays don't scale well" (https://developer.android.com/training/testing/espresso/idling-resource).
- Fake time: Java `Clock` (https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/Clock.html); Tokio time pause (https://docs.rs/tokio/latest/tokio/time/fn.pause.html).
- Test pyramid proportion: "70% unit tests, 20% integration tests, and 10% end-to-end tests" (https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html); Fowler's practical pyramid (https://martinfowler.com/articles/practical-test-pyramid.html).

## Flake tax

**What it is.** Tests that pass and fail on the same code force reruns and retries, erode trust in red builds, and make gate durations unstable. Google measured the base rate rather than relying on anecdotes.

**Signals.** CI is configured to rerun or retry on failure and reports "passed on retry". Known-flaky lists, quarantine directories, markers, or skip lists exist. A test's history shows both pass and fail on the same commit. Gate duration varies widely for the same test set, and manual reruns are common.

**Fixes (tool-agnostic).** Measure the flake rate per test from ordinary runs; do not rely on gut feel. Fix or remove flaky tests instead of making retries permanent. Quarantine with an owner, a bug, and an expiry. Remove badly flaky tests from selection until fixed, as Meta does. Reduce the flake surface structurally: smaller, hermetic tests with less real I/O. Keep retries bounded and visible, never silently green.

**Gives up.** Retries and reruns are lossy: they convert real intermittents into green, and they train people to treat failure as a hint. Quarantine is lossy while it lasts and becomes a graveyard without an owner and expiry. Measurement and fix-by-design are lossless but are slow work.

**Sources.**
- Google: "Almost 16% of our tests have some level of flakiness" (https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html); automatic quarantine "could easily mask a real race condition" (same URL).
- Meta probabilistic flakiness: all end-to-end tests carry some flakiness; "We treat the second attempt as the final outcome of the test" (https://engineering.fb.com/2020/12/10/developer-tools/probabilistic-flakiness/).
- Google flake sources: binary size and RAM correlate with flakiness (https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html).
- TAP's flake handling at scale (https://research.google.com/pubs/archive/45861.pdf).

## Unpriced check

**What it is.** Gates have no time or money budget, no owner, no concurrency cap, and unlimited retries. Nobody can say what a check costs per change, and nothing stops slow growth.

**Signals.** No job timeout, no per-test timeout, no suite budget. No review of CI usage or cost. Matrix `max-parallel` unset. Retries enabled everywhere. Gate duration grows over time with no alert.

**Fixes (tool-agnostic).** Give each gate a wall-clock and money budget and an owner; alert or fail on breach. Make cost visible with the platform's accounting. Cap concurrency. Separate budgets per stage: a short per-change budget and a longer scheduled budget. Treat test execution as a constrained resource; Google's TAP explicitly optimizes detection per unit of compute.

**Gives up.** Any cap that skips work is lossy unless the full run still happens on a schedule. Cost pressure can push work to weaker runners and increase flake. Budgets without owners drift.

**Sources.**
- GitHub Actions billing is per-minute per runner type (https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- GitLab compute minutes: "Job duration / 60 * Cost factor" (https://docs.gitlab.com/ci/pipelines/compute_minutes/).
- CircleCI credits: "the machine size and duration you use" (https://circleci.com/docs/credits/).
- GitHub `max-parallel` (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- TAP: improve "the ratio of change detection per unit of compute resource spent" (https://research.google.com/pubs/archive/45861.pdf).

## Subject sweep

**What it is.** A script loops over verification subjects and runs the full suite for each one. The classic case is mutation testing or fault injection, where each mutant, fault, or parameterized example gets inject plus full-suite-run. Cost is subjects × suite, the most expensive shape in this catalog. The same shape appears whenever a loop over examples, platforms, schemas, or configurations re-runs everything each time.

**Signals.** A loop whose body launches a bare full-suite command. The same suite is run once per subject with no per-subject selection. No coverage or dependency map exists to pick covering tests. No cache of prior results, no diff scope, no per-run timeout. The job is expected to take much longer than the suite time and grows linearly with the number of subjects.

**Fixes (tool-agnostic), in the order that pays first.**
- **Select per subject from a map built once.** Record which tests exercise which code in one baseline pass, then run only covering tests per subject. Uncovered subjects resolve to "uncovered" with no execution. This is standard in production mutation systems: PIT, StrykerJS, mutmut, and Google select per test coverage (see sources). Mull's 2018 paper described per-test coverage, but its JIT engine was removed in January 2021; current Mull filters mutants by coverage rather than selecting tests. For subjects without a coverage map, use a declared dependency map instead.
- **Reuse verdicts under content hashes.** Reuse a result only when the subject's code, the selected tests' code, and a declared environment fingerprint are unchanged. Invalidate on test-file changes. Keep a force-full switch. Document what is not in the key; Stryker is explicit that environment changes outside source and tests are not detected.
- **Scope to the diff.** Run only subjects overlapping the changed regions, plus a periodic full sweep. Note the trap: `cargo-mutants --in-diff` selects mutants, not tests; all tests still run per selected mutant. Test-only diffs match no source mutants, so test-file changes must invalidate cached verdicts. Diff scoping is "not a substitute for a full test run".
- **Prepare once, switch at run time.** Compiling or rebuilding per subject dominates. Production systems compile all mutants once behind a run-time switch (mutation switching or schemata: Stryker, Mull) or instrument in memory (PIT bytecode). Mutant schemata measured 9.62 times faster than plain per-mutant analysis, compile plus run, in the AccMut paper, on the first 100 tests of two C subjects.
- **Clamp every run.** Bound each subject run at a multiple of its measured baseline, because faults frequently create infinite loops. PIT uses factor 1.25 plus a 4000 ms constant; cargo-mutants derives the test timeout from its baseline run. cargo-mutants removed its automatic build timeout in 24.7.1 after baseline-derived build deadlines proved flaky.
- **Run off the blocking path, resumable, with capped findings.** Google runs mutation analysis asynchronously during review and surfaces at most one mutant per changed line; Meta schedules fault execution off-peak, 7 p.m. to 7 a.m. Pacific. Save partial results so an interrupted run resumes.
- **Suppress unproductive subjects.** Google's heuristics, one-per-line selection plus arid-node suppression, raised the share of mutants developers called productive from 15% to 89% (the 11% unproductive figure is the complement, derived). Unproductive findings are a wait tax with no value, and they erode trust.
- **Prove the baseline first.** A subject result counts only if the unmutated baseline passed in the same environment. cargo-mutants runs the baseline first and warns that skipping it makes results meaningless.

**Gives up.** Selection can miss kills: PIT, Stryker, and mutmut each state their incremental modes admit error; PIT calls its feature experimental. Diff scoping misses cross-region regressions. A subject reached by nearly every test gets covering tests equal to the suite, and the only cheap mitigation, a stack-depth limit, is lossy. Caching can go stale; no source measures how often hash-keyed reuse gives a wrong verdict. Sharding buys wall clock, not total work.

**Corrected facts, so the skill does not repeat bad claims.**
- PIT's "meta mutant" survivor grouping is not yet implemented; do not cite it as a feature.
- PIT's test-distance filter was removed in 1.9.0.
- Mull's SQLite output is an offline report, not a documented result cache.
- PIT's git integration ships through the licensed Arcmutate plugin, not as a native feature.
- Google's 820 / 77 / 7 mutants-per-changelist medians are all diff-scoped arms; the drop comes from one-per-line selection plus arid suppression.

**Sources.**
- PIT: "pick a set of test cases targeted at the mutated code"; incremental tracking "of the code and tests"; feature called experimental (https://pitest.org/quickstart/basic_concepts/, https://pitest.org/quickstart/incremental_analysis/).
- PIT timeouts: `--timeoutFactor` defaults to 1.25; `--timeoutConst` defaults to 4000 (https://pitest.org/quickstart/maven).
- StrykerJS: coverageAnalysis perTest "Only the tests that cover a specific mutant are executed"; incremental "only runs mutation testing on the changed code"; static mutants run all tests (https://stryker-mutator.io/docs/stryker-js/configuration/, https://stryker-mutator.io/docs/stryker-js/incremental/, https://stryker-mutator.io/docs/mutation-testing-elements/static-mutants).
- cargo-mutants: in-diff tests "only mutants that overlap with regions changed in the diff"; baseline sets the test timeout; shards run "an incremental build and ... all the tests"; build timeout removed in 24.7.1 (https://mutants.rs/in-diff.html, https://mutants.rs/baseline.html, https://mutants.rs/shards.html, https://mutants.rs/changelog.html).
- Google: diff-scoped, arid suppression, one mutant per line, medians 820 / 77 / 7; productive share "from 15% to 89%" (https://arxiv.org/html/2102.11378v2).
- Meta: learned mutation templates; off-peak "between 7 p.m. and 7 a.m. Pacific time"; hundreds to thousands of mutants per day (https://arxiv.org/abs/2010.13464v3).
- AccMut: "mutation schemata is on average 9.62 times faster", first 100 tests of two C subjects (https://ar5iv.labs.arxiv.org/html/1702.06689).
- Mull: git-diff incremental mode is experimental (https://mull.readthedocs.io/en/latest/IncrementalMutationTesting.html).

## Lossless and lossy at a glance

Lossless or near-lossless, given correct configuration: complete-input-hash caches, exact duplicate removal, sharding when all shards run, merge queues with the full gate required, hang timeouts above measured p95, flake measurement and fix-by-design, size-based stage splitting, cost visibility.

Lossy, acceptable only with a full-run backstop and stated risk: diff, coverage, and learned selection; retry-until-green and unbounded quarantine; tight budgets that truncate work; fail-fast cancellation in a single run; lint caches blind to cross-file rules; fakes where real timing or integration matters.

## Cross-cutting counter-evidence

Selection is not automatically unsafe: Google and Meta report controlled accuracy, and Test Impact Analysis ships a fallback. The antipattern is unmeasured selection with no backstop, not selection itself.

Sharding does not reduce total work: per-shard setup multiplies, and a shard-heavy run can cost more overall than it saves wall clock.

Caches can be wrong: GitLab documents same-key overwrites, and ESLint's cache ignores cross-file dependencies. Cache means "reuse", not "correct".

Google's 16% flake figure is from 2016. Rates differ by repo and stack; use it as an order-of-magnitude warning, not a benchmark.

The test pyramid is a heuristic. End-to-end tests remain the only check for some system-level failures.
