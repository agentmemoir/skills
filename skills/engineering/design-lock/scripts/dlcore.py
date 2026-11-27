"""Shared helpers for design-lock: config lookup, globs, protected paths, the baseline diff, change detection. Python 3 stdlib only."""
import hashlib
import json
import os
import re
import subprocess

CONFIG = ".design-lock.json"
DEFAULT_BASELINE = "design/baseline.json"
DEFAULT_LEDGER = "design/changes.json"
SCREEN_KEYS = {"frame", "image", "measured", "mode", "exceptions", "allowExtra", "sources"}
CONFIG_KEYS = {"version", "platform", "ui", "screens", "screenFiles", "capture", "gate", "gateTimeoutSec", "tolerance", "locked",
               "baseline", "ledger", "goldens", "forbidCommands"}


def find_root(start):
    """Nearest directory at or above `start` that holds .design-lock.json, else None. Pure os.stat, no subprocess."""
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, CONFIG)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def parse_config(text):
    cfg = json.loads(text)
    if not isinstance(cfg, dict) or not isinstance(cfg.get("screens"), dict) or not cfg["screens"]:
        raise ValueError(f"{CONFIG} must be an object with a non-empty \"screens\" object")
    bad = set(cfg) - CONFIG_KEYS
    if bad:
        raise ValueError(f"{CONFIG}: unknown keys {sorted(bad)}; known: {sorted(CONFIG_KEYS)}")
    for name, row in cfg["screens"].items():
        if not isinstance(row, dict) or not row.get("frame") or not row.get("measured"):
            raise ValueError(f"{CONFIG}: screen {name!r} needs \"frame\" and \"measured\"")
        bad = set(row) - SCREEN_KEYS
        if bad:
            raise ValueError(f"{CONFIG}: screen {name!r} has unknown keys {sorted(bad)}; known: {sorted(SCREEN_KEYS)}")
    return cfg


def load_config(root):
    with open(os.path.join(root, CONFIG)) as f:
        return parse_config(f.read())


def glob_re(pattern, fold=False):
    """`**` crosses directories, `*` and `?` do not. `fold` ignores case (case-insensitive volumes)."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$", re.I if fold else 0)


def matches(path, patterns, fold=False):
    if path.startswith("./"):
        path = path[2:]
    return any(glob_re(p, fold).match(path) for p in patterns)


def case_insensitive(root):
    """Whether the volume under `root` ignores case (macOS and Windows defaults): `Design/Frames` is then the locked `design/frames`."""
    return os.path.isfile(os.path.join(root, CONFIG.upper()))


def protected(cfg):
    """Paths agents may not change: frames, frame images, the config, the change ledger, and the `locked` globs."""
    out = list(cfg.get("locked", [])) + [CONFIG, cfg.get("ledger", DEFAULT_LEDGER)]
    for row in cfg["screens"].values():
        out += [row["frame"]] + ([row["image"]] if row.get("image") else [])
    return out


def baseline_path(cfg):
    return cfg.get("baseline", DEFAULT_BASELINE)


def triggers(cfg):
    """Paths whose change means the design may have changed."""
    return list(cfg.get("ui", [])) + protected(cfg) + [baseline_path(cfg)]


def baseline_grew(old, new):
    """Entries in `new` that `old` lacks. Known violations may be removed (fixed) but never added or edited."""
    if not isinstance(new, dict) or not all(isinstance(v, list) for v in new.values()):
        return ["the baseline must be an object of lists"]
    seen = {(k, json.dumps(e, sort_keys=True)) for k, v in (old or {}).items() for e in v}
    return sorted(f"{k}: {json.dumps(e, sort_keys=True)} added" for k, v in new.items() for e in v if (k, json.dumps(e, sort_keys=True)) not in seen)


def ledger_gained_entry(old, new):
    """The change ledger must gain at least one entry that names a reason and who asked for it."""
    olds = {json.dumps(e, sort_keys=True) for e in (old if isinstance(old, list) else [])}
    return any(isinstance(e, dict) and str(e.get("reason", "")).strip() and str(e.get("requestedBy", "")).strip()
               and json.dumps(e, sort_keys=True) not in olds for e in (new if isinstance(new, list) else []))


# ---------------------------------------------------------------- repo state (git when present)

def git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=20)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def project_files(root):
    """Relative paths of tracked and untracked (not ignored) files below `root`; a plain directory walk outside git."""
    out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is not None:
        return [f for f in out.split("\0") if f]
    found = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "build", "dist", ".gradle", ".venv")]
        found += [os.path.relpath(os.path.join(d, f), root) for f in files]
    return found


def dirty_files(root):
    """Relative paths changed in the work tree or index since HEAD, plus untracked ones; None outside git."""
    if git(root, "rev-parse", "--is-inside-work-tree") is None:
        return None
    if git(root, "rev-parse", "--verify", "-q", "HEAD") is None:
        return project_files(root)
    diff = git(root, "diff", "-z", "--name-only", "--no-renames", "--relative", "HEAD") or ""
    new = git(root, "ls-files", "-z", "--others", "--exclude-standard") or ""
    return sorted({f for f in (diff + "\0" + new).split("\0") if f})


def tree_digest(root, patterns):
    """Hash of the content of every project file matching `patterns` (tracked and untracked), so an unchanged tree is not re-gated."""
    h = hashlib.sha256()
    for f in sorted(project_files(root) or []):
        if matches(f, patterns):
            h.update(f.encode() + b"\0")
            try:
                with open(os.path.join(root, f), "rb") as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
            except OSError:
                h.update(b"missing")
    return h.hexdigest()
