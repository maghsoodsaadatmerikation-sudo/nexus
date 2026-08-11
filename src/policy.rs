use crate::{authorized::AuthorizedRequest, authority::{leq, Authority}, decision::{DenialReason, PolicyDecision}, envelope::RequestEnvelope};

#[derive(Debug, Default, Clone, Copy)]
pub struct PolicyEngine;

impl PolicyEngine {
    pub const fn new() -> Self { Self }

    /// Deterministic policy boundary. It never interprets payload semantics.
    pub(crate) fn evaluate(&self, envelope: RequestEnvelope) -> Result<AuthorizedRequest, PolicyDecision> {
        if envelope.payload.is_empty() {
            return Err(PolicyDecision::Deny { reason: DenialReason::EmptyPayload });
        }

        let effective = Authority::User;
        if !leq(envelope.authority, effective) {
            return Err(PolicyDecision::Deny { reason: DenialReason::AuthorityEscalation });
        }

        Ok(AuthorizedRequest { envelope, effective_authority: effective })
    }

    pub fn authorize(&self, envelope: RequestEnvelope) -> Result<AuthorizedRequest, PolicyDecision> {
        self.evaluate(envelope)
    }
}
