# Implementation Plan: [Short title]

> No code blocks and no file paths to change. Express deliverables as scenarios and acceptance criteria.

**Goal:** [One sentence in plain English.]

**Why:** [The problem this plan solves.]

**Locked decisions:**
1. [Decision] — [Why this one was chosen.]

**Out of scope:** [What this plan does not change.]

## Artifacts and links

Catalog every companion artifact this plan points to: child issues, companion files, and references. One bullet each: the link, then a one-sentence summary of what it holds. Delete this section when the plan has none.

- [Link or #issue] — [What it holds, in one sentence.]

## Reading paths

One ordered line per reader goal, naming the sections and artifacts that reader needs.

- Implementer: [Sections and artifacts, in reading order.]
- Reviewer: [Sections and artifacts, in reading order.]
- Operator: [Sections and artifacts, in reading order.]

Delete the lines that do not apply to this plan.

## Steps

1. [Step name]
   - Change: [What changes, in plain English, from the reader's side.]
   - Scenarios: [At least one Given-When-Then block per deliverable. Make each one executable when the deliverable is testable: a BDD feature, a contract test, or a property test.]
     - Given [a starting state], when [an action], then [an observable result].
   - Tracer bullet: [One line naming the thin end-to-end slice this step proves.]
   - Check: [One line naming the command or observation that proves this step is done. Do not paste a code block.]
   - Done when: [Acceptance criterion a reader can verify.]

## Done when

- [Acceptance criterion a reader can check.]
- [Acceptance criterion a reader can check.]

## Definition of Done

Every step meets this shared bar:

- Tests pass.
- No new warnings.
- Docs are updated.
- A reader can understand the step without a code snippet.

## Risks

- [Risk] → [How you reduce it.]
