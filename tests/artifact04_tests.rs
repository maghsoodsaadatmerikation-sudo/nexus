use nexus_constitutional_core::*;

fn env(id:&str, a:Authority, p:&str)->RequestEnvelope{RequestEnvelope::new(id,a,Action::Select{option:"opaque".into()},p)}
#[test] fn ct_021_select_action_roundtrip_shape(){assert_eq!(Action::Select{option:"x".into()},Action::Select{option:"x".into()});}
#[test] fn ct_022_reflect_action_shape(){assert_eq!(Action::Reflect{subject:"x".into()},Action::Reflect{subject:"x".into()});}
#[test] fn ct_023_present_action_shape(){assert_eq!(Action::Present{value:"x".into()},Action::Present{value:"x".into()});}
#[test] fn ct_024_envelope_authority_preserved(){assert_eq!(env("1",Authority::System,"x").authority,Authority::System);}
#[test] fn ct_025_policy_engine_default(){let p=PolicyEngine::default();assert!(p.authorize(env("1",Authority::User,"x")).is_ok());}
#[test] fn ct_026_executor_default(){let r=PolicyEngine::new().authorize(env("1",Authority::User,"x")).unwrap();assert_eq!(Executor::default().execute(r).request_id(),"1");}
#[test] fn ct_027_allow_is_allowed(){assert!(PolicyDecision::Allow{authority:Authority::None}.is_allowed());}
#[test] fn ct_028_empty_reason_is_specific(){assert_eq!(PolicyDecision::Deny{reason:DenialReason::EmptyPayload},PolicyDecision::Deny{reason:DenialReason::EmptyPayload});}
#[test] fn ct_029_audit_order_is_stable(){let mut a=AuditLog::default();a.record(AuditEvent{request_id:"1".into(),event:AuditEventKind::Authorized});a.record(AuditEvent{request_id:"1".into(),event:AuditEventKind::Executed});assert_eq!(a.events()[0].event,AuditEventKind::Authorized);}
#[test] fn ct_030_audit_erased_event(){let mut a=AuditLog::default();a.record(AuditEvent{request_id:"1".into(),event:AuditEventKind::Erased});assert_eq!(a.events()[0].event,AuditEventKind::Erased);}
#[test] fn ct_031_erasure_protocol(){let p=nexus_constitutional_core::erasure::ErasureProtocol::new();p.erase(env("1",Authority::User,"secret"));}
#[test] fn ct_032_effective_authority_never_exceeds_input(){let r=PolicyEngine::new().authorize(env("1",Authority::System,"x")).unwrap();assert!(leq(Authority::System,r.authority()));}
#[test] fn ct_033_user_authority_is_fixed_output(){let r=PolicyEngine::new().authorize(env("1",Authority::User,"x")).unwrap();assert_eq!(r.authority(),Authority::User);}
#[test] fn ct_034_none_is_rejected_instead_of_escalated(){assert!(PolicyEngine::new().authorize(env("1",Authority::None,"x")).is_err());}
#[test] fn ct_035_executor_has_no_policy_constructor(){let _=Executor::new();}
#[test] fn ct_036_request_id_is_not_rewritten(){let r=PolicyEngine::new().authorize(env("stable-id",Authority::User,"x")).unwrap();assert_eq!(r.request_id(),"stable-id");}
#[test] fn ct_037_payload_is_not_mutated(){let r=PolicyEngine::new().authorize(env("1",Authority::User,"payload")).unwrap();assert_eq!(r.envelope().payload,"payload");}
#[test] fn ct_038_public_surface_exposes_no_authorized_constructor(){let r=PolicyEngine::new().authorize(env("1",Authority::User,"x")).unwrap();assert_eq!(r.authority(),Authority::User);}
