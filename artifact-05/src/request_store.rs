//! Conservative single-host request markers. A reservation is synced before delegation.
use crate::RequestStatus;
use std::{
    collections::HashMap,
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    os::{
        fd::AsRawFd,
        unix::fs::{MetadataExt, OpenOptionsExt},
    },
    path::{Path, PathBuf},
};

pub(crate) struct RequestStore {
    root: PathBuf,
    // Keep a descriptor to the original directory for the store's lifetime.
    // Names are reopened through /proc/self/fd instead of through a mutable
    // ancestor pathname; a replaced directory cannot redirect writes.
    ledger: File,
}

impl RequestStore {
    pub(crate) fn open(root: &Path) -> io::Result<(Self, HashMap<String, RequestStatus>)> {
        let root = if root.is_absolute() {
            root.to_owned()
        } else {
            std::env::current_dir()?.join(root)
        };
        fs::create_dir_all(&root)?;
        // A path alias to a different ledger must not become a durable root.
        if !fs::symlink_metadata(&root)?.file_type().is_dir() {
            return Err(invalid());
        }
        // Persist every newly created ancestor as well as the marker directory.
        for ancestor in root.ancestors() {
            File::open(ancestor)?.sync_all()?;
        }
        let ledger = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC)
            .open(&root)?;
        let store = Self { root, ledger };
        store.verify_root()?;
        let mut statuses = HashMap::new();
        for entry in fs::read_dir(store.pinned_dir_path())? {
            let entry = entry?;
            let name = entry.file_name().into_string().map_err(|_| invalid())?;
            if !name.is_ascii()
                || !entry.file_type()?.is_file()
                || name.len() % 2 != 0
                || name.len() > 200
            {
                return Err(invalid());
            }
            let bytes = (0..name.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&name[i..i + 2], 16).map_err(|_| invalid()))
                .collect::<io::Result<Vec<_>>>()?;
            let id = String::from_utf8(bytes).map_err(|_| invalid())?;
            if store.path(&id).file_name() != Some(entry.file_name().as_os_str()) {
                return Err(invalid());
            }
            let marker = read_marker(&entry.path())?;
            let status = if marker == b"pending\n" {
                RequestStatus::Pending
            } else if marker.is_empty() || b"pending\n".starts_with(&marker) {
                RequestStatus::Indeterminate
            } else {
                return Err(invalid());
            };
            statuses.insert(id, status);
        }
        store.verify_root()?;
        Ok((store, statuses))
    }

    fn encoded_id(id: &str) -> String {
        id.as_bytes()
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>()
    }

    fn path(&self, id: &str) -> PathBuf {
        self.root.join(Self::encoded_id(id))
    }

    fn pinned_dir_path(&self) -> PathBuf {
        // Linux procfs resolves this handle to the already-open directory,
        // even if a parent path is subsequently renamed or replaced.
        Path::new("/proc/self/fd").join(self.ledger.as_raw_fd().to_string())
    }

    fn pinned_marker_path(&self, id: &str) -> PathBuf {
        self.pinned_dir_path().join(Self::encoded_id(id))
    }

    fn verify_root(&self) -> io::Result<()> {
        let linked = fs::symlink_metadata(&self.root)?;
        let pinned = self.ledger.metadata()?;
        if !linked.file_type().is_dir()
            || !pinned.is_dir()
            || (linked.dev(), linked.ino()) != (pinned.dev(), pinned.ino())
        {
            return Err(invalid());
        }
        Ok(())
    }

    /// Read-only runtime readiness. Check that the configured ledger path
    /// still names the pinned directory and its directory entries are
    /// traversable. This deliberately does not write a probe marker, clear
    /// recovery quarantine or promise that the next fsync will succeed.
    pub(crate) fn check_readiness(&self) -> io::Result<()> {
        self.verify_root()?;
        let mut entries = fs::read_dir(self.pinned_dir_path())?;
        // read_dir opens the directory; consuming one entry also surfaces
        // delayed enumeration errors without scanning the whole request log.
        if let Some(entry) = entries.next() {
            entry?;
        }
        self.verify_root()
    }

    fn verify_marker_identity(&self, file: &File, path: &Path, size: u64) -> io::Result<()> {
        let linked = fs::symlink_metadata(path)?;
        let actual = file.metadata()?;
        if !linked.file_type().is_file()
            || linked.nlink() != 1
            || actual.nlink() != 1
            || linked.len() != size
            || actual.len() != size
            || (linked.dev(), linked.ino()) != (actual.dev(), actual.ino())
        {
            return Err(invalid());
        }
        Ok(())
    }

    pub(crate) fn reserve(&self, id: &str) -> io::Result<()> {
        self.verify_root()?;
        let path = self.pinned_marker_path(id);
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC)
            .open(&path)?;
        // Allocate and sync a non-accepted prefix before crossing the delegate
        // boundary. An empty inode alone does not detect byte-capacity ENOSPC.
        // Legacy empty markers and a torn prefix still recover indeterminate.
        file.write_all(b"p")?;
        file.sync_all()?;
        self.ledger.sync_all()?;
        self.verify_marker_identity(&file, &path, 1)?;
        self.verify_root()
    }

    pub(crate) fn pending(&self, id: &str) -> io::Result<()> {
        self.verify_root()?;
        // A torn write recovers conservatively as indeterminate, never as accepted.
        let path = self.pinned_marker_path(id);
        let mut file = open_marker(&path, true)?;
        file.write_all(b"pending\n")?;
        file.sync_all()?;
        self.verify_marker_identity(&file, &path, 8)?;
        self.verify_root()
    }
}

// The gateway runs on Linux. Do not follow a replaced final-path symlink,
// block on a substituted FIFO, or write through an aliased hard-linked inode.
// The opened directory descriptor now prevents redirecting marker reads or
// writes through a replaced ancestor path. It does not authorize untrusted
// writers in that directory or replace host ownership/permission controls.
fn open_marker(path: &Path, writing: bool) -> io::Result<File> {
    let initial = fs::symlink_metadata(path)?;
    if !initial.file_type().is_file() || initial.nlink() != 1 || initial.len() > 8 {
        return Err(invalid());
    }
    let file = OpenOptions::new()
        .read(!writing)
        .write(writing)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let opened = file.metadata()?;
    if !opened.is_file()
        || opened.nlink() != 1
        || opened.len() > 8
        || (initial.dev(), initial.ino()) != (opened.dev(), opened.ino())
    {
        return Err(invalid());
    }
    Ok(file)
}

fn read_marker(path: &Path) -> io::Result<Vec<u8>> {
    let mut file = open_marker(path, false)?;
    let before = file.metadata()?;
    let mut bytes = Vec::new();
    (&mut file).take(9).read_to_end(&mut bytes)?;
    let after = file.metadata()?;
    let final_path = fs::symlink_metadata(path)?;
    if bytes.len() > 8
        || !final_path.is_file()
        || final_path.nlink() != 1
        || (after.dev(), after.ino()) != (before.dev(), before.ino())
        || (final_path.dev(), final_path.ino()) != (before.dev(), before.ino())
        || (
            before.len(),
            before.mtime(),
            before.mtime_nsec(),
            before.ctime(),
            before.ctime_nsec(),
        ) != (
            after.len(),
            after.mtime(),
            after.mtime_nsec(),
            after.ctime(),
            after.ctime_nsec(),
        )
        || after.len() != bytes.len() as u64
    {
        return Err(invalid());
    }
    Ok(bytes)
}

fn invalid() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "invalid request marker")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader},
        process::{Command, Stdio},
    };

    fn isolated_ledger(label: &str) -> PathBuf {
        let root =
            std::env::temp_dir().join(format!("nexus-ledger-{}-{}", label, uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn all_crash_prefixes_remain_indeterminate_but_only_full_marker_pending() {
        for length in 0..=8 {
            let root = isolated_ledger("torn");
            fs::write(root.join("61"), &b"pending\n"[..length]).unwrap();
            let (_, statuses) = RequestStore::open(&root).unwrap();
            let expected = if length == 8 {
                RequestStatus::Pending
            } else {
                RequestStatus::Indeterminate
            };
            assert_eq!(statuses.get("a"), Some(&expected));
            fs::remove_dir_all(root).unwrap();
        }
    }

    #[test]
    fn rejects_nonprefix_or_overlong_marker_bytes() {
        for bytes in [
            b"pendinX".as_slice(),
            b"pending\nx",
            b"p\0",
            b"accepted",
            b"\xff",
        ] {
            let root = isolated_ledger("invalid-marker");
            fs::write(root.join("61"), bytes).unwrap();
            assert!(RequestStore::open(&root).is_err());
            fs::remove_dir_all(root).unwrap();
        }
    }

    #[test]
    fn rejects_hardlinked_external_marker_during_startup() {
        let root = isolated_ledger("external-link");
        let outside = root.with_extension("external");
        fs::write(&outside, b"pending\n").unwrap();
        fs::hard_link(&outside, root.join("61")).unwrap();
        assert!(RequestStore::open(&root).is_err());
        assert_eq!(fs::read(&outside).unwrap(), b"pending\n");
        fs::remove_dir_all(root).unwrap();
        fs::remove_file(outside).unwrap();
    }

    #[test]
    fn pending_rejects_hardlinked_external_marker_without_mutating_it() {
        let root = isolated_ledger("pending-link");
        let (store, _) = RequestStore::open(&root).unwrap();
        store.reserve("a").unwrap();
        let outside = root.with_extension("external");
        fs::hard_link(store.path("a"), &outside).unwrap();
        assert!(store.pending("a").is_err());
        assert_eq!(fs::read(&outside).unwrap(), b"p");
        fs::remove_dir_all(root).unwrap();
        fs::remove_file(outside).unwrap();
    }

    #[test]
    fn pending_rejects_replaced_symlink_without_mutating_target() {
        use std::os::unix::fs::symlink;
        let root = isolated_ledger("pending-symlink");
        let (store, _) = RequestStore::open(&root).unwrap();
        store.reserve("a").unwrap();
        let outside = root.with_extension("external");
        fs::rename(store.path("a"), &outside).unwrap();
        symlink(&outside, store.path("a")).unwrap();
        assert!(store.pending("a").is_err());
        assert_eq!(fs::read(&outside).unwrap(), b"p");
        fs::remove_dir_all(root).unwrap();
        fs::remove_file(outside).unwrap();
    }

    #[test]
    fn normal_reservation_transitions_from_indeterminate_to_pending() {
        let root = isolated_ledger("normal-transition");
        let (store, _) = RequestStore::open(&root).unwrap();
        store.reserve("a").unwrap();
        let (_, recovered) = RequestStore::open(&root).unwrap();
        assert_eq!(recovered.get("a"), Some(&RequestStatus::Indeterminate));
        store.pending("a").unwrap();
        let (_, recovered) = RequestStore::open(&root).unwrap();
        assert_eq!(recovered.get("a"), Some(&RequestStatus::Pending));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn replacing_ledger_directory_cannot_redirect_reserved_or_pending_writes() {
        let root = isolated_ledger("replace-root");
        let (store, _) = RequestStore::open(&root).unwrap();
        store.reserve("a").unwrap();
        let original = root.with_extension("original");
        fs::rename(&root, &original).unwrap();
        fs::create_dir(&root).unwrap();
        fs::write(root.join("61"), b"p").unwrap();

        // The pinned descriptor still names the original directory, but
        // the changed visible path makes the store refuse any further write.
        assert_eq!(fs::read(store.pinned_marker_path("a")).unwrap(), b"p");
        assert!(store.reserve("b").is_err());
        assert!(store.pending("a").is_err());
        assert_eq!(fs::read(root.join("61")).unwrap(), b"p");
        assert_eq!(fs::read(original.join("61")).unwrap(), b"p");
        assert!(!root.join("62").exists());
        assert!(!original.join("62").exists());

        fs::remove_dir_all(root).unwrap();
        fs::remove_dir_all(original).unwrap();
    }

    #[test]
    fn replacing_ancestor_directory_cannot_redirect_writes() {
        let parent = isolated_ledger("replace-parent");
        let root = parent.join("requests");
        fs::create_dir(&root).unwrap();
        let (store, _) = RequestStore::open(&root).unwrap();
        store.reserve("a").unwrap();
        let original = parent.with_extension("original");
        fs::rename(&parent, &original).unwrap();
        fs::create_dir(&parent).unwrap();
        fs::create_dir(&root).unwrap();

        assert!(store.reserve("b").is_err());
        assert!(store.pending("a").is_err());
        assert!(!root.join("61").exists());
        assert!(!root.join("62").exists());
        assert_eq!(fs::read(original.join("requests/61")).unwrap(), b"p");

        fs::remove_dir_all(parent).unwrap();
        fs::remove_dir_all(original).unwrap();
    }

    #[test]
    fn new_store_rejects_symlinked_directory_alias() {
        use std::os::unix::fs::symlink;
        let root = isolated_ledger("symlink-root");
        let alias = root.with_extension("alias");
        symlink(&root, &alias).unwrap();
        assert!(RequestStore::open(&alias).is_err());
        fs::remove_file(alias).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn crash_writer() {
        let Some(root) = std::env::var_os("NEXUS_TEST_CRASH_STORE") else {
            return;
        };
        let (store, _) = RequestStore::open(Path::new(&root)).unwrap();
        store.reserve("interrupted").unwrap();
        println!("RESERVATION_SYNCED");
        std::io::stdout().flush().unwrap();
        loop {
            std::thread::park();
        }
    }

    #[test]
    fn killed_writer_recovers_reservation_as_indeterminate() {
        let root = std::env::temp_dir().join(format!("nexus-crash-{}", uuid::Uuid::new_v4()));
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "request_store::tests::crash_writer",
                "--nocapture",
            ])
            .env("NEXUS_TEST_CRASH_STORE", &root)
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let mut output = BufReader::new(child.stdout.take().unwrap());
        let mut line = String::new();
        loop {
            line.clear();
            assert!(output.read_line(&mut line).unwrap() > 0);
            if line.trim() == "RESERVATION_SYNCED" {
                break;
            }
        }
        child.kill().unwrap();
        assert!(!child.wait().unwrap().success());
        let (store, recovered) = RequestStore::open(&root).unwrap();
        assert_eq!(recovered["interrupted"], RequestStatus::Indeterminate);
        assert_eq!(
            store.reserve("interrupted").unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        fs::remove_dir_all(root).unwrap();
    }
}
