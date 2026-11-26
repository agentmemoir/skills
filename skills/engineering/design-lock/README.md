# design-lock

Stops AI coding agents from shipping UI that deviates from an approved design. Platform- and project-agnostic: one JSON schema, one compare engine (Python 3 stdlib), thin per-platform capture recipes, Claude Code hooks, and a CI workflow template.

Why it exists: agents rebuilt screens from approved mocks, the result looked close, tests were green, and the owner kept finding wrong fills, 0.5 sp font errors and 1-1.5 dp offsets. Goldens compare the app to its own past output, so they protect a wrong build. Memory notes and CLAUDE.md rules did not help. This enforces the rule with tooling, so no model has to remember it.

## The model

- An approved frame has **constants** (layout, containers, fonts, colours, in every theme) and **variables** (data-driven content). The engine fails on any constant that differs by more than the declared tolerance, on a missing or unlisted element, and on an invalid exception. For a variable it checks the slot (box minus its `flex` axes, font, and for an image its shape), never the content. A container around a variable is its own constant element; a container cannot be marked variable.
- An approved design is never violated. The one way it changes is an explicit owner request because something new was found, recorded in the **change ledger** (`design/changes.json`: reason, requestedBy). CI requires the ledger entry and the `design:approved-change` label together.
- **SOP:** frame spec, per-element table (frame vs implementation), gate green, then done. Done is the gate, not the tests.

## Layout

- [`SKILL.md`](SKILL.md): the playbook agents follow
- [`scripts/designlock.py`](scripts/designlock.py): `gate | compare | extract-web | init`
- [`scripts/dlcore.py`](scripts/dlcore.py): config lookup, globs, protected paths, baseline and ledger diffs, change detection
- [`scripts/hook.py`](scripts/hook.py): Claude Code hooks, `stop` (Stop, SubagentStop) and `pretool` (PreToolUse)
- [`scripts/guard.py`](scripts/guard.py): CI guard
- [`templates/`](templates/design-lock.yml): capture recipes (web, android, ios, flutter, command) and the GitHub Actions workflow
- [`recipes/README.md`](recipes/README.md): how each platform produces its measurement; structure-mode adapter sketches
- [`tests/run_tests.py`](tests/run_tests.py): the whole chain on sample projects (`--skip-web` when Playwright is missing)

## Adopt in minutes

1. `python3 <skill>/scripts/designlock.py init --platform <web|android|ios|flutter|desktop|command> --dir <repo> --screen home`. It writes `.design-lock.json`, `design/{baseline,changes}.json`, `tools/design-lock/*` (a vendored copy of the engine and guard), a capture recipe and `.github/workflows/design-lock.yml`. If a global gitignore hides dotfiles, `git add -f .design-lock.json`.
2. **Owner:** per screen and theme, put the approved frame image (`design/frames/<screen>.png`) and spec (`<screen>.spec.json`) in place. For an HTML mock: write a map file (`{"root": ".screen", "elements": [{"id": "title", "selector": ".title"}, {"id": "price", "selector": ".price", "variable": true, "flex": ["w"]}], "ignore": [{"selector": ".ad", "reason": "..."}]}`) and run `designlock.py extract-web --file mock.html --map map.json --theme dark --kind spec --name home.dark --out design/frames/home.dark.spec.json`. For Figma or other sources, write the same JSON from their export. List each screen under `screens` with its `sources` globs.
3. Edit `tools/design-lock/capture.sh` so it renders every registered screen into its `measured` path (see `recipes/README.md`).
4. Run `python3 tools/design-lock/designlock.py gate`. Fix the app, or record a known failure in `design/baseline.json` (`{element, property, value, issue}`; the list may only shrink) or a behaviour exception in the screen's `exceptions` (`{element, property, value, reason}`). `value` pins the accepted app value: any other value, a worse one included, still fails.
5. Commit. In the repo settings make the check `design-ok` required, and keep the label `design:approved-change` owner-only.
6. Hooks need nothing per project: they are registered once in `~/.claude/settings.json` and act in any repo that has `.design-lock.json`.

## `.design-lock.json`

```json
{
  "version": 1,
  "platform": "web",
  "ui": ["src/**", "app/**"],
  "capture": "sh tools/design-lock/capture.sh",
  "gate": "optional override of the whole gate command (default: designlock.py gate)",
  "gateTimeoutSec": 600,
  "tolerance": {"box": 0.5},
  "locked": ["tools/design-lock/**", ".github/workflows/design-lock.yml"],
  "baseline": "design/baseline.json",
  "ledger": "design/changes.json",
  "goldens": ["**/__snapshots__/**", "**/*.golden.png"],
  "forbidCommands": ["recordGoldens", "updateSnapshots"],
  "screenFiles": ["src/screens/**"],
  "screens": {
    "home.dark": {
      "frame": "design/frames/home.dark.spec.json",
      "image": "design/frames/home.dark.png",
      "measured": "build/design-lock/measured/home.dark.json",
      "mode": "structure",
      "exceptions": [{"element": "title", "property": "box.x", "value": 24, "reason": "RTL mirror"}],
      "sources": ["src/screens/Home.tsx"]
    }
  }
}
```

- `screens.*`: `frame` (spec), `image` (the approved picture), `measured` (what capture writes), `mode` `structure` (default: element table) or `pixel` (a PNG compared with the frame image, the spec's variable regions masked), `exceptions`, `allowExtra`, `sources`. Unknown keys are errors.
- `screenFiles` + `sources`: every UI file matching `screenFiles` must belong to a screen's `sources`, so a new screen cannot ship without a frame.
- **Protected paths** (the owner changes them; hooks deny agents, CI demands label + ledger entry): `.design-lock.json`, every screen's frame and image, the ledger, and the `locked` globs. The baseline is shrink-only: removing fixed entries is allowed, adding or editing is not.
- `gate` runs `capture` (deleting every `measured` file first, so a stale file can never pass), then compares each screen. Exit 0 pass, 1 violation, 2 input error.

## The spec schema (`design-lock/1`)

```json
{
  "schema": "design-lock/1", "kind": "spec", "frame": "home.dark", "theme": "dark",
  "viewport": {"width": 390, "height": 844},
  "renderer": {"browser": "120", "platform": "darwin"},
  "unmapped": [], "ignored": [{"selector": ".ad", "reason": "third-party slot"}],
  "elements": [{
    "id": "price", "role": "text", "variable": true, "flex": ["w"],
    "box": {"x": 236, "y": 156, "w": 122, "h": 20},
    "style": {
      "fill": [r, g, b, a] | null,
      "border": null | {"width": 1, "color": [r, g, b, a], "style": "solid"} | {"top": {...}|null, "right": ..., "bottom": ..., "left": ...},
      "radius": [tl, tr, br, bl], "shadow": "css-like string" | null,
      "opacity": 1, "backgroundImage": null, "filter": null, "clipPath": null, "outline": null,
      "font": {"family": "Arial", "size": 16, "weight": 600, "letterSpacing": 0, "lineHeight": 20, "style": "normal", "align": "right", "transform": "none", "decoration": "none"},
      "color": [r, g, b, a], "text": "constants only; omitted for variables"
    }
  }]
}
```

- `role`: `container` (fill, border, radius, shadow), `text`, `image`. Units are logical px/dp/pt, colours 0-255 with alpha 0-1, `box` relative to the frame root.
- **Every constant a role needs must be stated** (`null` means none): a spec that omits `fill`, `shadow`, a core font key, ... is invalid and fails the gate, because absence must never mean "no constraint". `opacity`, `backgroundImage`, `filter`, `clipPath`, `outline` default to none when absent, so an app cannot add them unnoticed. `font.style/align/transform/decoration` are compared when the frame states them.
- `variable: true` is for `text` and `image` only. `flex` lists what content may change: `x y w h color fill` (a right-aligned price in a content-sized box flexes `w`; a green or red change flexes `color`).
- `ignored` lists regions the frame deliberately skips; the app's capture may ignore none that the frame does not list (keep any capture map under a locked path).
- `unmapped` (web) lists painted elements nobody named, including painted pseudo-elements and gradients; a non-empty list fails the comparison. `ignored` regions need a reason.
- Ids are the join key; a duplicate id fails, an app element the frame lacks fails, a frame element the app lacks fails.

## Tolerances

Defaults are tighter than the errors owners complain about: `box` 0.5, `fontSize` 0.1, `lineHeight` 0.1, `letterSpacing` 0.1, `radius` 0.25, `borderWidth` 0.1, `color` 2 per channel, `alpha` 0.02. Pixel mode: `pixelRatio` 0.001 (share of differing pixels) AND `pixelBlock` 4 (differing pixels allowed in any 16x16 block), so scattered anti-aliasing noise passes but a whole wrong icon, badge or word does not. Override in `.design-lock.json` only (protected). Unknown keys and non-numbers are errors.

## Commands

```
designlock.py gate [--root .] [--out build/design-lock] [--no-capture]
designlock.py compare frame.spec.json app.measured.json [--tolerance 0.5 | box=0.5,fontSize=0.1] [--md out.md] [--json out.json] [--only-fail] [--allow-extra]
designlock.py extract-web (--file F | --url U) --out O [--kind spec|measured] [--map map.json] [--root SELECTOR] [--viewport 390x844] [--theme light|dark] [--name ID] [--screenshot png]
designlock.py init --platform P [--dir .] [--screen home]
```

`gate` writes `report.md` (every element, every property, frame value, app value, result; links the frame image) and `report.json`.

## `ui` is the trigger and cache key

The Stop hook gates only when UI files changed, and caches the result (green or red) by a hash of every file matching `ui`, the protected paths and the baseline. So `ui` must cover everything that changes rendering: styles, theme and token files, build configuration (tailwind, gradle), assets, dependency manifests. A change outside `ui` never runs the local gate (CI still runs it on every PR).

## Hooks (Claude Code)

Registered once, user-level, in `~/.claude/settings.json`: `Stop`, `SubagentStop` -> `python3 ~/.claude/skills/design-lock/scripts/hook.py stop` (timeout 900); `PreToolUse` with matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|mcp__.*` -> `... hook.py pretool` (timeout 10).

- Every hook is a silent no-op, with no subprocess, in a tree without `.design-lock.json`.
- **PreToolUse** denies Edit/Write/MultiEdit/NotebookEdit, shell writes and MCP tools that target a protected path. Every `mcp__*` tool is checked unless its name starts with a read verb (read, get, list, find, search, view, show, stat, query, ...); tools whose name looks like a shell (shell, exec, command, run, bash, script) have their `command`/`cmd` argument parsed like a Bash command. Shell targets are resolved wherever the command runs, so a command in another directory or worktree is checked too. Paths match case-insensitively on case-insensitive volumes (macOS, Windows defaults). `git restore .` and `git checkout -- .` are allowed (they restore the approved state); naming a locked file is not. The shell check parses commands (redirects, `rm`, `mv`, `cp`, `tee`, `sed -i`, `perl -pi`, `awk -i inplace`, `dd of=`, `git checkout/restore/apply`, `cd x && ...`, `bash -c`, inline python/node that opens a path for writing); reading a protected file is never denied. It also records UI edits for the Stop hook.
- **Stop** (main session) gates when it edited UI files or the work tree has uncommitted UI changes; **SubagentStop** only when that subagent edited UI files, so research agents are never blocked. A tree already proven green (content hash) is not gated again; concurrent gates are serialised with a lock; the gate runs in its own process group and is killed whole on timeout. After `DESIGN_LOCK_MAX_BLOCKS` (3) consecutive blocks the stop is released with a loud message; CI is the backstop.
- The owner starts a session with `DESIGN_LOCK_CHANGE="<why>"` when the design must change; the hook then lets the locked files be edited. CI still requires the label and the ledger entry.
- **The local hooks are advisory guardrails.** The hooks, the skill scripts and the settings files are deliberately not guarded: an agent that edits settings (`disableAllHooks`, the hook command, `DESIGN_LOCK_CHANGE` in `env`) switches them off. The hard guarantee is the required CI check below; the optional hard local guarantee is installing the hooks in managed settings with `allowManagedHooksOnly`.
- The Stop hook keys on the directory the session runs in: edits made to another project from here are enforced by that project's CI, and the Stop of a session started there. A failing result is cached by tree hash and replayed, and the hook keeps within a 880 s budget (waiting agents find the result cached; a gate that outlives the budget is killed with its capture).

## CI (the guarantee)

`templates/design-lock.yml` runs on `pull_request_target` (types opened, synchronize, reopened, labeled, unlabeled), `merge_group` and pushes to main; only the `design:approved-change` label reruns it, other labels run nothing and cannot cancel a real run. Actions are pinned to commit SHAs. GitHub runs the workflow and the tooling from the BASE branch; the pull request is checked out into `pr/` and measured.

**Be plain about PR code:** the capture command builds and runs the PR's own code (npm scripts, gradle, tests), so PR code does execute on the runner, with a read-only token and no secrets. Base tooling then fails the gate if capture modified a frame, the config, the baseline or a locked file, and it re-validates the measured output itself, but a PR can still misreport its own rendering inside the measured file. The capture script is a locked path (changing it needs label and ledger entry); review it and the report. `gate` runs `base/tools/design-lock/designlock.py gate --root pr`; `guard` runs `base/.../guard.py`. A push drops the `design:approved-change` label, so an approval covers one commit. `design-ok` is the single required check and fails when either job did not succeed (skipped counts as failure).

The guard rejects: a change to any protected path or an added baseline entry without BOTH the label and a new ledger entry; updated goldens/snapshots while the design check did not pass (a label never excuses that). The first adoption PR (no config on the base) is left to the owner.

Remaining trust: the owner must keep branch protection, the label permission and the required check out of the agent's reach (a separate agent GitHub identity). For a hard local guarantee, put the hooks in managed settings.

## What can still go wrong

| Gap | Mitigation |
| :- | :- |
| Shell write the heuristic misses (paths built at run time, a script that writes) | CI guard sees the diff |
| Agent runner that ignores Claude Code hooks | Required CI check |
| Frames extracted on one OS, measured on another: fonts differ, text widths drift | The spec records `renderer`; a mismatch warns. Pin browser and fonts in the CI job and extract frames in that same environment |
| Colour syntaxes | rgb()/rgba() are parsed, everything else (oklch, color(), color-mix) goes through a canvas into sRGB; an unparseable colour fails extraction |
| Not covered by the web extractor | gradients inside `url()` images (an image is a variable slot), SVG internals, animations, hover states (write them as named exceptions or capture them as their own screens) |
| `bypassPermissions` | The hooks docs do not say whether PreToolUse hooks still run; check per setup. CI covers it |
