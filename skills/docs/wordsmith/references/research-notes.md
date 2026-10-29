# DX Documentation Standards — Research Notes

A survey of the established, citable standards for writing developer documentation, focused on one question: **how do you write docs that deliver value fast, across a growing number of projects, without wasting the reader's time?**

Each section says what the standard is, what it actually prescribes, and what is worth stealing. Sources are listed at the end. The converged conclusions become the rules in [`style-guide.md`](style-guide.md).

---

## 1. Diátaxis — the structure standard

The most widely adopted documentation framework of the last decade (Daniele Procida; used by Django, Ubuntu, Gatsby, Cloudflare, Vonage). Its core claim: all documentation answers one of **four user needs**, and each need demands a different form.

| Type | User need | User state | Optimized for |
|---|---|---|---|
| Tutorial | "Teach me" | Studying, not yet competent | Learning, confidence |
| How-to guide | "Help me do X" | Working, competent | Task success |
| Reference | "Give me the facts" | Working, at the keyboard | Accuracy, completeness, neutrality |
| Explanation | "Help me understand" | Studying | Insight, context, the "why" |

The practical rules that fall out of it:

- **One page serves one need.** Mixing forms is the root cause of docs that waste time — a tutorial that stops to explain architecture, or a reference page that goes on a journey, serves nobody well and everybody slowly.
- Each type carries different obligations: tutorials *guarantee* success; how-tos *assume* competence; reference is neutral and mirrors the structure of the thing it describes; explanation may roam but never instructs.
- Routing new content becomes a lookup, not a debate: *is this teaching, task-solving, fact-stating, or understanding-building?*

**Limitation:** Diátaxis is an information-architecture tool, not a prose-quality tool. It tells you where content belongs, not how to write sentences. Pair it with a style guide.

## 2. Google Developer Documentation Style Guide — the prose standard

Public and continuously maintained at `developers.google.com/style`. Key features:

- It explicitly calls its own prescriptions "guidelines, not rules" and tells you to break them *deliberately and consistently* — a good posture to copy.
- Highest-frequency prescriptions: second person ("you"), active voice, present tense (never "the command will output…"), sentence-case headings, define terms on first use, and a plain-word list ("use" not "utilize", "once" not "after you have completed").
- **Document the common case first**; treat edge cases secondarily.
- Google's engineering-facing companion, the *Google Documentation Guide*, adds portfolio-level doctrine that matches a short-docs philosophy exactly: **Minimum Viable Documentation** ("a small set of fresh and accurate docs is better than a large assembly of documentation that is partially outdated"), *Update docs with code*, *Delete dead documentation*, *Prefer the good over the perfect*, *Duplication is evil* — under Brian Kernighan's epigraph: *"Say what you mean, simply and directly."*

## 3. Microsoft Writing Style Guide — the voice standard

Successor to the Microsoft Manual of Style, published online at `learn.microsoft.com/style-guide`. The most-imitated voice standards in software docs:

- Tone: **warm and relaxed, crisp and clear** — friendly without being chatty.
- Write for scanning: headings that carry meaning, short paragraphs, one idea each.
- Use the customer's words, not your internal vocabulary.
- Notable guardrails: avoid idioms that don't translate globally, and never write "simply" or "easily" — it insults readers who are stuck.
- Its A–Z word list converts directly into a Vale linter configuration.

## 4. The minimalism school — the philosophy

Three sources, one argument: length is not value; task completion is value.

- **John Carroll's minimalism** (*The Nurnberg Funnel*, 1990): people learn and act by *doing*, not by reading. Get the user up and running as fast as possible, let them improvise, support error recognition and recovery, and cut anything the user will not act on. This is the academic root of "docs should not be long."
- **Mark Baker, *Every Page Is Page One*** (2012): readers no longer arrive at page 1 and read linearly — they land on whatever search, GitHub, or an LLM surfaced. Every topic must therefore be **self-contained**, establish its own context, and have a specific, limited purpose.
- **Progressive disclosure** (Nielsen Norman Group): reveal complexity in layers. The default path stays simple; advanced material is one deliberate click away. This measurably reduces errors and speeds learning.

## 5. Community standards — the artifacts

- **standard-readme**: a formal spec for README structure (badges → TOC → background → install → usage → contributing → license). Opinionated and Node-flavored, but a sane default.
- **Make a README**: the README as the project's front door; famous for claiming "too long is better than too short" — see *Tensions* below.
- **The Good Docs Project**: free, battle-tested templates for quickstarts, READMEs, references, release notes. Their quickstart doctrine: each part delivers one success moment.
- **Write the Docs**: the practitioner community; its guide and conference archives are the best index of current practice.
- **GitLab Documentation Style Guide**: the best public end-to-end example of a real house style — structure, prose, word list, and the rule that docs change in the same MR as code. Steal its structure for your own guide.

## 6. Measuring docs DX

- Developers spend **3–10 hours per week** searching for information that should be documented (getdx analysis); documentation quality ranks among the strongest predictors of engineering velocity.
- The **DevEx framework** (Forsgren, Storey & Zimmermann, *ACM Queue*, 2022) gives three lenses that docs feed directly: **feedback loops, cognitive load, flow state**. A doc that answers without interruption protects all three; a doc that forces a support ticket breaks all three.
- Cheap, working signals: a per-page "Was this helpful?" control with reason codes — Google's own taxonomy is *easy to understand / solved my problem / too complicated / out of date / samples issue*; docs page analytics; support-channel tag counts; treating docs fixes as bugs with owners.
- **Test docs like code:** executable quickstarts in CI, doctests/example tests for code samples, link checking, and **Vale** — a prose linter that enforces your style guide mechanically and shares one config across all repos. This is how a style guide survives portfolio growth without depending on heroics or memory.

---

## Where everything converges

| Convergent principle | Diátaxis | Google | Microsoft | Minimalism | Community |
|---|:---:|:---:|:---:|:---:|:---:|
| One page, one job | ✔ | ✔ (common case first) | ✔ (one idea per paragraph) | ✔ (task-first) | ✔ (templates) |
| Assume a competent reader; don't over-teach | ✔ | ✔ | ✔ | ✔ | — |
| Show, then say | — | ✔ (samples everywhere) | — | ✔ (learning by doing) | ✔ (quickstart) |
| Fresh beats complete | — | ✔ (Minimum Viable Docs) | — | ✔ (cut what can't be acted on) | ✔ (docs debt) |
| Same voice everywhere | — | ✔ | ✔ | — | ✔ (GitLab, Vale) |
| Pages stand alone | ✔ (per-type pages) | — | — | ✔ (Every Page Is Page One) | ✔ (deep linking) |

This convergence is the strongest finding: five independent traditions, written for different audiences over ~35 years, land on the same six rules. The style guide in this kit is a distillation of this table, not one school's opinion.

## Honest tensions

1. **"Too long is better than too short"** (Make a README) vs. minimalism. Resolution: length is fine when it serves *distinct needs* (the four types); waste comes from one page serving several needs badly. A short README that links to a complete site satisfies both camps.
2. **Diátaxis doesn't guarantee quality.** A well-placed but badly written page still fails. Structure (Diátaxis) and prose (style guide) are separate halves.
3. **Markdown docs age faster than code.** Without the "docs change with the PR" rule, consistency decays in months. Linting catches style, never truth.
4. **Docs-as-code tooling is optional; conventions are not.** Everything in this kit runs on markdown and a couple of linters — no site generator, pipeline, or platform decision is required first.

## Sources

- Diátaxis — <https://diataxis.fr> (primer: <https://diataxis.fr/start-here>)
- Google Developer Documentation Style Guide — <https://developers.google.com/style>
- Google Documentation Guide, best practices — <https://google.github.io/styleguide/docguide/best_practices.html>
- Microsoft Writing Style Guide — <https://learn.microsoft.com/en-us/style-guide/welcome>
- Minimalism (Carroll) — <https://en.wikipedia.org/wiki/Minimalism_(technical_communication)>
- Every Page Is Page One — <https://everypageispageone.com/the-book/>
- Progressive disclosure (Nielsen Norman Group) — <https://www.nngroup.com/articles/progressive-disclosure/>
- standard-readme — <https://github.com/richardlitt/standard-readme>
- Make a README — <https://www.makeareadme.com>
- The Good Docs Project templates — <https://www.thegooddocsproject.dev/template>
- Write the Docs — <https://www.writethedocs.org/guide/>
- GitLab Documentation Style Guide — <https://docs.gitlab.com/development/documentation/styleguide/>
- Measuring docs impact (getdx) — <https://getdx.com/blog/developer-documentation/>
- Vale prose linter — <https://docs.vale.sh>
- Forsgren, Storey & Zimmermann, *DevEx: What Actually Drives Productivity*, ACM Queue, 2022.
- I'd Rather Be Writing on Diátaxis — <https://idratherbewriting.com/blog/what-is-diataxis-documentation-framework>
