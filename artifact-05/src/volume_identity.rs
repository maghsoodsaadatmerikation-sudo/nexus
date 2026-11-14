//! Fail-closed volume identity check before runtime creates data directories.
//!
//! This is an optional migration-compatible guard. Deployments that configure
//! NEXUS_EXPECTED_VOLUME_ID require an exact enrolled marker *before* startup.
//! The runtime never creates or repairs the marker. IDs are operator-held,
//! non-secret UUID-like hex identifiers: not signatures or backup evidence.
use std::{
    fs::{self, File, OpenOptions},
    io::Read,
    path::Path,
};

#[cfg(unix)]
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

#[cfg(target_os = "linux")]
use std::os::fd::AsRawFd;

pub(crate) const MARKER_NAME: &str = ".nexus-volume-identity";
pub(crate) const PREFIX: &str = "nexus.volume-identity.v1\n";
const MAX_MARKER_BYTES: u64 = 128;

/// Validate only a pinned existing root; a missing volume must NEVER be
/// manufactured by an implicit create_dir_all.
pub(crate) fn verify(root: &Path, expected: &str) -> Result<(), &'static str> {
    if expected.len() != 32
        || !expected
            .bytes()
            .all(|value| value.is_ascii_digit() || (b'a'..=b'f').contains(&value))
    {
        return Err("invalid expected volume ID configuration");
    }
    let before = fs::symlink_metadata(root).map_err(|_| "volume root missing")?;
    if !before.is_dir() {
        return Err("volume root is not a physical directory");
    }
    let mut root_options = OpenOptions::new();
    root_options.read(true);
    #[cfg(unix)]
    root_options.custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC);
    let directory = root_options
        .open(root)
        .map_err(|_| "volume root inaccessible")?;
    let opened = directory.metadata().map_err(|_| "volume root unreadable")?;
    if !same_inode(&before, &opened) {
        return Err("volume root changed during verification");
    }

    #[cfg(target_os = "linux")]
    let path = Path::new("/proc/self/fd")
        .join(directory.as_raw_fd().to_string())
        .join(MARKER_NAME);
    #[cfg(not(target_os = "linux"))]
    let path = root.join(MARKER_NAME);

    let linked = fs::symlink_metadata(&path).map_err(|_| "volume identity marker missing")?;
    if !linked.is_file() || linked.len() > MAX_MARKER_BYTES || linked.len() == 0 {
        return Err("volume identity marker invalid");
    }
    #[cfg(unix)]
    if linked.nlink() != 1 {
        return Err("volume identity marker hardlinked");
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC);
    let mut file: File = options
        .open(&path)
        .map_err(|_| "volume identity marker inaccessible")?;
    let initial = file
        .metadata()
        .map_err(|_| "volume identity marker unreadable")?;
    if !initial.is_file() || !same_inode(&initial, &linked) || initial.len() != linked.len() {
        return Err("volume identity marker changed");
    }
    let mut data = Vec::new();
    (&mut file)
        .take(MAX_MARKER_BYTES + 1)
        .read_to_end(&mut data)
        .map_err(|_| "volume identity read error")?;
    if data != format!("{PREFIX}{expected}\n").as_bytes() {
        return Err("volume identity mismatch");
    }
    let final_file = file
        .metadata()
        .map_err(|_| "volume identity marker unreadable")?;
    let final_link = fs::symlink_metadata(&path).map_err(|_| "volume identity marker removed")?;
    if !same_inode(&initial, &final_file)
        || !same_inode(&initial, &final_link)
        || final_file.len() != data.len() as u64
    {
        return Err("volume identity marker changed during verification");
    }
    let final_root = fs::symlink_metadata(root).map_err(|_| "volume root removed")?;
    if !same_inode(&opened, &final_root) || !final_root.is_dir() {
        return Err("volume root replaced");
    }
    Ok(())
}

fn same_inode(first: &fs::Metadata, second: &fs::Metadata) -> bool {
    #[cfg(unix)]
    {
        first.dev() == second.dev() && first.ino() == second.ino()
    }
    #[cfg(not(unix))]
    {
        first.file_type() == second.file_type() && first.created().ok() == second.created().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    const ID: &str = "1234567890abcdef1234567890abcdef";

    fn root() -> PathBuf {
        std::env::temp_dir().join(format!("nexus-volume-guard-{}", uuid::Uuid::new_v4()))
    }

    fn enroll(root: &Path) {
        fs::write(root.join(MARKER_NAME), format!("{PREFIX}{ID}\n")).unwrap();
    }

    #[test]
    fn missing_root_or_marker_is_never_created_by_guard() {
        let root = root();
        assert!(verify(&root, ID).is_err());
        assert!(!root.exists());
        fs::create_dir(&root).unwrap();
        assert!(verify(&root, ID).is_err());
        assert!(fs::read_dir(&root).unwrap().next().is_none());
        fs::remove_dir(root).unwrap();
    }

    #[test]
    fn enrolled_volume_reopens_but_wrong_identity_and_corruption_fail_closed() {
        let root = root();
        fs::create_dir(&root).unwrap();
        enroll(&root);
        assert!(verify(&root, ID).is_ok());
        assert!(verify(&root, "abcdef1234567890abcdef1234567890").is_err());
        for candidate in [
            "",
            "foo",
            "1234567890ABCDEF1234567890ABCDEF",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ] {
            assert!(verify(&root, candidate).is_err());
        }
        fs::write(root.join(MARKER_NAME), format!("{PREFIX}{ID}")).unwrap();
        assert!(verify(&root, ID).is_err());
        fs::write(root.join(MARKER_NAME), format!("{PREFIX}{ID}\nextra")).unwrap();
        assert!(verify(&root, ID).is_err());
        enroll(&root);
        assert!(verify(&root, ID).is_ok());
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn symlink_marker_and_hardlink_refused() {
        use std::os::unix::fs::symlink;
        let root = root();
        fs::create_dir(&root).unwrap();
        let outside = root.with_extension("source");
        fs::write(&outside, format!("{PREFIX}{ID}\n")).unwrap();
        symlink(&outside, root.join(MARKER_NAME)).unwrap();
        assert!(verify(&root, ID).is_err());
        fs::remove_file(root.join(MARKER_NAME)).unwrap();
        fs::hard_link(&outside, root.join(MARKER_NAME)).unwrap();
        assert!(verify(&root, ID).is_err());
        fs::remove_dir_all(root).unwrap();
        fs::remove_file(outside).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn substituted_root_and_symlinked_volume_refused() {
        use std::os::unix::fs::symlink;
        let root = root();
        let moved = root.with_extension("moved");
        fs::create_dir(&root).unwrap();
        enroll(&root);
        assert!(verify(&root, ID).is_ok());
        fs::rename(&root, &moved).unwrap();
        assert!(verify(&root, ID).is_err());
        fs::create_dir(&root).unwrap();
        assert!(verify(&root, ID).is_err());
        // Even a perfectly formatted but wrong marker must not be accepted.
        fs::write(
            root.join(MARKER_NAME),
            format!("{PREFIX}{}\n", "a".repeat(32)),
        )
        .unwrap();
        assert!(verify(&root, ID).is_err());
        fs::remove_dir_all(&root).unwrap();
        symlink(&moved, &root).unwrap();
        assert!(verify(&root, ID).is_err());
        fs::remove_file(&root).unwrap();
        fs::rename(&moved, &root).unwrap();
        assert!(verify(&root, ID).is_ok());
        fs::remove_dir_all(&root).unwrap();
    }
}
