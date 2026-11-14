mod health;
mod listener;

use axum::{routing::get, Json};
use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, SafetyConfig, Submission,
    WorkspaceDelegate, WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, AnalysisBatch, Claim, DurableWorkspaceError, FileWorkspaceRepository,
    HumanJudgment, PolicyEngine, ProvenanceId, RequestEnvelope, WorkspaceEngine, WorkspaceSnapshot,
};
use serde::Serialize;
use std::{net::SocketAddr, path::PathBuf, sync::Mutex, time::Duration};

#[derive(Debug, Serialize)]
struct RuntimeIdentity {
    schema: &'static str,
    source_tree_sha256: &'static str,
    authority: &'static str,
}

async fn runtime_identity() -> Json<RuntimeIdentity> {
    Json(RuntimeIdentity {
        schema: "nexus.runtime-identity.v1",
        source_tree_sha256: option_env!("NEXUS_SOURCE_TREE_SHA256").unwrap_or("unavailable"),
        authority: "non_authoritative_build_metadata",
    })
}

struct CoreDelegate {
    workspaces: Mutex<FileWorkspaceRepository>,
    // Independent read-only probe: readiness must not wait for a writer's mutex.
    workspace_probe: FileWorkspaceRepository,
}

impl CoreDelegate {
    fn new(root: PathBuf) -> Result<Self, DurableWorkspaceError> {
        let repository = FileWorkspaceRepository::new(root).pin_root()?;
        let workspace_probe = repository.clone();
        Ok(Self {
            workspaces: Mutex::new(repository),
            workspace_probe,
        })
    }
}

impl ConstitutionalDelegate for CoreDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        let request = PolicyEngine::new()
            .authorize(envelope)
            .map_err(|_| DelegateError)?;
        let receipt = nexus_constitutional_core::Executor::new().execute(request);
        Ok(Submission {
            request_id: receipt.request_id().to_owned(),
        })
    }
}

fn map_durable_error(error: DurableWorkspaceError) -> WorkspaceDelegateError {
    match error {
        DurableWorkspaceError::Io => WorkspaceDelegateError::StorageUnavailable,
        DurableWorkspaceError::AlreadyExists => WorkspaceDelegateError::AlreadyExists,
        _ => WorkspaceDelegateError::Invalid,
    }
}

impl WorkspaceDelegate for CoreDelegate {
    fn check_storage_readiness(&self) -> Result<(), WorkspaceDelegateError> {
        self.workspace_probe
            .check_runtime_readiness()
            .map_err(map_durable_error)
    }

    fn create_workspace(
        &self,
        workspace_id: String,
        question: String,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        let snapshot = WorkspaceEngine::new(workspace_id, question, provenance_id).snapshot();
        repository
            .create_new(snapshot.clone())
            .map_err(map_durable_error)?;
        Ok(snapshot)
    }

    fn import_workspace(
        &self,
        snapshot: WorkspaceSnapshot,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        WorkspaceEngine::from_snapshot(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        repository
            .create_new(snapshot.clone())
            .map_err(map_durable_error)?;
        Ok(snapshot)
    }

    fn get_workspace(
        &self,
        workspace_id: &str,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?
            .load(workspace_id)
            .map_err(map_durable_error)?
            .ok_or(WorkspaceDelegateError::NotFound)
    }

    fn add_claim(
        &self,
        workspace_id: &str,
        claim: Claim,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.add_claim(claim, provenance_id)
        })
    }

    fn add_alternative(
        &self,
        workspace_id: &str,
        alternative: Alternative,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.add_alternative(alternative, provenance_id)
        })
    }

    fn record_analysis_batch(
        &self,
        workspace_id: &str,
        batch: AnalysisBatch,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| engine.record_analysis_batch(batch))
    }

    fn record_human_judgment(
        &self,
        workspace_id: &str,
        judgment: HumanJudgment,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.record_human_judgment(judgment, provenance_id)
        })
    }
}

impl CoreDelegate {
    fn mutate_workspace<F>(
        &self,
        workspace_id: &str,
        mutate: F,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>
    where
        F: FnOnce(&mut WorkspaceEngine),
    {
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        let snapshot = repository
            .load(workspace_id)
            .map_err(map_durable_error)?
            .ok_or(WorkspaceDelegateError::NotFound)?;
        let mut engine = WorkspaceEngine::from_snapshot(snapshot)
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        mutate(&mut engine);
        let snapshot = engine.snapshot();
        repository
            .save(snapshot.clone())
            .map_err(map_durable_error)?;
        Ok(snapshot)
    }
}

#[tokio::main]
async fn main() {
    if std::env::args_os().nth(1).as_deref() == Some(std::ffi::OsStr::new("--health-check")) {
        let success = std::env::args_os().len() == 2 && health::from_env().is_ok();
        std::process::exit(if success { 0 } else { 1 });
    }
    let token = std::env::var("NEXUS_API_TOKEN")
        .expect("NEXUS_API_TOKEN is required for authenticated workspace access");
    assert!(
        !token.trim().is_empty(),
        "NEXUS_API_TOKEN must not be empty"
    );
    let data_root = std::env::var_os("NEXUS_DATA_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("nexus-data"));
    let bind_addr =
        std::env::var("NEXUS_BIND_ADDR").unwrap_or_else(|_| "127.0.0.1:3000".to_owned());
    let addr: SocketAddr = bind_addr.parse().expect("valid NEXUS_BIND_ADDR");
    let max_body_bytes = positive_env_usize("NEXUS_MAX_BODY_BYTES", 64 * 1024);
    let max_requests_per_window = positive_env_u64("NEXUS_RATE_LIMIT_REQUESTS", 120);
    let rate_window_seconds = positive_env_u64("NEXUS_RATE_LIMIT_WINDOW_SECONDS", 60);
    let max_tracked_requests = positive_env_usize("NEXUS_MAX_TRACKED_REQUESTS", 10_000);
    eprintln!(
        "NEXUS_OP event=startup bind_addr={} data_dir={} auth=configured",
        addr,
        data_root.display()
    );
    let safety = SafetyConfig::new(
        max_body_bytes,
        max_requests_per_window,
        Duration::from_secs(rate_window_seconds),
        max_tracked_requests,
    );
    // Pin the workspace directory before serving. If the volume later
    // vanishes or gets replaced, its next operation must fail closed rather
    // than adopt the substitute directory as the workspace store.
    let core_delegate = CoreDelegate::new(data_root.clone()).expect("pin workspace data root");
    let app = router(
        AppState::authenticated(core_delegate, token)
            .with_safety(safety)
            .with_recovery_gate(&data_root)
            .expect("inspect recovery quarantine")
            .with_request_store(data_root.join("requests"))
            .expect("open durable request store"),
    )
    .route("/v1/runtime-identity", get(runtime_identity));
    let listener = listener::open(addr).await.expect("open gateway listener");
    if let Err(error) = axum::serve(listener, app).await {
        eprintln!("NEXUS_OP event=server_exit error={error}");
        std::process::exit(1);
    }
}

fn positive_env_usize(name: &str, default: usize) -> usize {
    std::env::var(name)
        .map(|value| {
            value
                .parse::<usize>()
                .expect("positive integer safety limit")
        })
        .unwrap_or(default)
        .checked_sub(1)
        .map(|value| value + 1)
        .expect("safety limit must be positive")
}

fn positive_env_u64(name: &str, default: u64) -> u64 {
    std::env::var(name)
        .map(|value| value.parse::<u64>().expect("positive integer safety limit"))
        .unwrap_or(default)
        .checked_sub(1)
        .map(|value| value + 1)
        .expect("safety limit must be positive")
}

#[cfg(test)]
mod operational_storage_tests {
    use super::*;
    use axum::{
        body::{to_bytes, Body},
        http::{Request, StatusCode},
    };
    use tower::ServiceExt;

    #[tokio::test]
    async fn live_workspace_mount_substitution_flips_readiness_and_storage_errors() {
        let root = std::env::temp_dir().join(format!(
            "nexus-workspace-readiness-{}",
            uuid::Uuid::new_v4()
        ));
        let moved = root.with_extension("moved");
        let delegate = CoreDelegate::new(root.clone()).unwrap();
        delegate
            .create_workspace(
                "original".into(),
                "Question".into(),
                ProvenanceId::new("user"),
            )
            .unwrap();
        let app = router(AppState::authenticated(delegate, "test-secret"));
        let initial = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/readyz")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(initial.status(), StatusCode::OK);

        // Simulate the live workspace directory being replaced by an empty,
        // writable directory. Request ledger health does not cover this test.
        std::fs::rename(&root, &moved).unwrap();
        std::fs::create_dir(&root).unwrap();
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/readyz")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(response.headers()["cache-control"], "no-store");
        let bytes = to_bytes(response.into_body(), 128).await.unwrap();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&bytes).unwrap(),
            serde_json::json!({"status":"workspace_unavailable"})
        );

        for (method, path, body) in [
            ("GET", "/v1/workspaces/original", ""),
            (
                "POST",
                "/v1/workspaces",
                r#"{"workspace_id":"substitute","question":"Q","provenance_id":"p"}"#,
            ),
        ] {
            let response = app
                .clone()
                .oneshot(
                    Request::builder()
                        .method(method)
                        .uri(path)
                        .header("authorization", "Bearer test-secret")
                        .header("content-type", "application/json")
                        .body(Body::from(body))
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(
                response.status(),
                StatusCode::SERVICE_UNAVAILABLE,
                "{method} {path}"
            );
            let bytes = to_bytes(response.into_body(), 128).await.unwrap();
            assert_eq!(
                serde_json::from_slice::<serde_json::Value>(&bytes).unwrap(),
                serde_json::json!({"error":"workspace_storage_unavailable"})
            );
        }
        assert_eq!(std::fs::read_dir(&root).unwrap().count(), 0);
        let alive = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/livez")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(alive.status(), StatusCode::OK);

        // Only the exact pinned directory inode restores readiness.
        std::fs::remove_dir(&root).unwrap();
        std::fs::rename(&moved, &root).unwrap();
        let restored = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/readyz")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(restored.status(), StatusCode::OK);
        let loaded = app
            .oneshot(
                Request::builder()
                    .uri("/v1/workspaces/original")
                    .header("authorization", "Bearer test-secret")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(loaded.status(), StatusCode::OK);
        std::fs::remove_dir_all(root).unwrap();
    }
}
