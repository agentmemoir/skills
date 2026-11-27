---
name: design-lock
description: >-
  Stops UI work from drifting away from an approved design, on any platform (web, Android, iOS, Flutter, desktop). Use it whenever I ask you to
  build, rebuild, restyle, fix, or "make match" a screen, page, component, layout, or style from an approved mock, frame, Figma export,
  screenshot, or HTML design, whenever you edit UI files (CSS, Compose, SwiftUI, widgets, templates) in a repo that has a .design-lock.json,
  and whenever I ask you to adopt a design check in a repo. Done means the design gate is green, not that tests are green.
category: engineering
title: Design Lock
summary: >-
  Compares every element of the built UI with its approved frame and fails on any constant that differs.
  It checks position, size, container, font, and colour per theme. Hooks and a required CI check enforce it, so nobody has to remember it.
say: "Build this screen from the approved frame and prove it matches."
license: MIT
metadata:
  author: agentmemoir
  version: "2.0"
---

# Design Lock

An approved design is a contract. "Looks close" and "tests are green" are not evidence, and screenshot goldens only compare the app with its own past. The only evidence is the gate comparing the app with the approved frame.

## Rules

1. **Never violate an approved design.** The one exception is a change I ask for because something new turned up. It is recorded in `design/changes.json` (`reason`, `requestedBy`), made by me or in a session I start with `DESIGN_LOCK_CHANGE`, and labelled `design:approved-change` in CI. Never decide a change yourself.
2. **Constants must match the frame. Variables may differ.**
   - Constants: layout (position, size, spacing), containers (fill, border, radius, shadow, opacity), fonts (family, size, weight, spacing, line height), and colours, in every theme.
   - Variables: data-driven content only (a name, symbol, price, change, logo, or chart image). Its slot is still constant: the box (minus the axes in `flex`), the font, and for an image its shape. Only the frame spec marks a region variable.
   - A container around a variable logo is a constant. Variable is never a blanket mask.
3. **Done means the gate is green.** Passing tests and a screenshot do not count.

## Procedure

1. **Find the frame.** Every screen you touch maps to a frame image and spec in `.design-lock.json`. If there is none, stop and ask me. Never invent one.
2. **Write the element table before code.** One row per frame element: `element | role | constant or variable | property | frame value`. Take values from the spec, never from eyeballing the image.
3. **Build.** Tag each element with its table id (`data-dl-id`, a test tag, or an accessibility id) so measurements can name it.
4. **Run the gate:** `python3 tools/design-lock/designlock.py gate` (or the config's `gate` command). It captures the real rendering, compares it, and prints the failing elements. Fix the app and repeat. Do not stop at "close".
5. **Report the table** with `app value` and `pass` columns for every element, plus the gate's per-element report. A missing row is a failed check.
6. **Re-record goldens and snapshots only after the gate is green**, and say so.

## Never

- Edit frames, frame images, the config, tolerances, exceptions, the ledger, or the baseline to make a screen pass. The hooks deny it and CI rejects it.
- Add an exception or a baseline entry yourself. Each names one element and property and pins the accepted app `value`, so a worse value still fails. An exception needs a reason. A baseline entry needs an issue link and only ever shrinks.
- Mark something variable, ignore a region, or loosen a tolerance to get green.

If the frame itself looks wrong, stop and tell me what you found.

## Reviewing

Before merging, open the gate's `report.md`. Check every row of every touched screen: no FAIL, a reason or issue on every exception and baseline entry, no new entries, nothing changed under the locked paths. Reject a summary-only report or one that covers fewer screens than were touched.

## Hooks

- **Stop and SubagentStop** run the gate when you edited UI files and block the stop while it fails. After 3 blocks the stop is released with a warning and CI is the backstop.
- **PreToolUse** denies writes to locked design files through Edit, Write, shell commands, and MCP tools.
- The local hooks are guardrails, not protection: editing settings switches them off. The guarantee is the required CI check `design-ok`.

## Resources

- Read [references/adoption.md](references/adoption.md) when I ask you to adopt a design check in a repo. It covers `designlock.py init` and the commands.
- Read [references/config.md](references/config.md) before you touch `.design-lock.json`, screens, or tolerances.
- Read [references/spec-schema.md](references/spec-schema.md) when you read or write a frame spec or a measured file.
- Read [references/capture-recipes.md](references/capture-recipes.md) when you write a capture command for a platform.
- Read [references/hooks.md](references/hooks.md) when a hook blocks you, or when I ask how the hooks are registered.
- Read [references/ci.md](references/ci.md) when I ask about the CI workflow, the label, or branch protection.
- Run `scripts/designlock.py` for `gate`, `compare`, `extract-web`, and `init`. Run `scripts/self-check.py --skip-web` after you change a script.
