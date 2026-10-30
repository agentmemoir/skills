# PDS Anatomy

This is the only structure blueprint writes inside a suite. It follows the tidy contract: one topic per file, one source of truth, relative links, and an entry-point hub. Adapt folder names only when the product's real seams demand it. Never fragment into tiny files; target 50 to 300 lines per file, and earn each file with a distinct bounded context or update lifecycle. The one file blueprint may write outside a suite is the repo-root `PHILOSOPHY.md`, for a Migrate philosophy unit; it is never mirrored with the suite.

## Suite layout

```
<target>/                       # default: ~/.agentmemoir/<owner>/<repo>/blueprints/<product>/
├── blueprint.json              # sync settings, see references/sync-and-restore.md
├── README.md                   # entry hub: purpose, scope, domain map, navigation
├── glossary.md                 # ubiquitous language: one canonical definition per term
├── domains/                    # one file per bounded context
│   ├── <context>.md
│   └── ...
└── decisions/                  # one numbered record per amendment or migrated decision
    ├── 0001-<slug>.md
    └── ...
```

`blueprint.json` holds settings, not a PDS topic. It is never linked from the entry point and never defines product behavior. A suite may hold only this file before its first PDS file is written.

New suites use `README.md` as the entry point. A suite that still holds `index.md` keeps it until I agree to rename it; `blueprint.json` records the choice in `entry_file`.

For a small product, `domains/` and `decisions/` may sit flat next to the entry point. A new suite starts with `blueprint.json` and `README.md`, plus the domain files settled so far; create `decisions/` with the first amendment.

## README.md — the entry hub

Four required sections, per tidy's entry-point contract. The same sections apply when a suite still uses the legacy `index.md` entry point.

1. **Purpose & Problem Statement** — why the product exists and the problem it solves, in two or three sentences.
2. **Scope & Boundaries** — what the product governs, and what it explicitly does not.
3. **Domain Map** — every bounded context with its subdomain class (core, supporting, generic) and its relationships to the others as a text topology, using the DDD patterns. This section is automatically generated between `<!-- BEGIN GENERATED: domain map -->` and `<!-- END GENERATED: domain map -->` from domain files by `blueprint.py generate`.
4. **Navigation Index & Reading Paths** — one relative link per file with a one-sentence summary, plus reading paths. The file and decision tables are automatically generated between `<!-- BEGIN GENERATED: navigation -->` and `<!-- END GENERATED: navigation -->` by `blueprint.py generate`.

Zero duplication: the entry point routes, it does not define. Terms, rules, and models live in their domain files. An `Open:` point about the map or a term name parks under the Domain Map when no domain file owns it yet.

## glossary.md — the ubiquitous language

One line per term: the term, a short gloss, and a relative link to the domain file that owns it. Every term appears here exactly once. The domain file owns the full definition of its terms; the gloss is a pointer, never a second definition. When a gloss drifts from its domain file, fix the gloss in the same pass.

`glossary.md` is compiled automatically between `<!-- BEGIN GENERATED: ubiquitous language -->` and `<!-- END GENERATED: ubiquitous language -->` by `python3 <blueprint-skill-folder>/scripts/blueprint.py generate <suite-folder>`. Never hand-edit terms inside the generated region; update the domain file and regenerate.

## Domain file schema

One file per bounded context, named after the context, for example `domains/billing.md`. The first line under the title is a status line: `Status: draft` or `Status: settled`. Flip it to `settled` when the context is complete and its open points are resolved.

1. **Purpose & Scope** — what this domain owns and what belongs to sibling domains; its subdomain class lives in the context map in the suite entry point. One or two sentences.
2. **Ubiquitous Language** — the full definition of every term this context owns, and any local specializations. Shared terms link to `glossary.md`.
3. **Concepts & Model** — the entities, value objects, and aggregates in business terms. Each entity states its identity and lifecycle. Each value object states what makes two instances equal. Each aggregate states what it owns and what must stay consistent inside it.
4. **Capabilities & Operations** — what a user or another context can do here, and how the domain responds. Behavior serves the topic; it is never the structure.
5. **Rules & Invariants** — what is permitted, required, prohibited, and always true. Domain events named here state what happened in business words and which contexts care.
6. **Relationships** — relative links to the domains this one depends on, feeds, or shares events with; the pattern and nature of each link live in the context map in the suite entry point.

Any `Open:` points come last, one line each, with the question that must be answered. No technology anywhere: no storage schemas, protocols, frameworks, or code.

## Decision record schema

One file per amendment or migrated decision, named `NNNN-<slug>.md`. Numbers are monotonic and never reused. The first line under the title is the date line: `Date: YYYY-MM-DD`, the day the decision settled. Amend writes a record for every amendment, and Migrate writes a record for every decision the legacy sources settle. Author and Extract leave the settled suite as their record. Follow tidy's ADR anatomy:

1. **Context & Problem Statement** — the force or gap that forced the change.
2. **Decision & Drivers** — what was decided and why, in one or two sentences.
3. **Invariants & Consequences** — what the change guarantees, what it costs, and what becomes easier or harder.
4. **Rejected Alternatives** — the options not taken and the reason.
5. **Amends** — relative links to every domain file, glossary entry, or earlier record this one changes.

## Writing discipline

- CEFR A2 plainness — short sentences, active voice, no filler — in whatever language the suite uses. Extract and Migrate write in the source docs' language; Author and Amend write in my language. When my language differs from the suite's, ask me once whether to translate the touched files or keep the suite's language.
- One paragraph per line. Newlines only for structure: headings, list items, table rows, and fenced blocks.
- Present tense, as if the product already exists: "The ledger rejects a duplicate entry", never "will" or "should eventually".
- Relative links only. No file repeats another file's content.
- Run the generator (`python3 <blueprint-skill-folder>/scripts/blueprint.py generate <suite-folder>`) after changing domain files or decisions.
- Run the structural validator (`python3 <blueprint-skill-folder>/scripts/blueprint.py validate <suite-folder>`) to verify schema and link integrity.
- Run tidy's checker (`python3 <tidy-skill-folder>/scripts/check-tidy.py <suite-folder>`) after every writing pass and fix what it reports. Never skip it in silence.
