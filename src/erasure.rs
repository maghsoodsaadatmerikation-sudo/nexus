use crate::envelope::RequestEnvelope;

/// Explicit erasure operation. It consumes the envelope and leaves no owned copy.
pub fn erase(envelope: RequestEnvelope) {
    drop(envelope);
}

#[derive(Debug, Default)]
pub struct ErasureProtocol;

impl ErasureProtocol {
    pub const fn new() -> Self { Self }
    pub fn erase(&self, envelope: RequestEnvelope) { erase(envelope); }
}
