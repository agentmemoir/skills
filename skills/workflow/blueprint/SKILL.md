---
name: blueprint
description: >-
  Defines product domains and authors a Product Domain Specification (PDS): a technology-independent,
  Domain-Driven Design description of what a product is and how it behaves, one bounded context per
  file, written as if the product already exists. Use it when I say blueprint, PDS, or product
  domain spec, when I ask to define product domains, capabilities, rules, or bounded contexts, when
  I point at legacy documentation, PRDs, plans, or scattered notes and want a product spec extracted
  from them, or when I extend, amend, or continue an existing PDS. Also use it when a product idea
  needs shape before any PRD or code exists, when I want the suite mirrored to a project-local
  folder, when a fresh clone must restore a missing central suite, or when I migrate a very large
  legacy doc set across sessions with a saved next-session scope.
category: workflow
title: Blueprint
summary: >-
  Turns a product idea or scattered legacy docs into a Product Domain Specification: one bounded
  context per file, under the tidy contract. Questions every decision that shapes the product,
  puts costly choices through prism, and records every amendment as a decision record so the suite
  grows across sessions. Keeps the suite central, mirrors it to an optional project folder, restores
  it from a clone when the central copy is missing, and migrates large legacy sets one session scope
  at a time.
say: >-
  "Blueprint a PDS for this", "Extract the product spec from these docs", or "Migrate this legacy
  folder into blueprints."
license: MIT
compatibility: >-
  Needs a question tool for picks and git for the owner and repo. Requires the tidy skill. Writes
  under ~/.agentmemoir and to an optional project-local mirror. Works best with the prism skill
  installed.
metadata:
  author: agentmemoir
  version: "1.1"
---
# Blueprint

Decisions first, documents second. Blueprint shapes a product as a set of domains, then writes a Product Domain Specification (PDS) that describes the finished product as if it already exists.

A PDS says what the product is and how it behaves. It never says how to build it.

## Tidy gate (run first)

Before any work, load the `tidy` skill. If tidy is not present, stop immediately and ask me to install tidy first (`npx skills add agentmemoir/skills --skill tidy --global -y`). Do nothing else until tidy is installed.

Once tidy is loaded, strictly adhere to it for the rest of the task: one topic per file, one source of truth, boundaries derived from the product's real seams, an entry-point hub, relative links instead of copies, and the one-paragraph-per-line rule. Two tidy rules yield where the genre demands it: prose follows CEFR A2 plainness in whatever language the suite is written, and tidy's 100 percent preservation invariant scopes to domain content — domain rules, constraints, terms, and behavioral commitments are never dropped or weakened. Narration, history, and implementation detail are dropped on purpose in Extract, and reported.

## What a PDS is

- **Future-oriented.** The spec reads like user documentation for a product that is already finished and fully functional. Write "The product does X", never "we plan to build X" or "it will support X".
- **Present tense by convention.** The suite reads as if the product is finished, even when nothing is built yet. This is the genre's voice, not a claim that code exists, so tidy's codebase-grounding rule does not apply inside the suite.
- **Domain-first.** The primary organizing unit is the product domain and its topics. User stories, screens, epics, and components are never the structure. Behavior is documented only to explain a topic.
- **Technology-independent.** No languages, frameworks, storage engines, protocols, or UI layouts. The same PDS must guide a Python, Rust, or Go implementation without one concept changing.
- **Uncertainty-minimizing.** A PDS closes the conceptual gap between a PRD and the finished product. It gives product managers, designers, developers, and reviewers the same concepts, capabilities, rules, and expected behavior, so interpretation gaps die before implementation.
- **Not a technical answer sheet.** A PDS never tries to answer every technical question upfront. It settles what the product is and how it behaves, and preserves freedom on how it will be built.
- **A foundation for the PRD.** The PDS describes the product as an integrated whole; the PRD translates it into priorities and verifiable acceptance criteria. An existing PRD is source material for extraction, never the structure of the suite.

## DDD commitment

The PDS speaks Domain-Driven Design. Every suite follows these rules:

- **Ubiquitous language.** Every term has one meaning and one home: the domain file that owns it holds the full definition, and `glossary.md` indexes every term with a short gloss and a link. No definition lives twice.
- **Bounded contexts.** Each domain file is one bounded context. It owns its terms, its model, and its rules. What crosses a context boundary is named explicitly.
- **Subdomain classes.** Every domain is classified as core, supporting, or generic. Core domains get the most detail; generic ones get the least.
- **Context map.** The suite entry point (`README.md`, or a legacy `index.md`) holds the map: every context, its class, and its relationships to the others, using the DDD context-map patterns. The map is the single home of classes and relationship natures.
- **Tactical model in business terms.** Name entities, value objects, aggregates, domain events, and invariants, and give core domains the most of them. An aggregate states what it owns and what must stay consistent inside it. A domain event states what happened in business words. No repositories, services, or code patterns.
- **Rules and invariants.** Every domain file states what is permitted, required, prohibited, and always true.

## How you communicate with me

- **Use simple English (CEFR A2) and ASD-STE100**, including for domain and design talk.
- **Be concise.** Start with the answer. No greeting or filler. Keep each reply to 1-4 lines, except for a restated goal, a prism decision, or a saved suite.
- **Never invent an answer to my question.** When my answer is unclear, do not guess and do not pick the closest option. Ask again with the question tool, and say in one line which part was unclear.
- **Be relentless on ambiguity.** A vague term, a missing rule, an undefined owner, or a conflict between my statements or between legacy sources is a question when the answer only fixes meaning, and a decision when several valid readings exist. Ask until the domain language is exact. Ambiguity in a PDS becomes rework later.
- **More than one correct avenue is a decision, not a clarification.** When two or more avenues are clearly valid, ask me to pick. Costly, hard-to-undo choices go through the `prism` skill format. If prism is not installed, keep its gate — ask only about costly choices — and ask them as plain options with trade-offs and a recommendation. When one answer is clearly right, or the choice is cheap to undo, decide, act, and tell me in one line.
- **Adapt to custom answers.** When my answer is clear but matches no listed option, treat it as the instruction. Restate what you will do in one line, then follow it.
- **A re-ask keeps the format of the question it repeats.** If the unclear answer belonged to a prism decision, re-ask it in the prism format, mark my previous choice, and never drop it. Otherwise re-ask as a plain clarification.

## Where a PDS lives

A suite lives at `~/.agentmemoir/<owner>/<repo>/blueprints/<product>/`. Read `<owner>` and `<repo>` from `git remote -v`; `<product>` is a short slug for the product, and the repo name is the slug when the repo is the product. The folder sits outside every CLI's data folder, so session cleanup cannot delete it. One subfolder per product suite. The central suite is the only source of truth; a project-local folder is a mirror of it, never a second source.

Every suite holds `blueprint.json`, which records the sync choice and the mirror path. When I name a target folder, that folder is the mirror and the setting is saved. Mirror paths are relative to the repo root; refuse an absolute path and ask for a relative one. When the owner, repo, or product name is unclear — no git remote, several candidates, or an empty request — ask me one question before writing anything; with no git remote, ask me for the owner and repo and use my answers verbatim. Legacy source documents are never moved, edited, or deleted. Writes go into the suite folder, plus a repo-root `PHILOSOPHY.md` when a Migrate philosophy work unit calls for it.

## Session start

Run these steps in order before any other work.

1. Load `tidy` per the gate above.
2. Resolve `<owner>`, `<repo>`, and `<product>`. When the central suite has no entry point (`README.md`, or a legacy `index.md`) — the folder is absent or holds only settings — and a local suite exists, restore it and report the count, per [references/sync-and-restore.md](references/sync-and-restore.md).
3. Read `blueprint.json`. When it is absent, ask the two configuration questions together and write the file immediately. When it is unreadable or incomplete, stop and ask; never guess a setting.
4. State one line: the central suite path, the mirror path, and the sync state.
5. When sync is off and a stale local copy exists, ask once whether to delete it.

## Session end

The session ends after the final writing pass and its tidy check.

1. The mode's final tidy check is the gate. When it failed and cannot be fixed, report it and do not mirror.
2. When sync is on, mirror the whole suite to the local folder, delete local files that central does not have, and report the overwritten, deleted, and new counts. The first mirror into a non-empty folder that is not a suite stops and asks.
3. When sync is custom, follow the stored instruction within the core rules. When it conflicts with central-canonical or the mirror rule, apply the compatible part, stop, and ask.
4. When sync is off, do nothing.

A settings-only change mirrors that file immediately when sync is on, because it is not PDS content.

## The four modes

Detect the mode from my request. If it is unclear, ask one question before anything else. A request that touches an existing suite is always Amend, even when I call it a new feature. A request to migrate a large legacy set across sessions is Migrate.

### Author — start from nothing

1. Restate my goal in your own words: the product, who it serves, and the intent behind it. Wait for my confirmation.
2. Grill me on every decision that shapes the product: the core domain, the bounded contexts and their seams, the ubiquitous language, the capabilities, the rules, and the events that cross boundaries. One decision per message, and wait. Research what a decision needs so its options are honest, and reuse research across questions.
3. When a choice is costly to undo and no option is clearly best, use the prism format. When one answer is clearly right, or the choice is cheap to undo, decide and tell me in one line.
4. Before writing files, present the proposed topology: central suite path, mirror path, domain files, glossary, and entry-point layout. Wait for my approval. This is tidy's user alignment checkpoint.
5. Write the suite per `references/pds-anatomy.md`: skeleton first, then every settled decision in its file as it settles, with unfinished domains at `Status: draft` and unsettled decisions as explicit `Open:` points. Never hold a settled decision only in the conversation, and never fill an open point with an invention.
6. Wire the entry hub and the links. Run tidy's checker (`python3 <tidy-skill-folder>/scripts/check-tidy.py <suite-folder>`) and fix what it reports. If you cannot locate tidy's folder, ask me for the path, and never skip the check in silence.

### Extract — distill from legacy docs

1. I point you to the legacy documentation, specification, plan, or PRD, or you apply *Where a PDS lives* for the suite path. Read every source file first. Build an inventory of domains, concepts, rules, and conflicts.
2. Distill, never copy. Keep every domain rule, constraint, term, and behavioral commitment. Drop narration, history, meeting notes, implementation detail, and duplication. The suite is smaller than the sources because it holds only the domain, not the paperwork.
3. When a source is ambiguous or self-contradictory, do not guess. If one reading is clearly right, or the choice is cheap to undo, ask a plain clarification. When two readings are valid and the choice between them reshapes the product, that choice is a decision, and it goes through prism.
4. Propose the derived topology and the conflicts you found. Wait for my approval before writing files.
5. Write the suite per `references/pds-anatomy.md`. Run tidy's checker, then report what you dropped in one short line per category: narration, history and meeting notes, implementation detail, duplication.

### Amend — extend an existing suite

1. Read the suite entry point (`README.md`, or a legacy `index.md`), `glossary.md`, and every domain file the request touches. When the amendment distills new material from legacy sources, read every source file first and follow Extract steps 2 and 5 for distilling and the drop report; never copy their prose. Restate what I asked for and how it fits the current model. Wait for my confirmation.
2. Grill me on the new decisions the same way as in Author mode. A new capability, a new rule, a changed boundary, or a new term is settled before any edit.
3. Preserve 100 percent of existing invariants. When the change conflicts with one, surface the conflict and settle it with me before touching anything, through prism when the conflict is costly to undo.
4. Apply the change. Flip affected `Status: draft` markers, resolve `Open:` points I settled, and record every amendment as a decision record in `decisions/` per `references/pds-anatomy.md`.
5. Link the record from every file it changed, update the entry point and glossary, and run tidy's checker on the suite.

### Migrate — distill a very large legacy set across sessions

1. Resolve the legacy root from my request; ask for it when it is missing. Resolve the migration working directory from my request, then `blueprint.json`, then the default `./agent-files/blueprint-migration/`; save a directory I name when it differs.
2. Read `next.json` when it exists. Treat it as the session scope. When its shape is not migration scope — for example, it names build or implementation work — stop and ask. Move the consumed file to `~/.agentmemoir/<owner>/<repo>/migration-consumed/<date>-next.json` before starting. When no file exists, choose a reasonable subset of work units and present it to me for approval.
3. Read the suite and every work file in the working directory. Report which work units are already `migrated` or `verified`, and never repeat them.
4. For each work unit in scope, read every source, distill by Extract's rules, and settle every open decision one message at a time. Write the unit's targets and update its work file.
5. Write a decision record for every decision the legacy sources settle, per `references/pds-anatomy.md`.
6. Finish exactly the scope. Carry every unfinished unit into the new `next.json` with its status and reason.
7. Write the new `next.json` for the next session, in the shape `references/legacy-migration.md` defines.
8. Run tidy's checker, then follow *Session end*.

Migrate writes the PDS core and, for a philosophy unit, the repo-root `PHILOSOPHY.md`. It never authors another file. The full boundary, the work file schema, and the scope contract live in [references/legacy-migration.md](references/legacy-migration.md).

## The grilling session

All four modes share one protocol:

- The unit is one decision per message: a domain boundary, a subdomain class, a term definition, an aggregate ownership, a capability, an invariant, or a crossing event.
- Clarification goes through the question tool. Shape-defining and costly decisions go through prism. Never mix the two.
- Settle the topology, the context boundaries, and the term names before writing files. Behavior and capability decisions may stay `Open:` and park in their domain file until later.
- After I approve the topology, record each newly settled decision in its file as it settles, and carry it in with its meaning intact. Never drop a settled rule between interview and files, and never hold one only in the conversation.

## Anti-patterns

- One giant PDS file instead of one file per bounded context.
- Copying legacy prose into the suite instead of distilling it.
- Answering how to build instead of what the product is.
- Structuring the suite around user stories, screens, or epics.
- Silently rewriting or weakening an existing rule during Amend.
- A decision record with no link from the file it changed.
- An `Open:` point quietly filled with a guess.
- Treating the local mirror as a second source of truth.
- Restoring over a central suite that already has its entry point.
- Migrating a whole legacy set in one session.
- Writing a file outside Migrate's boundary.

## Resources

- [references/pds-anatomy.md](references/pds-anatomy.md): suite layout, entry-point contract, glossary, domain file schema, and decision record schema. Load it before writing any file.
- [references/sync-and-restore.md](references/sync-and-restore.md): settings schema, session-start detection, restore, the end-of-session mirror, and its guards. Load it before the first configuration question.
- [references/legacy-migration.md](references/legacy-migration.md): the Migrate protocol, next.json contract, work file schema, statuses, and the writing boundary. Load it before a Migrate session.
- The `tidy` skill is the base contract this skill follows and never overrides. The `prism` skill supplies the format for costly decisions.
