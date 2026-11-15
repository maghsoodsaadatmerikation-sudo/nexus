use nexus_constitutional_core::{
    AnalysisBatch, AnalysisObservation, AnalysisObservationKind, Claim, ClaimOrigin,
    ProvenanceId, Uncertainty, WorkspaceEngine, WorkspaceEventKind,
};

fn machine_snapshot() -> nexus_constitutional_core::WorkspaceSnapshot {
    let mut engine = WorkspaceEngine::new(
        "machine-import",
        "Question",
        ProvenanceId::new("human:creator"),
    );
    engine.record_analysis_batch(AnalysisBatch {
        adapter_id: "nexus-local-question-probe-v1".into(),
        run_id: "claimed-run".into(),
        observations: vec![AnalysisObservation {
            id: "claimed-machine-1".into(),
            kind: AnalysisObservationKind::UncertaintyNote,
            text: "Claimed historical machine execution".into(),
            uncertainty: Uncertainty::High,
            source_ids: vec![],
        }],
    });
    engine.snapshot()
}

#[test]
fn a_valid_machine_event_is_not_proof_of_external_attestation() {
    let forged_history = machine_snapshot();
    // This is a well-formed Rust snapshot, but the importing client controls
    // its contents and is not an authenticated adapter.
    assert!(WorkspaceEngine::from_snapshot(forged_history.clone()).is_ok());
    assert!(forged_history.claims_unattested_machine_execution());
}

#[test]
fn imported_machine_origin_and_event_provenance_are_checked_separately() {
    let baseline = machine_snapshot();
    assert!(baseline.claims_unattested_machine_execution());

    let mut claim_only = baseline.clone();
    claim_only.events[1].kind = WorkspaceEventKind::ClaimAdded {
        claim_id: "claimed-machine-1".into(),
    };
    claim_only.events[1].provenance_id = ProvenanceId::new("human:reported");
    assert!(claim_only.claims_unattested_machine_execution());

    let mut event_only = baseline.clone();
    event_only.workspace.claims[0].origin = ClaimOrigin::Human;
    assert!(event_only.claims_unattested_machine_execution());

    let mut prefix_only =
        WorkspaceEngine::new("prefix", "Q", ProvenanceId::new("machine:claimed:run")).snapshot();
    assert!(prefix_only.claims_unattested_machine_execution());

    prefix_only.events[0].provenance_id = ProvenanceId::new("human:creator");
    assert!(!prefix_only.claims_unattested_machine_execution());
}

#[test]
fn generic_unverified_evidence_does_not_block_offline_workspace_import() {
    let mut engine = WorkspaceEngine::new(
        "offline",
        "Offline snapshot",
        ProvenanceId::new("offline:creator"),
    );
    engine
        .add_claim(
            Claim {
                id: "reported-1".into(),
                text: "A user-reported model suggestion".into(),
                origin: ClaimOrigin::ExternalEvidence {
                    source: "offline-bridge:user-reported-machine-analysis-unattested".into(),
                },
                uncertainty: Uncertainty::High,
            },
            ProvenanceId::new("offline:user"),
        )
        .unwrap();
    let original = engine.snapshot();
    assert!(WorkspaceEngine::from_snapshot(original.clone()).is_ok());
    assert!(!original.claims_unattested_machine_execution());
}
