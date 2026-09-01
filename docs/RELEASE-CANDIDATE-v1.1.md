# NEXUS v1.1 Release Candidate Manifest

This stage packages already-validated Stage D and Stage E evidence into an offline release-candidate manifest. It does not create a tag, publish a GitHub Release, or expand machine epistemic authority.

The constitutional invariant remains:

`A_out <= A_in`

## Command

```bash
bash scripts/v1.1-release-candidate.sh ./stage-d-evidence <40-character-deployed-commit> <verification-run-id>
```

The command is fail-closed. It can produce `V1.1 RELEASE CANDIDATE: READY` only when `scripts/v1.1-release-readiness.sh` has independently accepted the complete Stage D evidence pack for the exact deployed commit.

The generated manifest binds:

- the exact deployed repository commit;
- the NEXUS Verification run ID supplied by the operator;
- the Stage D workspace snapshot SHA-256;
- the Stage D evidence-harness SHA-256;
- the Stage E release-readiness-gate SHA-256;
- explicit `Release Action Performed: NO`, `Tag Created: NO`, and `GitHub Release Published: NO` markers.

## Human release boundary

`Status: READY FOR HUMAN RELEASE DECISION` is deliberately not a release action. A human/operator still owns the decision to create the `v1.1.0` tag and GitHub Release after confirming that the referenced verification run completed successfully for the exact commit.

This stage must not infer that a run succeeded from a numeric run ID alone. Runtime verification status remains external evidence that must be checked directly.

A release-candidate manifest is operational evidence packaging only. It is not a claim of epistemic correctness, does not authorize machine judgment, and cannot substitute for real persistent-host Stage D evidence.
