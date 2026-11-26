---
name: design-lock
description: >-
  Stops UI work from drifting away from an approved design, on any platform (web, Android, iOS, Flutter, desktop). Use it whenever a screen, page,
  component, layout or style is built, rebuilt, restyled, fixed or "made to match" from an approved mock, frame, Figma export, screenshot or HTML
  design, whenever UI files (CSS, Compose, SwiftUI, widgets, templates) are edited in a repo that has a .design-lock.json, and whenever a repo needs
  a design check adopted. Done means the design gate is green, not that tests are green.
category: engineering
title: Design Lock
summary: >-
  Compares every element of the built UI with its approved frame and fails on any constant that differs.
  It checks position, size, container, font and colour per theme, and hooks plus a required CI check enforce it instead of anyone remembering.
say: "Build this screen from the approved frame and prove it matches."
license: MIT
metadata:
  author: agentmemoir
  version: "2.0"
---

# Design Lock

An approved design is a contract. "Looks close" and "tests are green" are not evidence; screenshot goldens only compare the app with its own past. The only evidence is the gate comparing the app with the approved frame.

## The rules

1. **Never violate an approved design.** The one exception is a change the owner explicitly requested because something new was found. It is recorded in `design/changes.json` (reason, requestedBy), done by the owner or in a session the owner launched with `DESIGN_LOCK_CHANGE`, and labelled in CI. You never decide it yourself.
2. **Constants must match the frame; variables may differ.**
   - Constants: layout (position, size, spacing), containers (fill, border, radius, shadow, opacity), fonts (family, size, weight, spacing, line height), colours, in every theme.
   - Variables: data-driven content only (a name, symbol, price, change, logo or chart image). The slot is still constant: box (minus the axes listed in `flex`), font, and for an image its shape. The frame spec marks variable regions; nothing else may be treated as variable.
   - A container around a variable logo is a constant. Variable is never a blanket mask.
3. **Done = the gate is green.** Not "tests pass", not a screenshot.

## Procedure (SOP)

1. **Frame spec.** Open `.design-lock.json`; every screen you touch maps to a frame image and spec. No frame means stop and ask the owner. Never invent one.
2. **Element table before code.** One row per frame element: `element | role | constant or variable | property | frame value`. Values come from the frame spec, never from eyeballing the image.
3. **Build.** Each element carries its table id (`data-dl-id`, a test tag or accessibility id), so measurements can name it.
4. **Gate.** Run `python3 tools/design-lock/designlock.py gate` (or the `gate` command of the config). It captures the real rendering, compares, and prints failing elements. Fix the app and repeat. Do not stop at "close".
5. **Report the table.** Add `app value` and `pass` columns for every element, and paste the gate's per-element report. A missing row is a failed check.
6. **Never re-record goldens or snapshots over a failing gate.** Re-record only once it is green, and say so.

## Never do these

- Edit frames, frame images, the config, tolerances, exceptions, the ledger or the baseline to make a screen pass. The hooks deny it and CI rejects it.
- Add an exception or baseline entry on your own. Each names one element and property and pins the accepted app `value`: a different (worse) value still fails. Exceptions need a reason; baseline entries need an issue link and only ever shrink.
- Mark something variable, ignore a region, or loosen a tolerance to get green.

If the frame itself seems wrong, stop and tell the owner what you found.

## Reviewer and coordinator

Before merging, open the gate's `report.md`. Every row of every touched screen: no FAIL, every exception and baseline entry has its reason or issue, no new entries, nothing changed under the locked paths. A summary-only report, or fewer screens than were touched, is rejected.

## What the hooks do, and what they do not

- **Stop / SubagentStop:** if you edited UI files (or the work tree has UI changes, for the main session) the gate runs and blocks the stop while it fails. A read-only subagent is never blocked. After 3 blocks the stop is released with a warning and CI is the backstop. A tree already gated (green or red) is not captured again.
- **PreToolUse:** writes to locked design files (Edit, Write, shell commands, every MCP tool that is not a plain read) are denied. It looks at the paths a command names, not at the directory it runs in.
- Both are silent no-ops in a repo without `.design-lock.json`.
- **The local hooks are advisory guardrails.** Anything that edits settings (`disableAllHooks`, a hook command, `DESIGN_LOCK_CHANGE` in `env`) can switch them off, and they deliberately do not guard themselves. The hard guarantee is the required CI check `design-ok` with branch protection or a ruleset the agent cannot change. The optional hard local guarantee is to install the hooks in managed settings with `allowManagedHooksOnly`. A repo is not protected until `design-ok` is a required check.

## Adopt in a new project (minutes)

1. `python3 <skill>/scripts/designlock.py init --platform web|android|ios|flutter|desktop|command --dir <repo>` scaffolds the config, tools, a capture recipe and the workflow. A global `.*` gitignore hides `.design-lock.json`: `git add -f` it.
2. Owner: put each approved frame image and spec under `design/frames/`, list them under `screens`, and edit `tools/design-lock/capture.sh`.
   - Image: export it from the design, or `designlock.py extract-web --file mock.html --screenshot design/frames/home.dark.png ...`.
   - Spec from an HTML mock: write a map `{"root": ".screen", "elements": [{"id": "title", "selector": ".title", "role": "text"}, {"id": "logo", "selector": ".logo", "role": "image", "variable": true}, {"id": "price", "selector": ".price", "variable": true, "flex": ["w"]}], "ignore": [{"selector": ".ad", "reason": "third-party slot"}]}` and run `designlock.py extract-web --file mock.html --map map.json --theme dark --kind spec --name home.dark --out design/frames/home.dark.spec.json`. Other sources: write the same JSON.
   - Tag the app's elements with the same ids: `data-dl-id`, plus `data-dl-role="image"` for an image-like slot with no `<img>` (else it is read as a container), `data-dl-variable` (optionally `="w,color"` flex axes). Capture with the same `--root` selector the frame was extracted with, and keep any capture map under a locked path (the app may not ignore more than the frame ignores).
   - `ui` globs are the trigger and cache key of the Stop hook: they must cover everything that changes rendering (styles, theme files, build config, assets), or a change there never runs the gate.
3. Run the gate until green (known failures go to `design/baseline.json` with issue links).
4. Commit, then make the `design-ok` check required and keep the `design:approved-change` label owner-only.

Full schema, adapters, tolerances and the bypass table: `README.md`; per-platform recipes: `recipes/README.md`.
