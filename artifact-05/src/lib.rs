#![forbid(unsafe_code)]

mod workspace_api;

use axum::{
    body::to_bytes,
    extract::{Path, Request, State},
    http::{header, HeaderMap, StatusCode},
    response::{Html, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use nexus_constitutional_core::{Action, Authority, RequestEnvelope};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    sync::{Arc, Mutex, RwLock},
    time::{Duration, Instant},
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

#[derive(Debug, Clone)]
pub struct SubmitRequest {
    pub request_id: Option<String>,
    pub authority: WireAuthority,
    pub action: Action,
    pub payload: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
enum ExactSubmitRequest {
    Reflect {
        request_id: Option<String>,
        authority: WireAuthority,
        subject: String,
        payload: String,
    },
    Present {
        request_id: Option<String>,
        authority: WireAuthority,
        value: String,
        payload: String,
    },
    Select {
        request_id: Option<String>,
        authority: WireAuthority,
        option: String,
        payload: String,
    },
}

impl<'de> Deserialize<'de> for SubmitRequest {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        Ok(match ExactSubmitRequest::deserialize(deserializer)? {
            ExactSubmitRequest::Reflect {
                request_id,
                authority,
                subject,
                payload,
            } => Self {
                request_id,
                authority,
                action: Action::Reflect { subject },
                payload,
            },
            ExactSubmitRequest::Present {
                request_id,
                authority,
                value,
                payload,
            } => Self {
                request_id,
                authority,
                action: Action::Present { value },
                payload,
            },
            ExactSubmitRequest::Select {
                request_id,
                authority,
                option,
                payload,
            } => Self {
                request_id,
                authority,
                action: Action::Select { option },
                payload,
            },
        })
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

#[derive(Debug, Clone, Copy)]
pub struct SafetyConfig {
    pub max_body_bytes: usize,
    pub max_requests_per_window: u64,
    pub rate_window: Duration,
    pub max_tracked_requests: usize,
}

impl SafetyConfig {
    pub fn new(
        max_body_bytes: usize,
        max_requests_per_window: u64,
        rate_window: Duration,
        max_tracked_requests: usize,
    ) -> Self {
        assert!(max_body_bytes > 0, "max_body_bytes must be positive");
        assert!(
            max_requests_per_window > 0,
            "max_requests_per_window must be positive"
        );
        assert!(!rate_window.is_zero(), "rate_window must be positive");
        assert!(
            max_tracked_requests > 0,
            "max_tracked_requests must be positive"
        );
        Self {
            max_body_bytes,
            max_requests_per_window,
            rate_window,
            max_tracked_requests,
        }
    }
}

impl Default for SafetyConfig {
    fn default() -> Self {
        Self::new(64 * 1024, 120, Duration::from_secs(60), 10_000)
    }
}

struct SafetyState {
    window_started: Instant,
    requests_in_window: u64,
    request_ids: HashSet<String>,
    tracked_requests: usize,
}

impl Default for SafetyState {
    fn default() -> Self {
        Self {
            window_started: Instant::now(),
            requests_in_window: 0,
            request_ids: HashSet::new(),
            tracked_requests: 0,
        }
    }
}

pub struct AppState<D> {
    pub delegate: Arc<D>,
    pub statuses: Arc<RwLock<HashMap<String, RequestStatus>>>,
    pub auth_token: Option<Arc<str>>,
    safety_config: SafetyConfig,
    safety_state: Arc<Mutex<SafetyState>>,
}

impl<D> Clone for AppState<D> {
    fn clone(&self) -> Self {
        Self {
            delegate: Arc::clone(&self.delegate),
            statuses: Arc::clone(&self.statuses),
            auth_token: self.auth_token.clone(),
            safety_config: self.safety_config,
            safety_state: Arc::clone(&self.safety_state),
        }
    }
}

impl<D: ConstitutionalDelegate> AppState<D> {
    pub fn new(delegate: D) -> Self {
        Self {
            delegate: Arc::new(delegate),
            statuses: Arc::new(RwLock::new(HashMap::new())),
            auth_token: None,
            safety_config: SafetyConfig::default(),
            safety_state: Arc::new(Mutex::new(SafetyState::default())),
        }
    }

    pub fn authenticated(delegate: D, token: impl Into<String>) -> Self {
        let token = token.into();
        assert!(
            !token.trim().is_empty(),
            "authentication token must not be empty"
        );
        Self {
            delegate: Arc::new(delegate),
            statuses: Arc::new(RwLock::new(HashMap::new())),
            auth_token: Some(Arc::<str>::from(token)),
            safety_config: SafetyConfig::default(),
            safety_state: Arc::new(Mutex::new(SafetyState::default())),
        }
    }

    pub fn with_safety(mut self, config: SafetyConfig) -> Self {
        self.safety_config = config;
        self.safety_state = Arc::new(Mutex::new(SafetyState::default()));
        self
    }
}

pub fn router<D>(state: AppState<D>) -> Router
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    Router::new()
        .route("/", get(web_workspace))
        .route("/v1/requests", post(submit::<D>))
        .route("/v1/requests/{id}", get(status::<D>))
        .route("/v1/workspaces", post(workspace_api::create_workspace::<D>))
        .route(
            "/v1/workspaces/import",
            post(workspace_api::import_workspace::<D>),
        )
        .route(
            "/v1/workspaces/{id}",
            get(workspace_api::get_workspace::<D>),
        )
        .route(
            "/v1/workspaces/{id}/claims",
            post(workspace_api::add_claim::<D>),
        )
        .route(
            "/v1/workspaces/{id}/alternatives",
            post(workspace_api::add_alternative::<D>),
        )
        .route(
            "/v1/workspaces/{id}/analysis",
            post(workspace_api::record_analysis_batch::<D>),
        )
        .route(
            "/v1/workspaces/{id}/judgment",
            post(workspace_api::record_human_judgment::<D>),
        )
        .with_state(state)
}

async fn web_workspace() -> Html<&'static str> {
    Html(include_str!("../../web/index.html"))
}

async fn submit<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    request: Request,
) -> impl IntoResponse {
    if !transport_authorized(&state, request.headers()) {
        return transport_unauthorized();
    }
    let (_, body) = request.into_parts();
    let body = match to_bytes(body, state.safety_config.max_body_bytes).await {
        Ok(body) => body,
        Err(_) => return safety_error(StatusCode::PAYLOAD_TOO_LARGE, "payload_too_large"),
    };
    if !consume_rate_budget(&state) {
        return safety_error(StatusCode::TOO_MANY_REQUESTS, "rate_limit_exceeded");
    }
    let input = match serde_json::from_slice::<SubmitRequest>(&body) {
        Ok(input) => input,
        Err(_) => return safety_error(StatusCode::UNPROCESSABLE_ENTITY, "invalid_request_shape"),
    };
    let request_id = input
        .request_id
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    if let Err(error) = reserve_request(&state, &request_id) {
        return error;
    }
    let envelope = RequestEnvelope::new(
        request_id.clone(),
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
        Err(_) => {
            release_request(&state, &request_id);
            safety_error(
                StatusCode::BAD_GATEWAY,
                "constitutional_delegate_unavailable",
            )
        }
    }
}

fn consume_rate_budget<D>(state: &AppState<D>) -> bool {
    let mut safety = state.safety_state.lock().expect("safety lock poisoned");
    if safety.window_started.elapsed() >= state.safety_config.rate_window {
        safety.window_started = Instant::now();
        safety.requests_in_window = 0;
    }
    if safety.requests_in_window >= state.safety_config.max_requests_per_window {
        return false;
    }
    safety.requests_in_window += 1;
    true
}

fn reserve_request<D>(
    state: &AppState<D>,
    request_id: &str,
) -> Result<(), axum::response::Response> {
    let mut safety = state.safety_state.lock().expect("safety lock poisoned");
    if safety.request_ids.contains(request_id) {
        return Err(safety_error(StatusCode::CONFLICT, "request_id_replayed"));
    }
    if safety.tracked_requests >= state.safety_config.max_tracked_requests {
        return Err(safety_error(
            StatusCode::SERVICE_UNAVAILABLE,
            "request_budget_exhausted",
        ));
    }
    safety.request_ids.insert(request_id.to_owned());
    safety.tracked_requests += 1;
    Ok(())
}

fn release_request<D>(state: &AppState<D>, request_id: &str) {
    let mut safety = state.safety_state.lock().expect("safety lock poisoned");
    if safety.request_ids.remove(request_id) {
        safety.tracked_requests = safety.tracked_requests.saturating_sub(1);
    }
}

fn safety_error(status: StatusCode, error: &'static str) -> axum::response::Response {
    (status, Json(ErrorResponse { error })).into_response()
}

async fn status<D: ConstitutionalDelegate>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> impl IntoResponse {
    if !transport_authorized(&state, &headers) {
        return transport_unauthorized();
    }
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

pub(crate) fn transport_authorized<D>(state: &AppState<D>, headers: &HeaderMap) -> bool {
    let Some(expected) = state.auth_token.as_deref() else {
        return true;
    };
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("Bearer "))
        .is_some_and(|provided| provided.as_bytes() == expected.as_bytes())
}

fn transport_unauthorized() -> axum::response::Response {
    (
        StatusCode::UNAUTHORIZED,
        Json(ErrorResponse {
            error: "transport_authentication_required",
        }),
    )
        .into_response()
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

        fn get_workspace(
            &self,
            _workspace_id: &str,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
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

        fn get_workspace(
            &self,
            _workspace_id: &str,
        ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
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
