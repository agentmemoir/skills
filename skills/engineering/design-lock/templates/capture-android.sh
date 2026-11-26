#!/bin/sh
# Capture recipe: Android emulator or device, pixel mode (the screenshot is compared with design/frames/<screen>.png, variable slots masked).
# Match the frame's size, density and theme first, e.g.: adb shell wm size 1080x2400; adb shell wm density 420; adb shell cmd uimode night yes
# For element-level checks use a Compose/Robolectric adapter that writes the design-lock/1 JSON (see recipes/README.md) and set the screen mode to structure.
set -e
OUT=build/design-lock/measured; mkdir -p "$OUT"
APP_ID="${APP_ID:?set APP_ID}"; ACTIVITY="${ACTIVITY:-.MainActivity}"
adb shell am start -W -n "$APP_ID/$ACTIVITY" >/dev/null
sleep 2
adb exec-out screencap -p > "$OUT/home.png"
