#!/usr/bin/env python3
"""Tests for design-lock. Needs python3 and git. The web tests also need Playwright with Chromium: without it they FAIL, unless --skip-web is given.
Run: python3 tests/run_tests.py [--skip-web]"""
import copy
import json
import re
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
FIX = os.path.join(HERE, "fixture")
sys.path.insert(0, SCRIPTS)
import designlock as D  # noqa: E402
import dlcore  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n     {detail}"))


def sh(cmd, cwd, env=None, stdin=None):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, env=dict(os.environ, **(env or {})), input=stdin)


def git(cwd, *args):
    return sh(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd)


def hook(mode, payload, cwd, env):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "hook.py"), mode], input=json.dumps(dict(payload, cwd=cwd)), capture_output=True, text=True,
                       env=dict(os.environ, **env))
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr


def denied(out):
    return bool(out) and out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def blocked(out):
    return bool(out) and out.get("decision") == "block"


def png(path, w, h, color=(10, 20, 30), rects=()):
    rows = []
    for y in range(h):
        row = bytearray(bytes(color) * w)
        for x0, y0, x1, y1, c in rects:
            if y0 <= y < y1:
                row[3 * x0:3 * x1] = bytes(c) * (x1 - x0)
        rows.append(b"\0" + bytes(row))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- JSON fixtures (no Playwright needed)

FONT = {"family": "Arial", "size": 16, "weight": 600, "letterSpacing": 0, "lineHeight": 20}


def style(**over):
    s = {"fill": None, "border": None, "radius": [0, 0, 0, 0], "shadow": None}
    s.update(over)
    return s


def el(i, role, x, y, w, h, variable=False, flex=None, **st):
    e = {"id": i, "role": role, "variable": variable, "box": {"x": x, "y": y, "w": w, "h": h}, "style": st}
    if flex:
        e["flex"] = flex
    return e


def make_frame():
    return {"schema": "design-lock/1", "kind": "spec", "frame": "home.dark", "theme": "dark", "viewport": {"width": 390, "height": 844}, "unmapped": [], "elements": [
        el("ring", "container", 28, 152, 48, 48, **style(fill=[40, 40, 50, 1], radius=[24] * 4)),
        el("logo", "image", 32, 156, 40, 40, variable=True, **style(fill=[98, 126, 234, 1], radius=[20] * 4)),
        el("title", "text", 24, 60, 342, 28, **style(color=[244, 244, 246, 1], font=dict(FONT, size=22, lineHeight=28), text="Markets")),
        el("price", "text", 236, 156, 122, 20, variable=True, flex=["w"], **style(color=[244, 244, 246, 1], font=dict(FONT))),
    ]}


def measured(frame, **edits):
    m = copy.deepcopy(frame)
    m["kind"] = "measured"
    by = {e["id"]: e for e in m["elements"]}
    by["price"]["box"]["w"] = 80  # a variable's content changed the width: allowed by flex
    by["logo"]["style"]["fill"] = [247, 147, 26, 1]  # another logo
    for path, v in edits.items():
        i, _, prop = path.partition("/")
        node = by[i]
        keys = prop.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = v
    return m


def fails(rows):
    return {(r["element"], r["property"]) for r in rows if r["status"] == "fail"}


def cmp(frame, app, tol=None, **kw):
    return D.compare_specs(frame, app, D.parse_tolerance(tol), **kw)


CAPTURE = "mkdir -p build/design-lock/measured && cp app/measured.json build/design-lock/measured/home.dark.json && echo run >> build/runs.log\n"


def make_repo(tmp, name="sample", sub="", capture=CAPTURE, extra_cfg=None):
    """A git repo whose project root is `sub` (a monorepo package when set): frame, image, an 'app' that writes a measured file, config, one commit."""
    top = os.path.join(tmp, name)
    root = os.path.join(top, sub) if sub else top
    for d in ("tools/design-lock", "design/frames", "app"):
        os.makedirs(os.path.join(root, d))
    for f in ("dlcore.py", "designlock.py", "guard.py"):
        shutil.copy(os.path.join(SCRIPTS, f), os.path.join(root, "tools/design-lock", f))
    open(os.path.join(root, "tools/design-lock/capture.sh"), "w").write(capture)
    frame = make_frame()
    json.dump(frame, open(os.path.join(root, "design/frames/home.dark.spec.json"), "w"), indent=1)
    png(os.path.join(root, "design/frames/home.dark.png"), 10, 10)
    json.dump(measured(frame), open(os.path.join(root, "app/measured.json"), "w"), indent=1)
    open(os.path.join(root, "design/baseline.json"), "w").write("{}")
    open(os.path.join(root, "design/changes.json"), "w").write("[]")
    cfg = {"version": 1, "ui": ["app/**"], "capture": "sh tools/design-lock/capture.sh", "gateTimeoutSec": 60, "locked": ["tools/design-lock/**", "design/frames/**"],
           "goldens": ["**/golden/**"], "forbidCommands": ["recordGoldens"],
           "screens": {"home.dark": {"frame": "design/frames/home.dark.spec.json", "image": "design/frames/home.dark.png",
                                     "measured": "build/design-lock/measured/home.dark.json", "exceptions": []}}}
    cfg.update(extra_cfg or {})
    json.dump(cfg, open(os.path.join(root, ".design-lock.json"), "w"), indent=1)
    open(os.path.join(top, ".gitignore"), "w").write("build/\n")
    git(top, "init", "-q", "-b", "master")
    git(top, "add", "-A")
    git(root, "add", "-f", ".design-lock.json")  # a global `.*` gitignore hides dotfiles
    git(top, "commit", "-qm", "base")
    return root


def set_app(root, **edits):
    json.dump(measured(make_frame(), **edits), open(os.path.join(root, "app/measured.json"), "w"), indent=1)


def gate_runs(root):
    p = os.path.join(root, "build/runs.log")
    return len(open(p).read().split()) if os.path.exists(p) else 0


def main():
    skip_web = "--skip-web" in sys.argv
    tmp = tempfile.mkdtemp(prefix="design-lock-test-")
    env = {"XDG_STATE_HOME": os.path.join(tmp, "state"), "DESIGN_LOCK_MAX_BLOCKS": "3"}
    env.pop("DESIGN_LOCK_CHANGE", None)
    os.environ.pop("DESIGN_LOCK_CHANGE", None)
    plain = os.path.join(tmp, "plain")
    os.makedirs(plain)
    compare_tests()
    root = make_repo(tmp)
    hook_tests(tmp, root, plain, env)
    stop_tests(tmp, root, env)
    gate_tests(tmp)
    guard_tests(tmp)
    init_and_ci_tests(tmp)
    pixel_tests(tmp)
    if skip_web:
        print("SKIPPED web tests (--skip-web)")
    else:
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError:
            check("web tests need Playwright (pip install playwright && playwright install chromium, or pass --skip-web)", False)
        else:
            web_tests(tmp, env)
    shutil.rmtree(tmp, ignore_errors=True)
    bad = RESULTS.count(False)
    print(f"\n{len(RESULTS) - bad}/{len(RESULTS)} passed")
    return 1 if bad else 0


# ---------------------------------------------------------------- the compare engine

def compare_tests():
    F = make_frame()
    rows = cmp(F, measured(F))
    check("a matching app passes; a variable's content and flex axes may differ", not fails(rows), str(fails(rows)))
    check("variables are reported as variable, never compared by content", {r["element"] for r in rows if r["property"] == "content"} == {"logo", "price"})
    check("a constant that differs fails (title x 1 px off)", fails(cmp(F, measured(F, **{"title/box.x": 25}))) == {("title", "box.x")})
    check("a variable's slot is still a constant outside its flex axis (price x)", fails(cmp(F, measured(F, **{"price/box.x": 240}))) == {("price", "box.x")})
    check("a variable image keeps its shape (a square crop of a round logo fails)", ("logo", "radius") in fails(cmp(F, measured(F, **{"logo/style.radius": [0] * 4}))))
    check("the container around a variable logo is a constant (its fill is checked)", fails(cmp(F, measured(F, **{"ring/style.fill": [41, 41, 51, 1]}))) == {("ring", "fill")}
          or fails(cmp(F, measured(F, **{"ring/style.fill": [60, 60, 70, 1]}))) == {("ring", "fill")})
    check("a variable's font is a constant", fails(cmp(F, measured(F, **{"price/style.font.size": 17}))) == {("price", "font.size")})
    bad = copy.deepcopy(F)
    bad["elements"][0]["variable"] = True
    check("a container cannot be marked variable (no blanket mask)", any("cannot be variable" in p for p in D.validate_spec(bad)))
    # tolerances
    check("default tolerance rejects a 0.75 px offset and accepts 0.4", ("title", "box.x") in fails(cmp(F, measured(F, **{"title/box.x": 24.75})))
          and not fails(cmp(F, measured(F, **{"title/box.x": 24.4}))))
    check("default tolerance rejects half a sp of font size and a 0.5 px border", ("title", "font.size") in fails(cmp(F, measured(F, **{"title/style.font.size": 22.5})))
          and ("ring", "border") in fails(cmp(F, measured(F, **{"ring/style.border": {"width": 0.5, "color": [0, 0, 0, 1]}}))))
    check("line height and radius drift of 0.3 fail by default", ("title", "font.lineHeight") in fails(cmp(F, measured(F, **{"title/style.font.lineHeight": 28.3})))
          and ("ring", "radius") in fails(cmp(F, measured(F, **{"ring/style.radius": [24.3] * 4}))))
    for bad_tol in ("nope=1", {"box": "x"}, {"box": -1}):
        try:
            D.parse_tolerance(bad_tol)
            ok = False
        except ValueError:
            ok = True
        check(f"tolerance {bad_tol!r} is an error, never silently ignored", ok)
    # blind spots
    check("a gradient background where the frame has none fails", ("ring", "backgroundImage") in fails(cmp(F, measured(F, **{"ring/style.backgroundImage": "linear-gradient(red, blue)"}))))
    check("opacity 0.5 where the frame has 1 fails", ("ring", "opacity") in fails(cmp(withst(F, "ring", opacity=1), measured(withst(F, "ring", opacity=1), **{"ring/style.opacity": 0.5}))))
    two = {"top": {"width": 1, "color": [0, 0, 0, 1], "style": "solid"}, "right": None, "bottom": None, "left": None}
    Fb = withst(F, "ring", border=two)
    check("per-side borders are compared (a bottom border added fails)", ("ring", "border") in fails(cmp(Fb, measured(Fb, **{"ring/style.border": dict(two, bottom=two["top"])}))))
    uni = {"width": 1, "color": [0, 0, 0, 1], "style": "solid"}
    Fu = withst(F, "ring", border=uni)
    check("a uniform border equals the same four sides; dashed vs solid fails", not fails(cmp(Fu, measured(Fu, **{"ring/style.border": {k: uni for k in ("top", "right", "bottom", "left")}})))
          and ("ring", "border") in fails(cmp(Fu, measured(Fu, **{"ring/style.border": dict(uni, style="dashed")}))))
    for k in ("filter", "clipPath", "outline"):
        Fk = withst(F, "ring", **{k: None})
        check(f"{k} that the frame lacks fails", (("ring", k)) in fails(cmp(Fk, measured(Fk, **{f"ring/style.{k}": "x"}))))
    Ft = copy.deepcopy(F)
    Ft["elements"][2]["style"]["font"].update(align="start", decoration="none", transform="none", style="normal")
    mt = measured(Ft, **{"title/style.font.decoration": "underline"})
    check("text decoration, alignment, transform and style are compared", ("title", "font.decoration") in fails(cmp(Ft, mt)))
    # spec validator
    thin = make_frame()
    del thin["elements"][2]["style"]["font"]["lineHeight"]
    del thin["elements"][0]["style"]["shadow"]
    probs = D.validate_spec(thin)
    check("a frame that omits a constant (lineHeight, shadow) is invalid, not 'no constraint'", any("font.lineHeight" in p for p in probs) and any("shadow" in p for p in probs), str(probs))
    check("the compare reports an invalid frame as a failing row", ("(frame spec)", "invalid") in fails(cmp(thin, measured(make_frame()))))
    # duplicates
    dup = measured(F)
    dup["elements"].append(copy.deepcopy(dup["elements"][2]))
    check("a duplicate id in the app fails (the first would be unchecked)", ("title", "duplicate id") in fails(cmp(F, dup)))
    # renderer
    Fr = dict(F, renderer={"browser": "120", "platform": "darwin"})
    rr = cmp(Fr, dict(measured(F), renderer={"browser": "121", "platform": "linux"}))
    check("different renderers warn (not fail) so cross-platform text drift is explained", not fails(rr) and any(r["property"] == "renderer" and r["status"] == "warn" for r in rr))
    # exceptions and known violations
    m = measured(F, **{"title/box.x": 30})
    ex = [{"element": "title", "property": "box.x", "value": 30, "reason": "RTL mirror, owner-approved"}]
    check("a named exception (element, property, value, reason) is applied", not fails(cmp(F, m, exceptions=ex)))
    worse = cmp(F, measured(F, **{"title/box.x": 300}), exceptions=ex)
    check("an exception pins the accepted value: x=300 instead of 30 still fails, with a note", ("title", "box.x") in fails(worse) and any("accepts 30" in r["note"] for r in worse))
    check("an exception without a value is invalid", ("title", "box.x") in fails(cmp(F, m, exceptions=[{k: v for k, v in ex[0].items() if k != "value"}])))
    check("an exception without a reason is invalid", fails(cmp(F, m, exceptions=[dict(ex[0], reason="")])) >= {("title", "box.x")})
    kv = [{"element": "title", "property": "box.x", "value": 30, "issue": "https://example.test/1"}]
    check("a known violation with an issue is tolerated; one that now matches must be removed",
          not fails(cmp(F, m, known=kv)) and fails(cmp(F, measured(F), known=kv)) == {("title", "box.x")})
    check("a known violation cannot worsen unnoticed (colour baseline pinned too)", ("title", "box.x") in fails(cmp(F, measured(F, **{"title/box.x": 60}), known=kv))
          and ("ring", "fill") in fails(cmp(F, measured(F, **{"ring/style.fill": [255, 0, 0, 1]}), known=[{"element": "ring", "property": "fill", "value": [60, 60, 70, 1], "issue": "i"}])))
    # ignored regions
    sneaky = dict(measured(F), ignored=[{"selector": ".ad", "reason": "promo"}])
    check("the app cannot ignore a region the approved frame does not ignore", (".ad", "ignored region") in fails(cmp(F, sneaky)))
    check("... but a region the frame ignores may be ignored", not fails(cmp(dict(F, ignored=[{"selector": ".ad", "reason": "promo"}]), sneaky)))
    # coverage
    root = os.path.join(tempfile.mkdtemp(prefix="dl-cov-"))
    os.makedirs(os.path.join(root, "src/screens"))
    for f in ("Home.tsx", "New.tsx"):
        open(os.path.join(root, "src/screens", f), "w").write("x")
    cfg = {"screenFiles": ["src/screens/**"], "screens": {"home": {"sources": ["src/screens/Home.tsx"]}}}
    cov = D.coverage_rows(cfg, root)
    check("a UI screen file with no registered frame fails the gate", [r["element"] for r in cov] == ["src/screens/New.tsx"], str(cov))
    shutil.rmtree(root)
    check("gateTimeoutSec is clamped below the hook timeout", D.gate_timeout({"gateTimeoutSec": 5000}) == 840)


def withst(frame, i, **st):
    f = copy.deepcopy(frame)
    for e in f["elements"]:
        if e["id"] == i:
            e["style"].update(st)
    return f


# ---------------------------------------------------------------- hooks: PreToolUse

def hook_tests(tmp, root, plain, env):
    def pre(tool, ti, cwd=root, e=env, **extra):
        return hook("pretool", dict({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti, "session_id": "sp"}, **extra), cwd, e)[1]

    def bash(cmd, cwd=root):
        return pre("Bash", {"command": cmd}, cwd)

    benign_cmds = [  # name settings or skill files, but write nothing locked
        "python3 -c \"import json; print(json.load(open('/home/x/.claude/settings.json')))\"", "node -e \"require('~/.claude/settings.json')\"",
        "bash -c 'cat ~/.claude/skills/design-lock/SKILL.md'", "rm -rf ~/.claude/skills/design-lock/tests/__pycache__",
        "git commit -m \"$(cat <<'EOF'\nfix\npython3 -c x .claude/settings.json\nEOF\n)\"", "jq '.a=1' ~/.claude/settings.json > /tmp/s && cp /tmp/s ~/.claude/settings.json",
        "H=~/.claude/skills/design-lock/scripts/hook.py python3 -c pass", "sed -i '' 's/a/b/' ~/.claude/settings.json", "rm -rf node_modules build", "ls -la && git status"]
    for where, cwd in (("a directory without .design-lock.json", plain), ("a repo with .design-lock.json", root)):
        check(f"ordinary and settings/skill-touching commands are never denied in {where}", all(bash(c, cwd) is None for c in benign_cmds), str([c for c in benign_cmds if bash(c, cwd)]))
    check("no-op in a directory without config: Edit, Write, MCP, Stop all silent", all(x is None for x in (
        pre("Edit", {"file_path": os.path.join(plain, "design/frames/a.json"), "old_string": "a", "new_string": "b"}, plain),
        pre("Write", {"file_path": os.path.join(plain, "x"), "content": "x"}, plain), pre("mcp__serena__create_text_file", {"relative_path": "design/frames/a.json", "content": "x"}, plain),
        hook("stop", {"hook_event_name": "Stop", "session_id": "s0"}, plain, env)[1])))
    check("invalid JSON and a list payload exit 0 silently", all(subprocess.run([sys.executable, os.path.join(SCRIPTS, "hook.py"), m], input=i, capture_output=True, text=True, env=dict(os.environ, **env)).returncode == 0
                                                                       for m in ("pretool", "stop") for i in ("not json", "[1, 2]", "null")))
    t = []
    for _ in range(5):
        t0 = time.time()
        hook("pretool", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, plain, env)
        t.append(time.time() - t0)
    check(f"the hook is fast without config (best of 5: {min(t) * 1000:.0f} ms)", min(t) < 0.3)
    src = open(os.path.join(SCRIPTS, "hook.py")).read()
    check("self-protection is gone: the hook knows nothing about settings files or its own scripts",
          not any(w in src for w in ("SELF_DIRS", "disableAllHooks", "DESIGN_LOCK_MAINTENANCE", "settings_check", "settings[^/]*")))
    hook_py = os.path.expanduser("~/.claude/skills/design-lock/scripts/hook.py")
    sj = os.path.expanduser("~/.claude/settings.json")
    check("editing the skill's scripts and settings.json is allowed in any repo", all(pre("Edit", {"file_path": p, "old_string": "a", "new_string": "b"}, c) is None
                                                                                       for p in (hook_py, sj) for c in (plain, root)))

    frame = os.path.join(root, "design/frames/home.dark.spec.json")
    cfgp = os.path.join(root, ".design-lock.json")
    check("PreToolUse denies an Edit, Write, MultiEdit and NotebookEdit on a locked frame",
          denied(pre("Edit", {"file_path": frame, "old_string": '"dark"', "new_string": '"light"'})) and denied(pre("Write", {"file_path": "design/frames/new.spec.json", "content": "{}"}))
          and denied(pre("MultiEdit", {"file_path": frame, "edits": [{"old_string": "a", "new_string": "b"}]})) and denied(pre("NotebookEdit", {"notebook_path": frame})))
    check("PreToolUse denies the frame image and the change ledger", denied(pre("Write", {"file_path": os.path.join(root, "design/frames/home.dark.png"), "content": "x"}))
          and denied(pre("Write", {"file_path": os.path.join(root, "design/changes.json"), "content": "[]"})))
    check("PreToolUse allows editing the app's UI files", pre("Edit", {"file_path": os.path.join(root, "app/measured.json"), "old_string": "a", "new_string": "b"}) is None)
    cfg = open(cfgp).read()
    for what, old, new in (("allowExtra on a screen", '"exceptions": []', '"exceptions": [], "allowExtra": true'), ("a hand-written measured path", "build/design-lock/measured/home.dark.json", "app/fake.json"),
                           ("a tolerance", '"version": 1,', '"version": 1, "tolerance": {"box": 50},'), ("an exception", '"exceptions": []', '"exceptions": [{"element":"x","property":"fill","reason":"r"}]'),
                           ("a new screen row", '"screens": {', '"screens": {"s2": {"frame": "a", "measured": "b", "exceptions": [{"element":"x","property":"y","reason":"z"}]}, ')):
        check(f".design-lock.json is locked: {what} is denied", denied(pre("Edit", {"file_path": cfgp, "old_string": old, "new_string": new})))
    bl = os.path.join(root, "design/baseline.json")
    open(bl, "w").write(json.dumps({"home.dark": [{"element": "title", "property": "box.x", "issue": "i"}]}))
    check("the baseline may shrink with the Edit tool", pre("Write", {"file_path": bl, "content": "{}"}) is None)
    check("the baseline may not grow or be edited", denied(pre("Write", {"file_path": bl, "content": json.dumps({"home.dark": [{"element": "title", "property": "box.x", "issue": "i"}, {"element": "ring", "property": "fill", "issue": "j"}]})}))
          and denied(pre("Write", {"file_path": bl, "content": "{not json"})))
    open(bl, "w").write("{}")
    check("a new baseline entry is denied", denied(pre("Write", {"file_path": bl, "content": json.dumps({"home.dark": [{"element": "x", "property": "fill", "issue": "i"}]})})))
    check("the baseline cannot be written from the shell", denied(bash("echo '{}' > design/baseline.json")))
    # mcp
    check("MCP write tools are guarded (Serena create_text_file / replace_content on a frame or the config)",
          denied(pre("mcp__serena__create_text_file", {"relative_path": "design/frames/home.dark.spec.json", "content": "{}"})) and denied(pre("mcp__serena__replace_content", {"relative_path": ".design-lock.json", "needle": "a", "repl": "b"}))
          and denied(pre("mcp__x__delete_lines", {"path": frame})))
    cfg_abs = os.path.join(root, ".design-lock.json")
    mcp_cases = [("mcp__serena__execute_shell_command", {"command": "echo x > .design-lock.json"}), ("mcp__x__append_file", {"path": "design/changes.json", "text": "x"}),
                 ("mcp__x__copy_file", {"source": "app/measured.json", "destination": "design/frames/home.dark.spec.json"}), ("mcp__x__set_contents", {"file": ".design-lock.json"}),
                 ("mcp__x__upload", {"target": {"path": "design/frames/home.dark.png"}}), ("mcp__x__run_script", {"script": "rm design/frames/home.dark.png"}),
                 ("mcp__shell__bash", {"cmd": f"echo x >> {cfg_abs}"})]
    check("every non-read MCP tool is checked, shell-like ones by parsing their command", all(denied(pre(t, a)) for t, a in mcp_cases), str([t for t, a in mcp_cases if not denied(pre(t, a))]))
    check("MCP read-verb tools and shell tools running harmless commands are allowed", all(pre(t, a) is None for t, a in (
        ("mcp__serena__read_file", {"relative_path": ".design-lock.json"}), ("mcp__serena__find_symbol", {"name": "design/frames"}), ("mcp__serena__execute_shell_command", {"command": "cat .design-lock.json && ls"}),
        ("mcp__x__get_file", {"path": "design/changes.json"}))))
    img = os.path.join(root, "design/frames/home.dark.png")
    vision = [("mcp__zai-mcp-server__ui_diff_check", {"expected_image_source": img, "actual_image_source": "app/shot.png"}), ("mcp__zai-mcp-server__analyze_image", {"image_source": img, "prompt": "describe"}),
              ("mcp__zai-mcp-server__extract_text_from_screenshot", {"image_source": "design/frames/home.dark.png"}), ("mcp__x__ui_to_artifact", {"image_source": img})]
    check("R1: vision and compare tools that name a frame image (the design workflow itself) are allowed, from the project and from a directory without config",
          all(pre(t, a) is None for t, a in vision) and all(pre(t, a, cwd=plain) is None for t, a in vision), str([t for t, a in vision if pre(t, a)]))
    check("R1: ... while write-verb tools on the same frame image stay denied", denied(pre("mcp__x__create_text_file", {"path": img})) and denied(pre("mcp__x__writeFile", {"path": img}))
          and denied(pre("mcp__x__create_text_file", {"path": img}, cwd=plain)))
    if dlcore.case_insensitive(root):
        cases = [("Edit", {"file_path": os.path.join(root, "Design/Frames/home.dark.spec.json"), "old_string": "a", "new_string": "b"}), ("Edit", {"file_path": os.path.join(root, ".DESIGN-LOCK.JSON"), "old_string": "a", "new_string": "b"}),
                 ("Write", {"file_path": os.path.join(root, "TOOLS/Design-Lock/capture.sh"), "content": "x"}), ("Bash", {"command": "echo x > Design/frames/home.dark.spec.json"})]
        check("on a case-insensitive volume, Design/Frames, .DESIGN-LOCK.JSON and TOOLS/Design-Lock are the locked files", all(denied(pre(t, a)) for t, a in cases), str([a for t, a in cases if not denied(pre(t, a))]))
    else:
        check("(this volume is case-sensitive, so a different case is a different file)", True)
    other = os.path.join(tmp, "elsewhere")
    os.makedirs(other, exist_ok=True)
    check("a shell command run from another directory is checked against the project it names", denied(bash(f"echo x > {root}/.design-lock.json", other)) and denied(bash(f"git -C {root} checkout -- design/frames/home.dark.spec.json", other))
          and denied(bash(f"cd {root} && rm design/changes.json", other)) and bash(f"echo x > {other}/ok.txt && cat {root}/.design-lock.json", other) is None)
    check("MCP read tools and writes to ordinary files are allowed", pre("mcp__serena__read_file", {"relative_path": "design/frames/home.dark.spec.json"}) is None
          and pre("mcp__serena__create_text_file", {"relative_path": "app/new.txt", "content": "x"}) is None)
    # shell
    deny_cmds = ["echo '{}' > design/frames/home.dark.spec.json", "sed -i 's/12/12.5/' design/frames/home.dark.spec.json", "python3 - <<'EOF'\nopen('design/frames/home.dark.spec.json','w').write('{}')\nEOF",
                 "git checkout HEAD~1 -- design/frames/home.dark.spec.json", "rm -rf design/frames", "dd if=/dev/zero of=design/frames/home.dark.spec.json", "awk -i inplace '{print}' design/frames/home.dark.spec.json",
                 "cd design && echo x > frames/home.dark.spec.json", "bash -c 'echo x >> design/frames/home.dark.spec.json'", "cat x | tee design/frames/home.dark.spec.json", "mv /tmp/x design/frames/a.json",
                 "python3 -c \"from pathlib import Path; Path('design/frames/home.dark.spec.json').write_text('x')\"", "node -e \"require('fs').writeFileSync('.design-lock.json','{}')\"",
                 "cp /tmp/x design/frames/home.dark.spec.json", "git -C . checkout -- design/frames/home.dark.spec.json", "mv design/frames/home.dark.png /tmp/", "./gradlew recordGoldens", "perl -pi -e 's/a/b/' design/frames/home.dark.spec.json"]
    check("shell writes to locked paths are denied", all(denied(bash(c)) for c in deny_cmds), str([c for c in deny_cmds if not denied(bash(c))]))
    open(os.path.join(tmp, "p.patch"), "w").write("--- a/design/frames/home.dark.spec.json\n+++ b/design/frames/home.dark.spec.json\n@@ -1 +1 @@\n-a\n+b\n")
    check("git apply of a patch that touches a locked file is denied", denied(bash(f"git apply {tmp}/p.patch")))
    allow_cmds = ["cat design/frames/home.dark.spec.json", "jq .elements design/frames/home.dark.spec.json | head", "git commit -m 'mention design/frames/x'", "sed -n 1,5p design/frames/home.dark.spec.json",
                  "cp design/frames/home.dark.spec.json /tmp/x.json", "cp notes.txt .", "echo hi > /tmp/out.txt", "grep -r price design/ app/", "python3 -c \"print(open('design/frames/home.dark.spec.json').read())\"",
                  "python3 -c \"import json;d=json.load(open('design/frames/home.dark.spec.json'));open('/tmp/table.txt','w').write(str(d))\"", "echo 'rm design/frames/x' > /tmp/note",
                  "git commit -m \"$(cat <<'EOF'\nnote: rm design/frames/a.json and sed -i design/frames\nEOF\n)\"", "git status && git diff design/frames", "rm -rf build node_modules", "git restore .", "git checkout -- .", "git checkout design", "git checkout tools",
                  "python3 -c \"print(open('design/frames/home.dark.spec.json', 'r').read())\"", "python3 -c \"print(open('design/frames/home.dark.spec.json', 'rb').read())\""]
    check("reads, copies out, commit messages and unrelated writes are allowed", all(bash(c) is None for c in allow_cmds), str([c for c in allow_cmds if bash(c)]))
    check("DESIGN_LOCK_CHANGE lets my session edit the lock (CI still wants the label and ledger entry)",
          pre("Edit", {"file_path": frame, "old_string": "a", "new_string": "b"}, e=dict(env, DESIGN_LOCK_CHANGE="owner found a new empty state")) is None)


# ---------------------------------------------------------------- hooks: Stop

def stop_tests(tmp, root, env):
    def stop(sid, cwd=root, event="Stop", **extra):
        return hook("stop", dict({"hook_event_name": event, "session_id": sid}, **extra), cwd, env)[1]

    def edit(sid, cwd=root, **extra):
        hook("pretool", dict({"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": sid, "tool_input": {"file_path": os.path.join(root, "app/measured.json"),
                                                                                                                  "old_string": "a", "new_string": "b"}}, **extra), cwd, env)

    check("Stop is silent when nothing UI changed", stop("a0") is None and gate_runs(root) == 0)
    # a UI edit leaves Stop blocked until the gate passes
    set_app(root, **{"title/box.x": 30})
    edit("a1")
    out = stop("a1")
    check("a UI edit leaves Stop blocked, naming screen, element and property", blocked(out) and "home.dark" in out["reason"] and "title" in out["reason"] and "box.x" in out["reason"], str(out)[:500])
    check("the block says how many blocks remain", "[block 1 of 3]" in out["reason"])
    check("the gate really ran once", gate_runs(root) == 1)
    set_app(root)
    out = stop("a1")
    check("fixing the app lets Stop through (the gate ran and passed)", out is None and gate_runs(root) == 2, str(out))
    check("the work is done and Stop passes again without gating", stop("a1") is None and gate_runs(root) == 2)
    set_app(root, **{"price/box.w": 81})  # a dirty tree that still matches (a variable's flex axis)
    check("a dirty UI tree that matches passes, one gate run", stop("a1b") is None and gate_runs(root) == 3)
    check("an identical tree proven green is NOT gated again, even by another session (the green cache really works)", stop("a1c") is None and gate_runs(root) == 3)
    set_app(root, **{"title/box.x": 30})
    out1 = stop("r1")
    out2 = stop("r2")
    check("a failing tree is cached by its hash too: no second capture, the same failure is replayed to the next block, turn or agent",
          blocked(out1) and blocked(out2) and gate_runs(root) == 4 and "title" in out2["reason"], f"runs={gate_runs(root)} {str(out2)[:200]}")
    set_app(root, **{"title/box.x": 30, "price/box.w": 82})
    check("a changed tree is gated again", blocked(stop("r3")) and gate_runs(root) == 5)
    set_app(root)
    stop("r3")
    # loop guard
    set_app(root, **{"title/box.x": 30})
    for _ in range(4):
        out = stop("a2", hook_event_name="Stop")
    check("loop guard: blocks are capped, then the stop is released with a loud message", out and not blocked(out) and "stopping anyway" in out.get("systemMessage", ""), str(out)[:300])
    # subagents
    out = stop("a3", event="SubagentStop", agent_id="reader", agent_type="research")
    check("a read-only subagent is not blocked by a dirty tree it did not touch", out is None)
    edit("a3", agent_id="coder")
    out = stop("a3", event="SubagentStop", agent_id="coder", agent_type="code")
    check("a subagent that edited UI is blocked like the main session", blocked(out), str(out)[:300])
    out = stop("a3", event="SubagentStop", agent_id="reader2")
    check("... and another read-only subagent of the same session still is not", out is None)
    out = stop("a4")
    check("the main session sees the dirty UI tree even with no recorded edit (e.g. shell edits)", blocked(out))
    # committed work: HEAD == master, nothing dirty, but this session edited
    set_app(root)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "ui")
    set_app(root, **{"title/box.x": 31})
    git(root, "commit", "-qam", "bad ui committed")
    edit("a5")
    check("committed-but-unproven UI work (HEAD == master) is still gated when the session edited it", blocked(stop("a5")))
    set_app(root)
    git(root, "commit", "-qam", "fix")
    stop("a5")
    # broken config fails closed
    cfgp = os.path.join(root, ".design-lock.json")
    good = open(cfgp).read()
    open(cfgp, "w").write("{broken")
    out = stop("a6")
    check("a broken config fails closed for the design check, with a clear message", blocked(out) and "could not run" in out["reason"], str(out))
    open(cfgp, "w").write(good)
    # subdirectory and monorepo
    set_app(root, **{"title/box.x": 32})
    out = stop("a7", cwd=os.path.join(root, "app"))
    check("the config is found from a subdirectory, and the gate blocks there", blocked(out), str(out))
    set_app(root)
    git(root, "commit", "-qam", "ok")
    mono = make_repo(tmp, "mono", sub="pkg")
    set_app(mono, **{"title/box.x": 33})
    out = hook("stop", {"hook_event_name": "Stop", "session_id": "m1"}, mono, env)[1]
    check("monorepo (.design-lock.json below the git root): a modified tracked UI file blocks the Stop", blocked(out), str(out))
    flat = os.path.join(tmp, "nogit")
    shutil.copytree(mono, flat, ignore=shutil.ignore_patterns("build"))
    check("a config in a directory with no git: silent without an edit marker", hook("stop", {"hook_event_name": "Stop", "session_id": "n1"}, flat, env)[1] is None)
    hook("pretool", {"tool_name": "Write", "session_id": "n1", "tool_input": {"file_path": os.path.join(flat, "app/measured.json"), "content": "{}"}}, flat, env)
    set_app(flat, **{"title/box.x": 33})
    check("... and gated after a recorded edit", blocked(hook("stop", {"hook_event_name": "Stop", "session_id": "n1"}, flat, env)[1]))
    # hook budget: a gate that outlives it is killed with its whole group, the capture's own group included
    slow = make_repo(tmp, "slow", extra_cfg={"gateTimeoutSec": 600, "capture": "(sleep 300 & echo $! > build/child.pid; wait)"})
    os.makedirs(os.path.join(slow, "build"), exist_ok=True)
    set_app(slow, **{"title/box.x": 40})
    hook("pretool", {"tool_name": "Edit", "session_id": "k1", "tool_input": {"file_path": os.path.join(slow, "app/measured.json"), "old_string": "a", "new_string": "b"}}, slow, env)
    t0 = time.time()
    out = hook("stop", {"hook_event_name": "Stop", "session_id": "k1"}, slow, dict(env, DESIGN_LOCK_HOOK_BUDGET="16"))[1]
    time.sleep(0.3)
    try:
        os.kill(int(open(os.path.join(slow, "build/child.pid")).read()), 0)
        alive = True
    except OSError:
        alive = False
    check("the Stop hook stays inside its budget: a gate that outlives it is killed, capture children included, and the stop is blocked with a message",
          blocked(out) and "did not finish" in out["reason"] and not alive and time.time() - t0 < 25, f"{str(out)[:200]} alive={alive} {time.time() - t0:.0f}s")
    # state gc
    sd = os.path.join(tmp, "state/design-lock")
    old = os.path.join(sd, "old_marker")
    open(old, "w").close()
    os.utime(old, (time.time() - 9 * 86400,) * 2)
    stop("gc")
    check("stale state files are garbage-collected", not os.path.exists(old))


# ---------------------------------------------------------------- the gate command

def gate_tests(tmp):
    root = make_repo(tmp, "gate")
    dl = [sys.executable, os.path.join(SCRIPTS, "designlock.py"), "gate", "--root", root]
    r = subprocess.run(dl, capture_output=True, text=True)
    check("gate runs the capture command and passes on the matching app", r.returncode == 0 and "PASS" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
    check("the gate writes report.md and report.json with every element", "| title | box.x |" in open(os.path.join(root, "build/design-lock/report.md")).read())
    set_app(root, **{"title/box.x": 30, "ring/style.fill": [200, 0, 0, 1]})
    r = subprocess.run(dl, capture_output=True, text=True)
    check("gate fails and names the screen and elements", r.returncode == 1 and "home.dark" in r.stdout and "| title | box.x |" in r.stdout and "| ring | fill |" in r.stdout, r.stdout[-400:])
    cfgp = os.path.join(root, ".design-lock.json")
    cfg = json.load(open(cfgp))
    ex = [{"element": "title", "property": "box.x", "value": 30, "reason": "RTL mirror"}, {"element": "ring", "property": "fill", "value": [200, 0, 0, 1], "reason": "pressed state"}]
    cfg["screens"]["home.dark"]["exceptions"] = ex
    json.dump(cfg, open(cfgp, "w"))
    check("named exceptions make the gate pass", subprocess.run(dl, capture_output=True, text=True).returncode == 0)
    cfg["screens"]["home.dark"]["exceptions"] = [dict(e, reason="") for e in ex]
    json.dump(cfg, open(cfgp, "w"))
    r = subprocess.run(dl, capture_output=True, text=True)
    check("an exception without a reason fails", r.returncode == 1 and "not valid" in r.stdout)
    cfg["screens"]["home.dark"]["exceptions"] = []
    json.dump(cfg, open(cfgp, "w"))
    json.dump({"home.dark": [{"element": "title", "property": "box.x", "value": 30, "issue": "https://e.test/1"}, {"element": "ring", "property": "fill", "value": [200, 0, 0, 1], "issue": "https://e.test/2"}]}, open(os.path.join(root, "design/baseline.json"), "w"))
    check("baseline (known violations) with issue links are tolerated", subprocess.run(dl, capture_output=True, text=True).returncode == 0)
    set_app(root)
    r = subprocess.run(dl, capture_output=True, text=True)
    check("a baseline entry that now matches must be removed", r.returncode == 1 and "now matches" in r.stdout)
    open(os.path.join(root, "design/baseline.json"), "w").write("{}")
    # stale measured file must not pass
    cfg["capture"] = "true"
    json.dump(cfg, open(cfgp, "w"))
    r = subprocess.run(dl, capture_output=True, text=True)
    check("F-extra: a stale measured file from an earlier run never passes for a fresh one", r.returncode == 1 and "did not run" in r.stdout, r.stdout[-300:])
    cfg["capture"] = "false"
    json.dump(cfg, open(cfgp, "w"))
    r = subprocess.run(dl, capture_output=True, text=True)
    check("a failing capture command fails the gate", r.returncode == 1 and "capture" in r.stdout)
    # timeout kills the process group
    cfg["capture"] = "(sleep 300 & echo $! > build/child.pid; wait)"
    cfg["gateTimeoutSec"] = 1
    json.dump(cfg, open(cfgp, "w"))
    os.makedirs(os.path.join(root, "build"), exist_ok=True)
    try:
        r = subprocess.run(dl, capture_output=True, text=True, timeout=30)  # without the process-group kill the orphaned pipe would hang: fail fast instead
    except subprocess.TimeoutExpired:
        r = subprocess.CompletedProcess(dl, 99, "", "hung")
        subprocess.run("pkill -f 'sleep 300'", shell=True)
    time.sleep(0.3)
    pid = int(open(os.path.join(root, "build/child.pid")).read())
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        alive = False
    check("a capture that exceeds the timeout is killed with its children and fails the gate", r.returncode == 1 and not alive, f"rc={r.returncode} alive={alive}")
    if alive:
        os.kill(pid, 9)
    cfg["capture"], cfg["gateTimeoutSec"] = "sh tools/design-lock/capture.sh", 60
    # N-extra: a capture that edits the approved frame is caught by base tooling
    cfg["capture"] = "echo '{}' > design/frames/home.dark.spec.json; sh tools/design-lock/capture.sh"
    json.dump(cfg, open(cfgp, "w"))
    spec_p = os.path.join(root, "design/frames/home.dark.spec.json")
    before_spec = open(spec_p).read()
    r = subprocess.run(dl, capture_output=True, text=True)
    check("README: a capture command that modifies an approved frame fails the gate (PR code runs in capture)", r.returncode == 1 and "modified the approved frames" in r.stdout + r.stderr, r.stdout[-300:])
    open(spec_p, "w").write(before_spec)
    cfg["capture"] = "sh tools/design-lock/capture.sh"
    json.dump(cfg, open(cfgp, "w"))
    cfg["tolerance"] = {"bogus": 1}
    json.dump(cfg, open(cfgp, "w"))
    check("an unknown tolerance key in the config is an input error (exit 2)", subprocess.run(dl, capture_output=True, text=True).returncode == 2)
    del cfg["tolerance"]
    cfg["screens"]["home.dark"]["typo"] = 1
    json.dump(cfg, open(cfgp, "w"))
    check("an unknown key on a screen is an input error", subprocess.run(dl, capture_output=True, text=True).returncode == 2)
    del cfg["screens"]["home.dark"]["typo"]
    cfg["screens"]["home.dark"]["image"] = "design/frames/missing.png"
    json.dump(cfg, open(cfgp, "w"))
    check("a screen without its approved frame image fails", subprocess.run(dl, capture_output=True, text=True).returncode == 1)
    # coverage through the gate
    cfg["screens"]["home.dark"]["image"] = "design/frames/home.dark.png"
    cfg["screenFiles"], cfg["screens"]["home.dark"]["sources"] = ["app/*.tsx"], ["app/Home.tsx"]
    json.dump(cfg, open(cfgp, "w"))
    open(os.path.join(root, "app/Home.tsx"), "w").write("x")
    open(os.path.join(root, "app/Settings.tsx"), "w").write("x")
    r = subprocess.run(dl, capture_output=True, text=True)
    check("the gate fails on a UI file with no frame", r.returncode == 1 and "app/Settings.tsx" in r.stdout, r.stdout[-300:])


# ---------------------------------------------------------------- CI guard

def guard_tests(tmp):
    root = make_repo(tmp, "guard")

    def guard(edit, labels="", gate_result="success", ledger=False):
        git(root, "checkout", "-q", "master")
        git(root, "checkout", "-q", "-B", "pr")
        edit()
        if ledger:
            json.dump([{"date": "2026-11-27", "reason": "owner found a new empty state", "requestedBy": "owner"}], open(os.path.join(root, "design/changes.json"), "w"))
        git(root, "add", "-A")
        git(root, "commit", "-qm", "pr")
        base = git(root, "rev-parse", "master").stdout.strip()
        r = sh([sys.executable, os.path.join(SCRIPTS, "guard.py")], root, env={"BASE_SHA": base, "HEAD_SHA": "pr", "LABELS": labels, "GATE_RESULT": gate_result})
        git(root, "checkout", "-q", "master")
        return r

    def edit_frame():
        p = os.path.join(root, "design/frames/home.dark.spec.json")
        open(p, "w").write(open(p).read().replace('"size": 22', '"size": 23', 1))

    L = "design:approved-change"
    r = guard(edit_frame)
    check("CI guard rejects a changed frame without the label", r.returncode == 1 and L in r.stdout, r.stdout)
    r = guard(edit_frame, labels=L)
    check("a label alone is not enough: the change must also be recorded in the ledger with a reason", r.returncode == 1 and "changes.json" in r.stdout, r.stdout)
    r = guard(edit_frame, ledger=True)
    check("... and a ledger entry alone is not enough either", r.returncode == 1 and L in r.stdout)
    r = guard(edit_frame, labels=L, ledger=True)
    check("a labelled, recorded change is accepted", r.returncode == 0, r.stdout)

    def edit_cfg():
        p = os.path.join(root, ".design-lock.json")
        c = json.load(open(p))
        c["tolerance"] = {"box": 9}
        json.dump(c, open(p, "w"))

    check("CI guard rejects a tolerance change in the config without label and ledger", guard(edit_cfg).returncode == 1)

    def edit_bl():
        json.dump({"home.dark": [{"element": "x", "property": "fill", "issue": "i"}]}, open(os.path.join(root, "design/baseline.json"), "w"))

    check("CI guard rejects an added baseline entry without label and ledger", guard(edit_bl).returncode == 1)

    def edit_unicode():
        open(os.path.join(root, "design/frames/home é.spec.json"), "w").write("{}")

    r = guard(edit_unicode)
    check("a frame with a non-ASCII or spaced name is guarded", r.returncode == 1 and "home" in r.stdout, r.stdout)

    def rename_cfg():
        git(root, "mv", ".design-lock.json", ".design-lock.json.off")

    def rename_frame():
        git(root, "mv", "design/frames/home.dark.png", "app/home.png")

    r = guard(rename_cfg)
    check("renaming .design-lock.json away is a guarded change (no rename detection)", r.returncode == 1 and L in r.stdout, r.stdout)
    check("moving a locked frame image out of the locked path is guarded", guard(rename_frame).returncode == 1)
    check("... and passes only with label and ledger", guard(rename_cfg, labels=L, ledger=True).returncode == 0)

    def edit_golden():
        os.makedirs(os.path.join(root, "app/golden"), exist_ok=True)
        open(os.path.join(root, "app/golden/home.png"), "w").write("png")

    r = guard(edit_golden, gate_result="failure")
    check("CI guard refuses updated goldens while the design check fails", r.returncode == 1 and "never re-recorded" in r.stdout, r.stdout)
    check("... and a label plus ledger entry does not excuse that", guard(edit_golden, labels=L, ledger=True, gate_result="failure").returncode == 1)
    check("CI guard accepts updated goldens when the design check passes", guard(edit_golden, gate_result="success").returncode == 0)
    # adoption
    top = os.path.join(tmp, "adopt")
    os.makedirs(top)
    open(os.path.join(top, "README"), "w").write("x")
    git(top, "init", "-q", "-b", "master")
    git(top, "add", "-A")
    git(top, "commit", "-qm", "base")
    base = git(top, "rev-parse", "HEAD").stdout.strip()
    shutil.copy(os.path.join(root, ".design-lock.json"), top)
    git(top, "add", "-Af")
    git(top, "commit", "-qm", "adopt")
    check("adopting design-lock (no config on the base) is left to my review", sh([sys.executable, os.path.join(SCRIPTS, "guard.py")], top, env={"BASE_SHA": base, "LABELS": ""}).returncode == 0)


# ---------------------------------------------------------------- init, CI workflow template

def load_yaml(path):
    try:
        import yaml
        return yaml.safe_load(open(path))
    except ImportError:
        return json.loads(subprocess.run(["yq", "-o=json", ".", path], capture_output=True, text=True, check=True).stdout)


def init_and_ci_tests(tmp):
    yml = open(os.path.join(SKILL, "templates/design-lock.yml")).read()
    check("the workflow reruns when the label is added or removed", all(t in yml for t in ("labeled", "unlabeled", "synchronize", "reopened")))
    check("approval is bound to a commit: a push removes the label", "--remove-label" in yml and "synchronize" in yml)
    check("the workflow judges the PR with tooling from the BASE commit (pull_request_target, base/ copy, not pr/)",
          "pull_request_target" in yml and "../base/tools/design-lock/designlock.py" in yml and "../base/tools/design-lock/guard.py" in yml and "base.sha" in yml)
    check("design-ok is the single required check and fails on skipped jobs", "design-ok" in yml and '"$GATE" = success' in yml)
    wf = load_yaml(os.path.join(SKILL, "templates/design-lock.yml"))
    on = wf.get("on", wf.get(True))
    jobs = wf["jobs"]
    steps = lambda j: [st for st in jobs[j]["steps"]]  # noqa: E731
    check("triggers are pull_request_target with the five types, merge_group and push", set(on["pull_request_target"]["types"]) == {"opened", "synchronize", "reopened", "labeled", "unlabeled"}
          and "merge_group" in on and "push" in on, str(on))
    check("the gate runs the BASE engine on the PR checkout; the guard runs the BASE guard", any("../base/tools/design-lock/designlock.py gate" in st.get("run", "") and st.get("working-directory") == "pr" for st in steps("gate"))
          and any("../base/tools/design-lock/guard.py" in st.get("run", "") and st.get("working-directory") == "pr" for st in steps("guard")))
    check("design-ok needs gate and guard and runs always", set(jobs["design-ok"]["needs"]) == {"gate", "guard"} and "always()" in jobs["design-ok"]["if"] and jobs["guard"]["needs"] == "gate")
    check("the gate job has read-only contents and no secrets are referenced", wf["permissions"] == {"contents": "read"} and "secrets." not in yml)
    uses = [st["uses"] for j in jobs for st in jobs[j]["steps"] if "uses" in st]
    check("every action is pinned to a full commit SHA", uses and all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u.split(" ")[0]) for u in uses), str(uses))
    check("other labels do not rerun the gate or cancel a real run (condition + separate concurrency group)", "design:approved-change" in jobs["gate"]["if"]
          and "other-label" in wf["concurrency"]["group"] and "design:approved-change" in jobs["design-ok"]["if"])
    check("merge_group events read their base and head shas", "merge_group.head_sha" in yml and "merge_group.base_sha" in yml)
    for plat in ("web", "android", "ios", "flutter", "desktop", "command"):
        d = os.path.join(tmp, "init-" + plat)
        os.makedirs(d)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "designlock.py"), "init", "--platform", plat, "--dir", d], capture_output=True, text=True)
        files = [".design-lock.json", "tools/design-lock/designlock.py", "tools/design-lock/capture.sh", ".github/workflows/design-lock.yml", "design/baseline.json", "design/changes.json"]
        ok = r.returncode == 0 and all(os.path.exists(os.path.join(d, f)) for f in files)
        try:
            cfg = dlcore.load_config(d)
        except Exception as e:  # noqa: BLE001
            cfg, ok = None, False
            r.stderr += str(e)
        check(f"init scaffolds a valid {plat} project", ok and cfg["platform"] == plat, r.stderr)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "designlock.py"), "init", "--platform", "web", "--dir", os.path.join(tmp, "init-web")], capture_output=True, text=True)
    check("init refuses to overwrite an existing setup", r.returncode == 2)
    d2 = os.path.join(tmp, "init-msg")
    os.makedirs(d2)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "designlock.py"), "init", "--platform", "android", "--dir", d2], capture_output=True, text=True)
    check("init says the hooks are advisory, that design-ok must be required, and that .design-lock.json is a dotfile", "advisory" in r.stdout and "design-ok" in r.stdout and ".design-lock.json" in r.stdout, r.stdout)
    fb = {p: json.load(open(os.path.join(tmp, f"init-{p}", ".design-lock.json"))).get("forbidCommands") for p in ("web", "android", "ios", "flutter")}
    check("init seeds forbidCommands per platform (golden re-record commands)", all(fb.values()) and "--update-goldens" in fb["flutter"] and "recordRoborazzi" in fb["android"], str(fb))
    skill_md = open(os.path.join(SKILL, "SKILL.md")).read()
    readme = open(os.path.join(SKILL, "README.md")).read()
    check("SKILL.md and README say that local hooks are guardrails, CI with branch protection is the guarantee, managed settings the optional hard local one",
          all(t in skill_md for t in ("guardrails", "design-ok")) and "allowManagedHooksOnly" in readme)
    check("README carries the map format, data-dl-role, --root and --screenshot", all(t in readme for t in ('"selector"', "data-dl-role", "--root", "--screenshot", "ignore")))
    check("the README states that capture runs the PR's code, and where `ui` is the trigger and cache key", "PR code" in readme and "trigger and cache key" in readme)
    d = os.path.join(tmp, "init-web")
    r = subprocess.run([sys.executable, os.path.join(d, "tools/design-lock/designlock.py"), "gate", "--root", d, "--no-capture"], capture_output=True, text=True)
    check("a freshly initialised project gate fails cleanly until I supply frames", r.returncode == 1 and "missing" in r.stdout, r.stdout[-200:] + r.stderr[-200:])


# ---------------------------------------------------------------- pixel mode (generic "a command writes a PNG")

def pixel_tests(tmp):
    d = os.path.join(tmp, "pix")
    os.makedirs(os.path.join(d, "design/frames"))
    os.makedirs(os.path.join(d, "build/design-lock/measured"))
    spec = {"schema": "design-lock/1", "kind": "spec", "frame": "p", "theme": "light", "viewport": {"width": 60, "height": 100},
            "elements": [{"id": "price", "role": "text", "variable": True, "box": {"x": 10, "y": 10, "w": 20, "h": 10}}]}
    json.dump(spec, open(os.path.join(d, "design/frames/p.spec.json"), "w"))
    base = [(0, 40, 60, 60, (200, 50, 50))]
    png(os.path.join(d, "design/frames/p.png"), 60, 100, rects=base)
    json.dump({"version": 1, "screens": {"p": {"frame": "design/frames/p.spec.json", "image": "design/frames/p.png", "measured": "build/design-lock/measured/p.png", "mode": "pixel"}}},
              open(os.path.join(d, ".design-lock.json"), "w"))
    run = lambda: subprocess.run([sys.executable, os.path.join(SCRIPTS, "designlock.py"), "gate", "--root", d], capture_output=True, text=True)  # noqa: E731
    m = os.path.join(d, "build/design-lock/measured/p.png")
    png(m, 60, 100, rects=base)
    check("pixel mode: an identical capture passes", run().returncode == 0)
    png(m, 60, 100, rects=base + [(12, 12, 28, 18, (255, 255, 255))])
    check("pixel mode: a different variable slot (masked) passes", run().returncode == 0)
    png(m, 60, 100, rects=[(0, 40, 60, 60, (200, 50, 50)), (0, 70, 60, 90, (255, 255, 255))])
    r = run()
    check("pixel mode: a different constant region fails and says where", r.returncode == 1 and "pixels" in r.stdout and "y 70-89" in r.stdout, r.stdout[-300:])
    png(m, 50, 100)
    check("pixel mode: a capture of another size fails", run().returncode == 1)
    # a small wrong element on a phone-sized screen must not fit under a global budget
    big = os.path.join(tmp, "pixbig")
    os.makedirs(os.path.join(big, "design/frames"))
    os.makedirs(os.path.join(big, "build/design-lock/measured"))
    json.dump({"schema": "design-lock/1", "kind": "spec", "frame": "b", "theme": "light", "viewport": {"width": 1080, "height": 2400},
               "elements": [{"id": "x", "role": "image", "variable": True, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}, open(os.path.join(big, "design/frames/b.spec.json"), "w"))
    png(os.path.join(big, "design/frames/b.png"), 1080, 2400)
    json.dump({"version": 1, "screens": {"b": {"frame": "design/frames/b.spec.json", "image": "design/frames/b.png", "measured": "build/design-lock/measured/b.png", "mode": "pixel"}}},
              open(os.path.join(big, ".design-lock.json"), "w"))
    runb = lambda: subprocess.run([sys.executable, os.path.join(SCRIPTS, "designlock.py"), "gate", "--root", big], capture_output=True, text=True)  # noqa: E731
    mb = os.path.join(big, "build/design-lock/measured/b.png")
    png(mb, 1080, 2400, rects=[(500, 1000, 540, 1040, (255, 0, 0))])
    r = runb()
    check("a wrong 40x40 element on a 1080x2400 screen (0.06% of the pixels) fails in pixel mode", r.returncode == 1 and "worst block" in r.stdout, r.stdout[-300:])
    png(mb, 1080, 2400, rects=[(x, y, x + 1, y + 1, (255, 0, 0)) for x in range(100, 1000, 100) for y in range(100, 2300, 100)])
    check("... while scattered single-pixel noise (anti-aliasing) still passes", runb().returncode == 0)
    spec["elements"][0]["variable"] = False
    json.dump(spec, open(os.path.join(d, "design/frames/p.spec.json"), "w"))
    png(m, 60, 100, rects=base)
    check("pixel mode: a spec may list only variable regions (no blanket constants hidden as masks)", run().returncode == 1)


# ---------------------------------------------------------------- web (needs Playwright)

def web_tests(tmp, env):
    dl = [sys.executable, os.path.join(SCRIPTS, "designlock.py")]

    def extract(page, theme, name, root=".screen", extra=()):
        out = os.path.join(tmp, name + ".json")
        r = subprocess.run(dl + ["extract-web", "--file", page, "--root", root, "--theme", theme, "--out", out, *extra], capture_output=True, text=True)
        return r, out

    def spec_of(theme):
        out = os.path.join(tmp, f"web-spec.{theme}.json")
        r = subprocess.run(dl + ["extract-web", "--file", os.path.join(FIX, "mock.html"), "--map", os.path.join(FIX, "map.json"), "--theme", theme, "--kind", "spec", "--name", f"home.{theme}", "--out", out],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return out

    def compare(frame, measured_file, *extra):
        res = measured_file + ".result.json"
        r = subprocess.run(dl + ["compare", frame, measured_file, "--json", res, *extra], capture_output=True, text=True)
        return r, (json.load(open(res)) if os.path.exists(res) else None)

    def page(name, edit):
        p = os.path.join(tmp, name + ".html")
        open(p, "w").write(edit(open(os.path.join(FIX, "app-match.html")).read()))
        return p

    dark, light = spec_of("dark"), spec_of("light")
    r, m_ok = extract(os.path.join(FIX, "app-match.html"), "dark", "w-match")
    r, res = compare(dark, m_ok)
    check("web: compare passes on the matching page, variables with different content included", r.returncode == 0 and res["pass"], r.stdout[-600:])
    r, m_bad = extract(os.path.join(FIX, "app-deviate.html"), "dark", "w-dev")
    r, res = compare(dark, m_bad)
    check("web: compare fails on the deviating page and prints the table", r.returncode == 1 and fails(res["rows"]) == {("title", "box.x"), ("row", "fill"), ("sym", "font.size")} and "**FAIL**" in r.stdout, str(fails(res["rows"])))
    r, res = compare(light, extract(os.path.join(FIX, "app-deviate.html"), "light", "w-dev-l")[1])
    check("web: a deviation only in dark is caught only in dark", r.returncode == 0)
    r, res = compare(dark, m_bad, "--tolerance", "box=2,fontSize=1")
    check("web: a wide tolerance hides box and font-size deviations, so the config must be locked", {x["element"] for x in res["rows"] if x["status"] == "fail"} == {"row"})
    r, res = compare(dark, extract(page("w-vf", lambda s: s.replace("</style>", ".price{letter-spacing:1px}</style>")), "dark", "w-vf")[1])
    check("web: a variable's font is a constant (letter spacing of the price slot)", ("price", "font.letterSpacing") in fails(res["rows"]))
    r, res = compare(dark, extract(page("w-x", lambda s: s.replace("</div>\n", '</div><div style="position:absolute;left:10px;top:700px;width:50px;height:50px;background:red"></div>\n', 1)), "dark", "w-x")[1])
    check("web: an untagged painted element fails (unmapped)", any(x["property"] == "unmapped" for x in res["rows"]))
    r, res = compare(dark, extract(page("w-m", lambda s: s.replace('data-dl-id="sym" data-dl-variable', "")), "dark", "w-m")[1])
    check("web: a missing element fails", ("sym", "presence") in fails(res["rows"]))
    r, res = compare(dark, extract(page("w-g", lambda s: s.replace("</style>", ".row{background-image:linear-gradient(#f00,#00f)}</style>")), "dark", "w-g")[1])
    check("web: a gradient on a container fails", ("row", "backgroundImage") in fails(res["rows"]))
    r, res = compare(dark, extract(page("w-b", lambda s: s.replace("</style>", ".row{border-bottom-width:4px}</style>")), "dark", "w-b")[1])
    check("web: one thicker border side fails", ("row", "border") in fails(res["rows"]))
    r, res = compare(dark, extract(page("w-d", lambda s: s.replace("</style>", ".title{text-decoration:underline}</style>")), "dark", "w-d")[1])
    check("web: text-decoration fails", ("title", "font.decoration") in fails(res["rows"]))
    r, res = compare(dark, extract(page("w-p", lambda s: s.replace("</style>", '.row::after{content:"";position:absolute;inset:0;background:#f00}</style>')), "dark", "w-p")[1])
    check("web: a painted pseudo-element is unmapped and fails", any(x["property"] == "unmapped" and x["frame"] != "" for x in res["rows"]))
    ok1 = extract(page("w-o1", lambda s: s.replace("</style>", ".title{color:oklch(0.2 0.05 250)}</style>")), "dark", "w-o1")
    ok2 = extract(page("w-o2", lambda s: s.replace("</style>", ".title{color:oklch(0.4 0.05 250)}</style>")), "dark", "w-o2")
    sp = os.path.join(tmp, "w-oklch-spec.json")
    shutil.copy(ok1[1], sp)
    d = json.load(open(sp))
    d["kind"] = "spec"
    json.dump(d, open(sp, "w"))
    r, res = compare(sp, ok1[1])
    r2, res2 = compare(sp, ok2[1])
    check("web: oklch() colours are normalised, so two different oklch colours differ and equal ones pass", r.returncode == 0 and ("title", "color") in fails(res2["rows"]), str(fails(res2["rows"])))
    for what, css in (("text-shadow", ".title{text-shadow:0 1px 2px #000}"), ("font-variant-numeric", ".price{font-variant-numeric:tabular-nums}"), ("mix-blend-mode", ".row{mix-blend-mode:multiply}"),
                      ("backdrop-filter", ".row{backdrop-filter:blur(4px)}"), ("text-indent", ".title{text-indent:6px}")):
        r, res = compare(dark, extract(page("w-n5", lambda s, c=css: s.replace("</style>", c + "</style>")), "dark", "w-n5")[1])
        check(f"web: {what} that the frame lacks fails", any(p in ("textShadow", "font.variantNumeric", "blendMode", "backdropFilter", "font.indent") for _, p in fails(res["rows"])), str(fails(res["rows"])))
    r, res = compare(dark, extract(page("w-n5s", lambda s: s.replace(">Markets<", '><span style="font-weight:900;color:red">Mark</span>ets<')), "dark", "w-n5s")[1])
    check("web: a differently styled <span> inside a tagged text element is no longer hidden by its parent", any(x["property"] == "unmapped" for x in res["rows"]), str(fails(res["rows"])))
    r, res = compare(dark, extract(page("w-n5p", lambda s: s.replace(">Markets<", '><i style="display:inline-block;width:8px;height:8px;background:red"></i>Markets<')), "dark", "w-n5p")[1])
    check("web: a painted element inside a tagged text element is unmapped", any(x["property"] == "unmapped" for x in res["rows"]))
    r = subprocess.run(dl + ["extract-web", "--file", os.path.join(FIX, "app-match.html"), "--root", ".screen", "--kind", "spec", "--out", os.path.join(tmp, "spec-var-container.json"),
                             "--map", os.path.join(tmp, "var-container-map.json")], capture_output=True, text=True)
    mp = json.load(open(os.path.join(FIX, "map.json")))
    mp["elements"][3]["variable"] = True  # `row` is a container
    json.dump(mp, open(os.path.join(tmp, "var-container-map.json"), "w"))
    r = subprocess.run(dl + ["extract-web", "--file", os.path.join(FIX, "mock.html"), "--map", os.path.join(tmp, "var-container-map.json"), "--kind", "spec", "--out", os.path.join(tmp, "spec-var-container.json")], capture_output=True, text=True)
    check("extract-web refuses to write a spec with a variable container, and hints at the role", r.returncode == 2 and "cannot be variable" in r.stderr and "role" in r.stderr, r.stderr[-300:])
    bad_map = os.path.join(tmp, "bad-map.json")
    m = json.load(open(os.path.join(FIX, "map.json")))
    m["ignore"] = [".row"]
    json.dump(m, open(bad_map, "w"))
    r = subprocess.run(dl + ["extract-web", "--file", os.path.join(FIX, "mock.html"), "--map", bad_map, "--out", os.path.join(tmp, "x.json")], capture_output=True, text=True)
    check("web: ignoring a region needs a stated reason", r.returncode == 2 and "reason" in r.stderr)
    # end to end in a scratch web repo: a UI edit leaves Stop blocked until the gate passes
    repo = os.path.join(tmp, "webrepo")
    for sub in ("tools/design-lock", "design/frames", "app"):
        os.makedirs(os.path.join(repo, sub))
    for f in ("dlcore.py", "designlock.py"):
        shutil.copy(os.path.join(SCRIPTS, f), os.path.join(repo, "tools/design-lock", f))
    shutil.copy(os.path.join(FIX, "app-match.html"), os.path.join(repo, "app/screen.html"))
    cap = "".join(f"python3 tools/design-lock/designlock.py extract-web --file app/screen.html --root .screen --theme {t} --out build/design-lock/measured/home.{t}.json || exit 2\n" for t in ("dark", "light"))
    open(os.path.join(repo, "tools/design-lock/capture.sh"), "w").write(cap)
    for t, sp_ in (("dark", dark), ("light", light)):
        shutil.copy(sp_, os.path.join(repo, f"design/frames/home.{t}.spec.json"))
        png(os.path.join(repo, f"design/frames/home.{t}.png"), 4, 4)
    json.dump({"version": 1, "platform": "web", "ui": ["app/**/*.html"], "capture": "sh tools/design-lock/capture.sh", "gateTimeoutSec": 120, "locked": ["tools/design-lock/**"],
               "screens": {f"home.{t}": {"frame": f"design/frames/home.{t}.spec.json", "image": f"design/frames/home.{t}.png", "measured": f"build/design-lock/measured/home.{t}.json"} for t in ("dark", "light")}},
              open(os.path.join(repo, ".design-lock.json"), "w"))
    open(os.path.join(repo, ".gitignore"), "w").write("build/\n")
    git(repo, "init", "-q", "-b", "master")
    git(repo, "add", "-A")
    git(repo, "add", "-f", ".design-lock.json")
    git(repo, "commit", "-qm", "base")
    shutil.copy(os.path.join(FIX, "app-deviate.html"), os.path.join(repo, "app/screen.html"))
    hook("pretool", {"tool_name": "Write", "session_id": "w1", "tool_input": {"file_path": os.path.join(repo, "app/screen.html"), "content": "x"}}, repo, env)
    out = hook("stop", {"hook_event_name": "Stop", "session_id": "w1"}, repo, env)[1]
    check("web e2e: a UI edit leaves Stop blocked, naming the elements", blocked(out) and "title" in out["reason"] and "box.x" in out["reason"], str(out)[:400])
    shutil.copy(os.path.join(FIX, "app-match.html"), os.path.join(repo, "app/screen.html"))
    out = hook("stop", {"hook_event_name": "Stop", "session_id": "w1"}, repo, env)[1]
    check("web e2e: after the app matches the frame again, Stop passes", out is None, str(out)[:400])


if __name__ == "__main__":
    sys.exit(main())
