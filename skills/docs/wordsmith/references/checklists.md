# CHECKLIST

Publish gates per doc type, plus a repo-level health check. Rules referenced by number point to [`STYLE_GUIDE.md`](STYLE_GUIDE.md), H-numbers to [`voice-and-tells.md`](voice-and-tells.md). Every type's gate ends with the voice gate. If a gate fails, the page isn't late — it's not finished.

## README gate

- [ ] One-sentence pitch in the first three lines: what it does + for whom (S9)
- [ ] Install is one copy-paste block
- [ ] 60-second quickstart that ends in something the reader can see working
- [ ] Links to the full docs site; no section longer than a screen (S18)
- [ ] Same section order as every other project's README (S21)
- [ ] No adjective a benchmark could fail ("blazingly fast") (S3)
- [ ] Badges: build/status only — vanity badges deleted

## Quickstart (tutorial) gate

- [ ] ≤ 10 steps, one action each
- [ ] Every command tested in a clean environment, in CI (S14)
- [ ] States prerequisites before step 1
- [ ] Ends with visible, verifiable success (S16)
- [ ] Exit ramp: one how-to + one next tutorial — not everything (S12)

## How-to gate

- [ ] Title is "How to {{verb phrase}}" naming the outcome (S8)
- [ ] First line states goal + starting conditions (S9)
- [ ] Assumes competence; teaches nothing — links to a tutorial instead (S7)
- [ ] Steps are imperative and sequential; no background narrative
- [ ] Failure is covered: troubleshooting section or link (minimalism: error recovery)

## Reference gate

- [ ] Mirrors the structure of the code (S17)
- [ ] Every entry has: signature, one-line description, parameters, defaults, errors
- [ ] Zero narrative — facts only (S7)
- [ ] Generated, or checked against generated output, where possible (S14)

## Explanation gate

- [ ] Answers a "why" question in the first line (S9)
- [ ] Contains no steps or commands (S7)
- [ ] Names its trade-offs
- [ ] Links to action pages for anything the reader now wants to do (S12)

## Voice gate (every page type — run it last)

The catalog is [`voice-and-tells.md`](voice-and-tells.md); the exemptions listed there override it. Check the delivered prose, not the whole file:

- [ ] No surviving **H1** not-X-but-Y, **H2** one-line closer, **H6** forced triad, **H8** dash-as-connector, or **H19** decorative bold — the five strongest
- [ ] No stock-word cluster (**H12**) and no sales register (**H16**) on a page that isn't a landing page
- [ ] No smart quotes (**H21**) in code, commands, paths, or config
- [ ] Every remaining tell is either fixed or named in "what was deliberately NOT done" with the H-number declined
- [ ] Nothing exempt was touched: the S9 outcome sentence, the S12 exit ramp, reference neutrality (S17), code samples (S13–S16)
- [ ] Claim check: the rewrite added no fact, name, number, date, or citation — and dropped none the patterns didn't call for

A voice pass that produced no H citations in the change log didn't run.

## Repo health check (monthly, all repos)

- [ ] Vale + markdownlint pass (S26)
- [ ] All code samples execute in CI (S14)
- [ ] No broken links (lychee or equivalent)
- [ ] Every feedback report ("out of date", "sample broken") has an owner or a fix (S28)
- [ ] Changelog current; deprecations carry removal dates + migration links
- [ ] README still matches the shared skeleton (S21)
- [ ] No page that survived a feature deletion (S23)
