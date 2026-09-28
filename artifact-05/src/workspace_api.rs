use crate::{AppState, ConstitutionalDelegate, ErrorResponse};
use axum::{
    extract::{Path, State},
    http::{header, HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use nexus_constitutional_core::{
    Alternative, AnalysisBatch, Claim, ClaimOrigin, HumanJudgment, ProvenanceId, Uncertainty,
    WorkspaceSnapshot,
};
use serde::Deserialize;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkspaceDelegateError {
    NotFound,
    AlreadyExists,
    Invalid,
    Unavailable,
}

pub trait WorkspaceDelegate: Send + Sync + 'static {
    fn create_workspace(
        &self,
        workspace_id: String,
        question: String,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>;

    fn import_workspace(
        &self,
        _snapshot: WorkspaceSnapshot,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::Unavailable)
    }

    fn get_workspace(
        &self,
        workspace_id: &str,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>;

    fn add_claim(
        &self,
        workspace_id: &str,
        claim: Claim,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>;

    fn add_alternative(
        &self,
        workspace_id: &str,
        alternative: Alternative,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>;

    fn record_analysis_batch(
        &self,
        _workspace_id: &str,
        _batch: AnalysisBatch,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        Err(WorkspaceDelegateError::Unavailable)
    }

    fn record_human_judgment(
        &self,
        workspace_id: &str,
        judgment: HumanJudgment,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>;
}

#[derive(Debug, Deserialize)]
pub struct CreateWorkspaceRequest {
    pub workspace_id: Option<String>,
    pub question: String,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum WireClaimOrigin {
    Human,
    ExternalEvidence { source: String },
    MachineAnalysis,
}

impl From<WireClaimOrigin> for ClaimOrigin {
    fn from(value: WireClaimOrigin) -> Self {
        match value {
            WireClaimOrigin::Human => ClaimOrigin::Human,
            WireClaimOrigin::ExternalEvidence { source } => {
                ClaimOrigin::ExternalEvidence { source }
            }
            WireClaimOrigin::MachineAnalysis => ClaimOrigin::MachineAnalysis,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum WireUncertainty {
    Unknown,
    Low,
    Medium,
    High,
}

impl From<WireUncertainty> for Uncertainty {
    fn from(value: WireUncertainty) -> Self {
        match value {
            WireUncertainty::Unknown => Uncertainty::Unknown,
            WireUncertainty::Low => Uncertainty::Low,
            WireUncertainty::Medium => Uncertainty::Medium,
            WireUncertainty::High => Uncertainty::High,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct AddClaimRequest {
    pub claim_id: Option<String>,
    pub text: String,
    pub origin: WireClaimOrigin,
    pub uncertainty: WireUncertainty,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
pub struct AddAlternativeRequest {
    pub alternative_id: Option<String>,
    pub label: String,
    #[serde(default)]
    pub consequences: Vec<String>,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
pub struct RecordJudgmentRequest {
    pub decision: String,
    pub rationale: String,
    pub provenance_id: String,
}

pub(crate) async fn create_workspace<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Json(input): Json<CreateWorkspaceRequest>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    let workspace_id = input
        .workspace_id
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    match state.delegate.create_workspace(
        workspace_id,
        input.question,
        ProvenanceId::new(input.provenance_id),
    ) {
        Ok(snapshot) => (StatusCode::CREATED, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn import_workspace<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Json(snapshot): Json<WorkspaceSnapshot>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    match state.delegate.import_workspace(snapshot) {
        Ok(snapshot) => (StatusCode::CREATED, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn get_workspace<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    match state.delegate.get_workspace(&id) {
        Ok(snapshot) => (StatusCode::OK, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn add_claim<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(input): Json<AddClaimRequest>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    let claim = Claim {
        id: input.claim_id.unwrap_or_else(|| Uuid::new_v4().to_string()),
        text: input.text,
        origin: input.origin.into(),
        uncertainty: input.uncertainty.into(),
    };
    match state
        .delegate
        .add_claim(&id, claim, ProvenanceId::new(input.provenance_id))
    {
        Ok(snapshot) => (StatusCode::OK, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn add_alternative<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(input): Json<AddAlternativeRequest>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    let alternative = Alternative {
        id: input
            .alternative_id
            .unwrap_or_else(|| Uuid::new_v4().to_string()),
        label: input.label,
        consequences: input.consequences,
    };
    match state
        .delegate
        .add_alternative(&id, alternative, ProvenanceId::new(input.provenance_id))
    {
        Ok(snapshot) => (StatusCode::OK, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn record_analysis_batch<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(batch): Json<AnalysisBatch>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    match state.delegate.record_analysis_batch(&id, batch) {
        Ok(snapshot) => (StatusCode::OK, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

pub(crate) async fn record_human_judgment<D>(
    State(state): State<AppState<D>>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(input): Json<RecordJudgmentRequest>,
) -> impl IntoResponse
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
{
    if !workspace_authorized(&state, &headers) {
        return unauthorized();
    }
    let judgment = HumanJudgment {
        decision: input.decision,
        rationale: input.rationale,
    };
    match state.delegate.record_human_judgment(
        &id,
        judgment,
        ProvenanceId::new(input.provenance_id),
    ) {
        Ok(snapshot) => (StatusCode::OK, Json(snapshot)).into_response(),
        Err(error) => workspace_error_response(error),
    }
}

fn workspace_authorized<D>(state: &AppState<D>, headers: &HeaderMap) -> bool {
    let Some(expected) = state.auth_token.as_deref() else {
        return true;
    };
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("Bearer "))
        .is_some_and(|provided| provided.as_bytes() == expected.as_bytes())
}

fn unauthorized() -> axum::response::Response {
    (
        StatusCode::UNAUTHORIZED,
        Json(ErrorResponse {
            error: "workspace_authentication_required",
        }),
    )
        .into_response()
}

fn workspace_error_response(error: WorkspaceDelegateError) -> axum::response::Response {
    let (status, message) = match error {
        WorkspaceDelegateError::NotFound => (StatusCode::NOT_FOUND, "workspace_not_found"),
        WorkspaceDelegateError::AlreadyExists => (StatusCode::CONFLICT, "workspace_already_exists"),
        WorkspaceDelegateError::Invalid => (StatusCode::UNPROCESSABLE_ENTITY, "workspace_invalid"),
        WorkspaceDelegateError::Unavailable => {
            (StatusCode::BAD_GATEWAY, "workspace_delegate_unavailable")
        }
    };
    (status, Json(ErrorResponse { error: message })).into_response()
}
