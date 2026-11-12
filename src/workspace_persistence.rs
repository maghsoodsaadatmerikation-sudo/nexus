use crate::{HumanJudgment, WorkspaceEventKind, WorkspaceSnapshot, WORKSPACE_SCHEMA_VERSION};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

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
    WorkspaceIdentityMismatch,
    Io,
    Serialization,
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
        // Persist newly created ancestors before acknowledging any snapshot.
        let absolute_root = fs::canonicalize(&self.root).map_err(|_| DurableWorkspaceError::Io)?;
        for directory in absolute_root.ancestors() {
            sync_directory(directory)?;
        }

        let path = self.path_for(&snapshot.workspace.id);
        if let Some(existing) = self.load(&snapshot.workspace.id)? {
            validate_history_extension(&existing, &snapshot)?;
        }

        let bytes = serde_json::to_vec_pretty(&snapshot)
            .map_err(|_| DurableWorkspaceError::Serialization)?;
        let (tmp, mut file) = create_temporary_snapshot(&path)?;
        let result = (|| {
            file.write_all(&bytes)
                .map_err(|_| DurableWorkspaceError::Io)?;
            file.sync_all().map_err(|_| DurableWorkspaceError::Io)?;
            fs::rename(&tmp, &path).map_err(|_| DurableWorkspaceError::Io)?;
            // File fsync alone does not persist the rename after power loss.
            sync_directory(&absolute_root)
        })();
        drop(file);
        // Never remove another writer's file; this name was exclusively created.
        let _ = fs::remove_file(&tmp);
        result
    }

    pub fn load(
        &self,
        workspace_id: &str,
    ) -> Result<Option<WorkspaceSnapshot>, DurableWorkspaceError> {
        let path = self.path_for(workspace_id);
        let mut file = match File::open(path) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(_) => return Err(DurableWorkspaceError::Io),
        };
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes)
            .map_err(|_| DurableWorkspaceError::Io)?;
        let snapshot: WorkspaceSnapshot =
            serde_json::from_slice(&bytes).map_err(|_| DurableWorkspaceError::Serialization)?;
        validate_snapshot(&snapshot)?;
        if snapshot.workspace.id != workspace_id {
            return Err(DurableWorkspaceError::WorkspaceIdentityMismatch);
        }
        Ok(Some(snapshot))
    }

    fn path_for(&self, workspace_id: &str) -> PathBuf {
        self.root.join(format!("{}.json", encode_id(workspace_id)))
    }
}

fn sync_directory(path: &Path) -> Result<(), DurableWorkspaceError> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| DurableWorkspaceError::Io)
}

fn create_temporary_snapshot(path: &Path) -> Result<(PathBuf, File), DurableWorkspaceError> {
    static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);
    for _ in 0..128 {
        let sequence = NEXT_TEMP.fetch_add(1, Ordering::Relaxed);
        let tmp = path.with_extension(format!("json.tmp-{}-{sequence}", std::process::id()));
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
    Err(DurableWorkspaceError::Io)
}

fn validate_history_extension(
    existing: &WorkspaceSnapshot,
    candidate: &WorkspaceSnapshot,
) -> Result<(), DurableWorkspaceError> {
    validate_snapshot(existing)?;
    validate_snapshot(candidate)?;
    if candidate.events.len() < existing.events.len() {
        return Err(DurableWorkspaceError::HistoryRollback);
    }
    if candidate.events[..existing.events.len()] != existing.events[..] {
        return Err(DurableWorkspaceError::HistoryDivergence);
    }
    let old = &existing.workspace;
    let new = &candidate.workspace;
    // Events identify claims/alternatives by ID, so event-prefix equality alone
    // cannot detect silent edits to their content or the original question.
    if old.id != new.id
        || old.question != new.question
        || old.goal != new.goal
        || old.constraints != new.constraints
        || old.values != new.values
        || !new.claims.starts_with(&old.claims)
        || !new.alternatives.starts_with(&old.alternatives)
    {
        return Err(DurableWorkspaceError::HistoryDivergence);
    }
    Ok(())
}

fn validate_snapshot(snapshot: &WorkspaceSnapshot) -> Result<(), DurableWorkspaceError> {
    if snapshot.schema_version != WORKSPACE_SCHEMA_VERSION {
        return Err(DurableWorkspaceError::UnsupportedSchemaVersion {
            found: snapshot.schema_version,
            supported: WORKSPACE_SCHEMA_VERSION,
        });
    }

    if snapshot.events.is_empty()
        || !matches!(
            snapshot.events[0].kind,
            WorkspaceEventKind::WorkspaceCreated
        )
        || snapshot.events[1..]
            .iter()
            .any(|event| matches!(event.kind, WorkspaceEventKind::WorkspaceCreated))
    {
        return Err(DurableWorkspaceError::InvalidWorkspaceCreationEvent);
    }

    if snapshot
        .events
        .iter()
        .enumerate()
        .any(|(index, event)| event.sequence != index as u64)
    {
        return Err(DurableWorkspaceError::InvalidAuditSequence);
    }

    if snapshot
        .events
        .iter()
        .any(|event| event.provenance_id.0.trim().is_empty())
    {
        return Err(DurableWorkspaceError::MissingProvenance);
    }

    let audited_claim_ids: Vec<&str> = snapshot
        .events
        .iter()
        .filter_map(|event| match &event.kind {
            WorkspaceEventKind::ClaimAdded { claim_id }
            | WorkspaceEventKind::MachineAnalysisRecorded { claim_id, .. } => {
                Some(claim_id.as_str())
            }
            _ => None,
        })
        .collect();
    let workspace_claim_ids: Vec<&str> = snapshot
        .workspace
        .claims
        .iter()
        .map(|claim| claim.id.as_str())
        .collect();
    if audited_claim_ids != workspace_claim_ids {
        return Err(DurableWorkspaceError::ClaimAuditMismatch);
    }

    let audited_alternative_ids: Vec<&str> = snapshot
        .events
        .iter()
        .filter_map(|event| match &event.kind {
            WorkspaceEventKind::AlternativeAdded { alternative_id } => {
                Some(alternative_id.as_str())
            }
            _ => None,
        })
        .collect();
    let workspace_alternative_ids: Vec<&str> = snapshot
        .workspace
        .alternatives
        .iter()
        .map(|alternative| alternative.id.as_str())
        .collect();
    if audited_alternative_ids != workspace_alternative_ids {
        return Err(DurableWorkspaceError::AlternativeAuditMismatch);
    }

    let mut audited_judgment: Option<HumanJudgment> = None;
    for event in &snapshot.events {
        if let WorkspaceEventKind::HumanJudgmentTransition { previous, current } = &event.kind {
            if previous.as_ref() != audited_judgment.as_ref() {
                return Err(DurableWorkspaceError::JudgmentAuditMismatch);
            }
            audited_judgment = Some(current.clone());
        }
    }
    if audited_judgment != snapshot.workspace.judgment {
        return Err(DurableWorkspaceError::JudgmentAuditMismatch);
    }

    Ok(())
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

    #[test]
    fn rejects_snapshot_stored_under_another_workspace_id() {
        let root = temp_root("identity");
        let mut repo = FileWorkspaceRepository::new(&root);
        let snapshot =
            WorkspaceEngine::new("a", "Question", ProvenanceId::new("human:p")).snapshot();
        repo.save(snapshot).unwrap();
        fs::copy(repo.path_for("a"), repo.path_for("b")).unwrap();
        assert!(repo.load("b").is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_content_rewrites_hidden_behind_unchanged_audit_events() {
        let root = temp_root("content-rewrite");
        let mut repo = FileWorkspaceRepository::new(&root);
        let mut engine = WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p"));
        engine.add_claim(claim("c"), ProvenanceId::new("human:p"));
        engine.add_alternative(
            crate::Alternative {
                id: "a".into(),
                label: "Original".into(),
                consequences: vec![],
            },
            ProvenanceId::new("human:p"),
        );
        let original = engine.snapshot();
        repo.save(original.clone()).unwrap();
        let mut candidates = vec![original.clone(); 7];
        candidates[0].workspace.question = "Rewritten".into();
        candidates[1].workspace.claims[0].text = "Rewritten".into();
        candidates[2].workspace.claims[0].origin = ClaimOrigin::MachineAnalysis;
        candidates[3].workspace.alternatives[0].label = "Rewritten".into();
        candidates[4].workspace.goal = Some("Rewritten".into());
        candidates[5].workspace.constraints.push("Rewritten".into());
        candidates[6].workspace.values.push("Rewritten".into());
        for candidate in candidates {
            assert_eq!(
                repo.save(candidate),
                Err(DurableWorkspaceError::HistoryDivergence)
            );
            assert_eq!(repo.load("w").unwrap(), Some(original.clone()));
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn stale_temporary_file_is_neither_followed_nor_overwritten() {
        let root = temp_root("stale-temp");
        fs::create_dir_all(&root).unwrap();
        let mut repo = FileWorkspaceRepository::new(&root);
        let stale = repo.path_for("w").with_extension("json.tmp");
        fs::write(&stale, b"previous interrupted write").unwrap();
        let snapshot =
            WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p")).snapshot();
        repo.save(snapshot.clone()).unwrap();
        assert_eq!(fs::read(&stale).unwrap(), b"previous interrupted write");
        assert_eq!(repo.load("w").unwrap(), Some(snapshot));
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn saved_snapshot_is_private_even_with_default_umask() {
        use std::os::unix::fs::PermissionsExt;
        let root = temp_root("private-mode");
        let mut repo = FileWorkspaceRepository::new(&root);
        repo.save(WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p")).snapshot())
            .unwrap();
        assert_eq!(
            fs::metadata(repo.path_for("w"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        fs::remove_dir_all(root).unwrap();
    }
}
