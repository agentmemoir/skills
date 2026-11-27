# Adopting design-lock in a repo

1. Run `python3 <skill>/scripts/designlock.py init --platform <web|android|ios|flutter|desktop|command> --dir <repo> --screen home`. It writes `.design-lock.json`, `design/{baseline,changes}.json`, `tools/design-lock/*` (a copy of the engine and guard), a capture recipe, and `.github/workflows/design-lock.yml`.
2. Ask me for the approved frame image (`design/frames/<screen>.png`) and spec (`<screen>.spec.json`) of each screen and theme. Never invent them. From an HTML mock, write a map and extract the spec:

   ```
   {"root": ".screen", "elements": [{"id": "title", "selector": ".title"}, {"id": "price", "selector": ".price", "variable": true, "flex": ["w"]}], "ignore": [{"selector": ".ad", "reason": "third-party slot"}]}
   designlock.py extract-web --file mock.html --map map.json --theme dark --kind spec --name home.dark --out design/frames/home.dark.spec.json
   ```

   For Figma or other sources, write the same JSON from the export. The image comes from the design, or from `extract-web --screenshot`.
3. Tag the app's elements with the same ids: `data-dl-id`, plus `data-dl-role="image"` for an image-like slot with no `<img>` (otherwise it reads as a container), and `data-dl-variable` (optionally `="w,color"` for flex axes). Capture with the same `--root` the frame used, and keep any capture map under a locked path: the app may not ignore more than the frame ignores.
4. Edit `tools/design-lock/capture.sh` so it renders every registered screen into its `measured` path. Platform recipes are in [capture-recipes.md](capture-recipes.md).
5. Run `python3 tools/design-lock/designlock.py gate`. Fix the app, or record a known failure in `design/baseline.json` (`{element, property, value, issue}`, shrink-only) or a deliberate difference in the screen's `exceptions` (`{element, property, value, reason}`). `value` pins the accepted app value, so any other value still fails.
6. Commit. Ask me to make `design-ok` a required check. The `design:approved-change` label stays with me.
7. The hooks need nothing per project. They are registered once in `~/.claude/settings.json` ([hooks.md](hooks.md)).

A global `.*` gitignore hides `.design-lock.json`: add it with `git add -f`.

## Commands

```
designlock.py gate [--root .] [--out build/design-lock] [--no-capture]
designlock.py compare frame.spec.json app.measured.json [--tolerance 0.5 | box=0.5,fontSize=0.1] [--md out.md] [--json out.json] [--only-fail] [--allow-extra]
designlock.py extract-web (--file F | --url U) --out O [--kind spec|measured] [--map map.json] [--root SELECTOR] [--viewport 390x844] [--theme light|dark] [--name ID] [--screenshot png]
designlock.py init --platform P [--dir .] [--screen home]
```

`gate` writes `report.md` (every element and property with frame value, app value, and result, linked to the frame image) and `report.json`. Exit codes: 0 pass, 1 violation, 2 input error.
