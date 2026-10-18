---
name: noexec-rust
description: "Guide for building and testing Rust on hosts where scratch storage is mounted noexec. Use when: (1) cargo test fails with Permission denied (os error 13) or EACCES on a target path, (2) a build script or proc macro fails to run or load, (3) a test writes a helper binary or script into a temp directory, (4) the cargo target dir may sit under TMPDIR, (5) a check skips or early-returns because scratch may refuse execution."
---

# Rust where scratch storage is `noexec`

## Overview

`noexec` is a mount flag. It blocks `execve` of a file on that mount. It does not block read, write, or `chmod`. Rust needs execution at four points: the test binary, `build.rs`, doctests, and helper binaries the tests start. Proc-macro dylibs are a related case: `rustc` loads them with `dlopen`, which needs `mmap(PROT_EXEC)`, and `noexec` refuses that. All of these need a mount that allows execution. Scratch storage is `TMPDIR`, `/tmp`, `/dev/shm`, and any short-lived directory the code creates: fine for data, wrong for programs.

`cargo test` compiles, then starts the binary. On a `noexec` target dir the build succeeds and the start fails:

```text
error: could not execute process `/tmp/build/target/debug/deps/mycrate-3f2a1b` (never executed)

Caused by:
  Permission denied (os error 13)
```

The mode bits are `0755`. `chmod +x` does not help. The mount refuses the start. The `noexec-coding` skill covers the mount rules and the three-way probe.

## Process

- [ ] 1. Find every place the code starts a process. Look for `Command::new`, `assert_cmd`, `CARGO_BIN_EXE_`, and test helpers.
- [ ] 2. Check where each spawned file is written. `temp_dir()` or `TempDir::path()` is a defect for a program.
- [ ] 3. Probe the cargo target dir before the first build, with the snippet in Quick Reference.
- [ ] 4. Move the target dir to executable storage if the probe refuses. Set it in `.cargo/config.toml` so every cargo subcommand agrees.
- [ ] 5. Add `exec_dir()` to the test support module, returning `Result`. Change each helper spawn to use it, and keep data in `TempDir`.
- [ ] 6. Delete every `#[ignore]`, `cfg(not(...))`, and runtime return that exists for `noexec`.
- [ ] 7. Add one negative test: force the resolver to a refusing path, and assert the error, not a fallback.
- [ ] 8. Run the smallest affected test, and report if the host refused in scratch.

### Checklist before saying done

Answer from the diff. A "no" is a defect.

1. Where does every executable path come from? Cargo, `current_exe`, or a resolved directory, never `temp_dir()`.
2. What happens if scratch is `noexec`? The code fails with a clear message, or never puts a program there.
3. Does any test skip, ignore, or early-return because storage may refuse execution?
4. Does any config or CI file point `CARGO_TARGET_DIR` at `$TMPDIR`, or leave a `noexec` `TMPDIR` for doctests?

## Quick Reference

### Target directory probe

Probe by running a file. Do not read `mount` or trust mode bits.

```sh
probe_exec_dir() {
  d=$1
  [ -d "$d" ] || mkdir -p "$d" || { echo "UNPROBED: cannot create $d" >&2; return 2; }
  f="$d/.exec-probe-$$"
  printf '#!/bin/sh\nexit 0\n' > "$f" || { echo "UNPROBED: cannot write $f" >&2; return 2; }
  chmod 755 "$f"
  "$f" >/dev/null 2>&1
  rc=$?
  rm -f "$f"
  case $rc in
    0) return 0 ;;
    126) echo "REFUSED: $d is on a noexec mount" >&2; return 1 ;;
    *) echo "UNPROBED: direct run failed with $rc" >&2; return 2 ;;
  esac
}

probe_exec_dir "${CARGO_TARGET_DIR:-target}" ||
  { export CARGO_TARGET_DIR="$PWD/.cargo-target"; probe_exec_dir "$CARGO_TARGET_DIR" || exit 1; }
```

Set `TMPDIR` to executable storage too. Doctests run from `TMPDIR`, so a target dir alone does not fix them. Probe the path first; `/var/tmp` is only a guess until a probe says it runs.

```sh
export CARGO_TARGET_DIR="$PWD/.cargo-target"
probe_exec_dir "$CARGO_TARGET_DIR" || exit 1

candidate="${TMPDIR:-/var/tmp}"
if ! probe_exec_dir "$candidate"; then
  candidate="$PWD/.cargo-target"
  probe_exec_dir "$candidate" || exit 1
fi
export TMPDIR="$candidate"
```

### The `TMPDIR` rule

A data-only `TMPDIR` is acceptable. Anything that must execute must not live on `noexec` scratch: cargo and rustc artifacts, doctests, helper binaries, and spawn helpers.

In Rust, `TMPDIR` must be on executable storage, because doctests and `cargo install` build scripts run from it. In Python, a script runs through the interpreter, so a data-only `TMPDIR` is fine.

Never move `TMPDIR` to hide a defect. Move only the programs.

Keep three outcomes apart: runs, refused, unprobed. Merging them hides a defect.

### Build scripts and proc macros

`build.rs` is a binary that cargo compiles and starts from the target dir; on a `noexec` target dir the failure is "failed to run custom build command". A proc macro is a `.so` that `rustc` loads with `dlopen`; the loader needs `mmap(PROT_EXEC)`, and `noexec` refuses that, so the failure can be a load error rather than `EACCES`. One target dir on executable storage serves the compiler, every build script, and every proc-macro dylib. Do not split them.

### Doctests

`cargo test --doc` builds a test program and runs it from `TMPDIR`, not from the target dir. With a `noexec` `TMPDIR` it fails with "Couldn't run the test: Permission denied ... maybe your tempdir is mounted with noexec?". A correct `CARGO_TARGET_DIR` does not save it. Point `TMPDIR` at executable storage as well.

`cargo install` has the same problem: it runs build scripts from a temp directory. Set both `TMPDIR` and `CARGO_TARGET_DIR`.

### Test harness patterns

| Pattern | Safe? | Why |
| --- | --- | --- |
| `cargo test` starting its own binary | Yes | Cargo owns the target dir |
| `env!("CARGO_BIN_EXE_mytool")` | Yes | Cargo sets a path in the target dir |
| `assert_cmd::Command::cargo_bin` | Yes | Same source |
| `Command::new(tempdir.path().join("h"))` | No | Scratch path; start is refused |
| `Command::new("sh").arg(script_in_scratch)` | Yes | `sh` is exec'd elsewhere; the script is read |
| Unit test calling a function in process | Yes | No new process |

`CARGO_TARGET_DIR` and `CARGO_BUILD_TARGET_DIR` are cargo variables. `TARGET_DIR` is not one; check what a wrapper exports. `cargo nextest` inherits the rule. `cargo fuzz` builds into `fuzz/target`; keep it in the project tree. `proptest` and `quickcheck` write files and never execute them, so scratch is fine.

### Resolving an executable directory

This excerpt needs `can_execute` from `references/exec-dir.rs`:

```rust
fn exec_dir() -> Result<std::path::PathBuf, String> {
    let dir = match std::env::var_os("NOEXEC_EXEC_DIR") {
        Some(dir) => std::path::PathBuf::from(dir),
        None => std::env::current_exe().ok()
            .and_then(|exe| exe.parent().map(|p| p.join("exec-fixtures")))
            .ok_or("no test binary; set NOEXEC_EXEC_DIR")?,
    };
    std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    if !can_execute(&dir) {
        return Err(format!("{} refuses exec; set NOEXEC_EXEC_DIR", dir.display()));
    }
    Ok(dir)
}
```

`can_execute` writes a `#!/bin/sh` probe, sets mode `0755`, runs it, and deletes it.

## Security

A `noexec` mount stops direct execution only. An interpreter on an executable mount can run any script it can read, so `noexec` is not a sandbox. Do not remount or raise privileges to make a check pass: that hides the defect.

## Reference Files

- `references/exec-dir.rs` — `exec_dir`, `can_execute`, two tests. Compile-checked.
- `references/spawn-helper.rs` — wrong and right helper spawn. Compile-checked and run.

The `noexec-coding` skill covers the mount rules and the three-way probe.

### Worked examples

#### (a) A test that spawns a helper binary

Wrong. The helper is written to scratch and started there:

```rust
use std::os::unix::fs::PermissionsExt;
use std::process::Command;

#[test]
fn spawns_from_scratch() {
    let dir = std::env::temp_dir().join(format!("helper-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let helper = dir.join("helper.sh");
    std::fs::write(&helper, "#!/bin/sh\necho ready\n").unwrap();
    std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755)).unwrap();
    // On a noexec mount this is Err(PermissionDenied), os error 13.
    let out = Command::new(&helper).output().expect("helper must start");
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "ready");
}
```

Right. The helper goes to a directory that ran a probe first:

```rust
use std::os::unix::fs::PermissionsExt;
use std::process::Command;

#[test]
fn spawns_from_executable_storage() {
    let dir = exec_dir().expect("this host has no executable directory");
    let helper = dir.join(format!("helper-{}.sh", std::process::id()));
    std::fs::write(&helper, "#!/bin/sh\necho ready\n").unwrap();
    std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755)).unwrap();

    let out = Command::new(&helper).output();
    let _ = std::fs::remove_file(&helper);
    assert_eq!(String::from_utf8_lossy(&out.unwrap().stdout).trim(), "ready");
}
```

Input data may still live in a `TempDir`. Only the program moves.

#### (b) A layout that keeps cargo executable and data in scratch

```text
project/
  .cargo/config.toml     # [build] target-dir = ".cargo-target"
  .cargo-target/         # executable storage; git-ignored
  tests/spawn.rs         # spawns helpers through exec_dir()
  fixtures/              # read-only data, may live anywhere
```

```toml
[build]
target-dir = ".cargo-target"
```

Pin the dir so every cargo command agrees. Keep `TMPDIR` on executable storage too, or `cargo test --doc` fails. Probe once per host.

## Key Rules

ALWAYS put `CARGO_TARGET_DIR` on executable storage when tests, build scripts, or proc macros run, and probe it by starting a file before a cold build. ALWAYS take a helper path from cargo, `current_exe()`, or a resolved directory, and name the remedy when none works.

NEVER write a program into `temp_dir()` or a `TempDir` and start it, and never use `#[ignore]`, `cfg(not(...))`, or a runtime return to avoid a `noexec` host.

NEVER use `chmod +x`, `test -x`, `os.access(_, X_OK)`, or `mount` output as an execution check. They report mode bits, not mount policy.

PREFER `env!("CARGO_BIN_EXE_<name>")`, a script run through its interpreter, and a negative test, over a lookup, a copied binary, and an OS-specific gate.

## Ground Rules

ALWAYS write the test so it fails on a defect, not on a host type. The macOS default temp dir allows execution, so a Linux-only bug hides there; a `noexec` APFS volume does reproduce the same refusal, so the check is still valid on macOS. ALWAYS keep `TempDir` for data and a resolved directory for programs. One question decides: will some process call `execve` on this path? Run the smallest affected test, and report whether scratch refused, ran, or was never probed.

NEVER count a skip as a pass, and never claim a `noexec` fix without a run that would have failed before it.

