use crate::{
    authority::Authority, capability::RevocationSnapshot, envelope::RequestEnvelope,
};

/// Proof that a request crossed the policy boundary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuthorizedRequest {
    pub(crate) envelope: RequestEnvelope,
    pub(crate) effective_authority: Authority,
}

impl AuthorizedRequest {
    pub fn request_id(&self) -> &str { &self.envelope.request_id }
    pub fn authority(&self) -> Authority { self.effective_authority }
    pub fn envelope(&self) -> &RequestEnvelope { &self.envelope }
}

/// Opaque proof that a delegated request crossed the capability boundary at a
/// specific revocation epoch. Execution must re-check this binding against the
/// current revocation state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegatedAuthorizedRequest {
    pub(crate) request: AuthorizedRequest,
    pub(crate) grant_id: String,
    pub(crate) revocation_epoch: u64,
    pub(crate) revocation_snapshot: RevocationSnapshot,
}

impl DelegatedAuthorizedRequest {
    pub fn request_id(&self) -> &str { self.request.request_id() }
    pub fn authority(&self) -> Authority { self.request.authority() }
    pub fn grant_id(&self) -> &str { &self.grant_id }
    pub fn revocation_epoch(&self) -> u64 { self.revocation_epoch }
    pub(crate) fn revocation_snapshot(&self) -> &RevocationSnapshot { &self.revocation_snapshot }
}
