#![forbid(unsafe_code)]

mod workspace_api;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use nexus_constitutional_core::{Action, Authority, RequestEnvelope};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{Arc, RwLock},
};
use uuid::Uuid;

pub use workspace_api::{WorkspaceDelegate, WorkspaceDelegateError};

#[derive(Debug, Clone, Copy, Deserialize)]
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
    #[serde(flatten)]
    pub action: Action,
    pub payload: String,
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

pub struct AppState<D> {
    pub delegate: Arc<D>,
    pub statuses: Arc<RwLock<HashMap<String, RequestStatus>>>,
}

impl<D> Clone for AppState<D> {
    fn clone(&self) -> Self {
        Self {
            delegate: Arc::clone(&self.delegate),
            statuses: Arc::clone(&self.statuses),
        }
    }
}

impl<D: ConstitutionalDelegate> AppState<D> {
    pub fn new(delegate: D) -> Self {
        Self {
            delegate: Arc::new(delegate),
            statuses: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}

pub fn router<D>(state: AppState<D>) -> Router
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    Router::new()
        .route("/v1/requests", post(submit::<D>))
        .route("/v1/requests/{id}", get(status::<D>))
        .route("/v1/workspaces", post(workspace_api::create_workspace::<D>))
        .route("/v1/workspaces/{id}", get(workspace_api::get_workspace::<D>))
        .route(
            "/v1/workspaces/{id}/claims",
            post(workspace_api::add_claim::<D>),
        )
        .route(
            "/v1/workspaces/{id}/alternatives",
            post(workspace_api::add_alternative::<D>),
        )
        .route(
            "/v1/workspaces/{id}/judgment",
            post(workspace_api::record_human_judgment::<D>),
        )
        .with_state(state)
}

async fn submit<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    Json(input): Json<SubmitRequest>,
) -> impl IntoResponse {
    let request_id = input
        .request_id
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    let envelope = RequestEnvelope::new(
        request_id,
        input.authority.into(),
        input.action,
        input.payload,
    );

    match state.delegate.submit(envelope) {
        Ok(submission) => {
            state
                .statuses
                .write()
                .expect("status lock poisoned")
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
            Json(ErrorResponse {
                error: "constitutional_delegate_unavailable",
            }),
        )
            .into_response(),
    }
}

async fn status<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    match state
        .statuses
        .read()
        .expect("status lock poisoned")
        .get(&id)
        .cloned()
    {
        Some(status) => (
            StatusCode::OK,
            Json(AcceptedResponse {
                request_id: id,
                status,
            }),
        )
            .into_response(),
        None => (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                error: "request_not_found",
            }),
        )
            .into_response(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexus_constitutional_core::{
        Alternative, Claim, HumanJudgment, ProvenanceId, WorkspaceSnapshot,
    };
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

    impl WorkspaceDelegate for RecordingDelegate {
        fn create_workspace(
            &self,
            _workspace_id: String,
            _question: String,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn get_workspace(&self, _workspace_id: &str) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn add_claim(
            &self,
            _workspace_id: &str,
            _claim: Claim,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn add_alternative(
            &self,
            _workspace_id: &str,
            _alternative: Alternative,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn record_human_judgment(
            &self,
            _workspace_id: &str,
            _judgment: HumanJudgment,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }
    }

    #[derive(Clone, Copy, Default)]
    struct FailingDelegate;

    impl ConstitutionalDelegate for FailingDelegate {
        fn submit(&self, _envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
            Err(DelegateError)
        }
    }

    impl WorkspaceDelegate for FailingDelegate {
        fn create_workspace(
            &self,
            _workspace_id: String,
            _question: String,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn get_workspace(&self, _workspace_id: &str) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn add_claim(
            &self,
            _workspace_id: &str,
            _claim: Claim,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn add_alternative(
            &self,
            _workspace_id: &str,
            _alternative: Alternative,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }

        fn record_human_judgment(
            &self,
            _workspace_id: &str,
            _judgment: HumanJudgment,
            _provenance_id: ProvenanceId,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
            Err(WorkspaceDelegateError::Unavailable)
        }
    }

    fn request(body: &str) -> axum::http::Request<axum::body::Body> {
        axum::http::Request::builder()
            .method("POST")
            .uri("/v1/requests")
            .header("content-type", "application/json")
            .body(axum::body::Body::from(body.to_owned()))
            .unwrap()
    }

    #[tokio::test]
    async fn gateway_delegates_without_authorizing() {
        let delegate = RecordingDelegate::default();
        let app = router(AppState::new(delegate.clone()));
        let body = serde_json::json!({
            "request_id": "r-05",
            "authority": "user",
            "action": "reflect",
            "subject": "opaque",
            "payload": "opaque"
        });
        let response = tower::ServiceExt::oneshot(app, request(&body.to_string()))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::ACCEPTED);
        let recorded = delegate.0.lock().unwrap();
        assert_eq!(recorded.len(), 1);
        assert_eq!(recorded[0].request_id, "r-05");
        assert_eq!(recorded[0].payload, "opaque");
        assert_eq!(
            recorded[0].action,
            Action::Reflect {
                subject: "opaque".into()
            }
        );
    }

    #[tokio::test]
    async fn accepted_request_is_queryable_as_pending() {
        let app = router(AppState::new(RecordingDelegate::default()));
        let body = serde_json::json!({
            "request_id": "r-status",
            "authority": "user",
            "action": "reflect",
            "subject": "opaque",
            "payload": "opaque"
        });
        let response = tower::ServiceExt::oneshot(app.clone(), request(&body.to_string()))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::ACCEPTED);

        let request = axum::http::Request::builder()
            .method("GET")
            .uri("/v1/requests/r-status")
            .body(axum::body::Body::empty())
            .unwrap();
        let response = tower::ServiceExt::oneshot(app, request).await.unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn unknown_request_is_not_found() {
        let app = router(AppState::new(RecordingDelegate::default()));
        let request = axum::http::Request::builder()
            .method("GET")
            .uri("/v1/requests/unknown")
            .body(axum::body::Body::empty())
            .unwrap();
        let response = tower::ServiceExt::oneshot(app, request).await.unwrap();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn delegate_failure_is_returned_without_pending_state() {
        let state = AppState::new(FailingDelegate);
        let app = router(state.clone());
        let body = serde_json::json!({
            "request_id": "r-fail",
            "authority": "user",
            "action": "reflect",
            "subject": "opaque",
            "payload": "opaque"
        });
        let response = tower::ServiceExt::oneshot(app, request(&body.to_string()))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_GATEWAY);
        assert!(!state.statuses.read().unwrap().contains_key("r-fail"));
    }

    #[tokio::test]
    async fn malformed_action_shape_is_rejected() {
        let app = router(AppState::new(RecordingDelegate::default()));
        let body =
            r#"{"request_id":"r-bad","authority":"user","action":"reflect","payload":"opaque"}"#;
        let response = tower::ServiceExt::oneshot(app, request(body))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNPROCESSABLE_ENTITY);
    }
}
