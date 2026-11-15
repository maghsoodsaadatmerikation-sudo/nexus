//! Read-only semantic validator for detached, operator-held workspace witnesses.
//!
//! A valid snapshot is NOT evidence of a genuine machine run, a trusted
//! signature, current key authorization, an append-only revision, or permission
//! to import it. The operator-side Python registry controls those separately.
//! No user content, path or workspace ID is included in diagnostic output.
use nexus_constitutional_core::{WorkspaceEngine, WorkspaceSnapshot};
use std::{
    fs::OpenOptions,
    io::Read,
    path::{Path, PathBuf},
};

const MAX_SNAPSHOT_BYTES: u64 = 16 * 1024 * 1024;

fn semantic_check(path: &Path, expected_id: &str) -> Result<(), ()> {
    if expected_id.is_empty() || expected_id.trim().is_empty() {
        return Err(());
    }

    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    let file = options.open(path).map_err(|_| ())?;
    let metadata = file.metadata().map_err(|_| ())?;
    if !metadata.is_file() || metadata.len() == 0 || metadata.len() > MAX_SNAPSHOT_BYTES {
        return Err(());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if metadata.nlink() != 1 {
            return Err(());
        }
    }

    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    file.take(MAX_SNAPSHOT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| ())?;
    if bytes.is_empty()
        || bytes.len() as u64 != metadata.len()
        || bytes.len() as u64 > MAX_SNAPSHOT_BYTES
    {
        return Err(());
    }
    let snapshot: WorkspaceSnapshot = serde_json::from_slice(&bytes).map_err(|_| ())?;
    if snapshot.workspace.id != expected_id {
        return Err(());
    }
    WorkspaceEngine::from_snapshot(snapshot).map_err(|_| ())?;
    Ok(())
}

fn main() {
    let mut args = std::env::args_os();
    let _program = args.next();
    let valid_args = match (args.next(), args.next(), args.next(), args.next(), args.next()) {
        (Some(flag_a), Some(path), Some(flag_b), Some(id), None)
            if flag_a == "--snapshot" && flag_b == "--expected-workspace-id" =>
        {
            Some((PathBuf::from(path), id))
        }
        _ => None,
    };
    let Some((path, id)) = valid_args else {
        eprintln!("NEXUS WORKSPACE SEMANTICS: BLOCKED (argument contract)");
        std::process::exit(2);
    };
    let Some(id) = id.to_str() else {
        eprintln!("NEXUS WORKSPACE SEMANTICS: BLOCKED (invalid ID encoding)");
        std::process::exit(2);
    };
    match semantic_check(&path, id) {
        Ok(()) => println!("NEXUS WORKSPACE SEMANTICS: PASS (structural only; authority=none)"),
        Err(()) => {
            eprintln!("NEXUS WORKSPACE SEMANTICS: BLOCKED (invalid or unsafe snapshot)");
            std::process::exit(1);
        }
    }
}
