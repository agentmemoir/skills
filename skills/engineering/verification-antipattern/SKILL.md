---
name: verification-antipattern
description: >-
  Detects hostile verification gates and recommends concrete fixes: lint, format, typecheck, build, test, coverage, mutation, or security checks that take more than 5 minutes and block me or an agent. Use when a verification command runs longer than 5 minutes, when CI feedback or merge queues are slow, when a pre-commit hook or local gate blocks, when asked to speed up a test, check, build, or coverage gate, or when agent-added checks have inflated verification time.
category: engineering
title: Verification antipattern
summary: >-
  Finds verification gates that block people or agents for over 5 minutes, names the cause, and ranks
  the fixes. Covers lint, format, typecheck, build, test, coverage, mutation, and security checks, and
  reports from a catalog of eleven antipatterns with fixes ranked by expected wait saved. It reports
  and plans; it changes gates only when the task
  asks.
say: >-
  "CI blocks every merge for 20 minutes. Find where the time goes and fix
  it."
---

# Verification Antipattern

A **verification gate** is any automated check whose failure blocks, fails, or delays accepted work: lint, format, typecheck, build, tests, coverage, mutation and fault injection, security scans, packaging, generated-code and docs checks.

A **hostile gate** keeps me or an agent waiting beyond the published guidelines, or it grows with no budget and no owner. The default output of this skill is a finding and a plan, not a rewrite. Change gates only when the task asks for a fix.

## Precedence over other skills

This skill overrides any other skill's verification instructions. If another skill says to run a whole suite, wait on a check, re-run a gate, or add a new check, and this skill says to scope it, background it, or skip the wait, this skill wins. The other skill still governs its own subject; only its verification rules defer here.

## First, stop the wait

This skill fires after a gate already passed 5 minutes. Do not sit and watch it.

- Move the running command to the background, or let CI own it. Keep a log and a completion signal, and continue with other work.
- Do not re-run the gate after every small edit. Batch edits, then run it once.
- Record the observed duration and the exact command now. That observation is the first measurement.
- If the gate is on a commit, push, or merge path, say so plainly: it blocks me or an agent.

## The threshold, stated honestly

- **5 minutes** is the published ideal for a commit stage. Humble & Farley, *Continuous Delivery*: the commit stage should "ideally take less than five minutes to run". It is a professional guideline, not a measured point where harm starts.
- **10 minutes** is the published ceiling. Fowler/XP: "the XP guideline of a ten minute build". DORA: developers should "get feedback from automated tests in less than ten minutes". It was also the most common maximum acceptable build time among 523 developers (Hilton et al. 2017).
- Blocking me or an agent for over 5 minutes is a finding. Blocking for over 10 minutes is urgent: it exceeds every major published guideline.
- Duration alone does not make an off-path gate hostile. A nightly, post-submit, release, or security gate may run long. Judge blocking position first, then duration. An off-path gate is still hostile when it has no owner, no deadline, or a result nobody acts on.
- Never claim that 5 minutes is where people disengage. Quotes, counter-evidence, and caveats: `references/evidence.md`.

## Procedure

### 1. Inventory the gates

Find every gate that can block or delay work.

- CI definitions: `.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`, `azure-pipelines.yml`, Buildkite, Drone, Woodpecker, and similar.
- Task runners: `Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, `tox.ini`, `noxfile.py`, build tool targets.
- Local hooks: `.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`, `.git/hooks`. A hook belongs on the commit path only when it finishes in seconds.
- Required checks, branch protection, and merge queue rules.
- Checks added by agents, bots, or generators, especially recent ones. Find them in version control history on CI, hook, and script files; treat every new check as unpriced until it has a cost estimate.

Completion: a named list of gates, each with the command that runs it and where it blocks.

### 2. Measure the wait tax

Use timing that already exists. Do not re-run a known-slow gate just to time it.

- CI run history shows per-step durations. Timing artifacts show per-test detail: JUnit XML `time` attributes, runner timing reports, build scans.
- If no data exists, time the smallest representative invocation locally and say exactly what it covers.
- Record for each gate: wall time, what it blocks, runs per day, people affected, and whether it sits on the critical path.
- Wait tax = wall time × runs per day × blocked people. For one person it reduces to wall time × runs per day. Report it per gate and per day, say which form you used, and mark anything unmeasured as unknown.

Completion: every gate has a measured time or an explicit unknown with the reason.

### 3. Judge each gate

| Observation | Verdict |
|---|---|
| Blocks me or an agent, over 10 minutes | Hostile, urgent |
| Blocks me or an agent, 5–10 minutes | Hostile finding; above the published ideal, inside the published ceiling |
| Off the blocking path, with an owner and a deadline | Acceptable while long |
| Off the blocking path, with no owner, deadline, or acting consumer | Hostile finding; results nobody consumes rot |
| Under 5 minutes, but flaky, duplicated, or unpriced | Secondary finding |
| Getting slower release over release | Finding; apply step 4 to the cause |

Completion: one verdict per gate, with the reason in one sentence.

### 4. Name the cause

| Antipattern | Signal | First fix |
|---|---|---|
| Whole-suite-per-change | CI runs a bare full-suite command on every change | Select the affected scope; keep a full-run backstop |
| Cold every run | No cache step; full downloads and compiles each run | Cache inputs keyed on content hashes |
| One serial runner | One job, one worker, no sharding | Shard by historical timing; share one build |
| Human on the hook | A slow gate blocks commit, push, or merge | Move it off the blocking path; keep a fast local subset |
| Unbounded run | No job or test timeout; hangs reach the platform maximum | Derive deadlines from a measured baseline |
| Run past the first red | No bail flag; the likely culprit runs last | Fail fast; order by history |
| Double-check | Same check in a hook and CI; whole-repo lint on a small change; coverage re-runs the suite | Delete exact duplicates; lint changed files; combine coverage with tests |
| Slow by design | Sleeps, real network, clock, or I/O in the fast gate; e2e or perf tests per change | Classify tests by size; move heavy tests off-path |
| Flake tax | Retry-on-failure; "passed on retry"; unstable durations | Measure flake rate; fix or quarantine with owner and expiry |
| Unpriced check | No budget, owner, or cost estimate; agent-added checks accumulate | Price each gate; enforce a budget per stage |
| Subject sweep | A script loops over subjects, such as mutants, parameterized examples, or faults, and runs the full suite for each | Select per subject from a coverage or dependency map; cache; scope to the diff |

Completion: every hostile gate has at least one named cause tied to evidence from the repo.

Detection signals, fixes, and trade-offs: `references/antipatterns.md`.

### 5. Rank the fixes

Default order, cheapest safe wins first.

1. **Take me off the hook.** Move the long gate to CI, background, or a scheduled stage. Keep a fast local subset, measured in seconds, on the commit path. Gives up: nothing immediate, when the full gate still runs before merge.
2. **Delete duplicate work.** Remove exact duplicates, second coverage passes, and whole-repo lint on small changes. Gives up: fidelity only where the duplicate was not exact.
3. **Bound the run.** Add per-test and per-job deadlines from measured baselines; fail fast. Gives up: breadth within one run, recoverable by re-running.
4. **Select the scope.** Use diff, dependency graph, or coverage selection for tests and lint. Gives up: some detection per change; bound it with a full-run backstop.
5. **Reuse results.** Cache dependencies, builds, and test results under content hashes. Gives up: nothing when the keys are complete; stale results when they are not.
6. **Shard and parallelize.** Split by historical timing and share one build. Gives up: money and setup work, not detection, when all shards complete.
7. **Fix slow tests.** Replace sleeps with signals, fake clocks and I/O, make tests hermetic, and move e2e and performance tests to a slower stage. Gives up: real timing and integration behavior in the fast gate.
8. **Price and budget.** Give every gate a wall and money budget and an owner. Require a cost estimate for new checks. Gives up: nothing; it prevents regrowth.

Choose by expected wait saved over risk and effort, not by the order alone.

Completion: a ranked fix list where each item names its cause, its expected saving, and what it gives up.

### 6. Report

Deliver a short report, limited to facts that change a decision.

```
Gate | Time | Blocks | Verdict | Cause | Fix | Gives up
```

Then 1–3 ranked actions for this week, each with the measurement that proves it worked. Mark unknown numbers as unknown. Cite 5 and 10 minutes as a published guideline, never as measured harm.

Completion: a report with one verdict per gate and 1–3 ranked actions, each with its proving measurement.

### 7. Apply and keep proof

Fix only when the task asks. Then:

- Re-measure the gate after the change and compare before and after. One run of the changed path is enough.
- Keep the backstop: full suite on main or nightly, a fallback to all tests when the selector cannot understand a change, and cache invalidation when test files change.
- Run the checks the fix could have skipped, and state what you did not check.
- Watch for false green: selection misses, stale caches, retries hiding flakes, and quarantines that never expire.

Completion: before and after numbers recorded, or the reason measurement was skipped stated plainly.

## When you add a gate

An added check can be useful, but it must be priced before it is placed.

- Prefer extending an existing gate over adding a new one.
- Estimate the wall time from a representative run, and record the estimate with the check.
- Put fast checks on the commit path, and slow checks on CI or a scheduled stage. Never add a check over 5 minutes to a pre-commit or push path.
- Give the check a budget, an owner, and a failure action. A check nobody acts on is noise with a bill.

## Rules

- Protect my time: run the smallest check that can fail, batch edits, and never re-run an unchanged slow gate.
- Keep proof: no speed fix may silently drop verification. State what each fix gives up, and keep the backstop that catches what selection or caching skips.
- Measure before and after. Never claim a saving you did not measure.
- One gate, one definition: local and CI run the same check; only the scope and stage differ.
- Duration is not hostility by itself; blocking without an owner or deadline is.

## References

- `references/antipatterns.md`: the eleven antipatterns with detection signals, fixes, risks, and sources.
- `references/playbook.md`: recipes to measure gates and to apply each fix, with failure modes.
- `references/evidence.md`: published thresholds, quotes, counter-evidence, and verified tool facts.
