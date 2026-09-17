use serde::{Deserialize, Serialize};

use crate::{actions::Action, authority::{leq, Authority}};

pub const CAPABILITY_SCHEMA_VERSION: u32 = 1;
pub const REVOCATION_SCHEMA_VERSION: u32 = 1;

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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RevocationEvent {
    pub sequence: u64,
    pub grant_id: String,
    pub provenance_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RevocationSnapshot {
    pub schema_version: u32,
    pub events: Vec<RevocationEvent>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RevocationReplayError {
    UnsupportedSchema,
    InvalidSequence,
    EmptyGrantId,
    EmptyProvenance,
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct RevocationSet {
    revoked: std::collections::BTreeSet<String>,
    events: Vec<RevocationEvent>,
}
impl RevocationSet {
    pub fn revoke(&mut self, grant_id: impl Into<String>) {
        self.revoke_with_provenance(grant_id, "legacy:unspecified");
    }

    pub fn revoke_with_provenance(&mut self, grant_id: impl Into<String>, provenance_id: impl Into<String>) {
        let grant_id = grant_id.into();
        let event = RevocationEvent {
            sequence: self.events.len() as u64,
            grant_id: grant_id.clone(),
            provenance_id: provenance_id.into(),
        };
        self.revoked.insert(grant_id);
        self.events.push(event);
    }

    pub fn is_revoked(&self, grant_id: &str) -> bool { self.revoked.contains(grant_id) }
    pub fn events(&self) -> &[RevocationEvent] { &self.events }

    pub fn snapshot(&self) -> RevocationSnapshot {
        RevocationSnapshot { schema_version: REVOCATION_SCHEMA_VERSION, events: self.events.clone() }
    }

    pub fn from_snapshot(snapshot: RevocationSnapshot) -> Result<Self, RevocationReplayError> {
        if snapshot.schema_version != REVOCATION_SCHEMA_VERSION {
            return Err(RevocationReplayError::UnsupportedSchema);
        }
        let mut set = Self::default();
        for (index, event) in snapshot.events.into_iter().enumerate() {
            if event.sequence != index as u64 { return Err(RevocationReplayError::InvalidSequence); }
            if event.grant_id.is_empty() { return Err(RevocationReplayError::EmptyGrantId); }
            if event.provenance_id.is_empty() { return Err(RevocationReplayError::EmptyProvenance); }
            set.revoked.insert(event.grant_id.clone());
            set.events.push(event);
        }
        Ok(set)
    }
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

    #[test] fn revocation_replay_reconstructs_state() {
        let mut r=RevocationSet::default();
        r.revoke_with_provenance("g-1","human:p1");
        r.revoke_with_provenance("g-2","human:p2");
        let restored=RevocationSet::from_snapshot(r.snapshot()).unwrap();
        assert!(restored.is_revoked("g-1")); assert!(restored.is_revoked("g-2"));
        assert_eq!(restored.events().len(),2);
    }
    #[test] fn repeated_revocation_remains_revoked_and_observable() {
        let mut r=RevocationSet::default();
        r.revoke_with_provenance("g-1","human:p1"); r.revoke_with_provenance("g-1","human:p2");
        assert!(r.is_revoked("g-1")); assert_eq!(r.events().len(),2);
    }
    #[test] fn broken_revocation_sequence_fails_closed() {
        let mut s=RevocationSet::default().snapshot();
        s.events.push(RevocationEvent{sequence:2,grant_id:"g".into(),provenance_id:"p".into()});
        assert_eq!(RevocationSet::from_snapshot(s),Err(RevocationReplayError::InvalidSequence));
    }
    #[test] fn unsupported_revocation_schema_fails_closed() {
        let mut s=RevocationSet::default().snapshot(); s.schema_version+=1;
        assert_eq!(RevocationSet::from_snapshot(s),Err(RevocationReplayError::UnsupportedSchema));
    }
    #[test] fn empty_revocation_identity_fails_closed() {
        let s=RevocationSnapshot{schema_version:REVOCATION_SCHEMA_VERSION,events:vec![RevocationEvent{sequence:0,grant_id:"".into(),provenance_id:"p".into()}]};
        assert_eq!(RevocationSet::from_snapshot(s),Err(RevocationReplayError::EmptyGrantId));
    }
    #[test] fn empty_revocation_provenance_fails_closed() {
        let s=RevocationSnapshot{schema_version:REVOCATION_SCHEMA_VERSION,events:vec![RevocationEvent{sequence:0,grant_id:"g".into(),provenance_id:"".into()}]};
        assert_eq!(RevocationSet::from_snapshot(s),Err(RevocationReplayError::EmptyProvenance));
    }
}
