use serde::{Deserialize, Serialize};

/// The epistemic state of a claim. It describes provenance and uncertainty,
/// but never grants authority to a generated interpretation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClaimOrigin {
    Human,
    ExternalEvidence { source: String },
    MachineAnalysis,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Claim {
    pub id: String,
    pub text: String,
    pub origin: ClaimOrigin,
    pub uncertainty: Uncertainty,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Uncertainty {
    Unknown,
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Alternative {
    pub id: String,
    pub label: String,
    pub consequences: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HumanJudgment {
    pub decision: String,
    pub rationale: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecisionWorkspace {
    pub id: String,
    pub question: String,
    pub goal: Option<String>,
    pub constraints: Vec<String>,
    pub values: Vec<String>,
    pub claims: Vec<Claim>,
    pub alternatives: Vec<Alternative>,
    pub judgment: Option<HumanJudgment>,
}

impl DecisionWorkspace {
    pub fn new(id: impl Into<String>, question: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            question: question.into(),
            goal: None,
            constraints: Vec::new(),
            values: Vec::new(),
            claims: Vec::new(),
            alternatives: Vec::new(),
            judgment: None,
        }
    }

    /// Records a claim without converting it into a decision.
    pub fn add_claim(&mut self, claim: Claim) {
        self.claims.push(claim);
    }

    /// Records an option without ranking it as the system's recommendation.
    pub fn add_alternative(&mut self, alternative: Alternative) {
        self.alternatives.push(alternative);
    }

    /// Only an explicit human judgment can populate the decision field.
    pub fn record_human_judgment(&mut self, judgment: HumanJudgment) {
        self.judgment = Some(judgment);
    }

    pub fn has_human_judgment(&self) -> bool {
        self.judgment.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn machine_analysis_cannot_become_human_judgment_implicitly() {
        let mut workspace = DecisionWorkspace::new("d-1", "Which option should I examine?");
        workspace.add_claim(Claim {
            id: "c-1".into(),
            text: "Machine-generated interpretation".into(),
            origin: ClaimOrigin::MachineAnalysis,
            uncertainty: Uncertainty::High,
        });

        assert!(!workspace.has_human_judgment());
    }

    #[test]
    fn human_judgment_is_explicit() {
        let mut workspace = DecisionWorkspace::new("d-2", "Question");
        workspace.record_human_judgment(HumanJudgment {
            decision: "Option A".into(),
            rationale: "My stated rationale".into(),
        });

        assert!(workspace.has_human_judgment());
    }
}
