use serde::{Deserialize, Serialize};

use crate::{actions::Action, authority::{leq, Authority}};

pub const CAPABILITY_SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CapabilityAction { Reflect, Present, Select }

impl CapabilityAction {
    pub fn matches(&self, action: &Action) -> bool {
        matches!((self, action),
            (Self::Reflect, Action::Reflect { .. }) |
            (Self::Present, Action::Present { .. }) |
            (Self::Select, Action::Select { .. }))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilityGrant {
    pub schema_version: u32,
    pub grant_id: String,
    pub issuer: String,
    pub subject: String,
    pub parent_authority: Authority,
    pub delegated_authority: Authority,
    pub scope: Vec<CapabilityAction>,
    pub issued_at: u64,
    pub expires_at: u64,
    pub provenance_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CapabilityDenial {
    EmptyPayload, UnsupportedSchema, EmptyIdentity, EmptyProvenance, EmptyScope, InvalidValidityWindow,
    AuthorityAmplification, SubjectMismatch, OutOfScope, NotYetValid, Expired, Revoked,
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct RevocationSet { revoked: std::collections::BTreeSet<String> }
impl RevocationSet {
    pub fn revoke(&mut self, grant_id: impl Into<String>) { self.revoked.insert(grant_id.into()); }
    pub fn is_revoked(&self, grant_id: &str) -> bool { self.revoked.contains(grant_id) }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CapabilityAuditOutcome { Authorized, Denied(CapabilityDenial) }
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilityAuditEvent { pub request_id: String, pub grant_id: String, pub outcome: CapabilityAuditOutcome }
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct CapabilityAuditLog { events: Vec<CapabilityAuditEvent> }
impl CapabilityAuditLog {
    pub fn record(&mut self, event: CapabilityAuditEvent) { self.events.push(event); }
    pub fn events(&self) -> &[CapabilityAuditEvent] { &self.events }
}

impl CapabilityGrant {
    pub fn validate(&self, input_authority: Authority, expected_subject: &str, action: &Action, now: u64, revocations: &RevocationSet) -> Result<Authority, CapabilityDenial> {
        if self.schema_version != CAPABILITY_SCHEMA_VERSION { return Err(CapabilityDenial::UnsupportedSchema); }
        if self.grant_id.is_empty() || self.issuer.is_empty() || self.subject.is_empty() { return Err(CapabilityDenial::EmptyIdentity); }
        if self.provenance_id.is_empty() { return Err(CapabilityDenial::EmptyProvenance); }
        if self.scope.is_empty() { return Err(CapabilityDenial::EmptyScope); }
        if self.expires_at <= self.issued_at { return Err(CapabilityDenial::InvalidValidityWindow); }
        if !leq(self.parent_authority, self.delegated_authority) || !leq(input_authority, self.parent_authority) { return Err(CapabilityDenial::AuthorityAmplification); }
        if self.subject != expected_subject { return Err(CapabilityDenial::SubjectMismatch); }
        if !self.scope.iter().any(|allowed| allowed.matches(action)) { return Err(CapabilityDenial::OutOfScope); }
        if now < self.issued_at { return Err(CapabilityDenial::NotYetValid); }
        if now >= self.expires_at { return Err(CapabilityDenial::Expired); }
        if revocations.is_revoked(&self.grant_id) { return Err(CapabilityDenial::Revoked); }
        Ok(self.delegated_authority)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn grant() -> CapabilityGrant { CapabilityGrant { schema_version: CAPABILITY_SCHEMA_VERSION, grant_id: "g-1".into(), issuer: "issuer".into(), subject: "worker".into(), parent_authority: Authority::User, delegated_authority: Authority::User, scope: vec![CapabilityAction::Reflect], issued_at: 10, expires_at: 20, provenance_id: "prov-1".into() } }
    fn action() -> Action { Action::Reflect { subject: "x".into() } }
    #[test] fn bounded_grant_is_valid() { assert_eq!(grant().validate(Authority::User, "worker", &action(), 15, &RevocationSet::default()), Ok(Authority::User)); }
    #[test] fn amplification_fails_closed() { let mut g=grant(); g.delegated_authority=Authority::Policy; assert_eq!(g.validate(Authority::User,"worker",&action(),15,&RevocationSet::default()),Err(CapabilityDenial::AuthorityAmplification)); }
    #[test] fn cross_scope_fails_closed() { assert_eq!(grant().validate(Authority::User,"worker",&Action::Select{option:"x".into()},15,&RevocationSet::default()),Err(CapabilityDenial::OutOfScope)); }
    #[test] fn expiry_is_exclusive() { assert_eq!(grant().validate(Authority::User,"worker",&action(),20,&RevocationSet::default()),Err(CapabilityDenial::Expired)); }
    #[test] fn pre_issuance_fails_closed() { assert_eq!(grant().validate(Authority::User,"worker",&action(),9,&RevocationSet::default()),Err(CapabilityDenial::NotYetValid)); }
    #[test] fn revocation_is_monotonic() { let g=grant(); let mut r=RevocationSet::default(); r.revoke("g-1"); assert_eq!(g.validate(Authority::User,"worker",&action(),15,&r),Err(CapabilityDenial::Revoked)); assert!(r.is_revoked("g-1")); }
    #[test] fn subject_mismatch_fails_closed() { assert_eq!(grant().validate(Authority::User,"other",&action(),15,&RevocationSet::default()),Err(CapabilityDenial::SubjectMismatch)); }
    #[test] fn unsupported_schema_fails_closed() { let mut g=grant(); g.schema_version=2; assert_eq!(g.validate(Authority::User,"worker",&action(),15,&RevocationSet::default()),Err(CapabilityDenial::UnsupportedSchema)); }
    #[test] fn empty_scope_fails_closed() { let mut g=grant(); g.scope.clear(); assert_eq!(g.validate(Authority::User,"worker",&action(),15,&RevocationSet::default()),Err(CapabilityDenial::EmptyScope)); }
    #[test] fn zero_length_validity_window_fails_closed() { let mut g=grant(); g.expires_at=g.issued_at; assert_eq!(g.validate(Authority::User,"worker",&action(),10,&RevocationSet::default()),Err(CapabilityDenial::InvalidValidityWindow)); }
    #[test] fn inverted_validity_window_fails_closed() { let mut g=grant(); g.expires_at=g.issued_at-1; assert_eq!(g.validate(Authority::User,"worker",&action(),10,&RevocationSet::default()),Err(CapabilityDenial::InvalidValidityWindow)); }
    #[test] fn audit_is_append_only_from_public_api() { let mut log=CapabilityAuditLog::default(); log.record(CapabilityAuditEvent{request_id:"r1".into(),grant_id:"g1".into(),outcome:CapabilityAuditOutcome::Authorized}); log.record(CapabilityAuditEvent{request_id:"r2".into(),grant_id:"g2".into(),outcome:CapabilityAuditOutcome::Denied(CapabilityDenial::Revoked)}); assert_eq!(log.events().len(),2); assert_eq!(log.events()[0].request_id,"r1"); }
}
