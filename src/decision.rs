use crate::authority::Authority;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolicyDecision {
    Allow { authority: Authority },
    Deny { reason: DenialReason },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DenialReason {
    EmptyPayload,
    UnsupportedAction,
    AuthorityEscalation,
}

impl PolicyDecision {
    pub const fn is_allowed(&self) -> bool {
        matches!(self, Self::Allow { .. })
    }
}
