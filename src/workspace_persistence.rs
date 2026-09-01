use crate::{WorkspaceSnapshot, WorkspaceStoreError, WorkspaceRepository};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
};

#[derive(Debug, Clone)]
pub struct FileWorkspaceRepository {
    root: PathBuf,
}

impl FileWorkspaceRepository {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn root(&self) -> &Path { &self.root }

    pub fn save(&mut self, snapshot: WorkspaceSnapshot) -> Result<(), WorkspaceStoreError> {
        crate::workspace::validate_snapshot(&snapshot)?;
        fs::create_dir_all(&self.root).map_err(|_| WorkspaceStoreError::Io)?;

        let path = self.path_for(&snapshot.workspace.id);
        if path.exists() {
            let existing = self.load(&snapshot.workspace.id)?.ok_or(WorkspaceStoreError::Io)?;
            crate::workspace::validate_history_extension(&existing, &snapshot)?;
        }

        let bytes = serde_json::to_vec_pretty(&snapshot).map_err(|_| WorkspaceStoreError::Serialization)?;
        let tmp = path.with_extension("json.tmp");
        {
            let mut file = File::create(&tmp).map_err(|_| WorkspaceStoreError::Io)?;
            file.write_all(&bytes).map_err(|_| WorkspaceStoreError::Io)?;
            file.sync_all().map_err(|_| WorkspaceStoreError::Io)?;
        }
        fs::rename(&tmp, &path).map_err(|_| WorkspaceStoreError::Io)?;
        Ok(())
    }

    pub fn load(&self, workspace_id: &str) -> Result<Option<WorkspaceSnapshot>, WorkspaceStoreError> {
        let path = self.path_for(workspace_id);
        if !path.exists() {
            return Ok(None);
        }
        let mut bytes = Vec::new();
        File::open(path)
            .map_err(|_| WorkspaceStoreError::Io)?
            .read_to_end(&mut bytes)
            .map_err(|_| WorkspaceStoreError::Io)?;
        let snapshot: WorkspaceSnapshot =
            serde_json::from_slice(&bytes).map_err(|_| WorkspaceStoreError::Serialization)?;
        crate::workspace::validate_snapshot(&snapshot)?;
        Ok(Some(snapshot))
    }

    fn path_for(&self, workspace_id: &str) -> PathBuf {
        self.root.join(format!("{}.json", encode_id(workspace_id)))
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

    #[test]
    fn durable_round_trip_preserves_snapshot() {
        let root = temp_root("round-trip");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut engine = WorkspaceEngine::new("workspace/1", "Question", ProvenanceId::new("human:p1"));
        engine.add_claim(
            Claim {
                id: "c-1".into(),
                text: "Evidence".into(),
                origin: ClaimOrigin::ExternalEvidence { source: "source-1".into() },
                uncertainty: Uncertainty::Low,
            },
            ProvenanceId::new("source:1"),
        );
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
        engine.add_claim(
            Claim {
                id: "c-1".into(),
                text: "Evidence".into(),
                origin: ClaimOrigin::Human,
                uncertainty: Uncertainty::Unknown,
            },
            ProvenanceId::new("human:p"),
        );
        repo.save(engine.snapshot()).unwrap();
        assert_eq!(repo.save(first), Err(WorkspaceStoreError::HistoryRollback));
        fs::remove_dir_all(root).unwrap();
    }
}
