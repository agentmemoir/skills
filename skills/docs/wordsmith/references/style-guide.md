# STYLE_GUIDE

The house style for all documentation across our projects. Rules are numbered so checklists, reviews, and PR comments can reference them (`violates S4` is a complete review comment).

These rules are deliberately opinionated. They are distilled from Diátaxis, the Google and Microsoft style guides, the minimalism school, and community specs — see [research-notes.md](research-notes.md) for the evidence. Break a rule when doing so serves the reader better; when you break one, break it consistently and note why in the PR.

**Overlap with the voice catalog.** Six rules here have a twin in [`voice-and-tells.md`](voice-and-tells.md): S1↔H11 (passive voice), S2↔H9 (stacked qualifiers), S3↔H16 (sales language), S4/S5↔H12 (stock words and filler), S11↔H19/H20 (decorative bold and headings), S23/S24↔H13 (inflated significance). Cite **one** of the pair in a review comment: the S rule is the policy, the H tell is the symptom. Where the two disagree, the exemption table in the voice file wins.

---

## A. Voice and prose

**S1 — Second person, active voice, present tense.** "You run the command" / "The command prints…". Never "the output will be displayed". Tense drift ("will", "would") is the most common marker of stale docs.

**S2 — One idea per paragraph, three sentences max.** If a paragraph needs a second read to find its point, it needs to become two paragraphs.

**S3 — Use the reader's words.** Name things what users type, see, and call them — not your internal vocabulary. Avoid idioms that don't translate.

**S4 — Never write "simply", "easily", "just", or "obviously".** If it were obvious, the reader wouldn't be on this page. (Microsoft rule; the kindest rule in this guide.)

**S5 — Cut filler on sight.** `utilize → use` · `in order to → to` · `at this point in time → now` · `it should be noted that → delete` · `please → delete`.

**S6 — Define or link every term on first use.** Every abbreviation, every project noun. A reader who landed from search has no memory of your glossary page.

## B. Page design

**S7 — One page, one job, one reader state.** Before writing: is this page *teaching* (tutorial), *doing* (how-to), *looking up* (reference), or *understanding* (explanation)? Never mix jobs on one page. If a second job appears while writing, it's a new page. (Diátaxis)

**S8 — Put the outcome in the title.** "How to deploy behind a proxy", not "Deployment". Titles are how readers find and choose pages.

**S9 — Front-load everything.** The first sentence of a page states what it gets you and its prerequisites. The reader must be able to leave after one sentence and still be right. (Inverted pyramid)

**S10 — Every page stands alone.** Assume the reader arrived from search, GitHub, or an LLM with zero context. Establish context in the first two lines; link to background instead of narrating it. (Every Page Is Page One)

**S11 — Write for scanning.** A heading every 2–4 paragraphs; tables for options, flags, and either/or choices; bullets only for genuinely parallel facts; bold the thing the eye is hunting for — sparingly.

**S12 — Provide an exit ramp.** Every page ends with one "next step" or two "related" links, matched to what the reader probably needs next. Dead ends are wasted time. (Progressive disclosure)

## C. Code samples

**S13 — Show working code before explaining it.** The sample is the payload; prose supports it. If the code can say it, the paragraph doesn't have to.

**S14 — Every sample must be executable and tested.** If it can't run in CI, it's a guess, not documentation. Broken samples destroy more trust than any prose mistake.

**S15 — Samples show the common case; the reader edits values, not deletes boilerplate.** Mark the two or three values the reader must change with comments.

**S16 — One code block, one outcome.** Show expected output when the reader needs to verify success, so they can tell "it worked" from "it ran".

**S17 — Reference entries are complete, neutral, and structural.** Every flag, parameter, default, and error case; facts only, no narrative, no opinions. Structure mirrors the code (module → class → method), so looking up is mechanical. (Diátaxis reference obligations)

## D. Portfolio structure (GitHub vs. site)

**S18 — The README is a landing page, not a manual.** Its job is orientation and fast success: what it does, who it's for, install, a 60-second quickstart, then link out. Nothing longer than a screen. (Google: Minimum Viable Documentation)

**S19 — The site owns the four types; GitHub owns the front door.** Tutorials, how-tos, reference, and explanation live on the docs site. When a README topic outgrows a screen, it's asking to move to the site.

**S20 — Link, never duplicate.** One fact has one home; everything else links to it. Duplicated content rots at double speed. (Google: *Duplication is evil*)

**S21 — Every repo uses the same README skeleton.** Navigating between our projects should never require relearning our docs. Start from [templates/README.template.md](../templates/README.template.md).

## E. Keeping it short

**S22 — Minimum viable documentation wins.** A small set of fresh, accurate pages beats a large assembly that's partly outdated. Ship the page the reader needs, not the page that feels complete. (Google MVD)

**S23 — Delete dead documentation in the same change that kills its feature.** Docs debt is tech debt. A wrong page is worse than a missing one, because the reader trusts it.

**S24 — Cut anything the reader can't act on.** If a paragraph doesn't help the reader decide, do, or understand something they will use next, it's padding. This applies to history, trivia, and most introductions. (Minimalism)

## F. The consistency system (across N repos)

**S25 — The style guide lives in one repo; every project links to it.** Rule numbers are the shared review vocabulary. Local edits require a PR to that repo, not a quiet divergence.

**S26 — Lint mechanically, judge humanly.** Vale enforces the prose rules (S1–S5) and markdownlint enforces structure in CI. Machines catch consistency; humans judge value. One shared config for all repos.

**S27 — Docs change with code.** A PR that changes behavior without touching the affected docs is incomplete. (GitLab's rule — the single highest-leverage anti-staleness policy.)

**S28 — Collect one signal per page.** A "Was this helpful?" control or an issue template with Google's reason codes (*too complicated / out of date / sample broken*). Every report routes to a fix, not a backlog graveyard.
