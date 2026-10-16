---
name: wordsmith
description: >-
  Write, audit, and rewrite developer documentation using the Wordsmith method: Diátaxis page
  typing, 28 numbered style rules (S1–S28), AI-tell removal (H1–H26, vendored from
  blader/humanizer), topic-coverage derivation, and rule-traced change logs. Use this skill
  whenever I ask to write, improve, review, rewrite, restructure, audit, or plan
  documentation of any kind (README, quickstart, how-to guide, reference, explanation, FAQ,
  guides, docs sites), say my docs are unclear, too long, inconsistent, or not helping
  readers, ask what documentation I need for a project, or want a documentation standard
  or style guide. Also use it when prose sounds machine-written: "reads like AI wrote it",
  "too robotic", "remove the AI tells", "de-slop this page", "sounds like ChatGPT", even if
  they never say "DX", "developer experience", or "style guide".
---

# Wordsmith — documentation that respects the reader's time

**The one principle: every page has one job. Cut everything that doesn't do that job.**

This method is distilled from the established documentation standards: Diátaxis (page types), the Google and Microsoft style guides (prose), Carroll's minimalism and Every Page Is Page One (what to cut), and community specs like standard-readme and the Good Docs Project (artifacts). The evidence behind every rule, with sources, is in `references/research-notes.md` — read it when I ask *why* a rule exists, not by default.

The method has three parts, and all of them matter:

- **WHAT to write** (`references/coverage.md`) — which pages a product needs, derived from its surface, its users' journey, and their question log
- **HOW to write it** (`references/style-guide.md`) — 28 numbered rules (S1–S28) that keep every page short, findable, and trustworthy
- **HOW IT MUST NOT READ** (`references/voice-and-tells.md`) — 26 AI-tell patterns (H1–H26, vendored verbatim from [blader/humanizer](https://github.com/blader/humanizer), plus the docs exemptions that override them)

Routing and classification live in this file; the rules live in the references. Run the S audit before the H pass — a page of the wrong type is a restructuring job, and humanizing it first wastes the work.

## The 28 rules (compact form)

The full rules with rationale and examples live in `references/style-guide.md`. This index is enough to route work; quote rule numbers when you apply them. Read the full file before writing or rewriting prose — the one-line versions below are reminders, not replacements.

**Voice and prose**
- **S1** Second person, active voice, present tense — tense drift marks stale docs
- **S2** One idea per paragraph, three sentences max
- **S3** Use the reader's words, not internal vocabulary; no untranslatable idioms
- **S4** Never write "simply", "easily", "just", "obviously" — it insults stuck readers
- **S5** Cut filler on sight: utilize→use, in order to→to, it should be noted that→delete
- **S6** Define or link every term on first use

**Page design**
- **S7** One page, one job, one reader state: teaching (tutorial), doing (how-to), looking up (reference), understanding (explanation) — never mix jobs on one page; *move*, don't kill
- **S8** Put the outcome in the title ("How to deploy behind a proxy", not "Deployment")
- **S9** Front-load: first sentence = what the page gets you + prerequisites
- **S10** Every page stands alone — assume arrival from search/LLM with zero context
- **S11** Write for scanning: heading every 2–4 paragraphs, tables for options, bold sparingly
- **S12** Every page ends with an exit ramp: one next step or two related links

**Code samples**
- **S13** Working code before prose; the sample is the payload
- **S14** Every sample must be executable and tested — untestable is a guess
- **S15** Common case only; reader edits values, not deletes boilerplate
- **S16** One code block, one outcome; show expected output where success is checkable
- **S17** Reference = complete, neutral, structural: every flag, default, error; facts only

**Portfolio structure (GitHub vs. docs site)**
- **S18** README is a landing page, not a manual: pitch, install, 60-second quickstart, link out
- **S19** The site owns the four doc types; GitHub owns the front door
- **S20** Link, never duplicate — duplicated content rots at double speed
- **S21** Same README skeleton in every repo; readers never relearn your docs

**Keeping it short**
- **S22** Minimum viable documentation: small and fresh beats large and stale
- **S23** Delete dead docs in the same change that kills the feature
- **S24** Cut anything the reader can't act on — the anti-padding rule

**Consistency system**
- **S25** One style guide, every repo links to it; rule numbers are the review vocabulary
- **S26** Lint mechanically (Vale/markdownlint), judge humanly
- **S27** Docs change with code — a behavior PR without docs is incomplete
- **S28** One feedback signal per page; every report routes to a fix

## Workflow — route by what I want

### Route A: "Rewrite / improve / fix this page"

1. Read the page. Classify it per S7 first: is it teaching, doing, looking up, or understanding? The correct type is usually kept — the fix is form-mixing and prose, not restructuring.
2. Audit against `references/style-guide.md`. **Start with what the page already does well** and say so — rewrites that churn compliant sections destroy contributor trust and prove the method is stylistic churn.
3. Rewrite. Keep passing content verbatim (a typical page keeps ~4 of 7 sections nearly intact). Move mixed-form content to the page type that owns it and *say where it went* — S7 means reroute, not delete. Target the reader's time, not a word count: the win condition is "~N words fewer, zero concepts lost."
4. Never invent or "improve" product facts. Every number, flag, and claim is verbatim from the source or explicitly flagged for verification.
5. Deliver: before (verbatim, nav artifacts stripped) → after (clean markdown, `{{url}}` placeholders for unknown links) → change-log table mapping each change to a rule number → a "what was deliberately NOT done" section listing kept-strengths, moved-not-deleted items, and anything the product team must verify. See `examples/rewrite-before-after.md` for the exact shape and register.

### Route B: "What docs do I need?" / docs planning

1. Read `references/coverage.md` and follow its three topic sources in order: surface inventory (every command/flag/error is reference-covered — the one place completeness beats minimality), user journey (stage → page type), question log (2nd occurrence = doc candidate, 3rd = must write).
2. Ask what I already have (GitHub docs, site, support channels) before recommending anything — the gap analysis matters more than the generic ideal.
3. Deliver: minimum coverage contract (checked against what exists), coverage matrix with empty core cells marked as backlog, and GitHub-vs-site placement per S19. Under time pressure, sequence by the journey: README → quickstart → reference → top-3 how-tos → troubleshooting.

### Route C: "Write a new page"

1. Classify the job (S7), then copy the matching skeleton from `templates/` — `README`, `quickstart`, `how-to`, `reference`, or `explanation`. Keep the HTML guidance comments while drafting; delete them before delivering.
2. Fill every section the skeleton requires; a missing section is a gap, not a style choice.
3. Run that type's publish gate from `references/checklists.md` before delivering, and state the gate result in the delivery.

### Route D: "Set up a docs standard for my project/team"

1. Deliver a tailored kit: `references/style-guide.md` + `references/coverage.md` + `references/checklists.md`, customized to their project type and stack (edit rules they disagree with — the numbers are what make reviews cheap: "violates S4" is a complete review comment).
2. Include the adoption sequence: adopt the guide → replace the worst README → wire markdownlint + Vale (S26) → add gates to the PR template (S27).

### Route E: "This reads like AI wrote it" / de-slop

1. Classify first (S7). A page mixing jobs is a type problem; fixing the type usually deletes most tells on its own, so do that before the voice pass.
2. Read `references/voice-and-tells.md` — the catalog there is generated from the pin, so it is always current. Mark the tells strongest first: H1, H2, H6, H8, and H19 justify an edit on a single sighting.
3. Rewrite from the whole paragraph, not phrase by phrase. Keep every claim: no fact, name, number, date, or citation may appear or vanish (fiction is the only exemption from this rule, and documentation is never fiction).
4. Apply the **docs exemptions** before flagging anything: the S9 outcome sentence, the S12 exit ramp, reference neutrality (S17), code samples (S13–S16), and section roadmaps stay exactly as they are. A tell that is doing the page's job is not a tell.
5. Run the voice gate from `references/checklists.md`, then deliver as usual: before → after → change-log citing H-numbers (plus the S rule where one owns the fix) → "what was deliberately NOT done", naming any tell you kept on purpose and why.

## Non-negotiables (these protect the reader and my trust)

- **Classify before touching prose.** Almost every docs problem is a type problem wearing a prose costume. The S7 question — teaching, doing, looking up, or understanding? — comes first, every time.
- **Never fabricate product facts.** A docs rewrite that invents a flag or a default destroys more value than a bloated paragraph ever did. Flag uncertain items for product verification instead.
- **Short is a discipline, not a word count.** "Short" means nothing left that the reader can't act on (S24) — not gutted. When a section survives, say why it survived.
- **Traceability over taste.** Every change in a rewrite cites a rule number so I can veto by rule ("keep the adjectives, I don't care for S3") instead of arguing line by line. If you make a change you can't tie to a rule, reconsider the change.
- **Respect the existing voice.** The method supplies consistency; the project supplies personality. Where the two conflict, ask.
- **Facts survive the voice pass.** De-slopping prose never adds, drops, or rewords a product claim — a tell you cannot fix without changing meaning gets reported, not smuggled. Vendored catalog, our rules: the generated region in `voice-and-tells.md` is never hand-edited, and the docs exemptions override it.
