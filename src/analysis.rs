use crate::{Claim, ClaimOrigin, DecisionWorkspace, ProvenanceId, Uncertainty};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AnalysisObservationKind {
    EvidenceLead,
    Counterargument,
    Assumption,
    UncertaintyNote,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AnalysisObservation {
    pub id: String,
    pub kind: AnalysisObservationKind,
    pub text: String,
    pub uncertainty: Uncertainty,
    pub source_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AnalysisBatch {
    pub adapter_id: String,
    pub run_id: String,
    pub observations: Vec<AnalysisObservation>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AnalysisError {
    pub message: String,
}

pub trait AnalysisAdapter {
    fn analyze(&self, workspace: &DecisionWorkspace) -> Result<AnalysisBatch, AnalysisError>;
}

impl AnalysisBatch {
    pub fn provenance_id(&self) -> ProvenanceId {
        ProvenanceId::new(format!("machine:{}:{}", self.adapter_id, self.run_id))
    }

    pub fn machine_claims(&self) -> Vec<Claim> {
        self.observations
            .iter()
            .map(|observation| Claim {
                id: observation.id.clone(),
                text: observation.text.clone(),
                origin: ClaimOrigin::MachineAnalysis,
                uncertainty: observation.uncertainty.clone(),
            })
            .collect()
    }
}

/// A bounded, deterministic question probe executed inside the server.
/// It does not fetch evidence, call a model, or make a factual assertion.
/// The trusted gateway, rather than the HTTP caller, supplies the run ID.
#[derive(Debug, Clone)]
pub struct LocalQuestionProbe {
    run_id: String,
}

impl LocalQuestionProbe {
    pub fn new(run_id: impl Into<String>) -> Self {
        Self {
            run_id: run_id.into(),
        }
    }
}

impl AnalysisAdapter for LocalQuestionProbe {
    fn analyze(&self, workspace: &DecisionWorkspace) -> Result<AnalysisBatch, AnalysisError> {
        if self.run_id.trim().is_empty() {
            return Err(AnalysisError {
                message: "missing-local-run-id".into(),
            });
        }
        let question: String = workspace.question.chars().take(240).collect();
        Ok(AnalysisBatch {
            adapter_id: "nexus-local-question-probe-v1".into(),
            run_id: self.run_id.clone(),
            observations: vec![AnalysisObservation {
                id: format!("local-question-probe-{}", self.run_id),
                kind: AnalysisObservationKind::UncertaintyNote,
                text: format!(
                    "Local rule-based question (not evidence): What observation could disconfirm: {question}"
                ),
                uncertainty: Uncertainty::High,
                source_ids: Vec::new(),
            }],
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct StaticChallengeAdapter;

    impl AnalysisAdapter for StaticChallengeAdapter {
        fn analyze(&self, workspace: &DecisionWorkspace) -> Result<AnalysisBatch, AnalysisError> {
            Ok(AnalysisBatch {
                adapter_id: "static-challenge".into(),
                run_id: "run-1".into(),
                observations: vec![AnalysisObservation {
                    id: "analysis-1".into(),
                    kind: AnalysisObservationKind::Counterargument,
                    text: format!("Challenge the assumptions behind: {}", workspace.question),
                    uncertainty: Uncertainty::High,
                    source_ids: vec![],
                }],
            })
        }
    }

    #[test]
    fn machine_analysis_can_only_materialize_as_machine_origin_claims() {
        let workspace = DecisionWorkspace::new("w", "Question");
        let batch = StaticChallengeAdapter.analyze(&workspace).unwrap();
        let claims = batch.machine_claims();
        assert_eq!(claims.len(), 1);
        assert_eq!(claims[0].origin, ClaimOrigin::MachineAnalysis);
        assert!(!workspace.has_human_judgment());
        assert_eq!(batch.provenance_id().0, "machine:static-challenge:run-1");
    }

    #[test]
    fn local_probe_is_bounded_questioning_not_external_evidence() {
        let question = "س".repeat(700);
        let workspace = DecisionWorkspace::new("local", question);
        let batch = LocalQuestionProbe::new("local-run-1")
            .analyze(&workspace)
            .unwrap();
        assert_eq!(batch.adapter_id, "nexus-local-question-probe-v1");
        assert_eq!(batch.run_id, "local-run-1");
        assert_eq!(batch.observations.len(), 1);
        let probe = &batch.observations[0];
        assert_eq!(probe.id, "local-question-probe-local-run-1");
        assert_eq!(probe.kind, AnalysisObservationKind::UncertaintyNote);
        assert_eq!(probe.uncertainty, Uncertainty::High);
        assert!(probe.source_ids.is_empty());
        assert!(probe.text.contains("not evidence"));
        assert!(probe.text.chars().count() <= 340);
        assert!(LocalQuestionProbe::new(" ")
            .analyze(&workspace)
            .is_err());
        assert!(!workspace.has_human_judgment());
    }

    #[test]
    fn sources_and_uncertainty_remain_explicit() {
        let batch = AnalysisBatch {
            adapter_id: "research".into(),
            run_id: "r-2".into(),
            observations: vec![AnalysisObservation {
                id: "e-1".into(),
                kind: AnalysisObservationKind::EvidenceLead,
                text: "External lead".into(),
                uncertainty: Uncertainty::Medium,
                source_ids: vec!["source:abc".into()],
            }],
        };
        assert_eq!(batch.observations[0].source_ids, vec!["source:abc"]);
        assert_eq!(batch.machine_claims()[0].uncertainty, Uncertainty::Medium);
    }
}
