---
name: bugster
description: >-
  Files every confirmed bug as a labeled issue, reproduces the failure through the real entry point
  before fixing it, and blocks "done" until the evidence is kept. Use it when a bug is suspected,
  discovered, reproduced, fixed, or reported, when I ask you to file an issue, or when a finding
  turns up during another task. Applies to every task, including ones that are not about bugs.
category: engineering
title: Bugster
summary: >-
  Files every confirmed bug as a labeled issue, reproduces it through the real entry point before the
  fix, and keeps both logs. Findings are classified as reproduced, confirmed by code, unconfirmed, or
  not a bug, so nothing is claimed without proof. Out-of-scope bugs are reported, never hidden.
say: "File a bug for this and prove the fix."
license: MIT
metadata:
  author: agentmemoir
  version: "1.0"
---

# Bugster

A bug you fix without filing is a bug the next person meets again. A bug you never reproduced is a bug you cannot claim to have fixed. This skill enforces both, in every task.

## 1. File every confirmed bug

Every confirmed, previously unfiled bug must produce an issue. That covers in-scope bugs, out-of-scope bugs, bugs already fixed, bugs found in passing, and bugs mentioned in chat. Fixing a bug never replaces filing it.

- **Standing authorization.** Confirming a bug is approval for exactly one issue creation: through the pipeline helper when the task runs in stages, or one `gh issue create` otherwise. Every other `gh` operation still needs my explicit approval.
- **File immediately.** Create the issue in the same turn the bug is confirmed, before or alongside the fix. Do not ask permission, defer it, or wait for instructions. Inside this workflow, the standing authorization outranks the usual confirmation prompt.
- **Privacy exception.** Do not publish a bug I marked private. Redact credentials, tokens, personal data, and anything else sensitive from public evidence.
- **No duplicates.** An existing tracked issue for the same underlying bug satisfies the requirement; reference it. A chat mention, a test, a commit, or a fix does not.
- **Unconfirmed findings.** Report a credible suspicion as unconfirmed in the task response. Do not claim confirmation, and do not file a speculative issue.
- **Required labels.** Every new issue carries a valid type, area, and difficulty label. An issue missing one is incomplete and must be corrected through an authorized route.
- **Failure handling.** If creation or labeling fails, report the failure with the issue URL or ID when you have one. Never claim an issue was filed without confirmation, never abandon it silently, and never retry blindly into duplicates.

Task scope, task completion, and an existing fix are not permission to skip reporting. Higher-priority safety, privacy, and authorization rules still win.

## 2. Reproduce before fixing

A passing test is not evidence that the reported failure was reproduced or fixed. Verify the failing path itself.

1. **Preserve the report.** Record the original command, inputs, environment, expected behavior, actual behavior, and the exact error. Do not quietly simplify the scenario.
2. **Use the real entry point.** Build and run the actual binary or service. For a CLI bug that means `make compile` or `make install` first, then the reported commands. Unit tests alone are not enough.
3. **Match the state that matters.** Include persisted data, configuration, process boundaries, restart behavior, and environment conditions when they affect the failure. Use real data safely; never destroy valuable data to reproduce a bug.
4. **Capture the baseline before editing.** Save the failing command and its output in the project's ignored log directory, under a filename no publication gate will pick up. Redact secrets and keep the diagnostic evidence.
5. **Verify after the fix.** Rebuild and rerun the same entry point, commands, and equivalent state. Keep both logs. Add regression tests, but never swap them for the original reproduction.
6. **Check existing damage.** If the change only prevents future failures and cannot restore corrupted or lost data, say so.

**No substitution.** A helper test, a mocked run, a fresh database, or an in-process call cannot establish a fix for a persisted-state, cross-process, or end-to-end failure unless it exercises the same mechanism.

If reproduction is impossible, write down why, what you tried, and what you did verify. Do not call the original failure reproduced, and do not call it fixed.

## 3. Detect, investigate, classify

Detection is continuous, not limited to the requested change. Watch for wrong behavior, violated invariants, missing validation, unsafe defaults, security defects, data loss, concurrency races, faulty error handling, regressions, and documentation conflicts.

For each suspicious finding:

1. Investigate the code, requirements, tests, documentation, and runtime behavior. Do not drop a finding just because it is unrelated to the task.
2. Separate observed facts from hypotheses, and take expected behavior from evidence rather than assumption.
3. Try a realistic reproduction through the real entry point when that is practical.
4. Classify it.

| Class | Means |
|---|---|
| **Reproduced** | The failure was observed under documented conditions. |
| **Confirmed by code** | A concrete, deterministic defect is established by code or invariants, though not at runtime. State that limit. |
| **Unconfirmed** | Evidence suggests a defect but the proof is missing. |
| **Not a bug** | Investigation shows the behavior is intended, or the suspicion is wrong. |

5. File confirmed defects immediately, including unrelated ones. Report unconfirmed findings with their uncertainty visible.
6. Fix only bugs inside the authorized scope, unless an unrelated one blocks completion. Report the others without widening the fix.

Scope governs remediation, never disclosure. Do not hide a bug to keep a task small, invent findings to fill a report, or promote an assumption to a confirmed defect.

## 4. What a bug issue contains

| Field | Holds |
|---|---|
| Summary | One precise sentence naming the defect. |
| Observed behavior | The actual result, with the relevant output or error. |
| Expected behavior | The correct result and the requirement or invariant behind it. |
| Evidence | The exact command, input, output, test, or code path. |
| Reproduction | Ordered, executable steps and the required state, when reproduced. |
| Verification status | Reproduced, confirmed by code, or unconfirmed. |
| Location | The exact file and line when known, otherwise the narrowest established location. |
| Impact | Affected behavior, the conditions, and the realistic consequences. |
| Cause | The established root cause, or `Unknown`. |
| Proposed fix | An evidence-supported approach when it is clear, otherwise `Undetermined`. |
| Labels | Type, area, and difficulty. |

Never invent a reproduction, root cause, file location, impact, or verification result. Keep established facts separate from proposed explanations.

## 5. Completion gate

Before you call the task complete:

- [ ] The original failure was reproduced and logged, or the limitation is documented.
- [ ] The real entry point was retested after the change, under equivalent conditions, with the output kept.
- [ ] Every confirmed bug has a filed issue or a referenced existing one, except bugs marked private.
- [ ] Every new issue carries valid type, area, and difficulty labels.
- [ ] Unconfirmed findings, unrelated defects, and submission failures are reported accurately.
- [ ] Remaining data damage, unverified behavior, and incomplete remediation are stated.

**Final report.** State what failed, what changed, what you actually verified, where the evidence is saved, and the issue URLs or IDs. Keep **fixed**, **verified**, **filed**, and **unresolved** as separate statuses.

Never claim a bug fixed, an issue submitted, or verification done unless the action demonstrably succeeded.
