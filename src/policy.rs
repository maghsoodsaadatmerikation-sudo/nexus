use crate::{
    authorized::AuthorizedRequest,
    authority::{leq, Authority},
    capability::{CapabilityAuditEvent, CapabilityAuditLog, CapabilityAuditOutcome, CapabilityDenial, CapabilityGrant, RevocationSet},
    decision::{DenialReason, PolicyDecision},
    envelope::RequestEnvelope,
};

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

    /// Capability-aware constitutional boundary. No AuthorizedRequest exists until
    /// the grant has passed every fail-closed capability check.
    pub fn authorize_delegated(
        &self,
        envelope: RequestEnvelope,
        grant: &CapabilityGrant,
        expected_subject: &str,
        now: u64,
        revocations: &RevocationSet,
        audit: &mut CapabilityAuditLog,
    ) -> Result<AuthorizedRequest, CapabilityDenial> {
        let request_id = envelope.request_id.clone();
        let grant_id = grant.grant_id.clone();
        if envelope.payload.is_empty() {
            let denial = CapabilityDenial::EmptyPayload;
            audit.record(CapabilityAuditEvent { request_id, grant_id, outcome: CapabilityAuditOutcome::Denied(denial.clone()) });
            return Err(denial);
        }
        let effective = match grant.validate(envelope.authority, expected_subject, &envelope.action, now, revocations) {
            Ok(authority) => authority,
            Err(denial) => {
                audit.record(CapabilityAuditEvent { request_id, grant_id, outcome: CapabilityAuditOutcome::Denied(denial.clone()) });
                return Err(denial);
            }
        };
        audit.record(CapabilityAuditEvent { request_id, grant_id, outcome: CapabilityAuditOutcome::Authorized });
        Ok(AuthorizedRequest { envelope, effective_authority: effective })
    }
}

#[cfg(test)]
mod capability_boundary_tests {
    use super::*;
    use crate::{Action, CapabilityAction, CAPABILITY_SCHEMA_VERSION};

    fn envelope() -> RequestEnvelope { RequestEnvelope::new("r-cap", Authority::User, Action::Reflect { subject: "opaque".into() }, "payload") }
    fn grant() -> CapabilityGrant { CapabilityGrant { schema_version: CAPABILITY_SCHEMA_VERSION, grant_id: "g-cap".into(), issuer: "issuer".into(), subject: "worker".into(), parent_authority: Authority::User, delegated_authority: Authority::User, scope: vec![CapabilityAction::Reflect], issued_at: 10, expires_at: 20, provenance_id: "prov-cap".into() } }

    #[test]
    fn delegated_authorization_crosses_boundary_only_after_validation() {
        let mut audit = CapabilityAuditLog::default();
        let request = PolicyEngine::new().authorize_delegated(envelope(), &grant(), "worker", 15, &RevocationSet::default(), &mut audit).expect("delegated authorization");
        assert_eq!(request.authority(), Authority::User);
        assert_eq!(audit.events().len(), 1);
        assert_eq!(audit.events()[0].outcome, CapabilityAuditOutcome::Authorized);
    }

    #[test]
    fn revoked_grant_never_constructs_authorized_request() {
        let mut revocations = RevocationSet::default(); revocations.revoke("g-cap");
        let mut audit = CapabilityAuditLog::default();
        assert_eq!(PolicyEngine::new().authorize_delegated(envelope(), &grant(), "worker", 15, &revocations, &mut audit), Err(CapabilityDenial::Revoked));
        assert_eq!(audit.events()[0].outcome, CapabilityAuditOutcome::Denied(CapabilityDenial::Revoked));
    }

    #[test]
    fn empty_payload_fails_closed_before_capability_execution() {
        let empty = RequestEnvelope::new("r-empty", Authority::User, Action::Reflect { subject: "opaque".into() }, "");
        let mut audit = CapabilityAuditLog::default();
        assert_eq!(PolicyEngine::new().authorize_delegated(empty, &grant(), "worker", 15, &RevocationSet::default(), &mut audit), Err(CapabilityDenial::EmptyPayload));
    }
}
