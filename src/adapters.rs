use crate::{
    AnalysisAdapter, AnalysisBatch, AnalysisError, AnalysisObservation, AnalysisObservationKind,
    DecisionWorkspace, Uncertainty,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvidenceRecord {
    pub id: String,
    pub text: String,
    pub source_id: String,
    pub uncertainty: Uncertainty,
}

pub trait EvidenceProvider: Send + Sync {
    fn research(&self, workspace: &DecisionWorkspace) -> Result<Vec<EvidenceRecord>, AnalysisError>;
}

pub struct ResearchEvidenceAdapter<P> {
    provider: P,
    run_id: String,
}

impl<P> ResearchEvidenceAdapter<P> {
    pub fn new(provider: P, run_id: impl Into<String>) -> Self {
        Self {
            provider,
            run_id: run_id.into(),
        }
    }
}

impl<P: EvidenceProvider> AnalysisAdapter for ResearchEvidenceAdapter<P> {
    fn analyze(&self, workspace: &DecisionWorkspace) -> Result<AnalysisBatch, AnalysisError> {
        let records = self.provider.research(workspace)?;
        if records.iter().any(|record| record.source_id.trim().is_empty()) {
            return Err(AnalysisError {
                message: "research evidence requires explicit source provenance".into(),
            });
        }
        Ok(AnalysisBatch {
            adapter_id: "research-evidence".into(),
            run_id: self.run_id.clone(),
            observations: records
                .into_iter()
                .map(|record| AnalysisObservation {
                    id: record.id,
                    kind: AnalysisObservationKind::EvidenceLead,
                    text: record.text,
                    uncertainty: record.uncertainty,
                    source_ids: vec![record.source_id],
                })
                .collect(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChallengeRecord {
    pub id: String,
    pub kind: AnalysisObservationKind,
    pub text: String,
    pub uncertainty: Uncertainty,
    pub source_ids: Vec<String>,
}

pub trait ChallengeProvider: Send + Sync {
    fn challenge(&self, workspace: &DecisionWorkspace) -> Result<Vec<ChallengeRecord>, AnalysisError>;
}

pub struct AiChallengeAdapter<P> {
    provider: P,
    run_id: String,
}

impl<P> AiChallengeAdapter<P> {
    pub fn new(provider: P, run_id: impl Into<String>) -> Self {
        Self {
            provider,
            run_id: run_id.into(),
        }
    }
}

impl<P: ChallengeProvider> AnalysisAdapter for AiChallengeAdapter<P> {
    fn analyze(&self, workspace: &DecisionWorkspace) -> Result<AnalysisBatch, AnalysisError> {
        let records = self.provider.challenge(workspace)?;
        if records.iter().any(|record| {
            !matches!(
                record.kind,
                AnalysisObservationKind::Counterargument
                    | AnalysisObservationKind::Assumption
                    | AnalysisObservationKind::UncertaintyNote
            )
        }) {
            return Err(AnalysisError {
                message: "challenge adapter cannot emit external-evidence observations".into(),
            });
        }
        Ok(AnalysisBatch {
            adapter_id: "ai-challenge".into(),
            run_id: self.run_id.clone(),
            observations: records
                .into_iter()
                .map(|record| AnalysisObservation {
                    id: record.id,
                    kind: record.kind,
                    text: record.text,
                    uncertainty: record.uncertainty,
                    source_ids: record.source_ids,
                })
                .collect(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ClaimOrigin, WorkspaceEngine, ProvenanceId};

    struct ResearchFixture;
    impl EvidenceProvider for ResearchFixture {
        fn research(&self, _workspace: &DecisionWorkspace) -> Result<Vec<EvidenceRecord>, AnalysisError> {
            Ok(vec![EvidenceRecord {
                id: "e-1".into(),
                text: "A source-backed lead".into(),
                source_id: "source:https://example.invalid/paper".into(),
                uncertainty: Uncertainty::Medium,
            }])
        }
    }

    struct ChallengeFixture;
    impl ChallengeProvider for ChallengeFixture {
        fn challenge(&self, _workspace: &DecisionWorkspace) -> Result<Vec<ChallengeRecord>, AnalysisError> {
            Ok(vec![ChallengeRecord {
                id: "a-1".into(),
                kind: AnalysisObservationKind::Counterargument,
                text: "Consider a competing explanation".into(),
                uncertainty: Uncertainty::High,
                source_ids: vec!["source:workspace".into()],
            }])
        }
    }

    #[test]
    fn research_adapter_preserves_source_and_uncertainty_without_judgment() {
        let workspace = DecisionWorkspace::new("w", "Question");
        let batch = ResearchEvidenceAdapter::new(ResearchFixture, "r-1")
            .analyze(&workspace)
            .unwrap();
        assert_eq!(batch.observations[0].source_ids, vec!["source:https://example.invalid/paper"]);
        assert_eq!(batch.observations[0].uncertainty, Uncertainty::Medium);
        assert!(!workspace.has_human_judgment());
    }

    #[test]
    fn challenge_adapter_materializes_only_non_authoritative_machine_claims() {
        let mut engine = WorkspaceEngine::new("w", "Question", ProvenanceId::new("human:owner"));
        let batch = AiChallengeAdapter::new(ChallengeFixture, "r-2")
            .analyze(engine.workspace())
            .unwrap();
        engine.record_analysis_batch(batch);
        assert_eq!(engine.workspace().claims[0].origin, ClaimOrigin::MachineAnalysis);
        assert!(!engine.workspace().has_human_judgment());
    }

    struct MissingSource;
    impl EvidenceProvider for MissingSource {
        fn research(&self, _workspace: &DecisionWorkspace) -> Result<Vec<EvidenceRecord>, AnalysisError> {
            Ok(vec![EvidenceRecord {
                id: "bad".into(),
                text: "Unprovenanced".into(),
                source_id: " ".into(),
                uncertainty: Uncertainty::Unknown,
            }])
        }
    }

    #[test]
    fn research_adapter_fails_closed_without_source_provenance() {
        let workspace = DecisionWorkspace::new("w", "Question");
        assert!(ResearchEvidenceAdapter::new(MissingSource, "r-3")
            .analyze(&workspace)
            .is_err());
    }
}
