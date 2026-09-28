use serde::{Deserialize, Serialize};

/// Ordered authority level. Higher values are strictly more authoritative.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[repr(u8)]
pub enum Authority {
    None = 0,
    User = 1,
    Policy = 2,
    System = 3,
}

/// Constitutional ordering: authority may be preserved or reduced, never amplified.
pub const fn leq(input: Authority, output: Authority) -> bool {
    (output as u8) <= (input as u8)
}

pub const fn authority_out(input: Authority) -> Authority { input }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn authority_cannot_increase() {
        assert!(leq(Authority::System, Authority::System));
        assert!(leq(Authority::User, Authority::None));
        assert!(!leq(Authority::User, Authority::Policy));
    }
}
