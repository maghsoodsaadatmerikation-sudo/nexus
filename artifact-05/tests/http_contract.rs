use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, RequestStatus, Submission,
    SafetyConfig, WorkspaceDelegate, WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, AnalysisBatch, Claim, HumanJudgment, InMemoryWorkspaceRepository, ProvenanceId,
    RequestEnvelope, WorkspaceEngine, WorkspaceRepository, WorkspaceSnapshot,
};
use std::{
    sync::{Arc, Mutex},
    time::Duration,
};
use tower::ServiceExt;

#[derive(Clone, Default)]
struct RecordingDelegate {
    requests: Arc<Mutex<Vec<RequestEnvelope>>>,
    workspaces: Arc<Mutex<InMemoryWorkspaceRepository>>,
    fail_requests: bool,
}

impl ConstitutionalDelegate for RecordingDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        if self.fail_requests {
            return Err(DelegateError);
        }
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
        self.mutate(workspace_id, |engine| engine.record_analysis_batch(batch))
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
async fn unknown_and_authority_like_fields_fail_closed_before_delegation() {
    for field in [
        "capability",
        "grant",
        "revocation_epoch",
        "authorized",
        "policy",
        "unexpected",
    ] {
        let delegate = RecordingDelegate::default();
        let app = router(AppState::new(delegate.clone()));
        let mut body = serde_json::json!({
            "request_id": "ambiguous-05",
            "authority": "user",
            "action": "present",
            "value": "opaque-value",
            "payload": "opaque-payload"
        });
        body.as_object_mut()
            .unwrap()
            .insert(field.to_string(), serde_json::json!({"claimed": true}));

        let request = Request::builder()
            .method("POST")
            .uri("/v1/requests")
            .header("content-type", "application/json")
            .body(Body::from(body.to_string()))
            .unwrap();

        let response = app.oneshot(request).await.unwrap();
        assert_eq!(
            response.status(),
            StatusCode::UNPROCESSABLE_ENTITY,
            "{field}"
        );
        assert!(delegate.requests.lock().unwrap().is_empty(), "{field}");
    }
}

#[tokio::test]
async fn gateway_exposes_no_capability_or_policy_mutation_routes() {
    for route in ["/v1/capabilities", "/v1/revocations", "/v1/policy"] {
        let delegate = RecordingDelegate::default();
        let app = router(AppState::new(delegate.clone()));
        let request = Request::builder()
            .method("POST")
            .uri(route)
            .header("content-type", "application/json")
            .body(Body::from("{}"))
            .unwrap();

        let response = app.oneshot(request).await.unwrap();
        assert_eq!(response.status(), StatusCode::NOT_FOUND, "{route}");
        assert!(delegate.requests.lock().unwrap().is_empty(), "{route}");
    }
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
async fn authenticated_request_routes_reject_before_parse_lookup_or_delegation() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::authenticated(delegate.clone(), "secret"));

    for authorization in [None, Some("Bearer wrong")] {
        let mut builder = Request::builder()
            .method("POST")
            .uri("/v1/requests")
            .header("content-type", "application/json");
        if let Some(value) = authorization {
            builder = builder.header("authorization", value);
        }
        let request = builder.body(Body::from("{not-json")).unwrap();
        let response = app.clone().oneshot(request).await.unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        assert!(delegate.requests.lock().unwrap().is_empty());
    }

    let status_request = Request::builder()
        .method("GET")
        .uri("/v1/requests/secret-or-missing")
        .body(Body::empty())
        .unwrap();
    let status_response = app.clone().oneshot(status_request).await.unwrap();
    assert_eq!(status_response.status(), StatusCode::UNAUTHORIZED);

    let valid = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json")
        .header("authorization", "Bearer secret")
        .body(Body::from(
            serde_json::json!({
                "request_id": "authenticated-05",
                "authority": "user",
                "action": "present",
                "value": "opaque",
                "payload": "opaque"
            })
            .to_string(),
        ))
        .unwrap();
    assert_eq!(
        app.oneshot(valid).await.unwrap().status(),
        StatusCode::ACCEPTED
    );
    assert_eq!(delegate.requests.lock().unwrap().len(), 1);
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
    assert_eq!(
        analysis_snapshot["workspace"]["claims"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
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

fn safety(max_body: usize, rate: u64, tracked: usize) -> SafetyConfig {
    SafetyConfig::new(max_body, rate, Duration::from_secs(60), tracked)
}

fn submit_request(id: &str, token: Option<&str>, padding: &str) -> Request<Body> {
    let mut builder = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json");
    if let Some(token) = token {
        builder = builder.header("authorization", format!("Bearer {token}"));
    }
    builder
        .body(Body::from(
            serde_json::json!({
                "request_id": id,
                "authority": "user",
                "action": "present",
                "value": "opaque",
                "payload": padding
            })
            .to_string(),
        ))
        .unwrap()
}

#[tokio::test]
async fn artifact_07_replay_is_rejected_before_second_delegation() {
    let delegate = RecordingDelegate::default();
    let app = router(
        AppState::authenticated(delegate.clone(), "secret").with_safety(safety(4096, 10, 10)),
    );

    assert_eq!(
        app.clone()
            .oneshot(submit_request("replay-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::ACCEPTED
    );
    assert_eq!(
        app.oneshot(submit_request("replay-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::CONFLICT
    );
    assert_eq!(delegate.requests.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn artifact_07_payload_cap_rejects_before_parse_and_delegation() {
    let delegate = RecordingDelegate::default();
    let app = router(
        AppState::authenticated(delegate.clone(), "secret").with_safety(safety(64, 10, 10)),
    );
    let response = app
        .oneshot(submit_request(
            "large-07",
            Some("secret"),
            &"x".repeat(256),
        ))
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    assert!(delegate.requests.lock().unwrap().is_empty());
}

#[tokio::test]
async fn artifact_07_rate_limit_fails_closed_before_second_delegation() {
    let delegate = RecordingDelegate::default();
    let app = router(
        AppState::authenticated(delegate.clone(), "secret").with_safety(safety(4096, 1, 10)),
    );
    assert_eq!(
        app.clone()
            .oneshot(submit_request("rate-a-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::ACCEPTED
    );
    assert_eq!(
        app.oneshot(submit_request("rate-b-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::TOO_MANY_REQUESTS
    );
    assert_eq!(delegate.requests.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn artifact_07_tracked_request_budget_fails_closed() {
    let delegate = RecordingDelegate::default();
    let app = router(
        AppState::authenticated(delegate.clone(), "secret").with_safety(safety(4096, 10, 1)),
    );
    assert_eq!(
        app.clone()
            .oneshot(submit_request("budget-a-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::ACCEPTED
    );
    assert_eq!(
        app.oneshot(submit_request("budget-b-07", Some("secret"), "opaque"))
            .await
            .unwrap()
            .status(),
        StatusCode::SERVICE_UNAVAILABLE
    );
    assert_eq!(delegate.requests.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn artifact_07_authentication_precedes_safety_budget_consumption() {
    let delegate = RecordingDelegate::default();
    let app = router(
        AppState::authenticated(delegate.clone(), "secret").with_safety(safety(64, 1, 1)),
    );
    let unauthenticated = app
        .clone()
        .oneshot(submit_request("hidden-07", None, &"x".repeat(256)))
        .await
        .unwrap();
    assert_eq!(unauthenticated.status(), StatusCode::UNAUTHORIZED);

    let authenticated = app
        .oneshot(submit_request("valid-07", Some("secret"), "x"))
        .await
        .unwrap();
    assert_eq!(authenticated.status(), StatusCode::ACCEPTED);
    assert_eq!(delegate.requests.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn artifact_07_delegate_failure_releases_replay_and_capacity_reservation() {
    let delegate = RecordingDelegate {
        fail_requests: true,
        ..RecordingDelegate::default()
    };
    let app = router(
        AppState::authenticated(delegate, "secret").with_safety(safety(4096, 10, 1)),
    );
    for _ in 0..2 {
        let response = app
            .clone()
            .oneshot(submit_request(
                "retry-after-failure-07",
                Some("secret"),
                "opaque",
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_GATEWAY);
    }
}
