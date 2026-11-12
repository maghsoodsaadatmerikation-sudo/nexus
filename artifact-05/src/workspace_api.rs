use crate::{AppState, ConstitutionalDelegate, ErrorResponse};
use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
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
#[serde(deny_unknown_fields)]
pub struct CreateWorkspaceRequest {
    pub workspace_id: Option<String>,
    pub question: String,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
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
#[serde(deny_unknown_fields)]
pub struct AddClaimRequest {
    pub claim_id: Option<String>,
    pub text: String,
    pub origin: WireClaimOrigin,
    pub uncertainty: WireUncertainty,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddAlternativeRequest {
    pub alternative_id: Option<String>,
    pub label: String,
    #[serde(default)]
    pub consequences: Vec<String>,
    pub provenance_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
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
    if !crate::valid_identifier(&workspace_id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::CREATED, move |delegate| {
        delegate.create_workspace(
            workspace_id,
            input.question,
            ProvenanceId::new(input.provenance_id),
        )
    })
    .await
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
    if !crate::valid_identifier(&snapshot.workspace.id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::CREATED, move |delegate| {
        delegate.import_workspace(snapshot)
    })
    .await
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
    if !crate::valid_identifier(&id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::OK, move |delegate| {
        delegate.get_workspace(&id)
    })
    .await
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
    if !crate::valid_identifier(&id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    let claim = Claim {
        id: input.claim_id.unwrap_or_else(|| Uuid::new_v4().to_string()),
        text: input.text,
        origin: input.origin.into(),
        uncertainty: input.uncertainty.into(),
    };
    if !crate::valid_identifier(&claim.id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::OK, move |delegate| {
        delegate.add_claim(&id, claim, ProvenanceId::new(input.provenance_id))
    })
    .await
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
    if !crate::valid_identifier(&id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    let alternative = Alternative {
        id: input
            .alternative_id
            .unwrap_or_else(|| Uuid::new_v4().to_string()),
        label: input.label,
        consequences: input.consequences,
    };
    if !crate::valid_identifier(&alternative.id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::OK, move |delegate| {
        delegate.add_alternative(&id, alternative, ProvenanceId::new(input.provenance_id))
    })
    .await
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
    if !crate::valid_identifier(&id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    delegate_workspace(state, StatusCode::OK, move |delegate| {
        delegate.record_analysis_batch(&id, batch)
    })
    .await
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
    if !crate::valid_identifier(&id) {
        return workspace_error_response(WorkspaceDelegateError::Invalid);
    }
    let judgment = HumanJudgment {
        decision: input.decision,
        rationale: input.rationale,
    };
    delegate_workspace(state, StatusCode::OK, move |delegate| {
        delegate.record_human_judgment(&id, judgment, ProvenanceId::new(input.provenance_id))
    })
    .await
}

async fn delegate_workspace<D, F>(
    state: AppState<D>,
    status: StatusCode,
    operation: F,
) -> axum::response::Response
where
    D: ConstitutionalDelegate + WorkspaceDelegate,
    F: FnOnce(&D) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> + Send + 'static,
{
    let permit = match crate::execution_permit(&state) {
        Ok(permit) => permit,
        Err(response) => return response,
    };
    match tokio::task::spawn_blocking(move || {
        let _permit = permit;
        operation(state.delegate.as_ref())
    })
    .await
    {
        Ok(Ok(snapshot)) => (status, Json(snapshot)).into_response(),
        Ok(Err(error)) => workspace_error_response(error),
        Err(_) => workspace_error_response(WorkspaceDelegateError::Unavailable),
    }
}

fn workspace_authorized<D>(state: &AppState<D>, headers: &HeaderMap) -> bool {
    crate::transport_authorized(state, headers)
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
