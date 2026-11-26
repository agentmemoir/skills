# Capture recipes

A capture command renders every registered screen at the frame's size, density and theme, and writes each screen's `measured` path. Two modes:

- **structure** (best): write `design-lock/1` JSON with every element found by its id. Element-level findings, exact numbers.
- **pixel** (works anywhere a command can write an 8-bit RGB/RGBA PNG): the capture is compared with the frame image; the spec's variable regions are masked, everything else is a constant. Set `"mode": "pixel"`; the spec then lists only variable regions (`{"id", "role", "variable": true, "box"}`).

Start with pixel mode if no structural adapter exists, then add one. Either way pin everything that makes renderings differ: device or browser version, fonts, locale, clock, density, theme, animations off.

| Platform | Recipe | Structure adapter |
| :- | :- | :- |
| web | `templates/capture-web.sh` (`extract-web`, Playwright) | shipped |
| Android | `templates/capture-android.sh` (`adb exec-out screencap -p`) | sketch below |
| iOS | `templates/capture-ios.sh` (`xcrun simctl io booted screenshot`) | sketch below |
| Flutter | `templates/capture-flutter.sh` (`flutter screenshot`) | sketch below |
| desktop, anything else | `templates/capture-command.sh` | any tool that reports a box and style per named element |

## Structure adapter sketches

Contract: same `id`, same units (logical px = dp = pt), same colour model, all constants a role needs (`designlock.py gate` validates the frame, and the frame must state `fill`, `border`, `radius`, `shadow`, fonts, ... for each role).

- **Android Compose.** In a Robolectric or instrumented test set the content at the frame's size and theme, give each element `Modifier.testTag(id)`, read the semantics tree: `onNodeWithTag(id).fetchSemanticsNode()` gives `boundsInRoot` (px to dp with the density). Text style comes from the `getTextLayoutResult` semantics action. Fills, borders and radii are not in the semantics tree: expose them from the themed container components through a debug-only custom `SemanticsPropertyKey`, so the value measured is the value drawn. Serialise to the schema and let `capture.sh` run the test task and copy the JSON out.
- **iOS.** XCUITest or a snapshot host: `accessibilityIdentifier` = id, `frame` from the accessibility element, fonts and colours from the view's `UIFont`/`UIColor` or the SwiftUI model that styled it.
- **Flutter.** A widget test: `find.byKey(ValueKey(id))`, `tester.getRect`, `RenderParagraph.text.style` and `BoxDecoration` of the found render objects.

The adapter is part of the measurement, so keep it under `locked` and review it once.
