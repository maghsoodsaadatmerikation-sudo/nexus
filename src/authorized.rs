use crate::{authority::Authority, envelope::RequestEnvelope};

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
