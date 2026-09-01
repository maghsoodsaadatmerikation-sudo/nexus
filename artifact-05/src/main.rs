use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, Submission, WorkspaceDelegate,
    WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, AnalysisBatch, Claim, FileWorkspaceRepository, HumanJudgment, PolicyEngine,
    ProvenanceId, RequestEnvelope, WorkspaceEngine, WorkspaceSnapshot,
};
use std::{net::SocketAddr, path::PathBuf, sync::Mutex};

struct CoreDelegate {
    workspaces: Mutex<FileWorkspaceRepository>,
}

impl CoreDelegate {
    fn new(root: PathBuf) -> Self {
        Self {
            workspaces: Mutex::new(FileWorkspaceRepository::new(root)),
        }
    }
}

impl ConstitutionalDelegate for CoreDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        let request = PolicyEngine::new()
            .authorize(envelope)
            .map_err(|_| DelegateError)?;
        let receipt = nexus_constitutional_core::Executor::new().execute(request);
        Ok(Submission {
            request_id: receipt.request_id().to_owned(),
        })
    }
}

impl WorkspaceDelegate for CoreDelegate {
    fn create_workspace(
        &self,
        workspace_id: String,
        question: String,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        if repository
            .load(&workspace_id)
            .map_err(|_| WorkspaceDelegateError::Invalid)?
            .is_some()
        {
            return Err(WorkspaceDelegateError::AlreadyExists);
        }
        let snapshot = WorkspaceEngine::new(workspace_id, question, provenance_id).snapshot();
        repository
            .save(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        Ok(snapshot)
    }

    fn import_workspace(
        &self,
        snapshot: WorkspaceSnapshot,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        WorkspaceEngine::from_snapshot(snapshot.clone())
            .map_err(|_| WorkspaceDelegateError::Invalid)?;
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        if repository
            .load(&snapshot.workspace.id)
            .map_err(|_| WorkspaceDelegateError::Invalid)?
            .is_some()
        {
            return Err(WorkspaceDelegateError::AlreadyExists);
        }
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
            .map_err(|_| WorkspaceDelegateError::Unavailable)?
            .load(workspace_id)
            .map_err(|_| WorkspaceDelegateError::Invalid)?
            .ok_or(WorkspaceDelegateError::NotFound)
    }

    fn add_claim(
        &self,
        workspace_id: &str,
        claim: Claim,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.add_claim(claim, provenance_id)
        })
    }

    fn add_alternative(
        &self,
        workspace_id: &str,
        alternative: Alternative,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.add_alternative(alternative, provenance_id)
        })
    }

    fn record_analysis_batch(
        &self,
        workspace_id: &str,
        batch: AnalysisBatch,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| engine.record_analysis_batch(batch))
    }

    fn record_human_judgment(
        &self,
        workspace_id: &str,
        judgment: HumanJudgment,
        provenance_id: ProvenanceId,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError> {
        self.mutate_workspace(workspace_id, |engine| {
            engine.record_human_judgment(judgment, provenance_id)
        })
    }
}

impl CoreDelegate {
    fn mutate_workspace<F>(
        &self,
        workspace_id: &str,
        mutate: F,
    ) -> Result<WorkspaceSnapshot, WorkspaceDelegateError>
    where
        F: FnOnce(&mut WorkspaceEngine),
    {
        let mut repository = self
            .workspaces
            .lock()
            .map_err(|_| WorkspaceDelegateError::Unavailable)?;
        let snapshot = repository
            .load(workspace_id)
            .map_err(|_| WorkspaceDelegateError::Invalid)?
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

#[tokio::main]
async fn main() {
    let token = std::env::var("NEXUS_API_TOKEN")
        .expect("NEXUS_API_TOKEN is required for authenticated workspace access");
    assert!(
        !token.trim().is_empty(),
        "NEXUS_API_TOKEN must not be empty"
    );
    let data_root = std::env::var_os("NEXUS_DATA_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("nexus-data"));
    let bind_addr =
        std::env::var("NEXUS_BIND_ADDR").unwrap_or_else(|_| "127.0.0.1:3000".to_owned());
    let addr: SocketAddr = bind_addr.parse().expect("valid NEXUS_BIND_ADDR");
    let app = router(AppState::authenticated(CoreDelegate::new(data_root), token));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind gateway");
    axum::serve(listener, app).await.expect("serve gateway");
}
