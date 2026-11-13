use nexus_constitutional_core::*;
use std::{
    fs,
    path::PathBuf,
    sync::{Arc, Barrier},
    thread,
    time::{SystemTime, UNIX_EPOCH},
};

fn engine() -> WorkspaceEngine {
    let mut engine = WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p"));
    engine.add_claim(
        Claim {
            id: "c1".into(),
            text: "original".into(),
            origin: ClaimOrigin::Human,
            uncertainty: Uncertainty::Unknown,
        },
        ProvenanceId::new("source:1"),
    );
    engine.add_alternative(
        Alternative {
            id: "a1".into(),
            label: "Option".into(),
            consequences: vec!["original".into()],
        },
        ProvenanceId::new("human:p"),
    );
    engine
}
fn root() -> PathBuf {
    std::env::temp_dir().join(format!(
        "nexus-integrity-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ))
}
fn reject_on_all_import_paths(snapshot: WorkspaceSnapshot) {
    assert!(WorkspaceEngine::from_snapshot(snapshot.clone()).is_err());
    assert!(InMemoryWorkspaceRepository::default()
        .save(snapshot.clone())
        .is_err());
    let dir = root();
    assert!(FileWorkspaceRepository::new(&dir).save(snapshot).is_err());
    let _ = fs::remove_dir_all(dir);
}
#[test]
fn missing_provenance_rejected_consistently() {
    let mut s = engine().snapshot();
    s.events[0].provenance_id = ProvenanceId::new(" ");
    reject_on_all_import_paths(s);
}
#[test]
fn duplicate_creation_event_rejected_consistently() {
    let mut s = engine().snapshot();
    s.events.push(WorkspaceEvent {
        sequence: s.events.len() as u64,
        provenance_id: ProvenanceId::new("p"),
        kind: WorkspaceEventKind::WorkspaceCreated,
    });
    reject_on_all_import_paths(s);
}
#[test]
fn duplicate_claim_identifiers_rejected_consistently() {
    let mut e = engine();
    e.add_claim(e.workspace().claims[0].clone(), ProvenanceId::new("p"));
    reject_on_all_import_paths(e.snapshot());
}
#[test]
fn duplicate_alternative_identifiers_rejected_consistently() {
    let mut e = engine();
    e.add_alternative(
        e.workspace().alternatives[0].clone(),
        ProvenanceId::new("p"),
    );
    reject_on_all_import_paths(e.snapshot());
}
#[test]
fn machine_analysis_cannot_be_relabeled_as_human_on_import() {
    let mut e = engine();
    e.record_analysis_batch(AnalysisBatch {
        adapter_id: "test".into(),
        run_id: "run".into(),
        observations: vec![AnalysisObservation {
            id: "m1".into(),
            kind: AnalysisObservationKind::Counterargument,
            text: "draft".into(),
            uncertainty: Uncertainty::Unknown,
            source_ids: vec![],
        }],
    });
    let mut s = e.snapshot();
    s.workspace.claims.last_mut().unwrap().origin = ClaimOrigin::Human;
    reject_on_all_import_paths(s);
}
#[test]
fn storage_rejects_content_edits_even_with_an_extended_event_log() {
    let initial = engine().snapshot();
    for variant in 0..5 {
        let mut e = WorkspaceEngine::from_snapshot(initial.clone()).unwrap();
        e.add_claim(
            Claim {
                id: "c2".into(),
                text: "new".into(),
                origin: ClaimOrigin::Human,
                uncertainty: Uncertainty::Unknown,
            },
            ProvenanceId::new("p"),
        );
        let mut changed = e.snapshot();
        match variant {
            0 => changed.workspace.claims[0].text = "rewritten".into(),
            1 => changed.workspace.alternatives[0].label = "rewritten".into(),
            2 => changed.workspace.question = "rewritten".into(),
            3 => changed.workspace.values.push("rewritten".into()),
            _ => changed.workspace.claims[0].origin = ClaimOrigin::MachineAnalysis,
        }
        let mut memory = InMemoryWorkspaceRepository::default();
        memory.save(initial.clone()).unwrap();
        assert_eq!(
            memory.save(changed.clone()),
            Err(WorkspaceStoreError::HistoryDivergence)
        );
        let dir = root();
        let mut disk = FileWorkspaceRepository::new(&dir);
        disk.save(initial.clone()).unwrap();
        assert_eq!(
            disk.save(changed),
            Err(DurableWorkspaceError::HistoryDivergence)
        );
        assert_eq!(disk.load("w").unwrap(), Some(initial.clone()));
        fs::remove_dir_all(dir).unwrap();
    }
}
#[test]
fn memory_rejects_rollback_and_divergent_events() {
    let mut memory = InMemoryWorkspaceRepository::default();
    let s = engine().snapshot();
    memory.save(s.clone()).unwrap();
    assert_eq!(
        memory.save(WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:p")).snapshot()),
        Err(WorkspaceStoreError::HistoryRollback)
    );
    let mut divergent = s;
    divergent.events[0].provenance_id = ProvenanceId::new("other");
    assert_eq!(
        memory.save(divergent),
        Err(WorkspaceStoreError::HistoryDivergence)
    );
}
#[test]
fn loading_a_different_workspace_from_the_requested_path_fails() {
    let dir = root();
    let mut disk = FileWorkspaceRepository::new(&dir);
    let mut s = engine().snapshot();
    s.workspace.id = "other".into();
    disk.save(s).unwrap();
    fs::copy(dir.join("6f74686572.json"), dir.join("77.json")).unwrap();
    assert_eq!(disk.load("w"), Err(DurableWorkspaceError::IdentityMismatch));
    fs::remove_dir_all(dir).unwrap();
}
#[test]
fn oversized_disk_snapshot_is_rejected_before_json_parsing() {
    let dir = root();
    fs::create_dir_all(&dir).unwrap();
    let file = fs::File::create(dir.join("77.json")).unwrap();
    file.set_len(16 * 1024 * 1024 + 1).unwrap();
    assert_eq!(
        FileWorkspaceRepository::new(&dir).load("w"),
        Err(DurableWorkspaceError::Capacity)
    );
    fs::remove_dir_all(dir).unwrap();
}
#[test]
fn independent_writers_cannot_both_replace_a_shared_revision() {
    let dir = root();
    let initial = engine().snapshot();
    FileWorkspaceRepository::new(&dir)
        .save(initial.clone())
        .unwrap();
    let barrier = Arc::new(Barrier::new(8));
    let writers: Vec<_> = (0..8)
        .map(|i| {
            let dir = dir.clone();
            let barrier = barrier.clone();
            let mut e = WorkspaceEngine::from_snapshot(initial.clone()).unwrap();
            e.add_claim(
                Claim {
                    id: format!("writer-{i}"),
                    text: "candidate".into(),
                    origin: ClaimOrigin::Human,
                    uncertainty: Uncertainty::Unknown,
                },
                ProvenanceId::new("p"),
            );
            thread::spawn(move || {
                barrier.wait();
                FileWorkspaceRepository::new(dir).save(e.snapshot())
            })
        })
        .collect();
    let results: Vec<_> = writers.into_iter().map(|t| t.join().unwrap()).collect();
    assert_eq!(results.iter().filter(|r| r.is_ok()).count(), 1);
    assert_eq!(
        results
            .iter()
            .filter(|r| matches!(r, Err(DurableWorkspaceError::HistoryDivergence)))
            .count(),
        7
    );
    assert_eq!(
        FileWorkspaceRepository::new(&dir)
            .load("w")
            .unwrap()
            .unwrap()
            .workspace
            .claims
            .len(),
        2
    );
    assert!(!fs::read_dir(&dir).unwrap().any(|e| e
        .unwrap()
        .file_name()
        .to_string_lossy()
        .contains("tmp")));
    fs::remove_dir_all(dir).unwrap();
}
#[test]
fn unchanged_and_append_only_saves_remain_supported() {
    let dir = root();
    let mut e = engine();
    let s = e.snapshot();
    let mut disk = FileWorkspaceRepository::new(&dir);
    disk.save(s.clone()).unwrap();
    disk.save(s).unwrap();
    // Operational locking must not add files rejected by strict backup readers.
    assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
    e.record_human_judgment(
        HumanJudgment {
            decision: "A".into(),
            rationale: "Reviewed".into(),
        },
        ProvenanceId::new("human:p"),
    );
    disk.save(e.snapshot()).unwrap();
    assert_eq!(disk.load("w").unwrap(), Some(e.snapshot()));
    fs::remove_dir_all(dir).unwrap();
}

#[cfg(unix)]
#[test]
fn snapshot_symlinks_and_hardlinks_are_rejected_without_touching_targets() {
    use std::os::unix::fs::symlink;
    for kind in ["symlink", "hardlink", "dangling"] {
        let dir = root();
        fs::create_dir_all(&dir).unwrap();
        let outside = dir.with_extension("outside");
        let bytes = serde_json::to_vec(&engine().snapshot()).unwrap();
        if kind != "dangling" {
            fs::write(&outside, &bytes).unwrap();
        }
        if kind == "hardlink" {
            fs::hard_link(&outside, dir.join("77.json")).unwrap();
        } else {
            symlink(&outside, dir.join("77.json")).unwrap();
        }
        let mut disk = FileWorkspaceRepository::new(&dir);
        assert_eq!(disk.load("w"), Err(DurableWorkspaceError::Io));
        assert_eq!(
            disk.save(engine().snapshot()),
            Err(DurableWorkspaceError::Io)
        );
        if kind != "dangling" {
            assert_eq!(fs::read(&outside).unwrap(), bytes);
        } else {
            assert!(!outside.exists());
        }
        fs::remove_dir_all(dir).unwrap();
        if kind != "dangling" {
            fs::remove_file(outside).unwrap();
        }
    }
}

#[cfg(unix)]
#[test]
fn nonregular_snapshot_cannot_block_readers_or_be_replaced_by_save() {
    use std::{ffi::CString, os::unix::ffi::OsStrExt, sync::mpsc, time::Duration};
    let dir = root();
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("77.json");
    let name = CString::new(path.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe { libc::mkfifo(name.as_ptr(), 0o600) }, 0);
    let (tx, rx) = mpsc::channel();
    let reader_dir = dir.clone();
    thread::spawn(move || {
        let _ = tx.send(FileWorkspaceRepository::new(reader_dir).load("w"));
    });
    assert_eq!(
        rx.recv_timeout(Duration::from_secs(2))
            .expect("snapshot FIFO blocked a reader"),
        Err(DurableWorkspaceError::Io)
    );
    assert_eq!(
        FileWorkspaceRepository::new(&dir).save(engine().snapshot()),
        Err(DurableWorkspaceError::Io)
    );
    assert!(!fs::symlink_metadata(path).unwrap().is_file());
    fs::remove_dir_all(dir).unwrap();
}

#[cfg(unix)]
#[test]
fn directory_aliases_are_rejected_but_missing_repositories_remain_empty() {
    use std::os::unix::fs::symlink;
    let dir = root();
    let alias = dir.with_extension("alias");
    let mut disk = FileWorkspaceRepository::new(&dir);
    assert_eq!(disk.load("w").unwrap(), None);
    disk.save(engine().snapshot()).unwrap();
    let original = fs::read(dir.join("77.json")).unwrap();
    symlink(&dir, &alias).unwrap();
    for spelling in [
        alias.clone(),
        PathBuf::from(format!("{}/", alias.display())),
    ] {
        let mut aliased = FileWorkspaceRepository::new(spelling);
        assert_eq!(aliased.load("w"), Err(DurableWorkspaceError::Io));
        assert_eq!(
            aliased.save(engine().snapshot()),
            Err(DurableWorkspaceError::Io)
        );
    }
    assert_eq!(fs::read(dir.join("77.json")).unwrap(), original);
    fs::remove_file(alias).unwrap();
    fs::remove_dir_all(dir).unwrap();
}
