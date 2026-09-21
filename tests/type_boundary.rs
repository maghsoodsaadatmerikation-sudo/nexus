use nexus_constitutional_core::{
    Action, Authority, Executor, PolicyEngine, RequestEnvelope,
};

#[test]
fn public_api_requires_policy_boundary_before_execution() {
    let policy = PolicyEngine::new();
    let executor = Executor::new();
    let envelope = RequestEnvelope::new(
        "7",
        Authority::User,
        Action::Reflect {
            subject: "opaque request".into(),
        },
        "opaque request",
    );

    let authorized = policy
        .authorize(envelope)
        .expect("non-empty request should authorize");
    let receipt = executor.execute(authorized);

    assert_eq!(receipt.request_id(), "7");
    assert_eq!(receipt.authority(), Authority::User);
}

#[test]
fn denied_request_never_reaches_executor() {
    let policy = PolicyEngine::new();
    let envelope = RequestEnvelope::new(
        "8",
        Authority::User,
        Action::Reflect {
            subject: "opaque request".into(),
        },
        "",
    );

    assert!(policy.authorize(envelope).is_err());
}
