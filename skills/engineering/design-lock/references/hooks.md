# Hooks

Register them once in `~/.claude/settings.json`: `Stop` and `SubagentStop` run `python3 ~/.claude/skills/design-lock/scripts/hook.py stop` (timeout 900). `PreToolUse` with matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|mcp__.*` runs `... hook.py pretool` (timeout 10). Both are silent no-ops, with no subprocess, in a tree without `.design-lock.json`.

## PreToolUse

Denies Edit, Write, MultiEdit, NotebookEdit, shell writes, and MCP tools that target a protected path. It also records UI edits for the Stop hook.

- Every `mcp__*` tool is checked unless its name starts with a read verb (read, get, list, find, search, view, show, stat, query, ...). Tools named like a shell (shell, exec, command, run, bash, script) have their `command` or `cmd` argument parsed like a Bash command.
- The shell check parses redirects, `rm`, `mv`, `cp`, `tee`, `sed -i`, `perl -pi`, `awk -i inplace`, `dd of=`, `git checkout/restore/apply`, `cd x && ...`, `bash -c`, and inline python or node that opens a path for writing. It resolves targets wherever the command runs. It never denies reading a protected file, and it allows `git restore .` and `git checkout -- .` because they restore the approved state.
- Paths match case-insensitively on case-insensitive volumes.

## Stop and SubagentStop

Stop gates the main session when it edited UI files or the work tree has uncommitted UI changes. SubagentStop gates only a subagent that edited UI files.

- A tree already proven green, or already failed, is not captured again (cached by a content hash of the `ui` files, protected paths, and baseline). Concurrent gates share one lock. The gate runs in its own process group and is killed whole on timeout, within an 880 s budget.
- After `DESIGN_LOCK_MAX_BLOCKS` (default 3) consecutive blocks the stop is released with a loud message. CI is the backstop.
- The hook keys on the directory the session runs in. Edits to another project are enforced by that project's CI and by the Stop of a session started there.

## Changing the design

A session started with `DESIGN_LOCK_CHANGE="<why>"` may edit locked files. Only I start one. CI still requires the label and the ledger entry.

## Limits

The hooks, the skill scripts, and the settings files are deliberately unguarded: an agent that edits settings (`disableAllHooks`, the hook command, `DESIGN_LOCK_CHANGE` in `env`) switches the hooks off. For a hard local guarantee, install them in managed settings with `allowManagedHooksOnly`. The guarantee is the required CI check ([ci.md](ci.md)).

| Gap | Mitigation |
| :- | :- |
| A shell write the heuristic misses (paths built at run time, a script that writes) | The CI guard sees the diff |
| An agent runner that ignores Claude Code hooks | The required CI check |
| `bypassPermissions` | The hooks docs do not say whether PreToolUse hooks still run. Check per setup. CI covers it |
