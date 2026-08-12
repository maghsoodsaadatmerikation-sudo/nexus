use axum::{body::Body, http::{Request, StatusCode}};
use nexus_artifact_05_gateway::{router, AppState, ConstitutionalDelegate, DelegateError, Submission};
use nexus_constitutional_core::RequestEnvelope;
use std::sync::{Arc, Mutex};
use tower::ServiceExt;

#[derive(Clone, Default)]
struct RecordingDelegate(Arc<Mutex<Vec<RequestEnvelope>>>);

impl ConstitutionalDelegate for RecordingDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        let id = envelope.request_id.clone();
        self.0.lock().unwrap().push(envelope);
        Ok(Submission { request_id: id })
    }
}

#[tokio::test]
async fn post_returns_202_and_delegates_exact_wire_input() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::new(delegate.clone()));

    let request = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json")
        .body(Body::from(r#"{
            "request_id":"contract-001",
            "authority":"user",
            "action":"reflect",
            "subject":"opaque",
            "payload":"opaque"
        }"#))
        .unwrap();

    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::ACCEPTED);

    let submitted = delegate.0.lock().unwrap();
    assert_eq!(submitted.len(), 1);
    assert_eq!(submitted[0].request_id, "contract-001");
    assert_eq!(submitted[0].payload, "opaque");
}

#[tokio::test]
async fn invalid_action_is_rejected_without_delegate_call() {
    let delegate = RecordingDelegate::default();
    let app = router(AppState::new(delegate.clone()));

    let request = Request::builder()
        .method("POST")
        .uri("/v1/requests")
        .header("content-type", "application/json")
        .body(Body::from(r#"{
            "authority":"user",
            "action":"authorize",
            "payload":"opaque"
        }"#))
        .unwrap();

    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    assert!(delegate.0.lock().unwrap().is_empty());
}

#[tokio::test]
async fn unknown_status_is_404() {
    let app = router(AppState::new(RecordingDelegate::default()));

    let request = Request::builder()
        .method("GET")
        .uri("/v1/requests/does-not-exist")
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}
