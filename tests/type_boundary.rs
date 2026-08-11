use nexus_constitutional_core::{Executor, PolicyEngine, Request, RequestId};

#[test]
fn public_api_requires_policy_boundary_before_execution() {
    let policy = PolicyEngine::new();
    let executor = Executor::new();
    let request = Request::new(RequestId::new(7), b"opaque request".to_vec());

    let authorized = policy.authorize(request).expect("non-empty request should authorize");
    let receipt = executor.execute(authorized);

    assert_eq!(receipt.request_id(), RequestId::new(7));
    assert!(receipt.accepted());
}

#[test]
fn denied_request_never_reaches_executor() {
    let policy = PolicyEngine::new();
    let request = Request::new(RequestId::new(8), Vec::<u8>::new());

    assert!(policy.authorize(request).is_err());
}
