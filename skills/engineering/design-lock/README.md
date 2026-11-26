# design-lock reference

The playbook is [`SKILL.md`](SKILL.md). This file holds the details: adoption, config, spec schema, tolerances, commands, hooks, and CI. Capture recipes are in [`recipes/README.md`](recipes/README.md). Scripts live in `scripts/` and the full chain is tested by `tests/run_tests.py` (`--skip-web` without Playwright).

## Adopt

1. `python3 <skill>/scripts/designlock.py init --platform <web|android|ios|flutter|desktop|command> --dir <repo> --screen home` writes `.design-lock.json`, `design/{baseline,changes}.json`, `tools/design-lock/*` (a copy of the engine and guard), a capture recipe, and `.github/workflows/design-lock.yml`.
2. I put the approved frame image (`design/frames/<screen>.png`) and spec (`<screen>.spec.json`) in place for each screen and theme. From an HTML mock, I write a map and extract the spec:

   ```
   {"root": ".screen", "elements": [{"id": "title", "selector": ".title"}, {"id": "price", "selector": ".price", "variable": true, "flex": ["w"]}], "ignore": [{"selector": ".ad", "reason": "third-party slot"}]}
   designlock.py extract-web --file mock.html --map map.json --theme dark --kind spec --name home.dark --out design/frames/home.dark.spec.json
   ```

   For Figma or other sources, I write the same JSON from the export. The image comes from the design, or from `extract-web --screenshot`.
3. Tag the app's elements with the same ids: `data-dl-id`, plus `data-dl-role="image"` for an image-like slot with no `<img>` (otherwise it reads as a container), and `data-dl-variable` (optionally `="w,color"` for flex axes). Capture with the same `--root` the frame used, and keep any capture map under a locked path: the app may not ignore more than the frame ignores.
4. Edit `tools/design-lock/capture.sh` so it renders every registered screen into its `measured` path.
5. Run `python3 tools/design-lock/designlock.py gate`. Fix the app, or record a known failure in `design/baseline.json` (`{element, property, value, issue}`, shrink-only) or a deliberate difference in the screen's `exceptions` (`{element, property, value, reason}`). `value` pins the accepted app value, so any other value still fails.
6. Commit. I make `design-ok` a required check and keep the `design:approved-change` label to myself.
7. The hooks need nothing per project. I register them once in `~/.claude/settings.json` (see Hooks).

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

- `screens.*`: `frame` (spec), `image` (the approved picture), `measured` (what capture writes), `mode` (`structure`, the default element table, or `pixel`, a PNG compared with the frame image with the spec's variable regions masked), `exceptions`, `allowExtra`, `sources`. Unknown keys are errors.
- `ui` is the Stop hook's trigger and cache key. It must cover everything that changes rendering: styles, theme and token files, build config (tailwind, gradle), assets, dependency manifests. A change outside `ui` never runs the local gate; CI still runs it on every PR.
- `screenFiles` and `sources`: every UI file matching `screenFiles` must belong to a screen's `sources`, so a new screen cannot ship without a frame.
- Protected paths: `.design-lock.json`, every screen's frame and image, the ledger, and the `locked` globs. Hooks deny agents, and CI demands the label and a ledger entry. The baseline is shrink-only.
- `gate` deletes every `measured` file, runs `capture`, then compares each screen. Exit 0 pass, 1 violation, 2 input error.

## Spec schema (`design-lock/1`)

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

- `role` is `container` (fill, border, radius, shadow), `text`, or `image`. Units are logical px/dp/pt, colours are 0-255 with alpha 0-1, and `box` is relative to the frame root.
- A spec must state every constant its role needs (`null` means none). A spec that omits `fill`, `shadow`, or a core font key is invalid and fails the gate. `opacity`, `backgroundImage`, `filter`, `clipPath`, and `outline` default to none when absent, so an app cannot add them unnoticed. `font.style/align/transform/decoration` are compared when the frame states them.
- `variable: true` is for `text` and `image` only. `flex` lists what the content may change: `x y w h color fill`. A right-aligned price in a content-sized box flexes `w`. A green or red change flexes `color`.
- `ignored` lists regions the frame skips on purpose, each with a reason. The app's capture may ignore none that the frame does not list.
- `unmapped` (web) lists painted elements nobody named, including painted pseudo-elements and gradients. A non-empty list fails the comparison.
- Ids are the join key. A duplicate id, an app element the frame lacks, or a frame element the app lacks fails.

## Tolerances

Defaults: `box` 0.5, `fontSize` 0.1, `lineHeight` 0.1, `letterSpacing` 0.1, `radius` 0.25, `borderWidth` 0.1, `color` 2 per channel, `alpha` 0.02. Pixel mode adds `pixelRatio` 0.001 (share of differing pixels) and `pixelBlock` 4 (differing pixels allowed in any 16x16 block): scattered anti-aliasing passes, a wrong icon, badge, or word does not. Override only in `.design-lock.json`. Unknown keys and non-numbers are errors.

## Commands

```
designlock.py gate [--root .] [--out build/design-lock] [--no-capture]
designlock.py compare frame.spec.json app.measured.json [--tolerance 0.5 | box=0.5,fontSize=0.1] [--md out.md] [--json out.json] [--only-fail] [--allow-extra]
designlock.py extract-web (--file F | --url U) --out O [--kind spec|measured] [--map map.json] [--root SELECTOR] [--viewport 390x844] [--theme light|dark] [--name ID] [--screenshot png]
designlock.py init --platform P [--dir .] [--screen home]
```

`gate` writes `report.md` (every element and property with frame value, app value, and result, linked to the frame image) and `report.json`.

## Hooks

I register them once in `~/.claude/settings.json`: `Stop` and `SubagentStop` run `python3 ~/.claude/skills/design-lock/scripts/hook.py stop` (timeout 900). `PreToolUse` with matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|mcp__.*` runs `... hook.py pretool` (timeout 10). Both are silent no-ops, with no subprocess, in a tree without `.design-lock.json`.

**PreToolUse** denies Edit, Write, MultiEdit, NotebookEdit, shell writes, and MCP tools that target a protected path.
- Every `mcp__*` tool is checked unless its name starts with a read verb (read, get, list, find, search, view, show, stat, query, ...). Tools named like a shell (shell, exec, command, run, bash, script) have their `command` or `cmd` argument parsed like a Bash command.
- The shell check parses redirects, `rm`, `mv`, `cp`, `tee`, `sed -i`, `perl -pi`, `awk -i inplace`, `dd of=`, `git checkout/restore/apply`, `cd x && ...`, `bash -c`, and inline python or node that opens a path for writing. It resolves targets wherever the command runs. It never denies reading a protected file, and it allows `git restore .` and `git checkout -- .` because they restore the approved state.
- Paths match case-insensitively on case-insensitive volumes.
- It also records UI edits for the Stop hook.

**Stop** gates the main session when it edited UI files or the work tree has uncommitted UI changes. **SubagentStop** gates only a subagent that edited UI files.
- A tree already proven green, or already failed, is not captured again (cached by a content hash of the `ui` files, protected paths, and baseline). Concurrent gates share one lock. The gate runs in its own process group and is killed whole on timeout, within an 880 s budget.
- After `DESIGN_LOCK_MAX_BLOCKS` (default 3) consecutive blocks the stop is released with a loud message. CI is the backstop.
- The hook keys on the directory the session runs in. Edits to another project are enforced by that project's CI and by the Stop of a session started there.

To change the design, I start a session with `DESIGN_LOCK_CHANGE="<why>"`. The hook then lets locked files be edited. CI still requires the label and the ledger entry.

The hooks, the skill scripts, and the settings files are deliberately unguarded: an agent that edits settings (`disableAllHooks`, the hook command, `DESIGN_LOCK_CHANGE` in `env`) switches the hooks off. For a hard local guarantee, I install them in managed settings with `allowManagedHooksOnly`.

## CI

`templates/design-lock.yml` runs on `pull_request_target` (opened, synchronize, reopened, labeled, unlabeled), `merge_group`, and pushes to main. Only the `design:approved-change` label reruns it. Other labels run nothing and cannot cancel a real run. Actions are pinned to commit SHAs.

GitHub runs the workflow and the tooling from the base branch. The pull request is checked out into `pr/` and measured with `base/tools/design-lock/designlock.py gate --root pr`, and `base/.../guard.py` runs the guard. The capture command builds and runs the PR's own code, so PR code does execute on the runner, with a read-only token and no secrets. Base tooling fails the gate if capture modified a frame, the config, the baseline, or a locked file, and it re-validates the measured output. A PR can still misreport its own rendering in the measured file, so I review the capture script (a locked path) and the report.

The guard rejects:
- a change to any protected path, or an added baseline entry, without both the label and a new ledger entry
- updated goldens or snapshots while the design check did not pass (a label never excuses this)

The first adoption PR (no config on the base) is left to me. A push drops the label, so an approval covers one commit. `design-ok` is the single required check. It fails unless both jobs succeeded (skipped counts as failure). Branch protection, the label permission, and the required check stay out of the agent's reach, for example behind a separate agent GitHub identity.

## Known gaps

| Gap | Mitigation |
| :- | :- |
| A shell write the heuristic misses (paths built at run time, a script that writes) | The CI guard sees the diff |
| An agent runner that ignores Claude Code hooks | The required CI check |
| Frames extracted on one OS and measured on another: fonts differ and text widths drift | The spec records `renderer` and a mismatch warns. Pin browser and fonts in CI and extract frames in that same environment |
| Colour syntaxes | `rgb()` and `rgba()` are parsed. Everything else (oklch, `color()`, `color-mix`) goes through a canvas into sRGB, and an unparseable colour fails extraction |
| Not covered by the web extractor | Gradients inside `url()` images (an image is a variable slot), SVG internals, animations, hover states. Write them as named exceptions or capture them as their own screens |
| `bypassPermissions` | The hooks docs do not say whether PreToolUse hooks still run. Check per setup. CI covers it |
