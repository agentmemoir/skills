# Reading a Rust Project's Test Policy

Before forming any opinion about a flaky test, find out what the project already decided. Most mature Rust projects have already codified anti-flake rules, and violating one is itself the finding. A report that ignores an existing convention reads as an outsider who did not read the docs.

## Where the policy lives

In rough order of authority:

1. `.config/nextest.toml` — the effective truth. Profiles, retries, timeouts, test groups, per-test overrides, quarantine list.
2. `.config/nextest.toml` block comments — projects often explain *why* each profile exists inline. Read them.
3. A testing doc — `docs/testing/`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`.
4. The CI workflows — `.github/workflows/*.yml` shows what actually runs when, and on what hardware. Report-only jobs versus gating jobs changes what a flake costs.
5. Test utility crates — a shared `test-utils` or `*-test-support` crate usually encodes the project's isolation rules as helper functions. Reading it is the fastest way to learn the intended pattern.

Confirm what the installed runner actually supports, and see effective test-group membership:

```bash
cargo nextest --version
cargo nextest show-config test-groups
cargo nextest run --help
```

`show-config` has only `version` and `test-groups` subcommands — there is no profile dump. Read profile values (`retries`, `slow-timeout`, `leak-timeout`, per-test overrides) from `.config/nextest.toml` directly. Record the version in your report, because several behaviours differ across releases.

## The `#[serial]` trap

This is the single most common misconception in Rust test suites, and a frequent root cause of "we thought it was serialized and it was not".

**`cargo nextest` runs every test in its own OS process.** `serial_test`'s `#[serial]` attribute takes an in-process mutex. There is no shared memory between nextest test processes, so the mutex cannot serialize anything. `#[serial]` is a no-op under nextest.

Cross-test serialization under nextest comes from:

- a `[test-groups]` entry with `max-threads = 1`, referenced by a per-test override, or
- a lane that runs with `-j 1`.

```toml
[test-groups]
serial-integration = { max-threads = 1 }

[[profile.default.overrides]]
filter = 'test(/^flaky_group::/)'
test-group = 'serial-integration'
```

If a project offers a plain `cargo test` fallback, treat its results as non-authoritative: test groups do not apply there, so the fallback run exercises a different execution model than the gate.

One exception worth knowing: `serial_test` also ships `file_serial`, which serializes across processes using file locks rather than an in-process mutex, so unlike `#[serial]` it *does* work under nextest. A nextest test group is still usually the better choice, because it does not require annotating every participant and cannot rot when someone adds an unmarked test.

**For an investigation, the implication is a test:** if a test relies on `#[serial]` and the project runs nextest, it is unprotected. That is a finding regardless of whether you have reproduced a failure yet.

## Project preference: isolation over serialization

The mature position, and the one to expect in a well-run project, is that tests should be self-isolating — per-test instance, ephemeral port, own temp dir — rather than serialized against each other. Serialization is slower and hides the coupling rather than removing it.

Check whether the project provides helpers for this and whether the failing test uses them. A test that hand-rolls a fixed path when a helper exists is a straightforward, low-risk fix.

## Profiles and what they gate

Projects commonly define a local profile, a CI gate profile, and separate lanes for slow, end-to-end, or platform-specific suites. Two things matter for a flake report:

- **Which profile observed the failure.** A test that is report-only in one lane and gating in another has different severity.
- **Retry configuration per profile.** A local profile that never retries plus a CI profile that retries only quarantined tests is a deliberate design: the project wants flakes to be visible, not absorbed.

Some projects pin lane membership by a digest of the selected test list, checked before the lane runs. If a rename or a new test changes membership, that check fails. Worth knowing when a test's name is part of the problem.

## Quarantine policy

Projects that take flakiness seriously usually run a four-step policy:

1. **Discover** — a nondeterministic failure, or a flaky marker in the JUnit report.
2. **File** — an issue within a short deadline, describing symptom, suspected cause, and affected suite. No silent re-runs.
3. **Contain** — add a per-test override granting a small number of retries, with a comment linking exactly one open issue.
4. **Resolve** — fix or delete the test within a longer deadline, and remove the override.

If the project has this, the right move is to check whether the failing test is already quarantined. If it is, there is an open issue to append evidence to rather than a new bug to file. If the project's rule is "a quarantine entry without a live issue link is a policy violation", that is worth reporting too.

## Name-based gates

Some projects select tests by name substring, with a floor on how many must match, so that a rename cannot silently thin a safety net. Common reserved substrings mark things like data migration, rebalance, or delete-marker handling.

If the failing test's name is involved in the problem — because someone renamed it, or because a gate rejects a proposed rename — that is part of the finding, and the fix has to change both the name and the floor in the same change.

## Things worth noting in the policy

- Whether the project mandates a specific runner, and whether `cargo test` fallback is even supported.
- Whether time-driven tests are required to use paused Tokio time.
- Whether there is a dev-dependency boundary that test utilities must respect.
- Which suites are report-only, and which are nightly. A nightly-only flake has a different urgency than a PR-gating one.
- Whether quarantine entries carry deadlines, and whether any are past due.

## Turning policy into report context

A short "Policy context" section in the report earns credibility and often shortens the investigation:

- Which profile and runner observed the failure, and whether it gates PRs.
- Whether the test is already quarantined, and the linked issue if so.
- Whether the test violates a written project rule, quoted.
- Whether `#[serial]` is being relied on for protection that does not exist under the project's runner.
- Which documented rule, if any, the proposed fix must not violate.
