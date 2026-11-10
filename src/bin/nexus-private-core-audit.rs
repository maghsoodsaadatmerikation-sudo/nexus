//! Read-only, bounded semantic audit of an operator-held private NEXUS copy.
//!
//! This is NOT a volume backup, independent proof of origin, point-in-time
//! consistency, an authenticated service login, or provider recovery witness.
//! Any failure is deliberately redacted: no workspace ID, path or content is
//! printed. The evaluator never writes to the directory it examines.
use nexus_constitutional_core::{FileWorkspaceRepository, WorkspaceSnapshot};
use std::fs;
use std::path::{Path, PathBuf};

const MAX_FILES: usize = 20_000;
const MAX_BYTES: u64 = 64 * 1024 * 1024;

fn hex_matches_id(file: &str, id: &str) -> bool {
    let mut encoded = String::with_capacity(id.len() * 2);
    for byte in id.as_bytes() {
        use std::fmt::Write;
        let _ = write!(&mut encoded, "{byte:02x}");
    }
    file == format!("{encoded}.json")
}

fn regular_file_len(path: &Path) -> Result<u64, ()> {
    let metadata = fs::symlink_metadata(path).map_err(|_| ())?;
    if !metadata.file_type().is_file() {
        return Err(());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if metadata.nlink() != 1 {
            return Err(());
        }
    }
    Ok(metadata.len())
}

fn audit(root: &Path) -> Result<(usize, usize), ()> {
    if !root.is_absolute() {
        return Err(());
    }
    let original = root.to_path_buf();
    let canonical = fs::canonicalize(root).map_err(|_| ())?;
    if original != canonical {
        return Err(());
    }
    if !fs::symlink_metadata(root).map_err(|_| ())?.file_type().is_dir() {
        return Err(());
    }
    let ledger = root.join("requests");
    if !fs::symlink_metadata(&ledger).map_err(|_| ())?.file_type().is_dir() {
        return Err(());
    }
    let mut count = 0usize;
    let mut total = 0u64;
    let mut requests = 0usize;
    for item in fs::read_dir(&ledger).map_err(|_| ())? {
        let entry = item.map_err(|_| ())?;
        let file_name = entry.file_name().into_string().map_err(|_| ())?;
        if file_name.is_empty() || file_name.len() > 200 || file_name.len() % 2 != 0
            || !file_name.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
            return Err(());
        }
        let len = regular_file_len(&entry.path())?;
        total = total.checked_add(len).ok_or(())?;
        count += 1;
        requests += 1;
        if total > MAX_BYTES || count > MAX_FILES {
            return Err(());
        }
    }
    let repo = FileWorkspaceRepository::new(root);
    let mut workspaces = 0usize;
    for item in fs::read_dir(root).map_err(|_| ())? {
        let entry = item.map_err(|_| ())?;
        let file_name = entry.file_name().into_string().map_err(|_| ())?;
        if file_name == "requests" {
            continue;
        }
        if file_name == ".nexus-recovery-required" {
            if regular_file_len(&entry.path())? > 1024 {
                return Err(());
            }
            continue;
        }
        if !file_name.ends_with(".json") || file_name.len() > 405 {
            return Err(());
        }
        let len = regular_file_len(&entry.path())?;
        total = total.checked_add(len).ok_or(())?;
        count += 1;
        workspaces += 1;
        if count > MAX_FILES || total > MAX_BYTES {
            return Err(());
        }
        // This is intentionally the same deserialization and durable audit
        // validation path used by the *actual* Rust gateway repository.
        let bytes = fs::read(entry.path()).map_err(|_| ())?;
        if bytes.len() as u64 != len {
            return Err(());
        }
        let parsed: WorkspaceSnapshot = serde_json::from_slice(&bytes).map_err(|_| ())?;
        if !hex_matches_id(&file_name, &parsed.workspace.id) {
            return Err(());
        }
        let loaded = repo.load(&parsed.workspace.id).map_err(|_| ())?.ok_or(())?;
        if loaded != parsed {
            return Err(());
        }
    }
    Ok((workspaces, requests))
}

fn main() {
    let mut args = std::env::args_os();
    let _binary = args.next();
    let root = args.next().map(PathBuf::from);
    if args.next().is_some() {
        eprintln!("NEXUS PRIVATE CORE AUDIT: BLOCKED (argument count)");
        std::process::exit(2);
    }
    let Some(root) = root else {
        eprintln!("NEXUS PRIVATE CORE AUDIT: BLOCKED (absolute private root required)");
        std::process::exit(2);
    };
    match audit(&root) {
        Ok((workspaces, _requests)) => {
            println!("NEXUS PRIVATE CORE AUDIT: PASS (validated workspaces: {workspaces}; authority=none)");
        }
        Err(()) => {
            // Never expose filenames, workspace IDs, raw errors or user data.
            eprintln!("NEXUS PRIVATE CORE AUDIT: BLOCKED (invalid or unsupported private data)");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::hex_matches_id;

    #[test]
    fn rejects_case_or_filename_mismatch() {
        assert!(hex_matches_id("776f726b7370616365.json", "workspace"));
        assert!(!hex_matches_id("776F726B7370616365.json", "workspace"));
        assert!(!hex_matches_id("776f726b7370616364.json", "workspace"));
    }
}
