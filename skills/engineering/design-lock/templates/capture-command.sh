#!/bin/sh
# Capture recipe: anything that can write a PNG (desktop apps, game UIs, a headless renderer). One command per registered screen, each writing
# the `measured` path of its screen in .design-lock.json at the frame's pixel size. 8-bit RGB or RGBA PNGs only.
set -e
mkdir -p build/design-lock/measured
# your-app --render home --size 1170x2532 --out build/design-lock/measured/home.png
echo "edit tools/design-lock/capture.sh: no capture command is set up yet" >&2
exit 2
