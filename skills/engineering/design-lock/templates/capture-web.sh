#!/bin/sh
# Capture recipe: web (Playwright). Renders each registered screen from the running app and writes build/design-lock/measured/<screen>.json.
# Edit once per project: start or serve the app, then one extract-web line per screen (name, url, viewport, theme as in the frame).
# Tag every element in the UI with data-dl-id="<id from the frame spec>" (data-dl-variable for data-driven slots). Pin the browser and fonts in CI.
set -e
DL="python3 tools/design-lock/designlock.py"
BASE="${APP_URL:-http://localhost:3000}"
# (cd app && npm run build && npx serve -l 3000 dist &) ; npx wait-on "$BASE"
$DL extract-web --url "$BASE/home" --viewport 390x844 --theme dark --name home --out build/design-lock/measured/home.json
