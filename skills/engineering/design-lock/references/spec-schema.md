# Spec schema (`design-lock/1`)

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
