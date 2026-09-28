# NEXUS Prototype-0.1 Verification Protocol

## Two-Phase Execution Flow

1. **Bootstrap (Phase 1):** 
   - Trigger `workflow_dispatch` with `mode: bootstrap`.
   - Generates a `Cargo.lock` and uploads it as `cargo-lock-candidate`.

2. **Human Commit (Boundary):**
   - Download the candidate `Cargo.lock` from the artifact.
   - Commit and push it to `main`. This commit becomes the **Source of Truth**.

3. **Verify (Phase 2):**
   - A `push` to `main` triggers the `verify` job.
   - The job runs all Gates with `--locked` and produces a `verification-manifest.txt`.

## Self-Audit & Sealing Condition

The system is **sealed** only when the following chain is complete:
- Gates 0, 1, 2, 3 pass
- `verification-manifest.txt` is generated
- `verify-manifest.sh` self-audit passes
- `verification-bundle.tar.gz` is attested by `actions/attest-build-provenance`

## Evidence Bundle

The final artifact `verification-bundle.tar.gz` contains:
- `verification-manifest.txt`
- `build_verification_<run-id>.log`
- `Cargo.lock`
- GitHub Attestation Provenance