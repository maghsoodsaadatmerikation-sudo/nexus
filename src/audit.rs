use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuditEvent {
    pub request_id: String,
    pub event: AuditEventKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AuditEventKind {
    Authorized,
    Executed,
    Erased,
}

#[derive(Debug, Default)]
pub struct AuditLog {
    events: Vec<AuditEvent>,
}

impl AuditLog {
    pub fn record(&mut self, event: AuditEvent) { self.events.push(event); }
    pub fn events(&self) -> &[AuditEvent] { &self.events }
}
