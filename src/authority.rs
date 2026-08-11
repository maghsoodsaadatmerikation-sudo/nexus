//! Explicit authority-boundary types.
//!
//! This module is intentionally small.  It exists to make the constitutional
//! boundary visible in the source tree rather than hiding it in HTTP or UI
//! code.

/// Marker for the policy boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PolicyBoundary;

impl PolicyBoundary {
    pub const fn new() -> Self {
        Self
    }
}

impl Default for PolicyBoundary {
    fn default() -> Self {
        Self::new()
    }
}
