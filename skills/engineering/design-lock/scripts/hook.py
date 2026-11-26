#!/usr/bin/env python3
"""Claude Code hooks for design-lock. `hook.py stop` serves Stop and SubagentStop; `hook.py pretool` serves PreToolUse.

Every mode is a silent no-op (no output, no subprocess, one directory walk) in a directory tree without .design-lock.json.
stop:    when this session (or this subagent) edited UI files, or the work tree has uncommitted UI changes, run the project's gate and
         block the stop while it fails. A tree already proven green is not re-gated.
pretool: deny writes to the project's locked design files (frames, config, ledger, tolerances, ...) and remember UI edits for `stop`.
The hooks never guard themselves or the settings files: the hard guarantee is the CI check, not this script.
Internal errors never crash a session: stop fails closed only once the project's config was found; pretool warns and allows.
"""
import fcntl
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dlcore  # noqa: E402

MAX_BLOCKS = int(os.environ.get("DESIGN_LOCK_MAX_BLOCKS", "3"))
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.claude/state"), "design-lock")
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# An MCP tool is checked when its name says it writes (a false deny hurts every project, CI is the hard guarantee); shell-like tools get their command parsed.
_W = "write|edit|create|delete|remove|rename|move|replace|insert|append|copy|set|put|upload|save|touch|truncate|patch|apply"
_SNAKE = re.compile(rf"(?:^|[_-])(?:{_W})", re.I)
_CAMEL = re.compile(rf"(?<=[a-z])(?:{_W.title().replace('|', '|')})")  # writeFile, createTextFile: capital letter starts the verb


class MCP_WRITE:  # noqa: N801 - keeps the `.search` interface of a compiled regex
    search = staticmethod(lambda name: _SNAKE.search(name) or _CAMEL.search(name))


MCP_SHELL = re.compile(r"shell|exec|command|run|bash|terminal|script|eval", re.I)
BUDGET = int(os.environ.get("DESIGN_LOCK_HOOK_BUDGET", "880"))  # seconds the Stop hook may use; the registered hook timeout is 900


def out(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def owner_change():
    """The owner starts a session with DESIGN_LOCK_CHANGE='<why>' when the design itself must change; CI still requires the label and ledger entry."""
    return bool(os.environ.get("DESIGN_LOCK_CHANGE", "").strip())


# ---------------------------------------------------------------- state (block counters, edit markers, green cache)

def state_file(*parts):
    os.makedirs(STATE, exist_ok=True)
    return os.path.join(STATE, re.sub(r"\W", "_", "-".join(parts)))


def root_key(root):
    return hashlib.sha1(os.path.realpath(root).encode()).hexdigest()[:12]


def gc_state(days=3):
    for f in os.listdir(STATE) if os.path.isdir(STATE) else []:
        p = os.path.join(STATE, f)
        if time.time() - os.path.getmtime(p) > days * 86400:
            os.remove(p)


def remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def read(p):
    try:
        return open(p).read()
    except OSError:
        return ""


def ids(data):
    return str(data.get("session_id") or "x"), str(data.get("agent_id") or "")


def note_edit(data, root):
    """Remember that this session (and subagent) edited a UI or locked file, so its Stop runs the gate."""
    sid, aid = ids(data)
    rk = root_key(root)
    for p in [state_file("touch", rk, sid)] + ([state_file("touch", rk, sid, aid)] if aid else []):
        open(p, "a").close()


# ---------------------------------------------------------------- stop

def block_or_release(data, reason):
    """Block the stop, but only MAX_BLOCKS times in a row per session and agent, so a gate nobody can satisfy cannot loop forever."""
    p = state_file("blocks", *ids(data))
    n = int(read(p) or 0)
    if n >= MAX_BLOCKS:
        remove(p)
        out({"systemMessage": f"design-lock: the design gate still fails after {n} blocks; stopping anyway. CI will reject this change.\n{reason}"})
        return
    open(p, "w").write(str(n + 1))
    out({"decision": "block", "reason": f"[block {n + 1} of {MAX_BLOCKS}] {reason}"})


def run_gate(cfg, root, limit):
    cmd = cfg.get("gate") or f"{shlex.quote(sys.executable)} {shlex.quote(os.path.join(HERE, 'designlock.py'))} gate --root {shlex.quote(root)}"
    p = subprocess.Popen(cmd, shell=True, cwd=root, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        text, _ = p.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        for sig in (signal.SIGTERM, signal.SIGKILL):  # TERM: the gate takes its capture's own process group down; KILL: everything left in ours
            try:
                os.killpg(p.pid, sig)
            except OSError:  # the group is already gone (macOS reports a zombie leader as EPERM)
                pass
            if sig == signal.SIGTERM:
                time.sleep(1)
        p.communicate()
        return False, f"the gate did not finish in {limit} s"
    return p.returncode == 0, text.strip()


def locked(path, deadline):
    """An exclusive lock on `path`, waiting at most until `deadline` (concurrent subagents share one build dir). None when it timed out."""
    fh = open(path, "w")
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if time.time() > deadline:
                fh.close()
                return None
            time.sleep(0.3)


def stop(data, root):
    cfg = dlcore.load_config(root)
    sid, aid = ids(data)
    rk = root_key(root)
    counter = state_file("blocks", sid, aid)
    marker = state_file("touch", rk, sid, aid) if aid else state_file("touch", rk, sid)
    pats = dlcore.triggers(cfg)
    need = os.path.exists(marker)
    if not need and not aid:  # a subagent is judged only by its own edits; the main session also by the work tree
        dirty = dlcore.dirty_files(root)
        need = bool(dirty) and any(dlcore.matches(f, pats) for f in dirty)
    if not need:
        remove(counter)
        return
    digest = dlcore.tree_digest(root, pats)
    green, red = state_file("green", rk), state_file("red", rk)
    start = time.time()
    lock = locked(state_file("lock", rk), start + BUDGET - 60)  # one gate at a time; the waiters then find its result cached
    if lock is None:
        return block_or_release(data, "another agent's design gate is still running; the budget of this hook ran out while waiting. Try finishing again.")
    try:
        cached = json.loads(read(red) or "{}")
        if read(green) == digest:
            ok, text = True, ""
        elif cached.get("digest") == digest:  # the same failing tree is not captured again, by this block, the next turn or another agent
            ok, text = False, cached["text"]
        else:
            limit = int(min(min(int(cfg.get("gateTimeoutSec", 600)), 840) + 10, BUDGET - (time.time() - start) - 10))
            ok, text = run_gate(cfg, root, limit)
            if ok:
                open(green, "w").write(digest)
                remove(red)
            else:
                open(red, "w").write(json.dumps({"digest": digest, "text": text}))
    finally:
        lock.close()
    if ok:
        remove(counter)
        remove(marker)
        return
    tail = "\n".join(text.splitlines()[-60:])
    block_or_release(data, (
        f"DESIGN GATE FAILED. Work is not done until it is green; passing tests do not count.\n{tail}\n\n"
        "Fix the app so every listed element matches its approved frame. Do not edit frames, tolerances, exceptions or the baseline, "
        "and do not re-record goldens or snapshots over a failing design check. If the design itself must change, stop and tell the owner."))


# ---------------------------------------------------------------- pretool

def deny(reason):
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "design-lock: " + reason}})


LOCKED_WHY = ("approved frames, specs, tolerances, exceptions and the design-lock setup change only when the owner asks for it (a recorded change request), "
              "never to make a screen pass. Fix the app to match the frame instead; if the design itself is wrong, stop and tell the owner.")


def literal_prefix(pattern):
    return re.split(r"[*?]", pattern, 1)[0]


def check_path(data, path, how="write", content=None):
    """Deny when `path` is a locked design file of the project that owns it. `how`: write | destroy (also guards directories that hold locked files).
    `content` is the file text after the edit, when known (to allow baseline removals). Returns True when it denied."""
    ap = os.path.realpath(path)
    root = dlcore.find_root(os.path.dirname(ap) if not os.path.isdir(ap) else ap)
    if not root:
        return False
    cfg = dlcore.load_config(root)
    rel = os.path.relpath(ap, os.path.realpath(root))
    if rel.startswith(".."):
        return False
    fold = dlcore.case_insensitive(root)  # `Design/Frames/x` is the locked `design/frames/x` on a case-insensitive volume
    low = (lambda t: t.lower()) if fold else (lambda t: t)
    if dlcore.matches(rel, dlcore.triggers(cfg), fold):
        note_edit(data, root)
    if owner_change():
        return False
    prot = dlcore.protected(cfg)
    hit = dlcore.matches(rel, prot, fold) or (how == "destroy" and (rel == "." or any(low(literal_prefix(p)).startswith(low(rel).rstrip("/") + "/") for p in prot)))
    if hit:
        deny(f"{rel} is locked: {LOCKED_WHY}")
        return True
    if low(rel) == low(dlcore.baseline_path(cfg)):
        try:
            grew = dlcore.baseline_grew(json.loads(read(ap) or "{}"), json.loads(content)) if content is not None else ["only the Edit tool may change the baseline"]
        except ValueError:
            grew = ["the baseline would not be valid JSON"]
        if grew:
            deny(f"{rel} may only shrink (fixed known violations are removed, none are added or edited): {'; '.join(grew[:3])}")
            return True
    return False


def new_content(tool, ti, path):
    """The file text after an Edit, MultiEdit or Write, or None when it cannot be worked out."""
    if tool == "Write":
        return ti.get("content", "")
    text = read(path)
    for e in (ti.get("edits") if tool == "MultiEdit" else [ti]) or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old not in text:
            return None
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


# Inline interpreter code: only the paths it explicitly opens for writing count, so reading a frame in `python -c` is never denied.
INLINE = re.compile(r"(?:^|[\s;&|(])(?:python[\d.]*|node|ruby|perl|php|deno|bun)\b[^\n]*(?:<<|\s-[ce]\s|\s-\s*(?:$|\n))")
INLINE_WRITES = [re.compile(p) for p in (
    r"""open\(\s*(['"])([^'"\n]+)\1\s*,\s*(['"])[^'"]*[wax+][^'"]*\3""",
    r"""Path\(\s*(['"])([^'"\n]+)\1\s*\)\s*\.\s*(?:write_text|write_bytes|unlink|rename|replace|touch)""",
    r"""(?:writeFile|appendFile|rename|unlink|rm|copyFile|truncate)(?:Sync)?\(\s*(['"`])([^'"`\n]+)\1""",
    r"""os\.(?:remove|unlink|rename|replace|truncate)\(\s*(['"])([^'"\n]+)\1""",
    r"""shutil\.(?:copy\w*|move|rmtree)\([^)\n]*(['"])([^'"\n]+)\1\s*\)""",
)]
DEST_ONLY = {"cp", "rsync", "install", "ln"}
ALL_ARGS = {"mv", "tee", "chmod", "chown", "truncate", "touch", "patch", "unlink", "rmdir", "shred"}
WRAPPERS = {"sudo", "command", "env", "nohup", "time", "exec", "builtin"}
GIT_PATHS = {"checkout", "restore", "rm", "mv", "clean"}


def tokens(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";<>|&()\n")
    lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
    return list(lex)


def strip_heredocs(cmd):
    return re.sub(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n)(.*?)(\n\s*\3\b)", lambda m: m.group(1) + m.group(5).lstrip("\n"), cmd, flags=re.S)


def patch_targets(path):
    """Files a patch file touches (`+++ b/path` lines), for `git apply`."""
    return [m.group(1) for m in re.finditer(r"^\+\+\+ (?:[ab]/)?(\S+)", read(path), re.M)]


def written_paths(cmd, cwd, depth=0):
    """[(absolute path, how)] a shell command writes or destroys, as far as its text shows. A heuristic: the CI guard is the authority."""
    found = []
    if INLINE.search(cmd):
        for rx in INLINE_WRITES:
            found += [(os.path.join(cwd, os.path.expanduser(m.group(2))), "write") for m in rx.finditer(cmd)]
    try:
        toks = tokens(strip_heredocs(cmd))
    except ValueError:
        return found
    cur, seg, i = cwd, [], 0

    def end(seg):
        nonlocal cur
        words = list(seg)
        while words and (re.match(r"^\w+=", words[0]) or words[0] in WRAPPERS):
            words.pop(0)
        if not words:
            return
        first, args = os.path.basename(words[0]), words[1:]
        paths = [t for t in args if not t.startswith("-")]
        add = lambda ps, how="write": found.extend((os.path.join(cur, os.path.expanduser(p)), how) for p in ps)  # noqa: E731
        if first in ("cd", "pushd") and paths:
            cur = os.path.join(cur, os.path.expanduser(paths[0]))
        elif first in ("sh", "bash", "zsh") and "-c" in args and args.index("-c") + 1 < len(args) and depth < 3:
            found.extend(written_paths(args[args.index("-c") + 1], cur, depth + 1))
        elif first in DEST_ONLY:
            add(paths[-1:])
        elif first == "rm":
            add(paths, "destroy")
        elif first == "mv":
            add(paths[:-1], "destroy")
            add(paths[-1:])
        elif first in ALL_ARGS:
            add(paths)
        elif first in ("sed", "perl") and any(re.match(r"^-[a-zA-Z]*i|^--in-place", t) for t in args):
            add(paths)
        elif first == "awk" and "inplace" in args:
            add(paths)
        elif first == "dd":
            add([t[3:] for t in args if t.startswith("of=")])
        elif first == "git":
            while args[:1] == ["-C"] and len(args) > 1:
                cur, args = os.path.join(cur, os.path.expanduser(args[1])), args[2:]
            sub = next((t for t in args if not t.startswith("-")), "")
            rest = args[args.index(sub) + 1:] if sub else []
            if sub in GIT_PATHS:  # explicit locked files only: `git restore .` or `git checkout design` restore the approved state, they do not damage it
                add([t for t in rest if not t.startswith("-")])
            elif sub in ("apply", "am"):
                for t in rest:
                    if not t.startswith("-"):
                        add(patch_targets(os.path.join(cur, t)))

    while i < len(toks):
        t = toks[i]
        if set(t) <= set(";|&\n()"):
            end(seg)
            seg = []
        elif set(t) <= set("<"):
            i += 1  # `< file` and heredoc markers read; their operand is not a write
        elif ">" in t and set(t) <= set("<>&|"):
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if not (t.endswith("&") and t != "&>" and re.fullmatch(r"\d+|-", nxt)):
                found.append((os.path.join(cur, os.path.expanduser(nxt)), "write"))
            i += 1
        else:
            seg.append(t)
        i += 1
    end(seg)
    return found


def bash(data, ti, cwd):
    cmd = ti.get("command")
    if not isinstance(cmd, str):
        return
    root = dlcore.find_root(cwd)
    if root:
        for pat in dlcore.load_config(root).get("forbidCommands", []):
            if re.search(pat, cmd):
                return deny(f"the command matches forbidCommands ({pat}). Goldens and snapshots are never re-recorded over a failing design check; the owner or CI does it.")
    for path, how in written_paths(cmd, cwd):  # each target finds its own project, so a command run from another directory is checked too
        if check_path(data, path, how):
            return


def mcp_write(data, ti, cwd, tool):
    """Any MCP tool whose name says it writes (Serena's create_text_file, replace_content, execute_shell_command, ...) may write the files it names."""
    stack = [(None, ti)]
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            stack += list(v.items())
        elif isinstance(v, list):
            stack += [(k, x) for x in v]
        elif isinstance(v, str) and 0 < len(v) < 4096:
            if MCP_SHELL.search(tool) and k in ("command", "cmd", "script", "code"):
                for path, how in written_paths(v, cwd):
                    if check_path(data, path, how):
                        return
            elif "\n" not in v and len(v) < 1024 and check_path(data, os.path.join(cwd, os.path.expanduser(v)), "write", content=None):
                return


def pretool(data, cwd):
    tool, ti = str(data.get("tool_name", "")), data.get("tool_input")
    if not isinstance(ti, dict):
        return
    if tool in FILE_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path")
        if isinstance(path, str) and path:
            path = os.path.join(cwd, os.path.expanduser(path))
            check_path(data, path, "write", content=new_content(tool, ti, path))
    elif tool == "Bash":
        bash(data, ti, cwd)
    elif tool.startswith("mcp__") and (MCP_SHELL.search(tool.split("__")[-1]) or MCP_WRITE.search(tool.split("__")[-1])):
        mcp_write(data, ti, cwd, tool.split("__")[-1])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else os.getcwd()
    t0 = time.time()
    if mode == "stop":
        root = dlcore.find_root(cwd)
        if root:
            try:
                gc_state()
            except OSError:
                pass
            try:
                stop(data, root)
            except Exception as e:  # fail closed, for the design check only
                block_or_release(data, f"design-lock could not run the design check ({type(e).__name__}: {e}). Fix .design-lock.json or the gate command in {root}.")
    elif mode == "pretool":
        try:
            pretool(data, cwd)
        except Exception as e:
            out({"systemMessage": f"design-lock pretool hook error, allowing the call: {type(e).__name__}: {e}"})
    if os.environ.get("DESIGN_LOCK_DEBUG"):
        sys.stderr.write(f"design-lock {mode}: {int((time.time() - t0) * 1000)} ms\n")


if __name__ == "__main__":
    main()
