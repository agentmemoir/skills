# `.design-lock.json` and tolerances

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
- `gate` deletes every `measured` file, runs `capture`, then compares each screen.

## Tolerances

Defaults: `box` 0.5, `fontSize` 0.1, `lineHeight` 0.1, `letterSpacing` 0.1, `radius` 0.25, `borderWidth` 0.1, `color` 2 per channel, `alpha` 0.02. Pixel mode adds `pixelRatio` 0.001 (share of differing pixels) and `pixelBlock` 4 (differing pixels allowed in any 16x16 block): scattered anti-aliasing passes, a wrong icon, badge, or word does not. Override only in `.design-lock.json`. Unknown keys and non-numbers are errors.
