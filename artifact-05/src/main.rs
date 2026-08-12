use nexus_artifact_05_gateway::{router, AppState, ConstitutionalDelegate, DelegateError, Submission};
use nexus_constitutional_core::{PolicyEngine, RequestEnvelope};
use std::net::SocketAddr;

struct CoreDelegate;

impl ConstitutionalDelegate for CoreDelegate {
    fn submit(&self, envelope: RequestEnvelope) -> Result<Submission, DelegateError> {
        // Authority/policy remains inside the Constitutional Core.
        let request = PolicyEngine::new()
            .authorize(envelope)
            .map_err(|_| DelegateError)?;
        let receipt = nexus_constitutional_core::Executor::new().execute(request);
        Ok(Submission { request_id: receipt.request_id().to_owned() })
    }
}

#[tokio::main]
async fn main() {
    let app = router(AppState::new(CoreDelegate));
    let addr: SocketAddr = "127.0.0.1:3000".parse().expect("valid address");
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind gateway");
    axum::serve(listener, app).await.expect("serve gateway");
}
