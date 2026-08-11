use serde::{Deserialize, Serialize};
use crate::{actions::Action, authority::Authority};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RequestEnvelope {
    pub request_id: String,
    pub authority: Authority,
    pub action: Action,
    pub payload: String,
}

impl RequestEnvelope {
    pub fn new(request_id: impl Into<String>, authority: Authority, action: Action, payload: impl Into<String>) -> Self {
        Self { request_id: request_id.into(), authority, action, payload: payload.into() }
    }
}
