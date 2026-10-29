# Flaky Test Bug Report Template

Fill this in per finding. Anything you did not verify goes in the "Not verified" section — an honest gap is worth more than a confident guess, because a wrong root cause sends the fixer in the wrong direction and costs more than an open question.

Write reports to `./flaky-reports/` unless I name a different directory.

---

# [FLAKY-001] <test identifier> fails intermittently

- **Severity:** high / medium / low
- **Confidence:** confirmed / probable / hypothesis
- **Flake rate:** N failures in M iterations (P%)
- **Layer:** unit / crate integration / e2e / conformance / fuzz

## Summary

One or two sentences. What fails, how often, and under what conditions.

## Test under investigation

- **Identifier (nextest form):** `binary::module::test_name`
- **File:** path to the test
- **Runner and profile:** e.g. `cargo nextest run --profile ci`
- **Gating:** does this block PRs, or is the lane report-only / nightly?

## Reproduction

The exact command, copy-pasteable, with no placeholders:

```
<command>
```

Environment: OS, core count, whether under load, debug or release, local or CI.

## Measured behaviour

| Condition | Iterations | Failures | Rate |
|---|---|---|---|
| Baseline (as configured) | | | |
| Alone | | | |
| `-j 1` | | | |
| Under CPU/IO load | | | |
| Release | | | |
| CI container | | | |

Every row is a command you actually ran. Delete rows you did not run rather than guessing.

## Failure signature

The actual failure output — panic message, timeout duration, error text. Trimmed to the informative part. If it varies between runs, say so and show both.

## Error decode

Every distinct value the error carries, and what its documentation says it means. If the line is `called Result::unwrap() on an Err value: Error { code: ReadOnly, extended_code: 776 }`, the answer is a table with one row, not a paragraph.

| Value | Kind | Documented meaning | Source |
|---|---|---|---|
| 776 | SQLite extended result code | `SQLITE_READONLY_ROLLBACK` — the database has a hot journal that needs to be rolled back and cannot be, because the connection is read-only | <https://www.sqlite.org/rescode.html> |
| 8 | SQLite primary code (`776 & 0xff`) | `SQLITE_READONLY` — the connection lacks write permission | same |

Then the emitting code path: the file and line that can produce that value, and what you found there. A decoded code with no matching code path is a hypothesis, not a finding.

If nothing could be decoded — the failure really is just a timeout — write that down too, and say what you looked at.

## Discrimination results

What each axis ruled in or out, and what that implies:

- **Isolation:** fails alone / only in suite → implies ...
- **Serialization:** passes with `-j 1` → implies ...
- **Ordering:** ...
- **Load:** ...
- **Other:** ...

## Root cause

Name the mechanism, not the symptom. "Binds a hardcoded port 9000 that a sibling test also binds" is a cause. "Fails sometimes" is not.

Every field here must be something you checked. The strongest thing in this report is a cause you can quote a code path for; the weakest is a plausible mechanism story with no experiment behind it, because a filed bug sends someone to implement it.

**In test code or production code?** If the test exposed a real defect — a component that does not shut down cleanly, a background task with no cancellation path — say so explicitly and note that the owner of the fix differs.

## Confirming experiment

The one experiment whose outcome depends on whether this cause is real.

- **Hypothesis:** if the cause is X, then Y.
- **Experiment:** what you changed or ran.
- **Result:** what happened. Include both directions if you tested both.

If you did not run it, this section says so and the confidence is `hypothesis`, not `confirmed`.

## When it never reproduced locally

If every attempt passed here, this is the report shape. It is a legitimate finding and it is filed, not shelved — but only with the evidence stated as what it is.

- **Cause basis:** inferred, not measured.
- **Where the failures were seen:** the exact command and workload from the original failing job, verbatim. Not a local substitute.
- **Attempts:** every one, with its command and result, including the ones that passed. If a command cache may have replayed a verdict, say so and do not count it.
- **Mechanism:** established by the decoded error value and by reading the emitting code path. Quote the file and line.
- **Rate:** not measured. Leave it unmeasured. Do not convert "20 of 20 passed" into a 0% rate; 20 passes bound nothing about the rate at the original failure site.
- **Next experiment:** the single cheap thing that would settle it, and where it has to run.

A reader who sees `confidence: confirmed` on a report with zero local reproductions should treat it as a bug in the report.

## Policy context

- Existing quarantine entry and linked issue, if any.
- Written project rule this test violates, quoted.
- Whether `#[serial]` is being relied on for protection that does not exist under the project's runner.
- Documented rules the fix must not violate.

## Proposed fix

Minimal and structural. Show the diff.

```
<diff>
```

**Explicitly rejected alternatives**, and why:

- Adding a retry — hides the defect, and the project may have a quarantine policy that requires a linked issue.
- Lengthening a sleep or timeout — raises the threshold without removing the race.
- Test-group serialization — containment, not a fix; slower, and leaves the coupling in place.

## Blast radius

Which other tests, suites, or code paths share this cause. If several symptoms share one cause, say so — that is one bug, not several.

## Not verified

Be specific. This is the most valuable section in the report.

- Could not reproduce in the release build.
- Did not test on macOS / ARM.
- Did not confirm whether the sibling test also binds the same port.
- The fix is proposed but was not applied, so the zero-failure rate is predicted, not measured.

## Suggested next step

One concrete action. File as a bug, append to the existing quarantine issue, or hand the fix to a specific person.
