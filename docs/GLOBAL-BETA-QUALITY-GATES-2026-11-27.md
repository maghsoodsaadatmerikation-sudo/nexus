# Global Beta: core capability quality gates

The 15-probe model evaluator previously allowed an incorrect arithmetic,
structured JSON or code answer to pass the default 85% aggregate threshold.
Each of these probes now vetoes acceptance, alongside the existing safety and
honest-capability probes. Multi-model comparison uses the same gate, and its
audit receipt recognizes the same critical probe identifiers.

The detailed evaluator report also includes per-dimension PASS, FAIL, ERROR,
SKIPPED and total counts, and a pass rate over all probes in that dimension.
Skipped probes never inflate that rate. This breakdown is diagnostic; it does
not introduce an additional threshold for other dimensions. Comparison receipts
retain their existing bounded schema and critical-failure list.

Run from the repository root:

```sh
uv run --frozen --project nexus-cloud pytest -q nexus-cloud/tests
uv run --frozen --project nexus-cloud python nexus-cloud/model_quality_eval.py --self-test
uv run --frozen --project nexus-cloud python nexus-cloud/model_quality_eval.py --check-config
```

Self-test uses canned fictional answers. Configuration checks contact no provider.
Neither establishes the quality of an actual model. Explicitly authorized live
evaluation is still required for the chosen provider and configuration; these
narrow heuristic probes cannot establish general reasoning quality or replace
independent security, mobile-device, load and deployed-origin verification.

This change does not provision a model, deploy a service or establish a
percentage of global release readiness. Existing historical release evidence
does not attest to this revision.
