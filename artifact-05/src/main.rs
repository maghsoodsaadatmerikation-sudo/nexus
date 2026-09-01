use nexus_artifact_05_gateway::{
    router, AppState, ConstitutionalDelegate, DelegateError, Submission, WorkspaceDelegate,
    WorkspaceDelegateError,
};
use nexus_constitutional_core::{
    Alternative, Claim, HumanJudgment, InMemoryWorkspaceRepository, PolicyEngine, ProvenanceId,
    RequestEnvelope, WorkspaceEngine, WorkspaceRepository, WorkspaceSnapshot,
};
use std::{net::SocketAddr, sync::Mutex};

#[derive(Default)]
struct CoreDelegate {
    workspaces: Mutex<InMemoryWorkspaceRepository>,
}

impl ConstitutionalDelegate for CoreDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        // Authority/policy remains inside the Constitutional Core.
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
        if repository.load(&workspace_id).is_some() {
            return Err(WorkspaceDelegateError::AlreadyExists);
        }
        let engine = WorkspaceEngine::new(workspace_id, question, provenance_id);
        let snapshot = engine.snapshot();
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
    let app = router(AppState::new(CoreDelegate::default()));
    let addr: SocketAddr = "127.0.0.1:3000".parse().expect("valid address");
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind gateway");
    axum::serve(listener, app).await.expect("serve gateway");
}
