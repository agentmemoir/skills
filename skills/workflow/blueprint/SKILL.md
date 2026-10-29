---
name: blueprint
description: >-
  Defines product domains and authors a Product Domain Specification (PDS): a technology-independent,
  Domain-Driven Design description of what a product is and how it behaves, one bounded context per
  file, written as if the product already exists. Use it when I say blueprint, PDS, or product
  domain spec, when I ask to define product domains, capabilities, rules, or bounded contexts, when
  I point at legacy documentation, PRDs, plans, or scattered notes and want a product spec extracted
  from them, or when I extend, amend, or continue an existing PDS. Also use it when a product idea
  needs shape before any PRD or code exists.
category: workflow
title: Blueprint
summary: >-
  Turns a product idea or scattered legacy docs into a Product Domain Specification: one bounded
  context per file, under the tidy contract. Grills me relentlessly on every decision that
  shapes the product, puts costly choices through prism, and records every amendment as a decision
  record so the suite grows across sessions.
say: >-
  "Blueprint a PDS for this" or "Extract the product spec from these docs."
license: MIT
compatibility: >-
  Needs a question tool for picks. Requires the tidy skill. Works best with the prism skill installed.
metadata:
  author: agentmemoir
  version: "1.0"
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
- **Context map.** `index.md` holds the map: every context, its class, and its relationships to the others, using the DDD context-map patterns. The map is the single home of classes and relationship natures.
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

A suite lives at `~/.agentmemoir/<owner>/<repo>/blueprints/<product>/`. Read `<owner>` and `<repo>` from `git remote -v`; `<product>` is a short slug for the product, and the repo name is the slug when the repo is the product. The folder sits outside every CLI's data folder, so session cleanup cannot delete it. One subfolder per product suite. When I name a target folder, use it. When the owner, repo, or product name is unclear — no git remote, several candidates, or an empty request — ask me one question before writing anything; with no git remote, ask me for the owner and repo and use my answers verbatim. Legacy source documents are never moved, edited, or deleted. Extraction writes only into the suite folder.

## The three modes

Detect the mode from my request. If it is unclear, ask one question before anything else. A request that touches an existing suite is always Amend, even when I call it a new feature.

### Author — start from nothing

1. Restate my goal in your own words: the product, who it serves, and the intent behind it. Wait for my confirmation.
2. Grill me on every decision that shapes the product: the core domain, the bounded contexts and their seams, the ubiquitous language, the capabilities, the rules, and the events that cross boundaries. One decision per message, and wait. Research what a decision needs so its options are honest, and reuse research across questions.
3. When a choice is costly to undo and no option is clearly best, use the prism format. When one answer is clearly right, or the choice is cheap to undo, decide and tell me in one line.
4. Before writing files, present the proposed topology: suite path, domain files, glossary, and index layout. Wait for my approval. This is tidy's user alignment checkpoint.
5. Write the suite per `references/pds-anatomy.md`: skeleton first, then every settled decision in its file as it settles, with unfinished domains at `Status: draft` and unsettled decisions as explicit `Open:` points. Never hold a settled decision only in the conversation, and never fill an open point with an invention.
6. Wire the entry hub and the links. Run tidy's checker (`python3 <tidy-skill-folder>/scripts/check-tidy.py <suite-folder>`) and fix what it reports. If you cannot locate tidy's folder, ask me for the path, and never skip the check in silence.

### Extract — distill from legacy docs

1. I point you to the legacy documentation, specification, plan, or PRD, or you apply *Where a PDS lives* for the suite path. Read every source file first. Build an inventory of domains, concepts, rules, and conflicts.
2. Distill, never copy. Keep every domain rule, constraint, term, and behavioral commitment. Drop narration, history, meeting notes, implementation detail, and duplication. The suite is smaller than the sources because it holds only the domain, not the paperwork.
3. When a source is ambiguous or self-contradictory, do not guess. If one reading is clearly right, or the choice is cheap to undo, ask a plain clarification. When two readings are valid and the choice between them reshapes the product, that choice is a decision, and it goes through prism.
4. Propose the derived topology and the conflicts you found. Wait for my approval before writing files.
5. Write the suite per `references/pds-anatomy.md`. Run tidy's checker, then report what you dropped in one short line per category: narration, history and meeting notes, implementation detail, duplication.

### Amend — extend an existing suite

1. Read the suite `index.md`, `glossary.md`, and every domain file the request touches. When the amendment distills new material from legacy sources, read every source file first and follow Extract steps 2 and 5 for distilling and the drop report; never copy their prose. Restate what I asked for and how it fits the current model. Wait for my confirmation.
2. Grill me on the new decisions the same way as in Author mode. A new capability, a new rule, a changed boundary, or a new term is settled before any edit.
3. Preserve 100 percent of existing invariants. When the change conflicts with one, surface the conflict and settle it with me before touching anything, through prism when the conflict is costly to undo.
4. Apply the change. Flip affected `Status: draft` markers, resolve `Open:` points I settled, and record every amendment as a decision record in `decisions/` per `references/pds-anatomy.md`.
5. Link the record from every file it changed, update the index and glossary, and run tidy's checker on the suite.

## The grilling session

All three modes share one protocol:

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

## Resources

- [references/pds-anatomy.md](references/pds-anatomy.md): suite layout, index contract, glossary, domain file schema, and decision record schema. Load it before writing any file.
- The `tidy` skill is the base contract this skill follows and never overrides. The `prism` skill supplies the format for costly decisions.
