use crate::{
    authorized::{AuthorizedRequest, DelegatedAuthorizedRequest},
    capability::RevocationSet,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DelegatedExecutionDenial {
    StaleRevocationEpoch { authorized_at: u64, current: u64 },
    DivergentRevocationState { epoch: u64 },
    Revoked,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExecutionReceipt {
    request_id: String,
    authority: crate::authority::Authority,
}

impl ExecutionReceipt {
    pub fn request_id(&self) -> &str { &self.request_id }
    pub fn authority(&self) -> crate::authority::Authority { self.authority }
}

#[derive(Debug, Default, Clone, Copy)]
pub struct Executor;

impl Executor {
    pub const fn new() -> Self { Self }

    /// Constitutional boundary: execution accepts only an AuthorizedRequest.
    pub fn execute(&self, request: AuthorizedRequest) -> ExecutionReceipt {
        ExecutionReceipt {
            request_id: request.request_id().to_owned(),
            authority: request.authority(),
        }
    }

    /// Delegated execution is valid only against the exact revocation epoch
    /// observed during authorization. Any newer, older, or otherwise unknown
    /// state fails closed before execution.
    pub fn execute_delegated(
        &self,
        request: DelegatedAuthorizedRequest,
        current_revocations: &RevocationSet,
    ) -> Result<ExecutionReceipt, DelegatedExecutionDenial> {
        let current = current_revocations.epoch();
        if request.revocation_epoch() != current {
            return Err(DelegatedExecutionDenial::StaleRevocationEpoch {
                authorized_at: request.revocation_epoch(),
                current,
            });
        }
        if request.revocation_snapshot() != &current_revocations.snapshot() {
            return Err(DelegatedExecutionDenial::DivergentRevocationState { epoch: current });
        }
        if current_revocations.is_revoked(request.grant_id()) {
            return Err(DelegatedExecutionDenial::Revoked);
        }
        Ok(ExecutionReceipt {
            request_id: request.request_id().to_owned(),
            authority: request.authority(),
        })
    }
}

#[cfg(test)]
mod delegated_freshness_tests {
    use super::*;
    use crate::{
        Action, Authority, CapabilityAction, CapabilityAuditLog, CapabilityGrant, PolicyEngine,
        RequestEnvelope, CAPABILITY_SCHEMA_VERSION,
    };

    fn grant() -> CapabilityGrant {
        CapabilityGrant {
            schema_version: CAPABILITY_SCHEMA_VERSION,
            grant_id: "g-fresh".into(),
            issuer: "issuer".into(),
            subject: "worker".into(),
            parent_authority: Authority::User,
            delegated_authority: Authority::User,
            scope: vec![CapabilityAction::Reflect],
            issued_at: 10,
            expires_at: 20,
            provenance_id: "prov-fresh".into(),
        }
    }

    fn authorize(revocations: &RevocationSet) -> DelegatedAuthorizedRequest {
        let envelope = RequestEnvelope::new(
            "r-fresh",
            Authority::User,
            Action::Reflect { subject: "opaque".into() },
            "payload",
        );
        PolicyEngine::new()
            .authorize_delegated(
                envelope,
                &grant(),
                "worker",
                15,
                revocations,
                &mut CapabilityAuditLog::default(),
            )
            .expect("delegated authorization")
    }

    #[test]
    fn exact_epoch_executes() {
        let revocations = RevocationSet::default();
        let request = authorize(&revocations);
        let receipt = Executor::new()
            .execute_delegated(request, &revocations)
            .expect("fresh delegated execution");
        assert_eq!(receipt.request_id(), "r-fresh");
    }

    #[test]
    fn revocation_after_authorization_rejects_stale_request() {
        let mut revocations = RevocationSet::default();
        let request = authorize(&revocations);
        revocations.revoke_with_provenance("g-fresh", "human:revoke");
        assert_eq!(
            Executor::new().execute_delegated(request, &revocations),
            Err(DelegatedExecutionDenial::StaleRevocationEpoch { authorized_at: 0, current: 1 })
        );
    }

    #[test]
    fn unrelated_revocation_invalidates_cached_authorization() {
        let mut revocations = RevocationSet::default();
        let request = authorize(&revocations);
        revocations.revoke_with_provenance("another-grant", "human:revoke-other");
        assert_eq!(
            Executor::new().execute_delegated(request, &revocations),
            Err(DelegatedExecutionDenial::StaleRevocationEpoch { authorized_at: 0, current: 1 })
        );
    }

    #[test]
    fn older_snapshot_cannot_execute_newer_authorization() {
        let older = RevocationSet::default();
        let mut current = RevocationSet::default();
        current.revoke_with_provenance("another-grant", "human:epoch-1");
        let request = authorize(&current);
        assert_eq!(
            Executor::new().execute_delegated(request, &older),
            Err(DelegatedExecutionDenial::StaleRevocationEpoch { authorized_at: 1, current: 0 })
        );
    }

    #[test]
    fn equal_epoch_divergent_history_fails_closed() {
        let mut authorized_state = RevocationSet::default();
        authorized_state.revoke_with_provenance("grant-a", "human:a");
        let request = authorize(&authorized_state);

        let mut divergent_state = RevocationSet::default();
        divergent_state.revoke_with_provenance("grant-b", "human:b");
        assert_eq!(authorized_state.epoch(), divergent_state.epoch());
        assert_eq!(
            Executor::new().execute_delegated(request, &divergent_state),
            Err(DelegatedExecutionDenial::DivergentRevocationState { epoch: 1 })
        );
    }

    #[test]
    fn reauthorization_at_current_epoch_restores_only_unrevoked_request() {
        let mut revocations = RevocationSet::default();
        revocations.revoke_with_provenance("another-grant", "human:epoch-1");
        let request = authorize(&revocations);
        assert!(Executor::new().execute_delegated(request, &revocations).is_ok());
    }
}
