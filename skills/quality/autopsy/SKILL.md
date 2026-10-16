---
name: autopsy
description: >-
  Runs a skeptical adversarial audit (an autopsy) on finished work I point to: code,
  a pull request, a document, a plan, an analysis, a decision, or an earlier session. Produces
  one HTML report and changes nothing until I pick fixes. Triggers: review, red-team,
  audit, autopsy, critique, roast, poke holes, devil's advocate, fact-check, verify, second
  opinion, check yourself, what did I miss.
license: MIT
compatibility: Requires Node.js to generate the report from findings.json, web search for claim verification, and a desktop session to auto-open the report (otherwise the report path is printed).
metadata:
  author: agentmemoir
  version: "2.0"
---

# Autopsy

A skeptical expert autopsy of already-finished work, delivered as a clickable HTML report. Nothing is changed until I ask.

## Core contract with me

1. **Reconstruct the standard, then audit against it.** Use the real requirements, not a rubric you softened to pass.
2. **Be adversarial toward the work.** Do not manufacture nitpicks or turn the critique on yourself.
3. **Verify externally wherever verification is cheap and material.** Use web search for any checkable factual, numerical, or current-state claim the work depends on.
4. **Produce the autopsy report.** Save findings to `findings.json` and generate `report.html` with `scripts/generate-report.cjs`; never edit the HTML by hand. Edit the JSON instead.
5. **Stop after presenting the report.** Do not fix anything yet. Wait for me to say what I want addressed. Showing the report before any fix is the point of this skill.

## Report assets & tools

- `scripts/generate-report.cjs` — deterministic generator that reads `findings.json`, renders `report.html`, copies `style.css` beside it, and opens the report when a GUI is available.
- `assets/style.css` — styling: design system, severity colors, dark mode, print. Never edited per report; copied beside `report.html`.
- `references/findings.schema.json` & `references/findings.example.json` — structural contract and complete example for `findings.json`.

`report.html` links `style.css` with a relative path, so the two files are one deliverable and stay in the same directory. `findings.json` is the source the agent edits and reads.

## Workflow

### Step 1 — Identify the subject

Figure out exactly what work is on the table: code, a pull request, a document, a plan, an analysis, a decision, or work from an earlier session. Default to the immediately preceding turn unless I point at something else. If it's ambiguous which piece of work is in scope, ask before doing the full analysis. Do not guess and spend a full review cycle on the wrong target.

### Step 2 — Perform the autopsy (internally)

Work through this method in your own reasoning. There is no need to narrate every sub-step to me; the output is the autopsy report. Do each step rather than jumping to conclusions:

**a. Reconstruct the standard.** Pull requirements from: what I explicitly asked for, the underlying intent, reasonable implicit requirements, stated/inferable constraints, relevant domain standards, and what a competent expert would consider table stakes. If the original request was ambiguous, name the ambiguity and judge whether your interpretation was reasonable, and don't retroactively justify it.

**b. Requirement-by-requirement audit.** For every meaningful requirement: Status (Fully satisfied / Partially satisfied / Missed / Not applicable), Evidence, Severity, Confidence, Correction needed (Yes/No/Unclear). Judge whether the intent was fulfilled, not just literal keyword coverage. Pay special attention to requirements that are easy to skip: formatting, validation, edge cases, secondary/implicit asks.

**c. Adversarial technical/substantive review.** Actively hunt for: incorrect facts/conclusions, unsupported assertions, weak evidence, unjustified assumptions, hidden dependencies, logical gaps, circular reasoning, contradictions, overgeneralization, shallow analysis, missing context, missing counterarguments/counterexamples, edge cases, failure modes, brittleness, unnecessary complexity, misleading framing, false precision, poor prioritization, internal inconsistencies, overconfident conclusions, undisclosed uncertainty, and places where speed was prioritized over quality. Ask yourself: what would a skeptical expert attack first? What single false assumption would break the most? What's the least-supported conclusion? What did I accept too easily?

**d. External verification.** For every externally-checkable claim, assumption, number, or spec that materially affects the conclusion, search and check it rather than re-asserting it from memory. Classify each as **Established / Supported / Inferred / Uncertain / Contradicted**. Prefer primary/authoritative/recent sources. If sources disagree, say so rather than cherry-picking. Don't treat absence of evidence as evidence of absence.

**e. Stress-test the reasoning.** Try to actually break important conclusions: construct counterexamples, test the opposite hypothesis, list the load-bearing assumptions, check whether the same logic would produce an obviously wrong answer elsewhere, re-derive any calculations independently, and check whether confidence exceeds the evidence. If there were alternatives to a chosen approach, compare against them honestly.

**f. Process audit.** Separate flaws in the *result* from flaws in the *reasoning* from flaws in the *process* (shortcuts taken, research stopped early, easy source chosen over a better one, assumption never checked, alternative approach never considered). Flag anything that's only a hypothetical nice-to-have versus something that materially affected the result.

**g. Second pass: does any of this require a change?** For every issue that needs correction, work out the specific fix. These appear in the report as proposed fixes; per the contract, do not apply them yet.

### Step 3 — Structure and write findings.json

Create a portable scratch directory:

```bash
SCRATCH=$(mktemp -d "${TMPDIR:-/tmp}/autopsy-XXXXXX")
```

Write your findings directly to `$SCRATCH/findings.json` matching `references/findings.schema.json`:

- `subject`: name or title of the artifact under review
- `verdict`: `Excellent` / `Good` / `Adequate` / `Inadequate`
- `verdict_justification`: 2-3 sentence summary explaining the verdict
- `metadata`: `{ generated: "YYYY-MM-DD", applies_to: "commit/version", source: "files evaluated" }`
- `standard[]`: bullet list of standards/expectations judged against
- `requirements[]`: `{ requirement, status, evidence, severity: "Low"|"Medium"|"High" }`
- `issues[]`: `{ id, title, severity: "Critical"|"Important"|"Minor", why_it_matters, impact, evidence, confidence, proposed_fix }`
- `dismissed[]`: things considered that turned out not to warrant a fix
- `verification[]`: `{ claim, classification: "Established"|"Supported"|"Inferred"|"Uncertain"|"Contradicted", source_note }`
- `unknowns[]`: `{ what, why_unknown, what_would_resolve_it, materiality }`
- `strengths[]`: genuinely earned strengths
- `regrets[]`: what you would do differently
- `process_changes[]`: workflow adjustments for next time
- `plan_1hr[]`: highest-impact fixes if given one hour
- `plan_unlimited[]`: redesigns/investigations with unlimited time

Number `issues[]` sequentially with a numeric `id` (1, 2, 3...) starting with Critical issues, continuing into Important, and then Minor. The generator maps these to the continuous rank chips (01, 02, 03...).

### Step 4 — Write the autopsy report

Generate `report.html` from `findings.json` using the generator script:

```bash
node "<skill-dir>/scripts/generate-report.cjs" "$SCRATCH"
```

This single command:
1. Validates and reads `$SCRATCH/findings.json`
2. Computes summary counts, coverage statistics, and continuous rank chips
3. Renders `$SCRATCH/report.html` with full UI Craft styling and dynamic TOC
4. Copies `assets/style.css` beside `report.html` if not already present
5. Reports `opened` and `open_status`, and opens `report.html` in the default browser only when a GUI is available (skipped on headless sessions, in CI, or with `--no-open` or `AUTOPSY_NO_OPEN=1`; the legacy `ADVERSARIAL_REVIEW_NO_OPEN` is still honored)

**Never edit HTML by hand.** To correct or reword anything, edit `$SCRATCH/findings.json` and re-run `generate-report.cjs`.

Exception when I explicitly request a single self-contained file with no separate CSS:
```bash
node "<skill-dir>/scripts/generate-report.cjs" "$SCRATCH" --inline-css
```

### Step 5 — Present the report and stop

Read the generator's JSON result. It reports `opened` and an `open_status` of `launched`, `disabled`, `env`, `ci`, `no-gui`, or `failed`. When the status is `launched`, the browser already shows the report. For any other status no browser opened, so say so briefly. Always include the absolute paths of `report.html` and `findings.json` in the chat message regardless of status, because `opened` is best-effort and even a launched opener can fail to render the page. Keep the rest short: a one-line verdict and the counts of critical/important issues. Do not paste the full audit into chat.

Pass `--no-open`, or set `AUTOPSY_NO_OPEN=1` (the legacy `ADVERSARIAL_REVIEW_NO_OPEN` still works), when I only want the file written without a browser.

Then **stop and wait**. Do not start fixing issues automatically, and do not ask for permission while immediately starting fixes in the same turn.

### Step 6 — Only once I respond

When I instruct which issues to fix (e.g., "fix #1 and #3", "fix critical issues"):
1. Re-read `$SCRATCH/findings.json` at the recorded scratch path
2. Resolve issue IDs and severities against my instructions
3. Apply the exact fixes to the codebase using each issue's `proposed_fix` as the blueprint
4. **Update `findings.json` to record what was done. Never delete issue entries.** Preserve all original issue text (`title`, `why_it_matters`, `evidence`, `proposed_fix`), and append resolution feedback:
   - Add `"fixed": true`
   - Add `"commentary": "<concise explanation of what was done to fix the issue or how it was resolved>"`
   - If requirement status changed, update the relevant item in `requirements[]` (e.g. `status: "Fully satisfied"`, `fixed: true`)
5. Regenerate `report.html` from the updated JSON:
   ```bash
   node "<skill-dir>/scripts/generate-report.cjs" "$SCRATCH"
   ```
   The HTML report will display the fixed visual cues: emerald rank chips, green "Fixed" badges, the resolution commentary block beneath the preserved proposed fix, and updated fixed counts in the header and closing panel.
6. Confirm what changed and point me to the refreshed report.

## Non-negotiables

- Never edit `report.html` by hand. Edit `findings.json` and regenerate with `generate-report.cjs`.
- Never skip straight to fixing before I instruct you to do so.
- Never inflate severity or manufacture nitpicks.
- If the work is solid, report verdict `Good` or `Excellent` plainly.
- Never modify `style.css`.
