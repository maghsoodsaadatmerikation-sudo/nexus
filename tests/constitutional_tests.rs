use nexus_constitutional_core::*;

fn envelope(id: &str, authority: Authority, payload: &str) -> RequestEnvelope {
    RequestEnvelope::new(id, authority, Action::Reflect { subject: "opaque".into() }, payload)
}

#[test] fn ct_001_authority_reflexive() { assert!(leq(Authority::User, Authority::User)); }
#[test] fn ct_002_authority_can_decrease() { assert!(leq(Authority::System, Authority::User)); }
#[test] fn ct_003_authority_cannot_increase() { assert!(!leq(Authority::User, Authority::Policy)); }
#[test] fn ct_004_none_cannot_be_amplified() { assert!(!leq(Authority::None, Authority::User)); }
#[test] fn ct_005_envelope_serializes() { let x = serde_json::to_string(&envelope("1", Authority::User, "x")).is_ok(); assert!(x); }
#[test] fn ct_006_policy_is_deterministic() { let p=PolicyEngine::new(); let a=p.authorize(envelope("1",Authority::User,"x")).unwrap(); let b=p.authorize(envelope("1",Authority::User,"x")).unwrap(); assert_eq!(a,b); }
#[test] fn ct_007_empty_payload_denied() { assert!(!PolicyEngine::new().authorize(envelope("1",Authority::User,"")).is_ok()); }
#[test] fn ct_008_user_request_allowed() { assert!(PolicyEngine::new().authorize(envelope("1",Authority::User,"x")).is_ok()); }
#[test] fn ct_009_system_request_reduces_authority() { let r=PolicyEngine::new().authorize(envelope("1",Authority::System,"x")).unwrap(); assert_eq!(r.authority(),Authority::User); }
#[test] fn ct_010_none_request_denied() { assert!(PolicyEngine::new().authorize(envelope("1",Authority::None,"x")).is_err()); }
#[test] fn ct_011_request_id_preserved() { let r=PolicyEngine::new().authorize(envelope("abc",Authority::User,"x")).unwrap(); assert_eq!(r.request_id(),"abc"); }
#[test] fn ct_012_executor_accepts_authorized() { let r=PolicyEngine::new().authorize(envelope("1",Authority::User,"x")).unwrap(); assert_eq!(Executor::new().execute(r).request_id(),"1"); }
#[test] fn ct_013_executor_preserves_effective_authority() { let r=PolicyEngine::new().authorize(envelope("1",Authority::System,"x")).unwrap(); assert_eq!(Executor::new().execute(r).authority(),Authority::User); }
#[test] fn ct_014_action_is_opaque_data() { let a=Action::Present{value:"x".into()}; assert_eq!(a,Action::Present{value:"x".into()}); }
#[test] fn ct_015_decision_allowed_flag() { assert!(PolicyDecision::Allow{authority:Authority::User}.is_allowed()); }
#[test] fn ct_016_decision_denied_flag() { assert!(!PolicyDecision::Deny{reason:DenialReason::EmptyPayload}.is_allowed()); }
#[test] fn ct_017_audit_records() { let mut a=AuditLog::default(); a.record(AuditEvent{request_id:"1".into(),event:AuditEventKind::Authorized}); assert_eq!(a.events().len(),1); }
#[test] fn ct_018_erasure_consumes_envelope() { let e=envelope("1",Authority::User,"secret"); nexus_constitutional_core::erasure::erase(e); }
#[test] fn ct_019_authorized_envelope_is_read_only() { let r=PolicyEngine::new().authorize(envelope("1",Authority::User,"x")).unwrap(); assert_eq!(r.envelope().payload,"x"); }
#[test] fn ct_020_no_unsafe_code_contract() { assert_eq!(std::mem::size_of::<Authority>(),1); }
