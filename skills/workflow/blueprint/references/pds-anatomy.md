# PDS Anatomy

This is the only structure blueprint writes. It follows the tidy contract: one topic per file, one source of truth, relative links, and an entry-point hub. Adapt folder names only when the product's real seams demand it. Never fragment into tiny files; target 50 to 300 lines per file, and earn each file with a distinct bounded context or update lifecycle.

## Suite layout

```
<target>/                       # default: ~/.agentmemoir/<owner>/<repo>/blueprints/<product>/
├── index.md                    # entry hub: purpose, scope, domain map, navigation
├── glossary.md                 # ubiquitous language: one canonical definition per term
├── domains/                    # one file per bounded context
│   ├── <context>.md
│   └── ...
└── decisions/                  # one numbered record per amendment
    ├── 0001-<slug>.md
    └── ...
```

For a small product, `domains/` and `decisions/` may sit flat next to `index.md`. A new suite starts with `index.md` plus the domain files settled so far; create `decisions/` with the first amendment.

## index.md — the entry hub

Four required sections, per tidy's entry-point contract:

1. **Purpose & Problem Statement** — why the product exists and the problem it solves, in two or three sentences.
2. **Scope & Boundaries** — what the product governs, and what it explicitly does not.
3. **Domain Map** — every bounded context with its subdomain class (core, supporting, generic) and its relationships to the others as a text topology, using the DDD patterns: partnership, shared kernel, customer-supplier, conformist, anti-corruption layer, open host service, published language. Name in one line what crosses each boundary. This is the context map, and it is the single home of each subdomain class and relationship.
4. **Navigation Index & Reading Paths** — one relative link per file with a one-sentence summary, plus a reading path per reader goal, such as implementer, reviewer, or new stakeholder.

Zero duplication: the index routes, it does not define. Terms, rules, and models live in their domain files. An `Open:` point about the map or a term name parks under the Domain Map when no domain file owns it yet.

## glossary.md — the ubiquitous language

One line per term: the term, a short gloss, and a relative link to the domain file that owns it. Every term appears here exactly once. The domain file owns the full definition of its terms; the gloss is a pointer, never a second definition. When a gloss drifts from its domain file, fix the gloss in the same pass. When two contexts need the same word for different things, each context names its own term, and the glossary records both, each linked to its owner.

## Domain file schema

One file per bounded context, named after the context, for example `domains/billing.md`. The first line under the title is a status line: `Status: draft` or `Status: settled`. Flip it to `settled` when the context is complete and its open points are resolved.

1. **Purpose & Scope** — what this domain owns and what belongs to sibling domains; its subdomain class lives in the context map in `index.md`. One or two sentences.
2. **Ubiquitous Language** — the full definition of every term this context owns, and any local specializations. Shared terms link to `glossary.md`.
3. **Concepts & Model** — the entities, value objects, and aggregates in business terms. Each entity states its identity and lifecycle. Each value object states what makes two instances equal. Each aggregate states what it owns and what must stay consistent inside it.
4. **Capabilities & Operations** — what a user or another context can do here, and how the domain responds. Behavior serves the topic; it is never the structure.
5. **Rules & Invariants** — what is permitted, required, prohibited, and always true. Domain events named here state what happened in business words and which contexts care.
6. **Relationships** — relative links to the domains this one depends on, feeds, or shares events with; the pattern and nature of each link live in the context map in `index.md`.

Any `Open:` points come last, one line each, with the question that must be answered. No technology anywhere: no storage schemas, protocols, frameworks, or code.

## Decision record schema

One file per amendment, named `NNNN-<slug>.md`. Numbers are monotonic and never reused. The first line under the title is the date line: `Date: YYYY-MM-DD`, the day the amendment settled. Only Amend mode writes records; the settled suite is the record of Author and Extract. Follow tidy's ADR anatomy:

1. **Context & Problem Statement** — the force or gap that forced the change.
2. **Decision & Drivers** — what was decided and why, in one or two sentences.
3. **Invariants & Consequences** — what the change guarantees, what it costs, and what becomes easier or harder.
4. **Rejected Alternatives** — the options not taken and the reason.
5. **Amends** — relative links to every domain file, glossary entry, or earlier record this one changes.

## Writing discipline

- CEFR A2 plainness — short sentences, active voice, no filler — in whatever language the suite uses. Extract writes in the source docs' language; Author and Amend write in my language. When my language differs from the suite's, ask me once whether to translate the touched files or keep the suite's language.
- One paragraph per line. Newlines only for structure: headings, list items, table rows, and fenced blocks.
- Present tense, as if the product already exists: "The ledger rejects a duplicate entry", never "will" or "should eventually".
- Relative links only. No file repeats another file's content.
- Run tidy's checker (`python3 <tidy-skill-folder>/scripts/check-tidy.py <suite-folder>`) after every writing pass and fix what it reports. Never skip it in silence.
