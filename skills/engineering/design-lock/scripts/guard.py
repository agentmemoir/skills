#!/usr/bin/env python3
"""CI guard. Fails a pull request that changes what the design gate measures against, or updates goldens while the design check fails.

Run it from a copy of the tooling taken from the BASE commit (the workflow template does this), inside a checkout of the PR head, so a pull
request cannot weaken the guard that judges it. The config is read from the base commit too.

Guarded (needs the label AND a new entry in the change ledger naming the reason and who asked): any change to a protected path, meaning the
`locked` globs, every screen's frame spec and image, .design-lock.json and the ledger itself; and any added or edited baseline entry.
Never excused by a label: changing a file matching `goldens` while GATE_RESULT is not "success".
Env: BASE_SHA; HEAD_SHA (default HEAD); GATE_RESULT (the design job's result); LABELS (space separated) or GH_REPO + PR_NUMBER + GH_TOKEN to read them.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dlcore  # noqa: E402

LABEL = os.environ.get("DESIGN_LOCK_LABEL", "design:approved-change")


def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def show(rev, path):
    try:
        return run("git", "show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None


def labels():
    if "LABELS" in os.environ:
        return os.environ["LABELS"].split()
    return run("gh", "api", f"repos/{os.environ['GH_REPO']}/issues/{os.environ['PR_NUMBER']}/labels", "--jq", ".[].name").split()


def load(rev, path, default):
    text = show(rev, path)
    return json.loads(text) if text else default


def main():
    base, head = os.environ["BASE_SHA"], os.environ.get("HEAD_SHA", "HEAD")
    base_cfg = show(base, dlcore.CONFIG)
    if not base_cfg:
        print("design guard: the base commit has no .design-lock.json, so this pull request adopts design-lock; the owner reviews it by hand")
        return 0
    cfg = dlcore.parse_config(base_cfg)
    head_cfg = dlcore.parse_config(show(head, dlcore.CONFIG) or base_cfg)
    prot = dlcore.protected(cfg) + dlcore.protected(head_cfg)
    files = [f for f in run("git", "diff", "-z", "--name-only", "--no-renames", f"{base}...{head}").split("\0") if f]
    guarded = [f"{f} changed" for f in files if dlcore.matches(f, prot)]
    bp = dlcore.baseline_path(cfg)
    if bp in files:
        guarded += [f"{bp}: {g}" for g in dlcore.baseline_grew(load(base, bp, {}), load(head, bp, {}))]
    golden = [f for f in files if dlcore.matches(f, cfg.get("goldens", []))]
    failures = []
    gate = os.environ.get("GATE_RESULT", "")
    if golden and gate != "success":
        failures.append(f"{len(golden)} golden/snapshot file(s) changed while the design check did not pass ({gate or 'no result'}): "
                        + ", ".join(golden[:5]) + ". A golden is never re-recorded over a failing design check.")
    if guarded:
        why = []
        if LABEL not in labels():
            why.append(f"it has no label {LABEL} (the owner adds it, and it must be added again after every push)")
        led = cfg.get("ledger", dlcore.DEFAULT_LEDGER)
        if not dlcore.ledger_gained_entry(load(base, led, []), load(head, led, [])):
            why.append(f"{led} gained no entry with a reason and requestedBy: an approved design changes only for a recorded, explicitly requested reason")
        if why:
            failures.append("this pull request changes what the design gate measures against, and " + " and ".join(why) + ":\n  - " + "\n  - ".join(guarded))
    if failures:
        print("design guard FAILED\n" + "\n".join(failures))
        return 1
    print(f"design guard: ok ({len(guarded)} recorded and approved change(s))" if guarded else "design guard: nothing the gate measures against changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
