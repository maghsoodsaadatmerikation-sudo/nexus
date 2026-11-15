# Stage D — 2-of-2 synthetic OCI evidence review and deny-only launch policy

## Problem proven by the preceding stages

The Stage 240 Docker build is a **local, synthetic-only image**, not a published registry artifact. Stage 241 demonstrated that its local-image-ID manifest and partial SBOM can be cryptographically signed with a **disposable Ed25519 key**. A valid signature alone is not independently attested builder provenance, an approved registry digest or permission to deploy to Railway/Render.

Stage 242 adds \`scripts/stage-d-two-reviewer-admission.py\` so that **two cryptographically different pinned Ed25519 public keys** must each sign a Stage-241 synthetic review binding the **same exact** pinned manifest, SBOM, reviewed PR SHA and local Docker image ID. One review cannot be reused as both reviewers. A third file describing a proposed *nonexecuting* container launch must match an exact synthetic-only deny-by-default contract.

### Verification inputs

The \`inspect-pair\` and \`admission-gate\` modes accept the same Stage-241 manifest/partial SBOM fields plus **two complete reviewer sets** and two exact external artifact pins:

\`\`\`sh
python3 scripts/stage-d-two-reviewer-admission.py inspect-pair \
  --manifest /private/manifest.json \
  --sbom /private/sbom.cdx.json \
  --reviewed-commit FULL_PR_GIT_SHA \
  --expected-manifest-sha256 EXTERNAL_MANIFEST_SHA256 \
  --expected-sbom-sha256 EXTERNAL_SBOM_SHA256 \
  --local-image-id sha256:LOCAL_IMAGE_ID \
  --deployment-intent /private/synthetic-intent.json \
  --expected-intent-sha256 EXTERNAL_INTENT_SHA256 \
  --candidate-spec /private/synthetic-launch.json \
  --candidate-spec-sha256 EXTERNAL_LAUNCH_SHA256 \
  --build-key-id BUILD_REVIEWER_ID \
  --build-public-key /private/build-public.pem \
  --build-public-der-sha256 EXTERNAL_BUILD_DER_SHA256 \
  --build-review /private/build-signed-review.json \
  --build-review-sha256 EXTERNAL_BUILD_REVIEW_SHA256 \
  --recovery-key-id RECOVERY_REVIEWER_ID \
  --recovery-public-key /private/recovery-public.pem \
  --recovery-public-der-sha256 EXTERNAL_RECOVERY_DER_SHA256 \
  --recovery-review /private/recovery-signed-review.json \
  --recovery-review-sha256 EXTERNAL_RECOVERY_REVIEW_SHA256
\`\`\`

**All external pins must be stored independently of the submitted evidence.** The tool verifies both Ed25519 signatures through the Stage-241 verifier, checks two different key IDs, public DER SHA-256 fingerprints, detached signature file SHA-256 values and paths, and rechecks the Stage-241 strict synthetic-only deployment intent. A correct \`inspect-pair\` exit zero means only **synthetic cryptographic and static policy consistency**.

### Strict nonexecuting candidate specification

\`--candidate-spec\` must be exact canonical JSON, signed by neither deploy controller nor registry, with schema \`nexus.stage-d.synthetic-nonexecuting-launch.v1\`. It contains only an unpublished local image ID, the guarded Python ENTRYPOINT, no command override, a non-root \`10001:10001\` user, read-only rootfs, no Docker capabilities/privilege escalation, no host PID or network access, \`network=none\`, two synthetic mounts (fresh disposable \`/data\` and independently pinned read-only policy), and \`deployment_approved=false\`. Unknown fields and any production service selection, real data, live mounts, network exposure, alternative entrypoint or privileged startup are rejected.

**This file is a proposal, not a captured Docker/OCI runtime state or installed Railway admission controller.** A privileged Docker daemon or deployment platform can still ignore or override it. The CLI provides no deployment action.

The \`admission-gate\` command always exits **nonzero** even when both signatures and static launch description are valid. Successful inspection reports all of these as false: \`different_human_reviewers_proven\`, \`different_physical_custody_proven\`, \`freshness_or_anti_replay_registry_proven\`, \`published_registry_image_digest_verified\`, \`build_provenance_independently_attested\`, \`real_orchestrator_admission_policy_installed\`, \`real_offhost_restore_proven\`, and \`production_release_authorized\`. The final \`release_gate\` remains \`BLOCKED\`.

### Threats and self-criticism

- Two keys prove **different signing key material**, not that two independent humans reviewed anything. A single operator or compromised CI runner can generate both. A true two-person rule needs independently provisioned key custody, verified identities, separation of permissions, an audit trail and anti-replay freshness.
- The old Railway recovery image has already been observed to ignore newer request markers and recovery quarantine; signing a synthetic review cannot repair that old binary.
- A local Docker image ID is not a published image digest and is not an independent build attestation. Stage 242 never treats it as one.
- A nonexecuting launch policy is not enforceable until the actual orchestrator admission surface is configured and independently checked. No deployment, no provider permission changes, no live volume access, no real signing keys, no registry push, no offsite destructive restore and no main merge are performed here.

## Two signatures over the *actual* synthetic Docker build

The separate \`NEXUS Stage D Guarded OCI Image — Synthetic Only\` workflow now also invokes \`scripts/stage-d-ci-dual-review-demo.py\` **after the actual guarded Docker build, real HTTP tests and Stage-240 manifest/SBOM capture**. It reuses the Stage-241 disposable CI review signature, generates a second independently *different* temporary Ed25519 key in a directory **outside the artifact upload**, signs the same exact manifest/SBOM and invokes the Stage-242 two-reviewer verifier on the two signed reviews.

It writes a synthetic-only nonexecuting candidate launch specification and Stage-241 intent, plus a local receipt proving the two keys verified, to the CI artifact. Only the public keys, signed reviews, strict synthetic candidate/intent, and local hashes are uploaded; no private key is uploaded. The CI job self-generates all both keys and hash references. Thus **cryptographic distinctness is tested but human/host independence is NOT tested or claimed**. The runtime remains local/synthetic, the launch specification is not a captured/provider-enforced deployment and no image is pushed.

The dedicated CI workflow \`NEXUS Stage D Two Distinct Synthetic Reviewer Admission Denial\` generates two ephemeral keys and tests both true 2-of-2 cryptographic verification and hostile substitutions. Its green result means the **synthetic integration worked**, not that any release was approved or two real custodians existed. The tests are also part of \`scripts/readonly-verification.sh\`.

## Operational dependency before deployment

A future *separately approved* real deployment gate needs: independently custodied publisher/reviewer keys, published immutable \`repository@sha256:...\` image digest, externally verified signed SLSA provenance and complete SBOM, provider-supported enforcement preventing ENTRYPOINT/mount/capability overrides, operator-owned independent off-host backup/monotonic checkpoint and a destructive restore on a genuinely separate disposable host. Until then, real Stage D release and downgrade are blocked.
