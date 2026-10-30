# Legacy Migration

This reference owns the Migrate mode: the working directory, the session scope, the work files, the writing boundary, and the session protocol. It inherits the PDS contract from [pds-anatomy.md](pds-anatomy.md) and the storage rules from [sync-and-restore.md](sync-and-restore.md).

## When Migrate applies

Use Migrate when the legacy set is too large for one session, when I say migrate or continue the migration, or when I point at a legacy folder for a migration. A small legacy set still uses Extract.

One session has one scope. The scope is a small set of work units, never the whole legacy set.

## Where the files live

| Path | Holds |
|---|---|
| `<repo>/agent-files/blueprint-migration/` | The default working directory: one work file per unit, plus `next.json`. |
| `blueprint.json`, field `migration_dir` | The working directory I named, relative to the repo root. The default applies when the field is absent. |
| `~/.agentmemoir/<owner>/<repo>/migration-consumed/` | Consumed `next.json` files, one per session. |
| `<repo>/PHILOSOPHY.md` | The product philosophy, written only for a philosophy work unit. |

The legacy root comes from my request at each session. Ask for it when it is missing; never guess. Legacy source documents are never moved, edited, or deleted. The working directory and the consumed folder are outside the suite, so the mirror never copies them.

## The scope file

`next.json` defines the session scope. It holds four keys:

```json
{
  "session_scope": "migrate-billing-context",
  "status": "ready",
  "deliverables": [
    {
      "name": "Billing context",
      "sources": ["legacy/billing.md"],
      "targets": ["domains/billing.md"],
      "description": "Migrate the billing bounded context."
    }
  ],
  "invariants_to_preserve": ["A settled rule survives every migration step."]
}
```

| Key | Rule |
|---|---|
| `session_scope` | A short slug naming the session's work. |
| `status` | A short state I can read, for example `ready` or `in_progress`. |
| `deliverables` | One entry per work unit in scope. Each entry carries `name`, `sources`, `targets`, and `description`. |
| `invariants_to_preserve` | The rules that must survive this session. |

Extra keys are allowed. The four keys above are required.

- A file whose shape is not migration scope is not a scope. When it names build, implementation, delivery, commands, or code targets, stop and ask.
- Move the consumed file to `migration-consumed/<YYYY-MM-DD>-next.json` before starting. `python3 <blueprint-skill-folder>/scripts/blueprint.py migrate rollover --work <work-dir>` automates archiving the consumed scope and carrying forward pending deliverables with numeric suffix collision guards.
- When no file exists, run `python3 <blueprint-skill-folder>/scripts/blueprint.py migrate init --legacy <legacy-dir> --work <work-dir>` to scaffold unit work files and an initial `next.json`, then present it to me for approval.

## Work units

A work unit is one bounded piece of the specification:

- one bounded context, written to `domains/<context>.md`;
- the ubiquitous language, written to `glossary.md` and the domain files that own the terms;
- the context map and navigation, written to the suite entry point (`README.md`, or `index.md` when kept);
- the decision set, written to `decisions/`;
- the product philosophy, written to the repo-root `PHILOSOPHY.md`.

A unit outside this list is not taken into scope. Name it and leave it to the skill that owns it.

## Work files

Keep one work file per unit in the working directory, named `<unit>.json`. The unit slug matches the file name.

| Key | Rule |
|---|---|
| `unit` | The unit slug. It matches the file name. |
| `status` | `pending`, `in_progress`, `migrated`, `verified`, or `blocked`. |
| `sources` | Every legacy file read for this unit. |
| `targets` | Every file written or changed for this unit. |
| `invariants` | The domain rules, constraints, terms, and commitments preserved. |
| `verification` | The checks run and their result. |

Extra keys are allowed; never drop a required key.

- `pending`: not started.
- `in_progress`: started, not finished.
- `migrated`: every target exists and the final tidy check passes. Keep the unit `in_progress` until that check passes.
- `verified`: `migrated`, plus the coverage and invariant checks recorded in `verification`.
- `blocked`: stopped by an unanswered decision or a missing source. The file records the reason.

## Progress truth

The work file records coverage of the legacy sources. The PDS `Status:` line records readiness of the context. They are different records with different jobs, and both are kept.

When they disagree, report the mismatch. Never treat a `draft` context as settled. Never redo a unit whose work file says `migrated` or `verified` and whose targets exist.

## Writing boundary

Migrate writes the PDS core — the suite entry point, `glossary.md`, `domains/`, and `decisions/` — and the repo-root `PHILOSOPHY.md` for a philosophy unit. It never authors another file.

For a philosophy unit, preserve every belief, hard line, and precedence rule. When the legacy source and the existing `PHILOSOPHY.md` conflict, stop and ask. `PHILOSOPHY.md` is not part of the suite mirror.

## The session protocol

1. Follow the tidy gate, the settings step, the notice, and the restore step in [sync-and-restore.md](sync-and-restore.md).
2. Resolve the legacy root and the working directory.
3. Read `next.json`, validate it, archive it via `blueprint.py migrate rollover`, or scaffold with `blueprint.py migrate init`.
4. Read the suite and work files via `python3 <blueprint-skill-folder>/scripts/blueprint.py migrate status --work <work-dir>`. Report the units already `migrated` or `verified`.
5. For each unit in scope, read every source, distill, and settle every open decision one message at a time. Write the targets and update the work file.
6. Write a decision record for every decision the legacy sources settle.
7. Stop at the scope boundary. Carry every unfinished unit into the new file.
8. Write the new `next.json` for the next session via `blueprint.py migrate rollover`.
9. Run `python3 <blueprint-skill-folder>/scripts/blueprint.py generate <suite-folder>`, run tidy's checker, then run `blueprint.py sync`.

## Effort and carry-over

The scope is a contract. Do not start a unit outside it, even when time remains.

When a unit is unfinished at the end, record why and carry it into the new `next.json` with `in_progress` or `blocked`. Always write the new file. When the scope is complete, propose the next reasonable batch.

## Grilling and records

Migrate follows the same grilling protocol as the other modes: one decision per message, prism for costly choices, and a plain clarification when one reading is clearly right.

Migrate writes decision records for decisions the legacy sources settle. Amend writes records for amendments. A partly finished unit keeps its `Open:` points open; never fill one with a guess.

## Relationships

- [../SKILL.md](../SKILL.md) holds the four modes and the session order.
- [pds-anatomy.md](pds-anatomy.md) defines every target file and the decision record schema.
- [sync-and-restore.md](sync-and-restore.md) defines the settings, restore, and mirror rules that every Migrate session follows.
