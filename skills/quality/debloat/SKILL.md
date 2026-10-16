---
name: debloat
description: "Enforce lean code in any language: confirm requirements, research current best practices, then write the smallest implementation that works. Use this skill whenever the user asks you to write, add, extend, or refactor code (a feature, script, module, function, endpoint, config, or integration), even if they never mention 'lean', 'minimal', or 'best practices'. Also use it when a task invites scope creep, such as 'make it flexible', 'set this up properly', or 'add support for X'. Skip it for prose, debug-only sessions, code review without edits, and one-line fixes."
license: MIT
---

# Debloat

Unrequested code is a liability: every extra function, flag, and dependency must be read, tested, and maintained, and most of it is never used. This skill makes you earn each line through three gates. The gates prevent the two failure modes that produce bloat: building the wrong thing because requirements were guessed, and building too much because nothing stopped you.

Lean does not mean sloppy. Input validation at trust boundaries, meaningful error handling, and tests for the behavior you add are part of the requirement, not extras.

## Hard limits

One number outranks every trade-off below, and it is checked before the task is called done.

**Every file you create or modify holds at most 450 lines.** Any language, any format, any purpose: source, config, scripts, tests, generated project files. Header comments count toward the total. 450 is the ceiling, not 449 — a file at exactly 450 lines passes, 451 fails. Markdown is the only exemption.

- **Stop before you pass it.** If a change would take a file above 450 lines, stop and redesign the implementation until it fits. Never land it over the line and plan to trim it later.
- **Split by responsibility.** Splitting a file is good practice when it follows the single-responsibility principle: each resulting file owns one job, can be named without "and", and reads on its own. Splitting at arbitrary cut points, or sharding content into files that serve no distinct purpose, is a code smell and does not count as a fix.
- **No file is grandfathered.** Size is never excused by age. If you modify a file that is already above 450 lines, dividing it by responsibility until every part is at 450 or fewer is part of that task — so a small edit to a large file is a large task. Size the work accordingly, and say in the final message which files you split.
- **Markdown exempt, logic not.** Prose files cost nothing at runtime and are the only ones outside the count. Anything that executes is inside it.

Only the user changes this number, and only by saying so explicitly.

## Scale the process to the task

| Task size | Gate 1 | Gate 2 | Gate 3 |
|---|---|---|---|
| Trivial (under ~10 lines, established pattern nearby) | One-sentence restatement | Skip; say "followed existing pattern in `<file>`" | Yes |
| Normal (a function, script, or small feature) | Restate + confirm | 2–3 targeted searches | Yes |
| Large (new module, integration, new dependency) | Restate + confirm, list open questions | Full research, cite sources | Yes, in reviewable increments |

## Gate 1: Requirements

Restate in your own words: the goal, inputs, outputs, and constraints (language, runtime, performance, compatibility, existing conventions). Then decide:

- **Interactive session:** Ask the user to confirm. If something material is ambiguous, ask at most 3 specific questions rather than guessing.
- **Autonomous or no-reply context:** Write the restatement as an explicit assumptions list at the top of your work, and choose the narrowest interpretation.
- **Existing codebase:** Read the neighboring code first so your requirements include its conventions (naming, error style, test framework, dependency policy).

Done when the user confirms, or the task is small enough that the restatement is the confirmation. Guessed requirements fail this gate, because code built on them is the most expensive kind to throw away.

## Gate 2: Best-Practices Research

Use your agent's search and page-reading tools to find current canonical guidance for the specific task: official docs, language or framework standards, RFCs, or widely cited guides. Prefer sources matching the project's actual language and version. Avoid blog folklore and answers that predate the version in use.

If no search tool is available, say so, fall back to established patterns in the codebase and your own knowledge, and flag anything version-sensitive that the user should verify.

Done when you can state:

1. **Apply:** the 2–3 practices that matter here (e.g. YAGNI, KISS, DRY, input validation, error handling, testing), each tied to a source or to the codebase.
2. **Skip:** the practices you are deliberately not applying, and why. Naming these prevents them from creeping back in.

Keep this to a few lines in your reply. Do not paste research notes.

## Gate 3: Minimal Implementation

Write the smallest code that satisfies the confirmed requirements and the practices from Gate 2.

Do not add, until a confirmed requirement demands it:

- Helpers or abstractions used in only one place
- Parameters, options, or config flags nothing currently passes
- Extension points for hypothetical future use
- New dependencies where the standard library or an existing dependency suffices
- Comments restating what the code already says, and error handling for cases that cannot occur

Prefer, in order: reuse existing code, use the standard library, write a few plain lines, and only then add a dependency. Duplication is cheaper than the wrong abstraction, so wait for the third repetition before extracting.

If you notice a nearby bug or improvement outside the requested scope, always mention it in the final message and leave it unchanged.

## Verification

Before finishing, check each item:

1. **Deletion test:** for every function, dependency, and flag you added, ask "what breaks if I delete this?" If the answer is "nothing," delete it.
2. **Requirement trace:** every added item maps to a confirmed requirement.
3. **Run it:** the affected tests pass — the smallest check that can prove the change. If there is no suite, run a smoke check (execute the script, call the function with a representative input) and report what you ran. Never claim it works without running something. If the only proof is a check that runs over five minutes, `verification-antipattern` overrides this step: scope the run to the change, or background it and leave the full gate to CI — do not block the task on it. Say what you ran, and what you left to a slower stage.
4. **Diff size:** skim the diff. Anything you would not defend line by line to a reviewer goes.
5. **Line counts:** count every file you created or modified (`wc -l` on text files). Any file you touched that ends above 450 lines fails the task, including one that was already over the line before you started. Redesign it — do not report it. Name the counts in the final message, and name the files you split. Markdown files are the only ones you skip.

## Final message

Keep it short, in this shape:

```
Built: <one line>
Practices applied: <2–3, with source or "existing pattern in <file>">
Left out on purpose: <bullet per item, with the reason>
Verified by: <tests run or smoke check; note anything left to a slower stage>
Line counts: <file: N — one line per file created or modified>
Noticed but untouched: <optional>
```

**Example: "Left out on purpose"**
- Retry logic: not required, and the caller already retries.
- Config file support: only one value, hardcoded as a named constant.
- `requests` dependency: `urllib.request` covers the single GET.