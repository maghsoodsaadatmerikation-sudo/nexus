# Stage D — signed *synthetic* OCI evidence and deny-only deployment admission

## Security boundary

Stage 240 produces a **local-image-ID-only** build manifest and partial CycloneDX 1.5 SBOM, with pinned Python/Rust OCI base manifests, exact reviewed guard script hashes and the historical gateway Git revision. The stage-240 manifest explicitly states that no published registry image digest or builder signature was verified. A verified SHA-256 of that manifest prevents accidental corruption, but **does not identify who approved it**.

Stage 241 adds \`scripts/stage-d-signed-oci-admission.py\` with \`sign-synthetic\`, \`verify\`, \`inspect-intent\` and \`admission-gate\` commands. The signed object binds *exactly* the approved Stage-240 manifest digest, SBOM digest, reviewed PR commit, local image ID and reviewer key ID. The Ed25519 preimage uses a fixed NEXUS-specific domain, an unambiguous length prefix and canonical JSON encoding to prevent signature use in another NEXUS protocol.

A reviewer must separately retain and trust (a) the **exact SHA-256 of the Ed25519 public key DER** (not a self-declared name) and (b) the exact SHA-256 of the signed review file. Both are supplied at verification time. The signed review is immutable on write: \`O_EXCL\`, owner-only mode and fsync. The private signing key must be provided outside the repository as an owner-only file. **Never put the signing private key in GitHub repository files, CI secrets, a container layer or a downloadable artifact.**

### What a successful verification means

A successful \`verify\` proves that the exact signed preimage was signed by the holder of the externally pinned Ed25519 private key, and that its approved *synthetic* manifest and SBOM bytes match the claimed digests. It does not prove:
- the reviewer is a genuinely independent person or key custodian;
- the GitHub CI runner is trustworthy, or its output was built from the asserted source;
- the image is reproducible, or that the local image ID identifies a published registry image;
- the already deployed Stage D container starts with the guard, can read real data safely, or has passed two-host recovery;
- the signature was made recently or is unique (there is no independent anti-replay ledger yet).

The reviewed document therefore *must* say \`scope=synthetic-offline-review-only\`, \`published_registry_digest=null\`, \`independent_builder_provenance_verified=false\` and \`production_release_authorized=false\`. A cryptographically valid signature **cannot change those fields or imply deployment approval**.

## Review signing and verification

Collect a Stage-240 \`manifest.json\` and \`sbom.cdx.json\`, retain their separately observed SHA-256 digests, and choose the exact reviewed PR SHA and local Docker image ID. An approved offline reviewer with a privately kept Ed25519 key can run:

\`\`\`sh
python3 scripts/stage-d-signed-oci-admission.py sign-synthetic \
  --manifest /private/review/manifest.json \
  --sbom /private/review/sbom.cdx.json \
  --reviewed-commit REVIEWED_FULL_PR_SHA \
  --expected-manifest-sha256 INDEPENDENT_MANIFEST_SHA256 \
  --expected-sbom-sha256 INDEPENDENT_SBOM_SHA256 \
  --local-image-id sha256:LOCAL_DOCKER_IMAGE_ID \
  --reviewer-key-id APPROVED_SYNTHETIC_REVIEWER_ID \
  --public-key /private/reviewer.pub.pem \
  --public-key-der-sha256 EXTERNALLY_PINNED_PUBLIC_DER_SHA256 \
  --private-key /private/reviewer.private.pem \
  --signed-review /private/review/signed-review.json
\`\`\`

The output records the exact signed review digest. Verification uses the **same** evidence and reviewer public key arguments, replacing the private key with \`--expected-signed-sha256 EXTERNALLY_RETAINED_SIGNED_REVIEW_SHA256\`:

\`\`\`sh
python3 scripts/stage-d-signed-oci-admission.py verify \
  --manifest /private/review/manifest.json \
  --sbom /private/review/sbom.cdx.json \
  --reviewed-commit REVIEWED_FULL_PR_SHA \
  --expected-manifest-sha256 INDEPENDENT_MANIFEST_SHA256 \
  --expected-sbom-sha256 INDEPENDENT_SBOM_SHA256 \
  --local-image-id sha256:LOCAL_DOCKER_IMAGE_ID \
  --reviewer-key-id APPROVED_SYNTHETIC_REVIEWER_ID \
  --public-key /private/reviewer.pub.pem \
  --public-key-der-sha256 EXTERNALLY_PINNED_PUBLIC_DER_SHA256 \
  --signed-review /private/review/signed-review.json \
  --expected-signed-sha256 EXTERNALLY_RETAINED_SIGNED_REVIEW_SHA256
\`\`\`

All pins must come from an independently retained approved record; automatically calculating them from potentially malicious files at verification time establishes **no external trust**.

## Deployment intent — structurally checked, never authorized

\`inspect-intent\` additionally requires \`--deployment-intent /private/review/synthetic-intent.json\` and \`--expected-intent-sha256 INDEPENDENT_INTENT_SHA256\`. The intent is strict canonical JSON containing **exactly**:

\`\`\`json
{
  "schema": "nexus.stage-d.synthetic-oci-deployment-policy.v1",
  "scope": "synthetic-only",
  "reviewed_pr_commit": "REVIEWED_FULL_PR_SHA",
  "evidence_manifest_sha256": "INDEPENDENT_MANIFEST_SHA256",
  "local_image_id": "sha256:LOCAL_DOCKER_IMAGE_ID",
  "requested_registry_digest": null,
  "network_policy": "isolated-loopback-only",
  "data_policy": "new-disposable-synthetic-volume",
  "container_user": "10001:10001",
  "expected_entrypoint": [
    "/usr/local/bin/python3",
    "-I",
    "-B",
    "/opt/nexus/stage-d-guarded-image-entrypoint.py"
  ],
  "entrypoint_override_allowed": false,
  "privileged_allowed": false,
  "privilege_escalation_allowed": false,
  "host_paths_allowed": false,
  "production_credentials_allowed": false,
  "live_provider_allowed": false,
  "deployment_authorized": false
}
\`\`\`

This strict review rejects attempts to allow image/entrypoint substitutions, production networking, privileged containers, changing a real data volume, reading live provider secrets or granting release authority, **even when the malicious intent is given a correct SHA-256 pin**. The \`inspect-intent\` exit code 0 means *only that a proposed synthetic policy is internally coherent with the cryptographically signed review*. The \`admission-gate\` command **always exits nonzero**, with \`release_gate=BLOCKED\`, even for a structurally perfect, validly signed policy. It is **not connected to an orchestrator admission controller** and cannot prevent a privileged deployment operator from ignoring the script.

## Tests and operational next step

\`scripts/test-stage-d-signed-oci-admission.py\` generates *disposable* Ed25519 keys on a private CI runner and exercises valid signing/verification, wrong key pin, unsigned data tampering, forged signature, unknown release flags, invalid SBOM and public key substitution, unapproved container/volume/entrypoint privileges, duplicate JSON, symlinks, and immutable signed output. The real CI runner has **no long-lived trusted signing key**, so a passing test is only a cryptographic integration test. No private key is committed or published.

### Actual guarded Docker image review in CI

The Stage-240 **real, synthetic guarded Docker build workflow** now also generates a fresh Ed25519 demo-reviewer key **inside that single ephemeral CI job**, signs the exact build's \`manifest.json\` and \`sbom.cdx.json\` and verifies the detached review using that generated public key. It uploads \`ci-demo-signed-review.json\`, \`ci-demo-public-ed25519.pem\` and \`ci-demo-public-der-sha256.txt\` along with the Stage-240 evidence; the private key is stored separately under the temporary build directory and deleted on job cleanup. The artifact's local checksums cover these added review files.

Because the *same CI job generates the key, the evidence and its verification pin*, this process proves **end-to-end cryptographic integration only**, not a signature from an independent release reviewer, independent custody, a trusted build service or authorization to deploy. A real operator review requires a separately held signing key, independently captured public key fingerprint, and a separately retained exact review file digest.

This stage does **not** create a signed image registry artifact or SLSA builder attestation. The next separately approved operational dependency is a published image \`registry/repository@sha256:...\` with independently verified registry provenance, *two distinct key custodians*, an admission policy enforced by the actual orchestrator, and a destructive isolated off-host restore test on a disposable approved volume. None of those are authorized by this PR.

Existing Railway/Render instances and persistent volumes are not awakened, redeployed, touched or converted; the existing Draft PR stack remains unmerged, and production rollout is always blocked.
