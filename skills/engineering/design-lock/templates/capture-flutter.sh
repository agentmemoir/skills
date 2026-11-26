#!/bin/sh
# Capture recipe: Flutter, pixel mode. Run on the device or emulator that matches the frame (size, density, theme).
# For element-level checks write a widget test that reads Rects and styles by ValueKey(id) and emits design-lock/1 JSON (see recipes/README.md).
set -e
OUT=build/design-lock/measured; mkdir -p "$OUT"
flutter screenshot -o "$OUT/home.png"
