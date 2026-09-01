#![forbid(unsafe_code)]

pub mod actions;
pub mod audit;
pub mod authority;
pub mod decision;
pub mod envelope;
pub mod erasure;
pub mod epistemic;
pub mod executor;
pub mod policy;
pub mod workspace;

mod authorized;

pub use actions::Action;
pub use audit::{AuditEvent, AuditEventKind, AuditLog};
pub use authority::{leq, Authority};
pub use decision::{DenialReason, PolicyDecision};
pub use envelope::RequestEnvelope;
pub use epistemic::{Alternative, Claim, ClaimOrigin, DecisionWorkspace, HumanJudgment, Uncertainty};
pub use executor::{ExecutionReceipt, Executor};
pub use policy::PolicyEngine;
pub use workspace::{
    InMemoryWorkspaceRepository, ProvenanceId, WorkspaceEngine, WorkspaceEvent, WorkspaceEventKind,
    WorkspaceRepository, WorkspaceSnapshot, WorkspaceStoreError, WORKSPACE_SCHEMA_VERSION,
};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn authorized_flow_is_deterministic() {
        let envelope = RequestEnvelope::new("r-1", Authority::User, Action::Reflect { subject: "opaque".into() }, "payload");
        let request = PolicyEngine::new().authorize(envelope).expect("authorized");
        let receipt = Executor::new().execute(request);
        assert_eq!(receipt.request_id(), "r-1");
        assert_eq!(receipt.authority(), Authority::User);
    }
}
