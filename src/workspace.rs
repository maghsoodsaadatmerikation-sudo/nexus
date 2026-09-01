use crate::{Alternative, Claim, DecisionWorkspace, HumanJudgment};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const WORKSPACE_SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProvenanceId(pub String);

impl ProvenanceId {
    pub fn new(value: impl Into<String>) -> Self { Self(value.into()) }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum WorkspaceEventKind {
    WorkspaceCreated,
    ClaimAdded { claim_id: String },
    AlternativeAdded { alternative_id: String },
    HumanJudgmentRecorded,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkspaceEvent {
    pub sequence: u64,
    pub provenance_id: ProvenanceId,
    pub kind: WorkspaceEventKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkspaceSnapshot {
    pub schema_version: u32,
    pub workspace: DecisionWorkspace,
    pub events: Vec<WorkspaceEvent>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkspaceStoreError {
    UnsupportedSchemaVersion { found: u32, supported: u32 },
    DuplicateWorkspace(String),
}

pub trait WorkspaceRepository {
    fn save(&mut self, snapshot: WorkspaceSnapshot) -> Result<(), WorkspaceStoreError>;
    fn load(&self, workspace_id: &str) -> Option<WorkspaceSnapshot>;
}

#[derive(Debug, Default)]
pub struct InMemoryWorkspaceRepository {
    snapshots: HashMap<String, WorkspaceSnapshot>,
}

impl WorkspaceRepository for InMemoryWorkspaceRepository {
    fn save(&mut self, snapshot: WorkspaceSnapshot) -> Result<(), WorkspaceStoreError> {
        if snapshot.schema_version != WORKSPACE_SCHEMA_VERSION {
            return Err(WorkspaceStoreError::UnsupportedSchemaVersion {
                found: snapshot.schema_version,
                supported: WORKSPACE_SCHEMA_VERSION,
            });
        }
        self.snapshots.insert(snapshot.workspace.id.clone(), snapshot);
        Ok(())
    }

    fn load(&self, workspace_id: &str) -> Option<WorkspaceSnapshot> {
        self.snapshots.get(workspace_id).cloned()
    }
}

#[derive(Debug, Clone)]
pub struct WorkspaceEngine {
    workspace: DecisionWorkspace,
    events: Vec<WorkspaceEvent>,
    next_sequence: u64,
}

impl WorkspaceEngine {
    pub fn new(
        id: impl Into<String>,
        question: impl Into<String>,
        provenance_id: ProvenanceId,
    ) -> Self {
        let workspace = DecisionWorkspace::new(id, question);
        Self {
            workspace,
            events: vec![WorkspaceEvent {
                sequence: 0,
                provenance_id,
                kind: WorkspaceEventKind::WorkspaceCreated,
            }],
            next_sequence: 1,
        }
    }

    pub fn from_snapshot(snapshot: WorkspaceSnapshot) -> Result<Self, WorkspaceStoreError> {
        if snapshot.schema_version != WORKSPACE_SCHEMA_VERSION {
            return Err(WorkspaceStoreError::UnsupportedSchemaVersion {
                found: snapshot.schema_version,
                supported: WORKSPACE_SCHEMA_VERSION,
            });
        }
        let next_sequence = snapshot.events.last().map_or(0, |event| event.sequence + 1);
        Ok(Self {
            workspace: snapshot.workspace,
            events: snapshot.events,
            next_sequence,
        })
    }

    pub fn workspace(&self) -> &DecisionWorkspace { &self.workspace }

    pub fn events(&self) -> &[WorkspaceEvent] { &self.events }

    pub fn add_claim(&mut self, claim: Claim, provenance_id: ProvenanceId) {
        let claim_id = claim.id.clone();
        self.workspace.add_claim(claim);
        self.append_event(provenance_id, WorkspaceEventKind::ClaimAdded { claim_id });
    }

    pub fn add_alternative(&mut self, alternative: Alternative, provenance_id: ProvenanceId) {
        let alternative_id = alternative.id.clone();
        self.workspace.add_alternative(alternative);
        self.append_event(
            provenance_id,
            WorkspaceEventKind::AlternativeAdded { alternative_id },
        );
    }

    pub fn record_human_judgment(
        &mut self,
        judgment: HumanJudgment,
        provenance_id: ProvenanceId,
    ) {
        self.workspace.record_human_judgment(judgment);
        self.append_event(provenance_id, WorkspaceEventKind::HumanJudgmentRecorded);
    }

    pub fn snapshot(&self) -> WorkspaceSnapshot {
        WorkspaceSnapshot {
            schema_version: WORKSPACE_SCHEMA_VERSION,
            workspace: self.workspace.clone(),
            events: self.events.clone(),
        }
    }

    fn append_event(&mut self, provenance_id: ProvenanceId, kind: WorkspaceEventKind) {
        self.events.push(WorkspaceEvent {
            sequence: self.next_sequence,
            provenance_id,
            kind,
        });
        self.next_sequence += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ClaimOrigin, Uncertainty};

    #[test]
    fn audit_events_are_append_only_and_sequenced() {
        let mut engine = WorkspaceEngine::new("w-1", "Question", ProvenanceId::new("human:p1"));
        engine.add_claim(
            Claim {
                id: "c-1".into(),
                text: "Evidence".into(),
                origin: ClaimOrigin::ExternalEvidence { source: "source-1".into() },
                uncertainty: Uncertainty::Medium,
            },
            ProvenanceId::new("source:1"),
        );
        engine.record_human_judgment(
            HumanJudgment { decision: "A".into(), rationale: "Human choice".into() },
            ProvenanceId::new("human:p1"),
        );

        assert_eq!(engine.events().len(), 3);
        assert_eq!(engine.events()[0].sequence, 0);
        assert_eq!(engine.events()[1].sequence, 1);
        assert_eq!(engine.events()[2].sequence, 2);
        assert!(engine.workspace().has_human_judgment());
    }

    #[test]
    fn persistence_round_trip_preserves_workspace_and_audit_history() {
        let engine = WorkspaceEngine::new("w-2", "Question", ProvenanceId::new("human:p2"));
        let snapshot = engine.snapshot();
        let mut repository = InMemoryWorkspaceRepository::default();
        repository.save(snapshot.clone()).unwrap();
        let loaded = repository.load("w-2").unwrap();
        assert_eq!(loaded, snapshot);

        let restored = WorkspaceEngine::from_snapshot(loaded).unwrap();
        assert_eq!(restored.workspace().id, "w-2");
        assert_eq!(restored.events().len(), 1);
    }

    #[test]
    fn unsupported_schema_is_rejected() {
        let engine = WorkspaceEngine::new("w-3", "Question", ProvenanceId::new("human:p3"));
        let mut snapshot = engine.snapshot();
        snapshot.schema_version = WORKSPACE_SCHEMA_VERSION + 1;
        assert!(matches!(
            WorkspaceEngine::from_snapshot(snapshot),
            Err(WorkspaceStoreError::UnsupportedSchemaVersion { .. })
        ));
    }
}
