use nexus_constitutional_core::{
    AnalysisBatch, AnalysisObservation, AnalysisObservationKind, Claim, ClaimOrigin, ProvenanceId,
    Uncertainty, WorkspaceEngine,
};
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};

fn binary() -> &'static str {
    env!("CARGO_BIN_EXE_nexus-workspace-snapshot-verify")
}

fn temporary_file(name: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "nexus-semantic-{}-{unique}-{name}.json",
        std::process::id()
    ))
}

fn engine() -> WorkspaceEngine {
    let mut engine = WorkspaceEngine::new(
        "semantic-test",
        "Question",
        ProvenanceId::new("human:creator"),
    );
    engine.record_analysis_batch(AnalysisBatch {
        adapter_id: "local-probe".into(),
        run_id: "run-1".into(),
        observations: vec![AnalysisObservation {
            id: "analysis-1".into(),
            kind: AnalysisObservationKind::UncertaintyNote,
            text: "A question, not evidence".into(),
            uncertainty: Uncertainty::High,
            source_ids: vec![],
        }],
    });
    engine
}

fn run(path: &Path, expected_id: &str) -> std::process::Output {
    Command::new(binary())
        .args(["--snapshot", path.to_str().unwrap()])
        .args(["--expected-workspace-id", expected_id])
        .output()
        .unwrap()
}

#[test]
fn validates_snapshot_by_real_core_semantics_without_granting_authority() {
    let path = temporary_file("valid");
    fs::write(&path, serde_json::to_vec(&engine().snapshot()).unwrap()).unwrap();
    let result = run(&path, "semantic-test");
    assert!(result.status.success(), "{:?}", result.stderr);
    assert!(String::from_utf8_lossy(&result.stdout).contains("authority=none"));
    assert!(!run(&path, "different-destination").status.success());
    fs::remove_file(path).unwrap();
}

#[test]
fn rejects_signed_but_semantically_false_machine_origin_and_event_audit() {
    let mut snapshots = Vec::new();
    let mut origin = engine().snapshot();
    origin.workspace.claims[0].origin = ClaimOrigin::Human;
    snapshots.push(origin);

    let mut invalid_id = engine().snapshot();
    invalid_id.events[1].kind = nexus_constitutional_core::WorkspaceEventKind::ClaimAdded {
        claim_id: "unrelated".into(),
    };
    snapshots.push(invalid_id);

    let mut wrong_audit = engine().snapshot();
    wrong_audit.events[1].provenance_id = ProvenanceId::new("machine:fake:run");
    snapshots.push(wrong_audit);

    let mut duplicate_claim = engine().snapshot();
    duplicate_claim.workspace.claims.push(Claim {
        id: "analysis-1".into(),
        text: "duplicated".into(),
        origin: ClaimOrigin::MachineAnalysis,
        uncertainty: Uncertainty::Unknown,
    });
    snapshots.push(duplicate_claim);

    let mut wrong_sequence = engine().snapshot();
    wrong_sequence.events[1].sequence = 17;
    snapshots.push(wrong_sequence);

    for (i, snapshot) in snapshots.into_iter().enumerate() {
        let path = temporary_file(&format!("forged-{i}"));
        fs::write(&path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
        assert!(!run(&path, "semantic-test").status.success(), "variant {i}");
        fs::remove_file(path).unwrap();
    }
}

#[cfg(unix)]
#[test]
fn rejects_symlink_hardlink_and_oversized_inputs_without_reading_user_data() {
    use std::os::unix::fs::symlink;
    let path = temporary_file("file");
    let alias = temporary_file("alias");
    fs::write(&path, serde_json::to_vec(&engine().snapshot()).unwrap()).unwrap();
    symlink(&path, &alias).unwrap();
    assert!(!run(&alias, "semantic-test").status.success());
    fs::remove_file(&alias).unwrap();

    fs::hard_link(&path, &alias).unwrap();
    assert!(!run(&alias, "semantic-test").status.success());
    fs::remove_file(&alias).unwrap();
    fs::remove_file(&path).unwrap();

    let huge = temporary_file("huge");
    fs::File::create(&huge)
        .unwrap()
        .set_len(16 * 1024 * 1024 + 1)
        .unwrap();
    assert!(!run(&huge, "semantic-test").status.success());
    fs::remove_file(huge).unwrap();
}
