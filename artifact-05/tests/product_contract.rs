use axum::{body::Body, http::{Request, StatusCode}};
use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, Submission, WorkspaceDelegate,
    WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, Claim, HumanJudgment, ProvenanceId, RequestEnvelope, WorkspaceEngine,
    WorkspaceSnapshot,
};
use tower::ServiceExt;

#[derive(Clone, Copy, Default)]
struct ProductDelegate;

impl ConstitutionalDelegate for ProductDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        Ok(Submission { request_id: envelope.request_id })
    }
}

impl WorkspaceDelegate for ProductDelegate {
    fn create_workspace(
        &self,
        workspace_id: String,
        question: String,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Ok(WorkspaceEngine::new(workspace_id, question, provenance_id).snapshot())
    }

    fn import_workspace(
        &self,
        snapshot: WorkspaceSnapshot,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        WorkspaceEngine::from_snapshot(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        Ok(snapshot)
    }

    fn get_workspace(&self, _workspace_id: &str) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::NotFound)
    }

    fn add_claim(
        &self,
        _workspace_id: &str,
        _claim: Claim,
        _provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::NotFound)
    }

    fn add_alternative(
        &self,
        _workspace_id: &str,
        _alternative: Alternative,
        _provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::NotFound)
    }

    fn record_human_judgment(
        &self,
        _workspace_id: &str,
        _judgment: HumanJudgment,
        _provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::NotFound)
    }
}

fn create_request(token: Option<&str>) -> Request<Body> {
    let mut builder = Request::builder()
        .method("POST")
        .uri("/v1/workspaces")
        .header("content-type", "application/json");
    if let Some(token) = token {
        builder = builder.header("authorization", format!("Bearer {token}"));
    }
    builder
        .body(Body::from(
            serde_json::json!({
                "workspace_id": "w-auth",
                "question": "Question",
                "provenance_id": "human:owner"
            })
            .to_string(),
        ))
        .unwrap()
}

#[tokio::test]
async fn authenticated_workspace_rejects_missing_or_wrong_bearer() {
    let app = router(AppState::authenticated(ProductDelegate, "secret"));
    assert_eq!(
        app.clone().oneshot(create_request(None)).await.unwrap().status(),
        StatusCode::UNAUTHORIZED
    );
    assert_eq!(
        app.oneshot(create_request(Some("wrong"))).await.unwrap().status(),
        StatusCode::UNAUTHORIZED
    );
}

#[tokio::test]
async fn authenticated_workspace_accepts_matching_bearer() {
    let app = router(AppState::authenticated(ProductDelegate, "secret"));
    assert_eq!(
        app.oneshot(create_request(Some("secret"))).await.unwrap().status(),
        StatusCode::CREATED
    );
}

#[tokio::test]
async fn import_revalidates_snapshot_before_acceptance() {
    let app = router(AppState::authenticated(ProductDelegate, "secret"));
    let mut snapshot = WorkspaceEngine::new("imported", "Question", ProvenanceId::new("human:owner"))
        .snapshot();
    snapshot.events[0].sequence = 7;
    let request = Request::builder()
        .method("POST")
        .uri("/v1/workspaces/import")
        .header("content-type", "application/json")
        .header("authorization", "Bearer secret")
        .body(Body::from(serde_json::to_string(&snapshot).unwrap()))
        .unwrap();
    assert_eq!(
        app.oneshot(request).await.unwrap().status(),
        StatusCode::UNPROCESSABLE_ENTITY
    );
}
