use crate::{HumanJudgment, WorkspaceEventKind, WorkspaceSnapshot, WORKSPACE_SCHEMA_VERSION};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
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

        let path = self.path_for(&snapshot.workspace.id);
        if path.exists() {
            let existing = self
                .load(&snapshot.workspace.id)?
                .ok_or(DurableWorkspaceError::Io)?;
            validate_history_extension(&existing, &snapshot)?;
        }

        let bytes = serde_json::to_vec_pretty(&snapshot)
            .map_err(|_| DurableWorkspaceError::Serialization)?;
        let tmp = path.with_extension("json.tmp");
        {
            let mut file = File::create(&tmp).map_err(|_| DurableWorkspaceError::Io)?;
            file.write_all(&bytes)
                .map_err(|_| DurableWorkspaceError::Io)?;
            file.sync_all().map_err(|_| DurableWorkspaceError::Io)?;
        }
        fs::rename(&tmp, &path).map_err(|_| DurableWorkspaceError::Io)?;
        Ok(())
    }

    pub fn load(
        &self,
        workspace_id: &str,
    ) -> Result<Option<WorkspaceSnapshot>, DurableWorkspaceError> {
        let path = self.path_for(workspace_id);
        if !path.exists() {
            return Ok(None);
        }
        let mut bytes = Vec::new();
        File::open(path)
            .map_err(|_| DurableWorkspaceError::Io)?
            .read_to_end(&mut bytes)
            .map_err(|_| DurableWorkspaceError::Io)?;
        let snapshot: WorkspaceSnapshot = serde_json::from_slice(&bytes)
            .map_err(|_| DurableWorkspaceError::Serialization)?;
        validate_snapshot(&snapshot)?;
        Ok(Some(snapshot))
    }

    fn path_for(&self, workspace_id: &str) -> PathBuf {
        self.root.join(format!("{}.json", encode_id(workspace_id)))
    }
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
        || !matches!(snapshot.events[0].kind, WorkspaceEventKind::WorkspaceCreated)
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
            WorkspaceEventKind::AlternativeAdded { alternative_id } => Some(alternative_id.as_str()),
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
        assert_eq!(repo.save(first), Err(DurableWorkspaceError::HistoryRollback));
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
