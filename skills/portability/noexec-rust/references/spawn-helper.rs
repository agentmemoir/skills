//! Worked example: a test that spawns a helper program.
//!
//! Compile check:
//!   mkdir -p target && rustc --edition 2021 --test spawn-helper.rs -o target/spawn-helper
//!
//! The `wrong_*` test is expected to pass on a host whose scratch storage
//! allows execution and to fail with `EACCES` where it does not. Do not
//! commit it. It is here to show the defect.

use std::path::{Path, PathBuf};
use std::process::Command;

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

const HELPER: &str = "#!/bin/sh\necho ready\n";

/// WRONG: the helper is written to scratch and started from there.
#[test]
fn wrong_spawns_the_helper_from_scratch() {
    let dir = std::env::temp_dir().join(format!("wrong-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let helper = dir.join("helper.sh");
    std::fs::write(&helper, HELPER).unwrap();
    std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755)).unwrap();

    // On a noexec mount this returns Err with kind PermissionDenied.
    let output = Command::new(&helper).output().expect("helper must start");
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "ready");

    let _ = std::fs::remove_dir_all(&dir);
}

/// RIGHT: the helper goes to a directory that runs a probe first.
#[test]
fn right_spawns_the_helper_from_executable_storage() {
    let exec_dir = exec_dir().expect("this host has no executable directory");
    let helper = exec_dir.join(format!("helper-{}.sh", std::process::id()));
    std::fs::write(&helper, HELPER).unwrap();
    std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755)).unwrap();

    let result = Command::new(&helper).output();
    let _ = std::fs::remove_file(&helper);

    let output = result.expect("the directory passed the exec probe, so the helper must start");
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "ready");
}

/// RIGHT: data may stay in scratch. Only programs move.
#[test]
fn right_keeps_data_in_scratch() {
    let dir = std::env::temp_dir().join(format!("data-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let data = dir.join("input.txt");
    std::fs::write(&data, b"payload").unwrap();

    assert_eq!(std::fs::read(&data).unwrap(), b"payload");

    let _ = std::fs::remove_dir_all(&dir);
}

/// Return a directory that permits running a file, or fail with a remedy.
fn exec_dir() -> Result<PathBuf, String> {
    let mut tried = Vec::new();
    for dir in candidates() {
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

fn candidates() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(dir) = std::env::var_os("NOEXEC_EXEC_DIR") {
        dirs.push(PathBuf::from(dir));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            dirs.push(parent.join("exec-fixtures"));
        }
    }
    dirs
}

fn can_execute(dir: &Path) -> bool {
    let probe = dir.join(format!("probe-{}", std::process::id()));
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
