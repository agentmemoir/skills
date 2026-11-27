#!/bin/sh
# Capture recipe: iOS Simulator, pixel mode. Boot the simulator with the frame's device, appearance and content size first:
#   xcrun simctl boot "iPhone 15"; xcrun simctl ui booted appearance dark
# For element-level checks use an XCUITest adapter that writes the design-lock/1 JSON (see references/capture-recipes.md).
set -e
OUT=build/design-lock/measured; mkdir -p "$OUT"
BUNDLE_ID="${BUNDLE_ID:?set BUNDLE_ID}"
xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4 >/dev/null 2>&1 || true
xcrun simctl launch booted "$BUNDLE_ID" >/dev/null
sleep 2
xcrun simctl io booted screenshot --type=png "$OUT/home.png"
