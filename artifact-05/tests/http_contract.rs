use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, RequestStatus, Submission,
};
use nexus_constitutional_core::RequestEnvelope;
use std::sync::{Arc, Mutex};
use tower::ServiceExt;

#[derive(Clone, Default)]
struct RecordingDelegate(Arc<Mutex<Vec<RequestEnvelope>>>);

impl ConstitutionalDelegate for RecordingDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        let request_id = envelope.request_id.clone();
        self.0.lock().unwrap().push(envelope);
        Ok(Submission { request_id })
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

    let calls = delegate.0.lock().unwrap();
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
    assert_eq!(status["status"], serde_json::to_value(RequestStatus::Pending).unwrap());
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
