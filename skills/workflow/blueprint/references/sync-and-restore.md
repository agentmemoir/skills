# Sync and Restore

This reference owns four subjects: the suite's settings file, what a session reads at its start, how a missing central suite is restored from a clone, and how the local mirror is written at the end. The PDS itself is defined in [pds-anatomy.md](pds-anatomy.md).

## The settings file

Each suite holds one visible `blueprint.json` at its root. It is settings, not a PDS topic: no link from the entry point, no product behavior, and no technology choice. One file exists per product suite.

```json
{
  "product": "demo",
  "entry_file": "README.md",
  "sync": "on",
  "local_dir": "product",
  "custom": "",
  "stale_local": "",
  "migration_dir": "agent-files/blueprint-migration",
  "updated": "2026-10-30"
}
```

| Field | Rule |
|---|---|
| `product` | The product slug. It must match the suite folder name. |
| `entry_file` | The suite entry point: `README.md` (the default) or `index.md` (a legacy name kept by choice). |
| `sync` | `on`, `off`, or `custom`. |
| `local_dir` | Relative to the repo root. Required when `sync` is `on` or `custom`; ignored when `off`. |
| `custom` | The instruction I gave, word for word. Required when `sync` is `custom`; empty otherwise. |
| `stale_local` | `keep` after I chose to keep a stale local copy while sync is off; empty otherwise. Reset when the sync setting changes. |
| `migration_dir` | Relative to the repo root. Defaults to `agent-files/blueprint-migration`. |
| `updated` | The date of the last settings change, in `YYYY-MM-DD` form. |

- The central suite is the source of truth. The local folder is a mirror. A hand edit to a local `blueprint.json` has no authority, because central wins at the next session end.
- Paths are relative to the repo root. Refuse an absolute path, a path that escapes the repo with `..`, and the repo root itself; ask for a relative path inside the repo.
- When the file is absent, ask the two configuration questions. When it is unreadable, has no `product`, or lacks a required field — `sync`, `updated`, and `local_dir` or `custom` as the sync value needs — stop and ask; never guess a setting and never treat a broken file as absent.
- `entry_file` names the suite entry point. New suites use `README.md`. When a suite has only `index.md`, ask once whether to rename it: on Yes, rename it and set `entry_file` to `README.md`; on No, set `entry_file` to `index.md`. When both files exist, ask which one is the entry point, and never delete the other without my consent. When the recorded file is absent, use the other name and ask once whether to update the record.

## Session start

1. Load the `tidy` skill per the gate in [../SKILL.md](../SKILL.md).
2. Resolve `<owner>`, `<repo>`, and `<product>`. When the central suite has no entry point (`README.md`, or a legacy `index.md`) — the folder is absent or holds only settings — find a local suite and restore it before reading any setting.
3. Read `blueprint.json`. When it is absent, ask the configuration questions below and write the file at once. Create the suite folder when it does not exist. When sync is on and the mirror target is safe, mirror the settings file immediately.
4. State one line: `Blueprints: <central path> · Mirror: <local path or none> (<sync state>)`.
5. When sync is off and a local copy exists from before, ask once whether to delete it. When I say keep, record `stale_local: keep` in the settings file, so the question is not asked again until the sync setting changes.

Ask the configuration questions in one message:

- **Sync the blueprints to a local project directory at the end of each session?** Yes, No, or Custom. Yes means mirror at every session end. No means keep the suite central-only. Custom means I describe the behavior, and you store my words and follow them.
- **Where should the local copy live?** `./blueprints/<product>`, `./products/<product>`, or Custom. Ask this only when the first answer is Yes or Custom. Custom here is a path: take it as given when it is relative, refuse an absolute path and ask for a relative one, restate it in one line, then follow it.

A custom answer that matches no listed option is still the instruction. Restate what you will do in one line, then follow it.

## Finding a local suite

- Prefer the recorded `local_dir` when that folder exists and is a suite.
- When there is no record, or the recorded folder does not exist, scan the repo for `blueprint.json`. A file counts only when it parses and holds `product` and `sync`. Skip `.git`, hidden directories, dependency folders, build output, and the legacy root.
- When none is found, scan for a folder that holds an entry point (`README.md` or `index.md`), `glossary.md`, and a `domains/` folder together.
- A candidate must match `<product>`, by folder name or by its `product` field. A suite for another product is never restored into this product's central path.
- When several candidates remain, ask me to pick one. Never pick for me.
- When the record and the found folder disagree, stop and ask.
- When no candidate exists, there is no local suite. Continue with the configuration questions.

A folder is a suite when it holds a `blueprint.json` that parses with `product` and `sync`, or when it holds an entry point (`README.md` or `index.md`), `glossary.md`, and a `domains/` folder together.

## Restore

- Restore only when the central suite has no entry point. A central folder with `README.md` or `index.md` counts as present, even when it is partial; central wins.
- Run `python3 <blueprint-skill-folder>/scripts/blueprint.py restore <product> [--owner <owner> --repo <repo>]` to find the local candidate, restore all suite files, preserve central settings, and report the copied count.
- Never restore over a central entry point, and never merge file by file.
- "Synchronized elsewhere" means another computer. Do not search other product slugs, other owners, or other repos.
- After a restore, read the restored `blueprint.json`. When the local suite had none, ask the two configuration questions.

## The end-of-session mirror

- The mirror runs after the mode's final tidy check passes. When the check failed and cannot be fixed, report it and do not mirror.
- Run `python3 <blueprint-skill-folder>/scripts/blueprint.py sync <suite-folder>` to mirror the whole suite, prune removed local files, and report the new, overwritten, and deleted counts.
- The mirror creates `local_dir` when it is absent.
- The first mirror stops and asks when `local_dir` exists, is not empty, and is not a suite (see *Finding a local suite*).
- When the mirror fails, report it and leave the central suite untouched. Do not roll back central.
- The repo-root `PHILOSOPHY.md` is not part of the suite. The mirror never copies it.
- A settings-only change is the one exception to the tidy gate. It mirrors that file immediately, because it is not PDS content.

## Custom behaviour

- The words are stored verbatim in `custom` and followed at every session end.
- Custom may change timing, add steps, or name exclusions. It never changes two rules: the central suite stays canonical, and the local copy stays a copy.
- When an instruction conflicts with either rule, apply the compatible part, stop, and ask about the conflict.

## Changing the settings

- When I ask to change the sync settings, ask the two questions again, update `blueprint.json` in the central suite, then mirror that file.
- When the new answer is No, ask once whether to delete the existing local copy, then record the answer in `stale_local`.
- Clear `stale_local` whenever `sync` changes.
- Never change a setting in silence.

## Failure modes

- Invalid JSON, a missing required field, or a `product` that does not match the folder: stop and ask. Do not re-ask the configuration questions as if the file were absent.
- Unwritable central path: report it, keep working in the conversation, and do not claim the settings were saved.
- Unwritable mirror: report it, leave central intact, and end the session.
- No `git remote`: ask for the owner and repo and use my answers verbatim.

## Relationships

- [../SKILL.md](../SKILL.md) holds the session order and the four modes.
- [pds-anatomy.md](pds-anatomy.md) defines the suite layout and the settings file's place in it.
- [legacy-migration.md](legacy-migration.md) defines Migrate, whose sessions use this file too.
