use nexus_constitutional_core::{
    AnalysisBatch, AnalysisObservation, AnalysisObservationKind, Claim, ClaimOrigin,
    DurableWorkspaceError, FileWorkspaceRepository, InMemoryWorkspaceRepository, ProvenanceId,
    Uncertainty, WorkspaceEngine, WorkspaceRepository, WorkspaceSnapshot, WorkspaceStoreError,
};
use std::{
    fs,
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};

fn machine_analysis() -> WorkspaceEngine {
    let mut workspace = WorkspaceEngine::new(
        "provenance-workspace",
        "Should this claim be trusted?",
        ProvenanceId::new("human:creator"),
    );
    workspace.record_analysis_batch(AnalysisBatch {
        adapter_id: "research".into(),
        run_id: "run-17".into(),
        observations: vec![AnalysisObservation {
            id: "claim-17".into(),
            kind: AnalysisObservationKind::Counterargument,
            text: "Machine-generated interpretation".into(),
            uncertainty: Uncertainty::High,
            source_ids: vec!["source-4".into()],
        }],
    });
    workspace
}

fn temporary_root() -> PathBuf {
    std::env::temp_dir().join(format!(
        "nexus-provenance-audit-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock")
            .as_nanos()
    ))
}

fn assert_rejected_on_every_import(snapshot: WorkspaceSnapshot) {
    assert_eq!(
        WorkspaceEngine::from_snapshot(snapshot.clone()).unwrap_err(),
        WorkspaceStoreError::ClaimAuditMismatch
    );
    let mut memory = InMemoryWorkspaceRepository::default();
    assert_eq!(
        memory.save(snapshot.clone()),
        Err(WorkspaceStoreError::ClaimAuditMismatch)
    );
    let root = temporary_root();
    let mut disk = FileWorkspaceRepository::new(&root);
    assert_eq!(
        disk.save(snapshot),
        Err(DurableWorkspaceError::ClaimAuditMismatch)
    );
    assert!(!root.exists(), "invalid snapshots must not touch the durable store");
}

#[test]
fn generic_claim_event_cannot_impersonate_machine_analysis() {
    let mut workspace = WorkspaceEngine::new(
        "provenance-workspace",
        "Question",
        ProvenanceId::new("human:creator"),
    );
    workspace.add_claim(
        Claim {
            id: "forged-machine-claim".into(),
            text: "Looks like machine analysis, but is not".into(),
            origin: ClaimOrigin::MachineAnalysis,
            uncertainty: Uncertainty::Unknown,
        },
        ProvenanceId::new("machine:research:run-17"),
    );
    assert_rejected_on_every_import(workspace.snapshot());
}

#[test]
fn machine_analysis_provenance_must_match_its_adapter_and_run() {
    let mut snapshot = machine_analysis().snapshot();
    snapshot.events[1].provenance_id = ProvenanceId::new("machine:other:run-17");
    assert_rejected_on_every_import(snapshot);
}

#[test]
fn machine_analysis_rejects_unrelated_nonempty_provenance() {
    let mut snapshot = machine_analysis().snapshot();
    snapshot.events[1].provenance_id = ProvenanceId::new("human:creator");
    assert_rejected_on_every_import(snapshot);
}

#[test]
fn genuine_machine_analysis_retains_all_existing_import_paths() {
    let snapshot = machine_analysis().snapshot();
    assert!(WorkspaceEngine::from_snapshot(snapshot.clone()).is_ok());
    let mut memory = InMemoryWorkspaceRepository::default();
    memory.save(snapshot.clone()).unwrap();
    assert_eq!(
        memory.load("provenance-workspace"),
        Some(snapshot.clone())
    );
    let root = temporary_root();
    let mut disk = FileWorkspaceRepository::new(&root);
    disk.save(snapshot.clone()).unwrap();
    assert_eq!(disk.load("provenance-workspace").unwrap(), Some(snapshot));
    fs::remove_dir_all(root).unwrap();
}
