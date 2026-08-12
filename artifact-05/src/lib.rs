#![forbid(unsafe_code)]

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use nexus_constitutional_core::{Action, Authority, RequestEnvelope};
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::{Arc, RwLock}};
use uuid::Uuid;

/// Transport-only representation of authority. Conversion is syntactic; it does not
/// authorize or elevate anything. Constitutional authorization remains in the delegate.
#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum WireAuthority {
    None,
    User,
    Policy,
    System,
}

impl From<WireAuthority> for Authority {
    fn from(value: WireAuthority) -> Self {
        match value {
            WireAuthority::None => Authority::None,
            WireAuthority::User => Authority::User,
            WireAuthority::Policy => Authority::Policy,
            WireAuthority::System => Authority::System,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct SubmitRequest {
    pub request_id: Option<String>,
    pub authority: WireAuthority,
    pub action: String,
    pub subject: Option<String>,
    pub value: Option<String>,
    pub option: Option<String>,
    pub payload: String,
}

impl SubmitRequest {
    /// Shape validation only. This function intentionally performs no policy decision.
    fn into_envelope(self) -> Result<RequestEnvelope, &'static str> {
        let request_id = self.request_id.unwrap_or_else(|| Uuid::new_v4().to_string());
        let action = match self.action.as_str() {
            "reflect" => Action::Reflect {
                subject: self.subject.ok_or("missing_subject")?,
            },
            "present" => Action::Present {
                value: self.value.ok_or("missing_value")?,
            },
            "select" => Action::Select {
                option: self.option.ok_or("missing_option")?,
            },
            _ => return Err("invalid_action"),
        };

        Ok(RequestEnvelope::new(
            request_id,
            self.authority.into(),
            action,
            self.payload,
        ))
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AcceptedResponse {
    pub request_id: String,
    pub status: RequestStatus,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum RequestStatus {
    Pending,
    Completed,
}

#[derive(Debug, Clone, Serialize)]
pub struct ErrorResponse {
    pub error: &'static str,
}

#[derive(Debug, Clone)]
pub struct Submission {
    pub request_id: String,
}

pub trait ConstitutionalDelegate: Send + Sync + 'static {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError>;
}

#[derive(Debug, Clone, Copy)]
pub struct DelegateError;

#[derive(Clone)]
pub struct AppState<D> {
    pub delegate: Arc<D>,
    pub statuses: Arc<RwLock<HashMap<String, RequestStatus>>>,
}

impl<D: ConstitutionalDelegate> AppState<D> {
    pub fn new(delegate: D) -> Self {
        Self {
            delegate: Arc::new(delegate),
            statuses: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}

pub fn router<D: ConstitutionalDelegate>(state: AppState<D>) -> Router {
    Router::new()
        .route("/v1/requests", post(submit::<D>))
        .route("/v1/requests/{id}", get(status::<D>))
        .with_state(state)
}

async fn submit<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    Json(input): Json<SubmitRequest>,
) -> impl IntoResponse {
    // HTTP responsibility ends at parsing, shape validation, envelope construction,
    // delegation, and serialization. No constitutional decision is made here.
    let envelope = match input.into_envelope() {
        Ok(envelope) => envelope,
        Err(error) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse { error }),
            )
                .into_response();
        }
    };

    let request_id = envelope.request_id.clone();

    match state.delegate.submit(envelope) {
        Ok(submission) => {
            state.statuses.write().expect("status lock poisoned")
                .insert(submission.request_id.clone(), RequestStatus::Pending);
            (
                StatusCode::ACCEPTED,
                Json(AcceptedResponse {
                    request_id: submission.request_id,
                    status: RequestStatus::Pending,
                }),
            )
                .into_response()
        }
        Err(_) => (
            StatusCode::BAD_GATEWAY,
            Json(ErrorResponse { error: "constitutional_delegate_unavailable" }),
        )
            .into_response(),
    }
}

async fn status<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    match state.statuses.read().expect("status lock poisoned").get(&id).cloned() {
        Some(status) => (
            StatusCode::OK,
            Json(AcceptedResponse { request_id: id, status }),
        )
            .into_response(),
        None => (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse { error: "request_not_found" }),
        )
            .into_response(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::Request;
    use http_body_util::BodyExt;
    use std::sync::{Arc, Mutex};

    #[derive(Clone, Default)]
    struct RecordingDelegate(Arc<Mutex<Vec<RequestEnvelope>>>);

    impl ConstitutionalDelegate for RecordingDelegate {
        fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
            let id = envelope.request_id.clone();
            self.0.lock().unwrap().push(envelope);
            Ok(Submission { request_id: id })
        }
    }

    async fn body_json(response: axum::response::Response) -> serde_json::Value {
        serde_json::from_slice(&response.into_body().collect().await.unwrap().to_bytes()).unwrap()
    }

    #[tokio::test]
    async fn gateway_delegates_without_authorizing() {
        let delegate = RecordingDelegate::default();
        let router = router(AppState::new(delegate.clone()));

        let body = serde_json::json!({
            "request_id": "r-05",
            "authority": "user",
            "action": "reflect",
            "subject": "opaque",
            "payload": "opaque"
        });
        let request = Request::builder()
            .method("POST")
            .uri("/v1/requests")
            .header("content-type", "application/json")
            .body(Body::from(body.to_string()))
            .unwrap();

        let response = tower::ServiceExt::oneshot(router, request).await.unwrap();
        assert_eq!(response.status(), StatusCode::ACCEPTED);

        let recorded = delegate.0.lock().unwrap();
        assert_eq!(recorded.len(), 1);
        assert_eq!(recorded[0].request_id, "r-05");
        assert_eq!(recorded[0].payload, "opaque");
        assert_eq!(recorded[0].authority, Authority::User);
    }

    #[tokio::test]
    async fn malformed_shape_is_rejected_before_delegation() {
        let delegate = RecordingDelegate::default();
        let router = router(AppState::new(delegate.clone()));
        let body = serde_json::json!({
            "authority": "user",
            "action": "reflect",
            "payload": "opaque"
        });
        let request = Request::builder()
            .method("POST")
            .uri("/v1/requests")
            .header("content-type", "application/json")
            .body(Body::from(body.to_string()))
            .unwrap();

        let response = tower::ServiceExt::oneshot(router, request).await.unwrap();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        assert_eq!(body_json(response).await["error"], "missing_subject");
        assert!(delegate.0.lock().unwrap().is_empty());
    }

    #[tokio::test]
    async fn unknown_request_is_not_found() {
        let router = router(AppState::new(RecordingDelegate::default()));
        let request = Request::builder()
            .method("GET")
            .uri("/v1/requests/unknown")
            .body(Body::empty())
            .unwrap();

        let response = tower::ServiceExt::oneshot(router, request).await.unwrap();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }
}
