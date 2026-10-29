# COVERAGE

The *what to write* half of the kit. [`style-guide.md`](style-guide.md) governs **how** every page is written; this governs **which pages must exist**. The two are independent: a complete topic map full of badly written pages fails, and so does a beautifully written docs set that never covers the flag users actually need.

Industry standards (Diátaxis, Google, Microsoft) deliberately stop short of dictating topics — a topic list is product-specific. But the *procedure* for deriving one is standard practice. It has three sources, one contract, one matrix, and one negative list.

---

## 1. The three sources of topics

### A. The surface inventory (mechanical, exhaustive)

Every element of the product's public surface is entitled to documentation. For a CLI/framework, enumerate:

- every command and subcommand
- every flag, option, and config key — name, type, default, since-version
- every error and failure mode a user can hit
- every exit code, environment variable, and file the tool reads or writes
- every breaking change, with its migration path

**Rule: if a user can type it or hit it, it is reference-covered.** This is the one place completeness beats minimality — in the reference quadrant, completeness *is* the value (S17). Everything else in this file can stay lean; the reference cannot.

### B. The user journey (staged, maps to doc types)

Walk the journey; each stage names its page type (this is Diátaxis applied as a content generator, not just an organizer):

| Stage | Reader question | Page type | Lives on |
|---|---|---|---|
| Decide | "Should I use this?" | README landing (S18) + when-to-use | GitHub |
| Install & first success | "Get me something working" | Install + quickstart (tutorial) | GitHub links → site |
| Daily jobs | "How do I do X?" | One how-to per recurring job | Site |
| Understand | "Why is it built this way?" | One explanation per concept used in how-tos | Site |
| Recover | "It broke — fix it" | Troubleshooting per failure cluster | Site |
| Upgrade | "How do I migrate?" | Migration guide per breaking release | Site |

The "daily jobs" row is where most portfolios under-document: derive the job list from what users *repeatedly* do, not from what features exist. A feature without a recurring job gets a reference entry, not a how-to.

### C. The question log (empirical, ongoing)

Every repeated question from issues, support, Discord, or docs feedback (S28) is either a missing page or a findability failure. Triage rule:

- 1st occurrence — investigate; may be a product bug
- 2nd occurrence — doc candidate
- 3rd occurrence — must be written before the next release

This is the 3–10 hours/week search-cost finding (see `research-notes.md` §6) inverted into a content generator: your users are already telling you what to write. The question log is also the only legitimate source for *removing* planned pages nobody needs.

## 2. The minimum coverage contract

Every project in the portfolio ships, at minimum:

- [ ] README landing page, shared skeleton (S18, S21)
- [ ] Install (one copy-paste block) + quickstart tested in CI (S14)
- [ ] One how-to per core job — start with the three most common
- [ ] Full reference, auto-generated or generated-checked where possible
- [ ] Errors / troubleshooting page
- [ ] Changelog + migration notes for every breaking change (Keep a Changelog format)
- [ ] License and a feedback channel (S28)

Nothing beyond this list is written until the question log asks for it (S22). A project that fails the contract is not "documented enough" — the contract is the floor, not the target.

## 3. The coverage matrix (find the gaps)

Rows come from the surface inventory (source A); columns are the doc types. Mark each cell **core** (must exist), *optional*, or —. Empty core cells are your backlog.

| Surface item | Quickstart mention | How-to | Reference entry | Explanation |
|---|---|---|---|---|
| `{{command}}` | shown? | recurring job? | every flag + error? | concept worth a "why"? |
| `{{flag}}` | — | — | ✓ | ⚠ only if it answers a real why |

Run the matrix **per release**: new surface item = new row, reviewed in the same PR as the code (S27). The matrix also settles GitHub-vs-site placement mechanically: anything in the how-to / reference / explanation columns lives on the site (S19); the README only carries the quickstart-mention column and links out.

## 4. The negative list (what NOT to write)

Coverage discipline is mostly refusal. Do not write:

- **Feature-tour pages** that narrate what the reference already states (S20)
- **An explanation per concept** — only ones answering a "why" that actually occurred (question log) or that how-tos depend on
- **How-tos for one-shot tasks** — a good reference example covers them
- **Roadmap and speculation pages** — they rot fastest of all (S23)

When in doubt, apply S24: if no reader can act, decide, or understand something *they will use next*, don't create the page.

## Where this comes from

- Diátaxis, "Applying" guidance — content lists are derived from user needs per quadrant, stage by stage; the framework maps needs to forms, never prescribes topics
- Google *Minimum Viable Documentation* (S22) — the contract above is MVD made checkable
- The Good Docs Project — its template catalog doubles as a per-type "what" checklist
- GitLab's docs workflow — docs required in the same MR as feature changes (S27), which is also what keeps the matrix from drifting
