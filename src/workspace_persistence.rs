use crate::WorkspaceSnapshot;
use fs2::FileExt;
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
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
    Io,
    Serialization,
    IdentityMismatch,
    Capacity,
}

#[derive(Debug, Clone)]
pub struct FileWorkspaceRepository {
    root: PathBuf,
}

impl FileWorkspaceRepository {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn save(&mut self, snapshot: WorkspaceSnapshot) -> Result<(), DurableWorkspaceError> {
        validate_snapshot(&snapshot)?;
        fs::create_dir_all(&self.root).map_err(|_| DurableWorkspaceError::Io)?;

        let path = self.path_for(&snapshot.workspace.id);
        // Lock the directory itself: no lock metadata enters the data tree or
        // its strict recovery archives. This serializes cooperating writers
        // across all workspaces; the kernel releases the lock on process exit.
        let lock = File::open(&self.root).map_err(|_| DurableWorkspaceError::Io)?;
        lock.lock_exclusive()
            .map_err(|_| DurableWorkspaceError::Io)?;
        if let Some(existing) = self.load(&snapshot.workspace.id)? {
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
        fs::rename(&tmp, &path).map_err(|_| DurableWorkspaceError::Io)?;
        // Persist the directory entry, not only the temporary file contents.
        #[cfg(unix)]
        File::open(&self.root)
            .and_then(|directory| directory.sync_all())
            .map_err(|_| DurableWorkspaceError::Io)?;
        Ok(())
    }

    pub fn load(
        &self,
        workspace_id: &str,
    ) -> Result<Option<WorkspaceSnapshot>, DurableWorkspaceError> {
        let path = self.path_for(workspace_id);
        let file = match File::open(path) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(_) => return Err(DurableWorkspaceError::Io),
        };
        let mut bytes = Vec::new();
        file.take(MAX_SNAPSHOT_BYTES + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| DurableWorkspaceError::Io)?;
        if bytes.len() as u64 > MAX_SNAPSHOT_BYTES {
            return Err(DurableWorkspaceError::Capacity);
        }
        let snapshot: WorkspaceSnapshot =
            serde_json::from_slice(&bytes).map_err(|_| DurableWorkspaceError::Serialization)?;
        validate_snapshot(&snapshot)?;
        if snapshot.workspace.id != workspace_id {
            return Err(DurableWorkspaceError::IdentityMismatch);
        }
        Ok(Some(snapshot))
    }

    fn path_for(&self, workspace_id: &str) -> PathBuf {
        self.root.join(format!("{}.json", encode_id(workspace_id)))
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
}
