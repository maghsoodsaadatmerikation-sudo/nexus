use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, RequestStatus, Submission,
    WorkspaceDelegate, WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, AnalysisBatch, Claim, HumanJudgment, InMemoryWorkspaceRepository, ProvenanceId,
    RequestEnvelope, WorkspaceEngine, WorkspaceRepository, WorkspaceSnapshot,
};
use std::sync::{Arc, Mutex};
use tower::ServiceExt;

#[derive(Clone, Default)]
struct RecordingDelegate {
    requests: Arc<Mutex<Vec<RequestEnvelope>>>,
    workspaces: Arc<Mutex<InMemoryWorkspaceRepository>>,
}

impl ConstitutionalDelegate for RecordingDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        let request_id = envelope.request_id.clone();
        self.requests.lock().unwrap().push(envelope);
        Ok(Submission { request_id })
    }
}

impl WorkspaceDelegate for RecordingDelegate {
    fn create_workspace(
        &self,
        workspace_id: String,
        question: String,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        let mut repository = self.workspaces.lock().unwrap();
        if repository.load(&workspace_id).is_some() {
            return Err(WorkspaceDelegateError::AlreadyExists);
        }
        let snapshot = WorkspaceEngine::new(workspace_id, question, provenance_id).snapshot();
        repository
            .save(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        Ok(snapshot)
    }

    fn get_workspace(
        &self,
        workspace_id: &str,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.workspaces
            .lock()
            .unwrap()
            .load(workspace_id)
            .ok_or(WorkspaceDelegateError::NotFound)
    }

    fn add_claim(
        &self,
        workspace_id: &str,
        claim: Claim,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate(workspace_id, |engine| {
            engine.add_claim(claim, provenance_id)
        })
    }

    fn add_alternative(
        &self,
        workspace_id: &str,
        alternative: Alternative,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate(workspace_id, |engine| {
            engine.add_alternative(alternative, provenance_id)
        })
    }

    fn record_analysis_batch(
        &self,
        workspace_id: &str,
        batch: AnalysisBatch,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate(workspace_id, |engine| {
            engine.record_analysis_batch(batch)
        })
    }

    fn record_human_judgment(
        &self,
        workspace_id: &str,
        judgment: HumanJudgment,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate(workspace_id, |engine| {
            engine.record_human_judgment(judgment, provenance_id)
        })
    }
}

impl RecordingDelegate {
    fn mutate<F>(
        &self,
        workspace_id: &str,
        mutate: F,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>
    where
        F: FnOnce(&mut WorkspaceEngine),
    {
        let mut repository = self.workspaces.lock().unwrap();
        let snapshot = repository
            .load(workspace_id)
            .ok_or(WorkspaceDelegateError::NotFound)?;
        let mut engine = WorkspaceEngine::from_snapshot(snapshot)
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        mutate(&mut engine);
        let snapshot = engine.snapshot();
        repository
            .save(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        Ok(snapshot)
    }
}

#[tokio::test]
async fn post_requests_is_async_202_and_delegates_opaque_payload() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::new(delegate.clone()));

    let body = serde_json::json!({
        "request_id": "contract-05",
        "authority": "user",
        "action": "present",
        "value": "opaque-value",
        "payload": "opaque-payload"
    });

    let request = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();

    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::ACCEPTED);

    let calls = delegate.requests.lock().unwrap();
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].request_id, "contract-05");
    assert_eq!(calls[0].payload, "opaque-payload");
}

#[tokio::test]
async fn accepted_request_is_reported_as_pending() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::new(delegate));

    let request = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::json!({
                "request_id": "pending-05",
                "authority": "user",
                "action": "present",
                "value": "opaque",
                "payload": "opaque"
            })
            .to_string(),
        ))
        .unwrap();

    let response = app.clone().oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::ACCEPTED);

    let body = axum::body::to_bytes(response.into_body(), usize::MAX)
        .await
        .unwrap();
    let accepted: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(accepted["request_id"], "pending-05");
    assert_eq!(accepted["status"], "pending");

    let status_request = Request::builder()
        .method("GET")
        .uri("/v1/requests/pending-05")
        .body(Body::empty())
        .unwrap();
    let status_response = app.oneshot(status_request).await.unwrap();
    assert_eq!(status_response.status(), StatusCode::OK);

    let status_body = axum::body::to_bytes(status_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let status: serde_json::Value = serde_json::from_slice(&status_body).unwrap();
    assert_eq!(status["request_id"], "pending-05");
    assert_eq!(
        status["status"],
        serde_json::to_value(RequestStatus::Pending).unwrap()
    );
}

#[tokio::test]
async fn unknown_request_status_is_404() {
    let app = router(AppState::new(RecordingDelegate::default()));

    let request = Request::builder()
        .method("GET")
        .uri("/v1/requests/does-not-exist")
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn workspace_lifecycle_is_delegated_and_auditable() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::new(delegate));

    let create = Request::builder()
        .method("POST")
        .uri("/v1/workspaces")
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::json!({
                "workspace_id": "w-http",
                "question": "Which option should I examine?",
                "provenance_id": "human:owner"
            })
            .to_string(),
        ))
        .unwrap();
    let created = app.clone().oneshot(create).await.unwrap();
    assert_eq!(created.status(), StatusCode::CREATED);

    let claim = Request::builder()
        .method("POST")
        .uri("/v1/workspaces/w-http/claims")
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::json!({
                "claim_id": "c-http",
                "text": "Human-provided evidence remains explicit",
                "origin": {"kind": "human"},
                "uncertainty": "medium",
                "provenance_id": "human:owner"
            })
            .to_string(),
        ))
        .unwrap();
    let claim_response = app.clone().oneshot(claim).await.unwrap();
    assert_eq!(claim_response.status(), StatusCode::OK);

    let analysis = Request::builder()
        .method("POST")
        .uri("/v1/workspaces/w-http/analysis")
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::json!({
                "adapter_id": "challenge-adapter",
                "run_id": "run-http-1",
                "observations": [{
                    "id": "m-http",
                    "kind": "Counterargument",
                    "text": "A machine-generated counterargument",
                    "uncertainty": "High",
                    "source_ids": ["source:example"]
                }]
            })
            .to_string(),
        ))
        .unwrap();
    let analysis_response = app.clone().oneshot(analysis).await.unwrap();
    assert_eq!(analysis_response.status(), StatusCode::OK);
    let analysis_body = axum::body::to_bytes(analysis_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let analysis_snapshot: serde_json::Value = serde_json::from_slice(&analysis_body).unwrap();
    assert!(analysis_snapshot["workspace"]["judgment"].is_null());
    assert_eq!(analysis_snapshot["workspace"]["claims"].as_array().unwrap().len(), 2);
    assert_eq!(
        analysis_snapshot["workspace"]["claims"][1]["origin"],
        "MachineAnalysis"
    );

    let judgment = Request::builder()
        .method("POST")
        .uri("/v1/workspaces/w-http/judgment")
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::json!({
                "decision": "Option A",
                "rationale": "Explicit human choice",
                "provenance_id": "human:owner"
            })
            .to_string(),
        ))
        .unwrap();
    let judgment_response = app.clone().oneshot(judgment).await.unwrap();
    assert_eq!(judgment_response.status(), StatusCode::OK);

    let get = Request::builder()
        .method("GET")
        .uri("/v1/workspaces/w-http")
        .body(Body::empty())
        .unwrap();
    let get_response = app.oneshot(get).await.unwrap();
    assert_eq!(get_response.status(), StatusCode::OK);
    let get_body = axum::body::to_bytes(get_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let snapshot: serde_json::Value = serde_json::from_slice(&get_body).unwrap();
    assert_eq!(snapshot["workspace"]["judgment"]["decision"], "Option A");
    assert_eq!(snapshot["events"].as_array().unwrap().len(), 4);
}

#[tokio::test]
async fn malformed_workspace_claim_is_422_before_delegate() {
    let app = router(AppState::new(RecordingDelegate::default()));
    let request = Request::builder()
        .method("POST")
        .uri("/v1/workspaces/w/claims")
        .header("content-type", "application/json")
        .body(Body::from(
            r#"{"text":"missing origin","uncertainty":"medium","provenance_id":"source:1"}"#,
        ))
        .unwrap();
    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::UNPROCESSABLE_ENTITY);
}
