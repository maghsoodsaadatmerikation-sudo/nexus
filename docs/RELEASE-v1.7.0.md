# NEXUS v1.7.0 — Runtime Provenance & Source-Tree Identity

Status: **RELEASE CANDIDATE / FAIL-CLOSED UNTIL EXACT-CANDIDATE VERIFICATION AND RELEASE GATE PASS**

NEXUS v1.7.0 extends the sealed v1.6 exact-promotion boundary while preserving:

`A_out <= A_in`

## Runtime target boundary

- Runtime target commit: `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`
- Provider: Railway
- Service: `nexus-stage-d`
- Environment: `production`
- Active provider source pin: `source.commitSha=3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`
- Post-change deployment: `b0e78cf8-af51-4092-9bf6-99e1ac5cc13b` — `SUCCESS`
- Durable boundary: `/data`
- Canonical source-tree SHA-256: `d66021fc1e8c276df2c673d26b05f2de58ef4c81589261cb41aefa1ad047f1c7`
- Independent runtime-identity workflow: `34884505985` — `SUCCESS`
- Public production reconciliation workflow: `34886934100` — `SUCCESS`
- Production runtime endpoint returned HTTP `200` and the same canonical digest.
- Runtime authority marker: `non_authoritative_build_metadata`

## Evidence boundary

The release evidence is recorded in `evidence/v1.7/production-runtime-evidence.json`. It records the exact runtime target, provider source binding, successful deployment, preserved durable mount, independently computed digest, public runtime observation, and exact digest equality.

The runtime identity endpoint is evidence-only. It does not authorize requests, create HumanJudgment, mutate policy, widen execution authority, or substitute for a release decision.

## Release gate

The historical `v1.6.0` release must remain unchanged. The final `v1.7.0` seal is permitted only after an explicit release-intent commit completes `NEXUS Verification` successfully and the dedicated release workflow independently validates the evidence fields and confirms that no `v1.7.0` tag already exists.

No paid upgrade, new production service, new production volume, secret disclosure, or authority expansion is authorized by this release.

## Claim boundary

If sealed, v1.7.0 may claim that the observed production executable reported a source-tree identity exactly matching independently computed repository evidence for the recorded runtime target and Railway deployment under the preserved `/data` durable-state boundary.

It may not claim bit-for-bit reproducible binaries across arbitrary builders, formal verification of Railway, universal security, universal availability, or formal proof of epistemic correctness.
