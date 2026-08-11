#![forbid(unsafe_code)]

//! NEXUS Constitutional Core — Prototype 0.1.
//!
//! The core deliberately separates computation from epistemic authority.
//! The executor accepts only an `AuthorizedRequest`. Construction of that
//! type is restricted to the crate's policy boundary.

use std::marker::PhantomData;

/// Opaque request identifier supplied by the caller.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct RequestId(u64);

impl RequestId {
    pub const fn new(value: u64) -> Self {
        Self(value)
    }

    pub const fn value(self) -> u64 {
        self.0
    }
}

/// Input presented to the policy boundary.
///
/// The core treats the payload as opaque data. It does not interpret meaning,
/// diagnose a person, or infer an identity from it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Request {
    id: RequestId,
    payload: Vec<u8>,
}

impl Request {
    pub fn new(id: RequestId, payload: impl Into<Vec<u8>>) -> Self {
        Self {
            id,
            payload: payload.into(),
        }
    }

    pub const fn id(&self) -> RequestId {
        self.id
    }

    pub fn payload(&self) -> &[u8] {
        &self.payload
    }
}

/// Marker proving that a request crossed the policy boundary.
///
/// The constructor is intentionally private. External callers cannot forge
/// an `AuthorizedRequest` merely by constructing a value with the same data.
#[derive(Debug)]
pub struct AuthorizedRequest {
    request: Request,
    _authority: PhantomData<AuthorityToken>,
}

#[derive(Debug)]
struct AuthorityToken;

impl AuthorizedRequest {
    pub fn id(&self) -> RequestId {
        self.request.id()
    }

    pub fn payload(&self) -> &[u8] {
        self.request.payload()
    }
}

/// Policy decisions are deliberately narrow: authorization is a boundary
/// operation, not interpretation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolicyDecision {
    Authorized,
    Denied,
}

/// The public entry point for creating an `AuthorizedRequest`.
///
/// This type is the constitutional policy boundary. It can authorize or
/// reject access, but it does not interpret the request payload.
pub struct PolicyEngine {
    _private: (),
}

impl PolicyEngine {
    pub const fn new() -> Self {
        Self { _private: () }
    }

    pub fn authorize(&self, request: Request) -> Result<AuthorizedRequest, PolicyDecision> {
        // Prototype policy: an empty payload is rejected; non-empty opaque
        // payloads may cross the boundary. No semantic interpretation occurs.
        if request.payload().is_empty() {
            return Err(PolicyDecision::Denied);
        }

        Ok(AuthorizedRequest {
            request,
            _authority: PhantomData,
        })
    }
}

impl Default for PolicyEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Output produced by the executor.
///
/// The executor is intentionally incapable of producing an interpretation or
/// diagnostic. It receives only an already-authorized opaque request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExecutionReceipt {
    request_id: RequestId,
    accepted: bool,
}

impl ExecutionReceipt {
    pub const fn request_id(&self) -> RequestId {
        self.request_id
    }

    pub const fn accepted(&self) -> bool {
        self.accepted
    }
}

/// Constitutional executor.
pub struct Executor {
    _private: (),
}

impl Executor {
    pub const fn new() -> Self {
        Self { _private: () }
    }

    pub fn execute(&self, request: AuthorizedRequest) -> ExecutionReceipt {
        ExecutionReceipt {
            request_id: request.id(),
            accepted: true,
        }
    }
}

impl Default for Executor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn authorized_request_can_cross_executor_boundary() {
        let policy = PolicyEngine::new();
        let executor = Executor::new();
        let request = Request::new(RequestId::new(1), b"opaque".to_vec());

        let authorized = policy.authorize(request).expect("request should authorize");
        let receipt = executor.execute(authorized);

        assert_eq!(receipt.request_id(), RequestId::new(1));
        assert!(receipt.accepted());
    }

    #[test]
    fn empty_payload_is_denied_without_interpretation() {
        let policy = PolicyEngine::new();
        let request = Request::new(RequestId::new(2), Vec::<u8>::new());

        assert!(matches!(
            policy.authorize(request),
            Err(PolicyDecision::Denied)
        ));
    }
}
