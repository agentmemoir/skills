//! Find a directory that permits running a helper program.
//!
//! Unix only. Windows has no `noexec` mount flag.
//!
//! Compile check:
//!   rustc --edition 2021 --crate-type lib exec-dir.rs
//! Run the tests with:
//!   mkdir -p target && rustc --edition 2021 --test exec-dir.rs -o target/exec-dir && ./target/exec-dir

use std::path::{Path, PathBuf};
use std::process::Command;

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

/// Return a directory where a helper file can be started.
///
/// Order: `NOEXEC_EXEC_DIR`, the current binary's directory, the cargo
/// target directory, then `target/` under the current directory.
/// Fails with a message naming the remedy when none runs.
pub fn exec_dir() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Some(dir) = std::env::var_os("NOEXEC_EXEC_DIR") {
        candidates.push(PathBuf::from(dir));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("exec-fixtures"));
        }
    }
    if let Some(dir) = std::env::var_os("CARGO_TARGET_DIR") {
        candidates.push(PathBuf::from(dir).join("exec-fixtures"));
    }
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("target/exec-fixtures"));
    }

    let mut tried = Vec::new();
    for dir in candidates {
        if std::fs::create_dir_all(&dir).is_err() {
            tried.push(format!("{} (cannot create)", dir.display()));
            continue;
        }
        if can_execute(&dir) {
            return Ok(dir);
        }
        tried.push(format!("{} (refuses execution)", dir.display()));
    }

    Err(format!(
        "no directory permits running a helper; set NOEXEC_EXEC_DIR. Tried: {}",
        tried.join(", ")
    ))
}

/// Write a probe, make it executable, and run it. The exit status is the
/// only proof that the mount permits `execve`.
pub fn can_execute(dir: &Path) -> bool {
    static NEXT: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let unique = format!(
        "{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    );
    let probe = dir.join(format!("probe-{unique}"));
    let written = std::fs::write(&probe, "#!/bin/sh\nexit 0\n").and_then(|()| {
        std::fs::set_permissions(&probe, std::fs::Permissions::from_mode(0o755))
    });
    let ran = written.is_ok()
        && Command::new(&probe)
            .status()
            .is_ok_and(|status| status.success());
    let _ = std::fs::remove_file(&probe);
    ran
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A helper without the execute bit fails on every OS. This keeps the
    /// error path covered where the mount itself allows execution.
    #[test]
    fn a_mode_0644_helper_does_not_run() {
        let dir = std::env::temp_dir().join(format!("exec-dir-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let helper = dir.join("helper.sh");
        std::fs::write(&helper, "#!/bin/sh\nexit 0\n").unwrap();
        std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o644)).unwrap();

        let ran = Command::new(&helper)
            .status()
            .is_ok_and(|status| status.success());
        assert!(!ran, "a mode 0644 file must not run");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn exec_dir_returns_a_working_directory_or_names_the_remedy() {
        match exec_dir() {
            Ok(dir) => assert!(can_execute(&dir), "{}", dir.display()),
            Err(message) => assert!(message.contains("NOEXEC_EXEC_DIR"), "{message}"),
        }
    }
}
