use nexus_constitutional_core::{Action, Authority, Executor, RequestEnvelope};

fn main() {
    let envelope = RequestEnvelope::new("x", Authority::User, Action::Reflect { subject: "x".into() }, "payload");
    let _forged = nexus_constitutional_core::authorized::AuthorizedRequest {
        envelope,
        effective_authority: Authority::User,
    };
    let _ = Executor::new();
}
