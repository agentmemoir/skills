#!/usr/bin/env bash
# Validates every skill under skills/<category>/ against the core Agent Skills rules,
# and checks the Claude Code marketplace lists exactly those skills.
# Usage: ./scripts/validate.sh [skills/<category>/<name>] [--quick]
# With explicit targets, only those skills are checked. The marketplace check
# runs on full scans only, so temporary test skills do not trip it.
# --quick skips the self-check suite (used by the pre-commit hook).
set -euo pipefail

QUICK=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --quick) QUICK=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
if [ "${#ARGS[@]}" -gt 0 ]; then
  set -- "${ARGS[@]}"
else
  set --
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS=()
if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  for cat in "$ROOT"/skills/*/; do
    [ -d "$cat" ] || continue
    for d in "$cat"*/; do
      [ -d "$d" ] && TARGETS+=("skills/$(basename "$cat")/$(basename "$d")")
    done
  done
fi

fail=0
for target in "${TARGETS[@]}"; do
  dir="$ROOT/$target"
  file="$dir/SKILL.md"
  name="$(basename "$dir")"
  if [ ! -f "$file" ]; then
    echo "FAIL $target: missing SKILL.md"
    fail=1
    continue
  fi
  python3 - "$file" "$name" "$target" <<'PY' || fail=1
import re
import sys

path, dirname, target = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
errors = []


def parse_frontmatter(front):
    """Minimal YAML frontmatter reader: single-line values plus > and | blocks."""
    data = {}
    lines = front.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        if rest.startswith((">", "|")):
            style = rest[0]
            i += 1
            buf, indent = [], None
            while i < len(lines):
                cur_line = lines[i]
                if not cur_line.strip():
                    buf.append("")
                    i += 1
                    continue
                cur_indent = len(cur_line) - len(cur_line.lstrip(" "))
                if cur_indent == 0:
                    break
                if indent is None:
                    indent = cur_indent
                if cur_indent < indent:
                    break
                buf.append(cur_line[indent:])
                i += 1
            while buf and buf[-1] == "":
                buf.pop()
            if style == ">":
                paras, cur_para = [], []
                for b in buf:
                    if b == "":
                        paras.append(" ".join(cur_para))
                        cur_para = []
                    else:
                        cur_para.append(b)
                paras.append(" ".join(cur_para))
                data[key] = "\n".join(paras)
            else:
                data[key] = "\n".join(buf)
        else:
            value = rest.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            data[key] = value
            i += 1
    return data


def valid_name(name):
    if not 1 <= len(name) <= 64:
        return False
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False
    for ch in name:
        if ch == "-":
            continue
        if not ch.isalnum() or ch.isupper():
            return False
    return True


m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    errors.append("missing YAML frontmatter block")
    print(f"FAIL {target}: " + "; ".join(errors))
    sys.exit(1)

front = parse_frontmatter(m.group(1))
if "name" not in front:
    errors.append("frontmatter missing 'name'")
else:
    name = front["name"]
    if name != dirname:
        errors.append(f"name '{name}' must match directory '{dirname}'")
    if not valid_name(name):
        errors.append(f"name '{name}' violates spec (lowercase alnum+hyphen, 1-64 chars, no leading/trailing/double hyphen)")
if "description" not in front or not front["description"]:
    errors.append("frontmatter missing 'description'")
else:
    desc = front["description"]
    if len(desc) > 1024:
        errors.append(f"description is {len(desc)} chars, max 1024")
    if re.search(r"<[A-Za-z/!]", desc):
        errors.append("description must not contain XML tags")
    if re.search(r"\b(whenever|when)\s+the\s+user\b", desc, re.I):
        errors.append("description must use first-person ('whenever I' / 'when I') rather than 'the user'")

# Real-YAML safety: an unquoted single-line value may not contain ': '.
for fm_line in m.group(1).split("\n"):
    lm = re.match(r"^([A-Za-z0-9_-]+):\s+(\S.*)$", fm_line)
    if not lm:
        continue
    value = lm.group(2).strip()
    if value[:1] in ">|":
        continue
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        continue
    if ": " in value:
        errors.append(
            f"frontmatter '{lm.group(1)}' has an unquoted ': '; quote it or use a block scalar"
        )

body = text[m.end():]
lines = body.count("\n") + 1
if lines > 500:
    errors.append(f"body is {lines} lines, keep under 500")

if errors:
    print(f"FAIL {target}: " + "; ".join(errors))
    sys.exit(1)
print(f"OK {target}")
PY
done

if [ "$#" -eq 0 ]; then
  echo "== marketplace =="
  python3 - "$ROOT" <<'PY' || fail=1
import json
import os
import sys

root = sys.argv[1]
errors = []
mp_path = os.path.join(root, ".claude-plugin", "marketplace.json")
try:
    marketplace = json.load(open(mp_path, encoding="utf-8"))
except (OSError, ValueError) as exc:
    print(f"FAIL marketplace: cannot read {mp_path}: {exc}")
    sys.exit(1)

mp_root = os.path.dirname(os.path.dirname(mp_path))
listed = set()
for plugin in marketplace.get("plugins", []):
    for entry in plugin.get("skills", []):
        listed.add(os.path.normpath(os.path.join(mp_root, entry)))

actual = set()
skills_dir = os.path.join(root, "skills")
for cat in sorted(os.listdir(skills_dir)):
    cat_dir = os.path.join(skills_dir, cat)
    if not os.path.isdir(cat_dir):
        continue
    for name in sorted(os.listdir(cat_dir)):
        skill_dir = os.path.join(cat_dir, name)
        if os.path.isdir(skill_dir) and os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
            actual.add(skill_dir)

for entry in sorted(listed):
    if not os.path.isfile(os.path.join(entry, "SKILL.md")):
        errors.append(f"marketplace lists '{os.path.relpath(entry, root)}' but no SKILL.md exists there")
for skill in sorted(actual):
    if skill not in listed:
        errors.append(f"'{os.path.relpath(skill, root)}' has a SKILL.md but is not listed in marketplace.json")

if errors:
    print("FAIL marketplace: " + "; ".join(errors))
    sys.exit(1)
print("OK marketplace")
PY
fi

if [ "$QUICK" -eq 0 ]; then
  echo "== autopsy self-check =="
  node "$ROOT/skills/review/autopsy/scripts/generate-report.cjs" --self-check || fail=1
fi

exit "$fail"
