//! Test-only, read-only shim over the actual checkout's constitutional core.
//!
//! Copy ONLY into a disposable Git worktree at an exact approved historical
//! commit. It executes that version's WorkspaceEngine deserializer/validator
//! and detects silently dropped fields by semantic JSON roundtrip.
//! No server, disk store writes, machine execution authority or import.
use nexus_constitutional_core::{WorkspaceEngine, WorkspaceSnapshot};
use std::{env, fs, path::PathBuf};

fn verify() -> Result<(), ()> {
    let argv: Vec<_> = env::args_os().collect();
    if argv.len() != 4 || argv[1] != "--snapshot" {
        return Err(());
    }
    let path = PathBuf::from(&argv[2]);
    let expected = argv[3].to_str().ok_or(())?;
    if expected.trim().is_empty() {
        return Err(());
    }
    let metadata = fs::symlink_metadata(&path).map_err(|_| ())?;
    if !metadata.file_type().is_file()
        || metadata.len() == 0
        || metadata.len() > 16 * 1024 * 1024
    {
        return Err(());
    }
    let bytes = fs::read(&path).map_err(|_| ())?;
    if bytes.len() as u64 != metadata.len() {
        return Err(());
    }
    let deserialized: WorkspaceSnapshot = serde_json::from_slice(&bytes).map_err(|_| ())?;
    if deserialized.workspace.id != expected {
        return Err(());
    }
    let engine = WorkspaceEngine::from_snapshot(deserialized).map_err(|_| ())?;
    let encoded = serde_json::to_value(engine.snapshot()).map_err(|_| ())?;
    let supplied: serde_json::Value = serde_json::from_slice(&bytes).map_err(|_| ())?;
    // Rust serde ignores extra struct keys by default. Such silent dropping
    // is unsafe for a downgrade: refuse when the old reader loses any data.
    if encoded != supplied {
        return Err(());
    }
    Ok(())
}

fn main() {
    match verify() {
        Ok(()) => println!("NEXUS HISTORICAL CORE READ: PASS (synthetic only; authority=none)"),
        Err(()) => {
            eprintln!("NEXUS HISTORICAL CORE READ: BLOCKED (unsupported or lossy)");
            std::process::exit(1);
        }
    }
}
