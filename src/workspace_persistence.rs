use crate::WorkspaceSnapshot;
use fs2::FileExt;
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::Arc,
};

const MAX_SNAPSHOT_BYTES: u64 = 16 * 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DurableWorkspaceError {
    UnsupportedSchemaVersion { found: u32, supported: u32 },
    InvalidAuditSequence,
    InvalidWorkspaceCreationEvent,
    MissingProvenance,
    ClaimAuditMismatch,
    AlternativeAuditMismatch,
    JudgmentAuditMismatch,
    HistoryRollback,
    HistoryDivergence,
    AlreadyExists,
    Io,
    Serialization,
    IdentityMismatch,
    Capacity,
}

#[derive(Debug, Clone)]
pub struct FileWorkspaceRepository {
    root: PathBuf,
    // Optional startup identity for a long-lived runtime. Short-lived
    // library callers retain the existing per-transaction behavior.
    pinned_root: Option<Arc<File>>,
}

impl FileWorkspaceRepository {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self {
            root: root.into(),
            pinned_root: None,
        }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Pin the writable data directory before accepting live traffic.
    /// If a volume/path changes after startup, reject later operations
    /// instead of silently creating a separate workspace history.
    pub fn pin_root(mut self) -> Result<Self, DurableWorkspaceError> {
        let directory =
            SnapshotDirectory::open(&self.root, true)?.ok_or(DurableWorkspaceError::Io)?;
        self.root = directory.root;
        self.pinned_root = Some(Arc::new(directory.file));
        self.verify_pin()?;
        Ok(self)
    }

    /// Read-only operational probe for a gateway-lifetime pinned workspace
    /// store. Missing, replaced or symlinked roots fail closed. This checks
    /// directory identity/accessibility, not disk writability or full-data
    /// integrity; an unpinned library instance has no runtime identity to
    /// certify and is deliberately rejected.
    pub fn check_runtime_readiness(&self) -> Result<(), DurableWorkspaceError> {
        if self.pinned_root.is_none() {
            return Err(DurableWorkspaceError::Io);
        }
        let directory = self.open_directory(false)?.ok_or(DurableWorkspaceError::Io)?;
        directory.verify()?;
        self.verify_pin()
    }

    fn verify_pin(&self) -> Result<(), DurableWorkspaceError> {
        if let Some(pinned) = &self.pinned_root {
            let linked = fs::symlink_metadata(&self.root).map_err(|_| DurableWorkspaceError::Io)?;
            let original = pinned.metadata().map_err(|_| DurableWorkspaceError::Io)?;
            if !linked.is_dir() || !original.is_dir() || !same_identity(&linked, &original) {
                return Err(DurableWorkspaceError::Io);
            }
        }
        Ok(())
    }

    fn open_directory(
        &self,
        create: bool,
    ) -> Result<Option<SnapshotDirectory>, DurableWorkspaceError> {
        self.verify_pin()?;
        // Never recreate a missing pinned path on a replacement volume.
        let directory =
            SnapshotDirectory::open(&self.root, create && self.pinned_root.is_none())?;
        if let Some(pinned) = &self.pinned_root {
            let opened = directory.as_ref().ok_or(DurableWorkspaceError::Io)?;
            let original = pinned.metadata().map_err(|_| DurableWorkspaceError::Io)?;
            let current = opened.file.metadata().map_err(|_| DurableWorkspaceError::Io)?;
            if !same_identity(&original, &current) {
                return Err(DurableWorkspaceError::Io);
            }
            self.verify_pin()?;
        }
        Ok(directory)
    }

    /// Atomically create an ID exactly once, even when separate gateway
    /// processes race. The existence check happens *inside* the same
    /// cross-process directory lock as the durable rename, never before it.
    pub fn create_new(
        &mut self,
        snapshot: WorkspaceSnapshot,
    ) -> Result<(), DurableWorkspaceError> {
        self.write_snapshot(snapshot, true)
    }

    /// Preserve audit-checked append/update semantics for existing workspaces.
    pub fn save(&mut self, snapshot: WorkspaceSnapshot) -> Result<(), DurableWorkspaceError> {
        self.write_snapshot(snapshot, false)
    }

    fn write_snapshot(
        &mut self,
        snapshot: WorkspaceSnapshot,
        must_be_absent: bool,
    ) -> Result<(), DurableWorkspaceError> {
        validate_snapshot(&snapshot)?;
        let directory = self.open_directory(true)?.ok_or(DurableWorkspaceError::Io)?;
        let path = directory.path_for(&snapshot.workspace.id);
        // Lock the directory itself: no lock metadata enters the data tree or
        // its strict recovery archives. This serializes cooperating writers
        // across all workspaces; the kernel releases the lock on process exit.
        directory
            .file
            .lock_exclusive()
            .map_err(|_| DurableWorkspaceError::Io)?;
        directory.verify()?;
        if let Some(existing) = directory.load(&snapshot.workspace.id)? {
            if must_be_absent {
                return Err(DurableWorkspaceError::AlreadyExists);
            }
            validate_history_extension(&existing, &snapshot)?;
        }

        let bytes = serde_json::to_vec_pretty(&snapshot)
            .map_err(|_| DurableWorkspaceError::Serialization)?;
        if bytes.len() as u64 > MAX_SNAPSHOT_BYTES {
            return Err(DurableWorkspaceError::Capacity);
        }
        let (tmp, mut file) = temporary_file(&path)?;
        let _cleanup = TemporaryFile(tmp.clone());
        {
            file.write_all(&bytes)
                .map_err(|_| DurableWorkspaceError::Io)?;
            file.sync_all().map_err(|_| DurableWorkspaceError::Io)?;
        }
        directory.verify()?;
        fs::rename(&tmp, &path).map_err(|_| DurableWorkspaceError::Io)?;
        // Persist the directory entry, not only the temporary file contents.
        #[cfg(unix)]
        directory
            .file
            .sync_all()
            .map_err(|_| DurableWorkspaceError::Io)?;
        directory.verify()?;
        self.verify_pin()
    }

    pub fn load(
        &self,
        workspace_id: &str,
    ) -> Result<Option<WorkspaceSnapshot>, DurableWorkspaceError> {
        match self.open_directory(false)? {
            Some(directory) => {
                let result = directory.load(workspace_id)?;
                self.verify_pin()?;
                Ok(result)
            }
            None => Ok(None),
        }
    }
}

// Pin one directory for the whole read or write transaction. On Linux every
// child operation resolves through the descriptor, not mutable ancestor paths.
struct SnapshotDirectory {
    root: PathBuf,
    file: File,
}

impl SnapshotDirectory {
    fn open(root: &Path, create: bool) -> Result<Option<Self>, DurableWorkspaceError> {
        let root = if root.is_absolute() {
            root.to_owned()
        } else {
            std::env::current_dir()
                .map_err(|_| DurableWorkspaceError::Io)?
                .join(root)
        };
        // A trailing slash otherwise makes the kernel follow a final symlink
        // before O_NOFOLLOW/symlink_metadata can inspect it as the final entry.
        let root: PathBuf = root.components().collect();
        if create {
            fs::create_dir_all(&root).map_err(|_| DurableWorkspaceError::Io)?;
        }
        let initial = match fs::symlink_metadata(&root) {
            Ok(meta) if meta.is_dir() => meta,
            Ok(_) => return Err(DurableWorkspaceError::Io),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound && !create => return Ok(None),
            Err(_) => return Err(DurableWorkspaceError::Io),
        };
        let mut options = OpenOptions::new();
        options.read(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.custom_flags(
                libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC,
            );
        }
        let file = options.open(&root).map_err(|_| DurableWorkspaceError::Io)?;
        if !same_identity(
            &initial,
            &file.metadata().map_err(|_| DurableWorkspaceError::Io)?,
        ) {
            return Err(DurableWorkspaceError::Io);
        }
        let directory = Self { root, file };
        directory.verify()?;
        Ok(Some(directory))
    }

    fn verify(&self) -> Result<(), DurableWorkspaceError> {
        let linked = fs::symlink_metadata(&self.root).map_err(|_| DurableWorkspaceError::Io)?;
        let pinned = self
            .file
            .metadata()
            .map_err(|_| DurableWorkspaceError::Io)?;
        if !linked.is_dir() || !pinned.is_dir() || !same_identity(&linked, &pinned) {
            return Err(DurableWorkspaceError::Io);
        }
        Ok(())
    }

    fn path_for(&self, workspace_id: &str) -> PathBuf {
        #[cfg(target_os = "linux")]
        let root = {
            use std::os::fd::AsRawFd;
            Path::new("/proc/self/fd").join(self.file.as_raw_fd().to_string())
        };
        #[cfg(not(target_os = "linux"))]
        let root = self.root.clone();
        root.join(format!("{}.json", encode_id(workspace_id)))
    }

    fn load(&self, workspace_id: &str) -> Result<Option<WorkspaceSnapshot>, DurableWorkspaceError> {
        self.verify()?;
        let path = self.path_for(workspace_id);
        let initial = match fs::symlink_metadata(&path) {
            Ok(meta) => meta,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                self.verify()?;
                return Ok(None);
            }
            Err(_) => return Err(DurableWorkspaceError::Io),
        };
        regular_snapshot(&initial)?;
        let mut options = OpenOptions::new();
        options.read(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC);
        }
        let file = match options.open(&path) {
            Ok(file) => file,
            Err(_) => return Err(DurableWorkspaceError::Io),
        };
        let before = file.metadata().map_err(|_| DurableWorkspaceError::Io)?;
        regular_snapshot(&before)?;
        if !stable_file(&initial, &before) {
            return Err(DurableWorkspaceError::Io);
        }
        let mut bytes = Vec::new();
        (&file)
            .take(MAX_SNAPSHOT_BYTES + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| DurableWorkspaceError::Io)?;
        if bytes.len() as u64 > MAX_SNAPSHOT_BYTES {
            return Err(DurableWorkspaceError::Capacity);
        }
        let after = file.metadata().map_err(|_| DurableWorkspaceError::Io)?;
        let linked = fs::symlink_metadata(&path).map_err(|_| DurableWorkspaceError::Io)?;
        regular_snapshot(&after)?;
        regular_snapshot(&linked)?;
        if !stable_file(&before, &after)
            || !stable_file(&after, &linked)
            || after.len() != bytes.len() as u64
        {
            return Err(DurableWorkspaceError::Io);
        }
        self.verify()?;
        let snapshot: WorkspaceSnapshot =
            serde_json::from_slice(&bytes).map_err(|_| DurableWorkspaceError::Serialization)?;
        validate_snapshot(&snapshot)?;
        if snapshot.workspace.id != workspace_id {
            return Err(DurableWorkspaceError::IdentityMismatch);
        }
        Ok(Some(snapshot))
    }
}

fn regular_snapshot(meta: &fs::Metadata) -> Result<(), DurableWorkspaceError> {
    if !meta.is_file() {
        return Err(DurableWorkspaceError::Io);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if meta.nlink() != 1 {
            return Err(DurableWorkspaceError::Io);
        }
    }
    if meta.len() > MAX_SNAPSHOT_BYTES {
        return Err(DurableWorkspaceError::Capacity);
    }
    Ok(())
}

fn same_identity(a: &fs::Metadata, b: &fs::Metadata) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        (a.dev(), a.ino()) == (b.dev(), b.ino())
    }
    #[cfg(not(unix))]
    {
        a.file_type() == b.file_type() && a.created().ok() == b.created().ok()
    }
}

fn stable_file(a: &fs::Metadata, b: &fs::Metadata) -> bool {
    if !same_identity(a, b) || a.len() != b.len() || a.modified().ok() != b.modified().ok() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        (a.nlink(), a.ctime(), a.ctime_nsec()) == (b.nlink(), b.ctime(), b.ctime_nsec())
    }
    #[cfg(not(unix))]
    {
        true
    }
}

struct TemporaryFile(PathBuf);
impl Drop for TemporaryFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

fn temporary_file(path: &Path) -> Result<(PathBuf, File), DurableWorkspaceError> {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    loop {
        let tmp = path.with_extension(format!(
            "json.tmp-{}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        match options.open(&tmp) {
            Ok(file) => return Ok((tmp, file)),
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(_) => return Err(DurableWorkspaceError::Io),
        }
    }
}

fn validate_history_extension(
    existing: &WorkspaceSnapshot,
    candidate: &WorkspaceSnapshot,
) -> Result<(), DurableWorkspaceError> {
    crate::workspace::validate_history_extension(existing, candidate).map_err(map_validation_error)
}

fn validate_snapshot(snapshot: &WorkspaceSnapshot) -> Result<(), DurableWorkspaceError> {
    crate::workspace::validate_snapshot(snapshot).map_err(map_validation_error)
}

fn map_validation_error(error: crate::WorkspaceStoreError) -> DurableWorkspaceError {
    use crate::WorkspaceStoreError as E;
    match error {
        E::UnsupportedSchemaVersion { found, supported } => {
            DurableWorkspaceError::UnsupportedSchemaVersion { found, supported }
        }
        E::InvalidAuditSequence => DurableWorkspaceError::InvalidAuditSequence,
        E::InvalidWorkspaceCreationEvent => DurableWorkspaceError::InvalidWorkspaceCreationEvent,
        E::MissingProvenance => DurableWorkspaceError::MissingProvenance,
        E::ClaimAuditMismatch => DurableWorkspaceError::ClaimAuditMismatch,
        E::AlternativeAuditMismatch => DurableWorkspaceError::AlternativeAuditMismatch,
        E::JudgmentAuditMismatch => DurableWorkspaceError::JudgmentAuditMismatch,
        E::HistoryRollback => DurableWorkspaceError::HistoryRollback,
        E::HistoryDivergence => DurableWorkspaceError::HistoryDivergence,
    }
}

fn encode_id(value: &str) -> String {
    let mut out = String::with_capacity(value.len() * 2);
    for byte in value.as_bytes() {
        use std::fmt::Write as _;
        let _ = write!(&mut out, "{byte:02x}");
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Claim, ClaimOrigin, ProvenanceId, Uncertainty, WorkspaceEngine};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_root(name: &str) -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("nexus-{name}-{stamp}"))
    }

    fn claim(id: &str) -> Claim {
        Claim {
            id: id.into(),
            text: "Evidence".into(),
            origin: ClaimOrigin::Human,
            uncertainty: Uncertainty::Unknown,
        }
    }

    #[test]
    fn concurrent_creates_for_identical_workspace_id_have_one_winner() {
        use std::sync::{Arc, Barrier};
        use std::thread;

        let root = temp_root("atomic-create-race");
        fs::create_dir_all(&root).unwrap();
        let initial = WorkspaceEngine::new(
            "same-id",
            "Original",
            ProvenanceId::new("human"),
        )
        .snapshot();
        let mut workers = Vec::new();
        let start = Arc::new(Barrier::new(8));
        for _ in 0..8 {
            let root = root.clone();
            let snapshot = initial.clone();
            let start = Arc::clone(&start);
            workers.push(thread::spawn(move || {
                let mut repo = FileWorkspaceRepository::new(root).pin_root().unwrap();
                start.wait();
                repo.create_new(snapshot)
            }));
        }
        let mut created = 0;
        let mut duplicate = 0;
        for handle in workers {
            match handle.join().unwrap() {
                Ok(()) => created += 1,
                Err(DurableWorkspaceError::AlreadyExists) => duplicate += 1,
                other => panic!("unexpected atomic create result: {other:?}"),
            }
        }
        assert_eq!(created, 1);
        assert_eq!(duplicate, 7);
        let mut repository = FileWorkspaceRepository::new(&root).pin_root().unwrap();
        assert_eq!(repository.load("same-id").unwrap(), Some(initial.clone()));
        assert_eq!(
            repository.create_new(initial.clone()),
            Err(DurableWorkspaceError::AlreadyExists)
        );
        // Existing validated workspace history extension remains supported,
        // while create-if-absent never replaces it.
        let mut engine = WorkspaceEngine::from_snapshot(initial).unwrap();
        engine.add_claim(claim("new-claim"), ProvenanceId::new("human"));
        let extended = engine.snapshot();
        repository.save(extended.clone()).unwrap();
        assert_eq!(
            repository.create_new(extended.clone()),
            Err(DurableWorkspaceError::AlreadyExists)
        );
        assert_eq!(repository.load("same-id").unwrap(), Some(extended));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn durable_round_trip_preserves_snapshot() {
        let root = temp_root("round-trip");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut engine =
            WorkspaceEngine::new("workspace/1", "Question", ProvenanceId::new("human:p1"));
        engine.add_claim(claim("c-1"), ProvenanceId::new("source:1"));
        let snapshot = engine.snapshot();
        repo.save(snapshot.clone()).unwrap();
        assert_eq!(repo.load("workspace/1").unwrap(), Some(snapshot));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn durable_repository_rejects_history_rollback() {
        let root = temp_root("rollback");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut engine = WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p"));
        let first = engine.snapshot();
        repo.save(first.clone()).unwrap();
        engine.add_claim(claim("c-1"), ProvenanceId::new("human:p"));
        repo.save(engine.snapshot()).unwrap();
        assert_eq!(
            repo.save(first),
            Err(DurableWorkspaceError::HistoryRollback)
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn durable_repository_rejects_divergent_history() {
        let root = temp_root("divergence");
        let mut repo = FileWorkspaceRepository::new(&root);
        let engine = WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p"));
        let first = engine.snapshot();
        repo.save(first.clone()).unwrap();
        let mut divergent = first;
        divergent.events[0].provenance_id = ProvenanceId::new("human:other");
        assert_eq!(
            repo.save(divergent),
            Err(DurableWorkspaceError::HistoryDivergence)
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn durable_repository_rejects_missing_provenance() {
        let root = temp_root("provenance");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut snapshot =
            WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p")).snapshot();
        snapshot.events[0].provenance_id = ProvenanceId::new(" ");
        assert_eq!(
            repo.save(snapshot),
            Err(DurableWorkspaceError::MissingProvenance)
        );
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn durable_repository_rejects_future_schema() {
        let root = temp_root("schema");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut snapshot =
            WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p")).snapshot();
        snapshot.schema_version += 1;
        assert!(matches!(
            repo.save(snapshot),
            Err(DurableWorkspaceError::UnsupportedSchemaVersion { .. })
        ));
        let _ = fs::remove_dir_all(root);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn gateway_pinned_root_rejects_substitution_then_accepts_exact_restoration() {
        let parent = temp_root("runtime-root-identity");
        let root = parent.join("workspaces");
        let moved = parent.with_extension("moved");
        let mut repo = FileWorkspaceRepository::new(&root).pin_root().unwrap();
        let first = WorkspaceEngine::new("w", "Original", ProvenanceId::new("p")).snapshot();
        repo.save(first.clone()).unwrap();
        assert_eq!(repo.load("w").unwrap(), Some(first.clone()));

        // A vanished mount/ancestor is replaced by another writable folder.
        fs::rename(&parent, &moved).unwrap();
        fs::create_dir_all(&root).unwrap();
        let witness = root.join("sentinel");
        fs::write(&witness, b"not the original store").unwrap();
        let second = WorkspaceEngine::new("new", "Other", ProvenanceId::new("p")).snapshot();
        assert_eq!(repo.load("w"), Err(DurableWorkspaceError::Io));
        assert_eq!(repo.save(second.clone()), Err(DurableWorkspaceError::Io));
        assert_eq!(fs::read(&witness).unwrap(), b"not the original store");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);

        // A symlink alias to the original directory must not be accepted
        // as a recovery of the configured actual directory pathname.
        fs::remove_dir_all(&parent).unwrap();
        fs::create_dir_all(&parent).unwrap();
        std::os::unix::fs::symlink(moved.join("workspaces"), &root).unwrap();
        assert_eq!(repo.load("w"), Err(DurableWorkspaceError::Io));
        assert_eq!(repo.save(second.clone()), Err(DurableWorkspaceError::Io));
        fs::remove_file(&root).unwrap();
        fs::remove_dir(&parent).unwrap();

        // Returning the original inode to the configured path preserves its
        // history and allows legitimate extensions and new workspaces.
        fs::rename(&moved, &parent).unwrap();
        assert_eq!(repo.load("w").unwrap(), Some(first));
        repo.save(second.clone()).unwrap();
        assert_eq!(repo.load("new").unwrap(), Some(second));
        fs::remove_dir_all(parent).unwrap();
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn pinned_directory_cannot_redirect_operations_after_an_ancestor_is_replaced() {
        let parent = temp_root("pinned-ancestor");
        let root = parent.join("workspaces");
        let original = parent.with_extension("original");
        let mut repo = FileWorkspaceRepository::new(&root);
        let snapshot = WorkspaceEngine::new("w", "Question", ProvenanceId::new("p")).snapshot();
        repo.save(snapshot.clone()).unwrap();
        let directory = SnapshotDirectory::open(&root, false).unwrap().unwrap();
        fs::rename(&parent, &original).unwrap();
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("77.json"), b"replacement must remain untouched").unwrap();
        assert!(directory.verify().is_err());
        assert!(directory.load("w").is_err());
        // Even the internal descriptor path continues to name the original,
        // rather than silently resolving into the replacement directory.
        let old: WorkspaceSnapshot =
            serde_json::from_slice(&fs::read(directory.path_for("w")).unwrap()).unwrap();
        assert_eq!(old, snapshot);
        assert_eq!(
            fs::read(root.join("77.json")).unwrap(),
            b"replacement must remain untouched"
        );
        fs::remove_dir_all(parent).unwrap();
        fs::remove_dir_all(original).unwrap();
    }
}
