use crate::authorized::AuthorizedRequest;

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
}
