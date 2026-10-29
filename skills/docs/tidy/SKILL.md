---
name: tidy
description: >-
  Decompose sprawling documentation, plans, and technical specifications into domain-derived
  bounded contexts with one file per topic, eliminate duplication, ground claims in code, and
  preserve all invariants. Use when organizing, refactoring, or splitting documentation,
  specifications, or architectural guides, when files become monolithic and hard to navigate,
  when a repository accumulates file sprawl or bloated monolithic documents, or when context
  consumption must stay minimal for both humans and agents. Skills that build documentation,
  plans, or specifications load tidy first and follow its contract.
category: docs
title: Tidy
summary: >-
  Splits sprawling docs, plans, and specs into one-topic-per-file bounded contexts with one
  source of truth and zero content loss. A reusable base skill: consumer skills load it first
  and strictly follow its contract for file organization, deduplication, and verification.
say: >-
  "Tidy these docs" or "Split this monolithic spec with tidy."
---

# Tidy

Information sprawl is a common problem in software engineering. When unmanaged, documentation, specifications, and architecture plans accumulate in giant files. Critical rules, contracts, and architecture decisions get lost under old clutter and duplicate tables. When files grow too large, readers and coding agents miss important details, repeat work, and cause bugs.

Tidy provides a universal structure: split knowledge into domain-derived bounded contexts, isolate one topic per file, keep one source of truth, verify claims against working code, and preserve 100 percent of domain rules during refactoring.

## Core Philosophy and Invariants

Tidy operates on four foundational principles:

### 1. One File per Topic (Single Source of Truth)

Every distinct concept, specification, wire contract, data schema, or state machine must live in exactly one authoritative file. Never copy identical tables, configuration schemas, or rules across multiple documents. Duplication causes drift: one copy changes while other copies become stale. Under Tidy, one authoritative document owns the canonical definition. All other files that reference the concept must link to the canonical file using relative Markdown links rather than repeating its content.

### 2. 100% Preservation Invariant

Tidying is structural refactoring, never re-architecting or silent redesign. Refactoring must never drop, weaken, or silently alter an existing design decision, security constraint, schema field, behavioral rule, or error contract. Every technical requirement in the original text must survive intact in the refactored files. If the source material contains ambiguities, contradictions, or missing details, do not guess. Stop and resolve the uncertainty through explicit clarification before editing.

### 3. Codebase Grounding

Documentation is a map of working software, not speculative notes. Verify all file paths, module names, symbols, CLI commands, and environment variables against the real codebase and environment. When documentation describes planned capabilities or unbuilt targets, mark them as proposal or planned. Never present an unverified assumption or future proposal as a finished fact.

### 4. Progressive Disclosure

Keep entry points and top-level summaries concise, clear, and easy to navigate. Move deep details, reference tables, raw payloads, and edge cases into dedicated topic files behind explicit relative links. Progressive disclosure protects reader attention: readers see the high-level landscape first and open detailed specifications only when their work requires them.

## Universal Domain-Derived Decomposition

Tidy rejects fixed folder templates. Instead, follow one universal rule:

> Derive boundaries from the subject domain bounded contexts; never force an arbitrary fixed folder template.

Do not force every system into a pre-assigned set of folders. Forcing artificial categories creates confusion and scatters related concepts. Instead, inspect the subject, identify its natural seams and cohesive duties, and create boundaries that match the domain.

### Natural Decomposition Examples

The archetypes below show how different technical domains divide. They are helpful examples, not rigid rules or universal templates. File and folder organization must always be domain-driven, derived directly from the natural bounded contexts of the problem space, and structured to serve readers well. Select or adapt the organization that fits the true domain boundaries of the system.

- **Complex Multi-Tier System or Platform**: A large system separates into high-level concepts (`concepts/`), interface contracts and protocols (`contracts/`), design trade-offs and decisions (`architecture/`), and operating procedures (`guides/` or `runbooks/`).
- **Autonomous Agent Capability or Tool Extension**: A tool capability organizes into its root guide (`README.md` or `SKILL.md`), technical references (`references/`), scaffold templates (`templates/` or `assets/`), and verification scripts (`scripts/`).
- **API Service or Backend Application**: An API codebase organizes around route interfaces (`routes/` or `endpoints/`), domain models and business rules (`models/` or `domain/`), database schemas and migrations (`schemas/` or `migrations/`), and deployment runbooks (`runbooks/`).
- **Developer Documentation or User Manual**: A documentation portal follows user progression: quick orientation (`quickstart/`), guided walkthroughs (`tutorials/`), interface contracts (`reference/`), and foundational concepts (`concepts/`).
- **Architectural Decision & Research Repository**: A decision repository organizes around numbered decision records (`decisions/` or `adr/`), test evaluations and benchmarks (`evaluations/`), and trade-off studies (`research/`).
- **Data Pipeline or Machine Learning Project**: A data system organizes around dataset schemas (`datasets/`), processing pipelines (`pipelines/`), model specifications (`models/`), and evaluation metrics (`metrics/`).
- **Software Library or CLI Tool**: A library or tool organizes into core engine primitives (`core/`), user commands and flags (`commands/`), protocol adapters (`protocols/`), and integration examples (`examples/`).
- **Lightweight Single Feature or Focused Utility**: A small tool or single feature does not need subdirectories. It separates into flat peer topic files grouped by duty (for example: `overview.md`, `state-machine.md`, `storage-schema.md`, `migration.md`).

### Avoiding Micro-Fragmentation

Do not split text into dozens of tiny files with only one paragraph each. Tiny files increase navigation friction. Group closely related rules into substantial topic files (typically 50 to 300 lines). A dedicated file is earned only when a topic represents a distinct bounded context, serves a separate reader audience, or has an independent update lifecycle.

## Anatomy of a Tidy Document

Every topic document in a Tidy suite follows a clear, predictable structure matching its document type. Choose the schema that fits the document purpose:

- **Technical Specifications & Contracts (Default Schema)**:
  1. *Purpose & Scope*: A short statement (1 to 2 sentences) describing what this topic solves, what this file canonically owns, and what belongs to sibling files.
  2. *Core Concepts & Specifications*: The authoritative technical substance (data models, state flows, schemas, or procedures).
  3. *Invariants & Guarantees*: Non-negotiable boundaries, constraints, validation rules, and error behaviors.
  4. *Relationships & Relative Links*: Direct relative links to canonical parent and sibling topics.
- **Operational Runbooks & How-To Guides**:
  1. *Purpose & Preconditions*: Operational goal, required permissions, tools, and system state before starting.
  2. *Step-by-Step Procedure*: Ordered commands, exact parameters, and expected intermediate outputs.
  3. *Verification & Rollback*: Concrete checks to confirm success and exact steps to revert safely if execution fails.
  4. *Troubleshooting*: Known failure modes, error messages, causes, and corrective actions.
- **Architecture Decision Records (ADRs)**:
  1. *Context & Problem Statement*: Background circumstances, architectural forces, and specific problem to solve.
  2. *Decision & Drivers*: Chosen solution and primary technical reasons for selecting it.
  3. *Invariants & Consequences*: Resulting system guarantees, positive outcomes, trade-offs, and downstream impacts.
  4. *Rejected Alternatives*: Evaluated options that were rejected and the reasons why.
- **Tutorials & Onboarding Guides**:
  1. *Learning Goal & Setup*: What the reader will build or achieve, with environment prerequisites.
  2. *Guided Walkthrough*: Incremental instructions with code snippets and explanations.
  3. *Validation*: Executable test command or check to confirm correct operation.
  4. *Next Steps & Related Topics*: Relative links to deeper reference specifications.
- **Reference Sheets & Data Dictionaries**:
  1. *Domain Scope*: Overview of fields, constants, error codes, or configuration keys owned by this file.
  2. *Definitions & Types*: Authoritative list of keys, data types, default values, and valid ranges.
  3. *Validation Constraints*: Mandatory checks, formatting constraints, and schema rules.
  4. *Cross-References*: Relative links to parent models and consuming services.

Write all prose in CEFR A2 plain technical English. Use short sentences, active voice, and direct words. Remove filler words, excessive adjectives, and speculative ideas.

## Universal Entry Point Contract

The entry point (`README.md`, `index.md`, or root specification) is the front door to a documentation domain. It serves as an orientation map and routing hub, not a dumping ground for raw reference data.

### Four Required Sections of an Entry Point

Every entry point document must contain:

- **1. Purpose & Problem Statement**: A concise explanation of why the system, component, or workflow exists, what problems it solves, and its core mission.
- **2. Scope & Boundaries**: Clear definition of what the domain governs, what lives here, and what is handled elsewhere.
- **3. Domain / Component Map**: A high-level diagram, text topology, or visual overview showing primary components and relationships.
- **4. Navigation Index & Reading Paths**: A complete catalog linking to every topic file with a one-sentence summary, paired with reading sequences for different reader goals (for example: implementer, operator, or reviewer).

### Zero-Duplication Rule

The entry point must never repeat full database schemas, endpoint payloads, or extended background rationales. It provides the high-level landscape and routes the reader to the authoritative topic file through relative links.

## The Universal 6-Step Tidy Lifecycle

When creating, refactoring, or restructuring technical documentation, execute these six steps in order:

### Step 1: Inventory & Map

Scan the target directory and inspect every existing document. Identify all topics, models, schemas, and procedures. Note duplicate tables, conflicting statements, obsolete instructions, and fragmented notes. Build an inventory of all active technical commitments.

### Step 2: Ground in Reality (No Silent Deletion)

Verify documented statements against the live codebase, configuration files, test suites, and environment tools. Mark what is currently implemented versus what is planned or proposed.

*Strict Non-Deletion Invariant*: Never silently delete instructions or specifications that contradict working code. Working code may have bugs, or code may lag behind intended architecture. When documentation and code disagree, flag the contradiction explicitly, mark the text with a clear notice (such as `[DISCREPANCY]`), and ask the user for clarification before deleting or changing requirements.

### Step 3: Derive Domain Boundaries

Identify the domain's natural bounded contexts and seams. Group inventoried topics into logical, cohesive clusters based on responsibility. Determine the canonical home for every concept without imposing arbitrary folder templates.

### Step 3.5: User Alignment Checkpoint

In standalone or interactive workflows, stop before moving or creating files. Present the proposed domain topology to the user: folder paths, file names, canonical owners for shared concepts, and the entry-point navigation layout. Request user approval or feedback before executing file changes. In automated pipelines where an explicit plan was approved upstream, verify against the approved plan before editing.

### Step 4: Refactor & Deduplicate

Write or restructure focused topic documents using the appropriate anatomy schema. Move duplicated schemas, tables, and rules into their single canonical owner. Replace repeated text across secondary files with relative Markdown links pointing to the authoritative source. Maintain 100 percent of existing invariants, contracts, and decisions.

### Step 5: Wire Navigation Hub & Inbound Links

Author or update the entry point document following the Universal Entry Point Contract. Construct two-way links: the entry point links down to each topic document, and every topic document links back to the entry point and sideways to related topics.

*Inbound Reference Audit*: When moving or renaming existing files, scan the repository for references to the old paths (for example using `git grep '<old-path>'` or `check-tidy.py <target-dir> --inbound-root <repo-root>`). Update external links pointing to moved files, or leave a pointer file at the old path so external references do not break.

### Step 6: Verify & Gate

Audit the refactored documentation suite using the automated verification tool:

```bash
python3 <skill-dir>/scripts/check-tidy.py <target-directory> [--inbound-root <path>]
```

The verification tool enforces four quality gates:
- **Relative Link & Anchor Resolution**: Verifies all relative file links resolve to existing files and all internal `#anchors` match valid heading slugs.
- **Line-Breaking Gate**: Confirms every prose paragraph is on a single line (one-paragraph-per-line rule) and verifies no wrapped column text exists.
- **Entry-Point Gate**: Confirms `README.md` or `index.md` exists and contains navigation links to suite topic files.
- **Zero Content Loss & Inbound Gate**: Cross-checks against the Step 1 inventory to guarantee zero lost invariants, and verifies inbound references from the repository root remain valid.

## The Tidy Contract for Any Consumer

Tidy is a foundational primitive with zero upstream dependencies. It does not depend on, invoke, or reference any higher-level workflow, tool, or skill.

Any workflow, agent, or author creating or refactoring documentation adheres to Tidy's contract:

- **One Topic per File**: Writes one file per distinct topic or concept.
- **Sprawl Prevention**: Keeps files bounded and prevents unmanaged growth.
- **Single Source of Truth**: Maintains one canonical source and links to it rather than duplicating.
- **Domain Boundaries**: Organically derives boundaries from the problem domain.
- **Entry-Point Hub**: Provides a clear entry-point navigation hub (`README.md` or `index.md`) without duplicating topic content.
- **Full Preservation**: Preserves 100% of existing invariants, contracts, and decisions without silent deletion.
- **Line-Breaking Discipline**: Follows the self-contained line-breaking rule (one paragraph per line).

## Mandatory Line-Breaking Rule

Every Markdown document authored or refactored under Tidy must follow this self-contained line-breaking rule:

- **One Paragraph Per Line**: Write every prose paragraph as a single continuous line of text. Never hard-wrap paragraphs at arbitrary column widths such as 80 or 100 characters. Modern editors, terminal pagers, and web tools wrap prose dynamically to fit the reader viewport.
- **Semantic Line Breaks**: Reserve newlines solely for structural Markdown elements: starting a new paragraph, a list item, a heading, a table row, or a fenced code block.
- **Automated Verification**: Before completing any documentation task, run the automated checker to verify line breaks and links:

```bash
python3 <skill-dir>/scripts/check-tidy.py <target-directory>
```
