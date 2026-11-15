# End-to-end offline witness drill audit and release-blocking boundary

## What is implemented

\`scripts/workspace-witness-drill-audit.py\` is a **read-only** verifier for the complete synthetic or externally transported NEXUS v1 → v2 witness recovery chain. It ties together:
- Independently pinned historical v1 ledger, last signed package and three-party v1→v2 key-transition consent;
- A verified v2 ledger bridge and its independently pinned last signed acknowledgment and monotonic minimum sequence;
- Two privately staged copies (origin and post-restore) with exactly matching canonical bytes and approved SHA-256;
- An independently pinned, fully cryptographically verified **cold backup** matching those copies;
- Two different Ed25519 observer keys and exact SHA-256-pinned signed origin/recovery reports;
- A private challenge registry at an independently pinned exact SHA-256 head, with a **single** prior issued and consumed event binding the challenge, both reports and the v2 signed tail.

The tool does not write files, issue or consume a challenge, change a key, deploy or contact a host. It uses the source repository's existing verifiers, rejecting any wrong historical entry, altered signed report, invalid backup, missing consume, stale registry pin, mismatched origin/recovery copy, unknown signer key or invalid sequence floor. All externally supplied pins must have been retained *independently*; trusting the hash of an untrusted retrieved file is not independent custody.

### Commands and outputs

Invoke \`verify\` with all required public evidence and the explicitly selected private stage directories:

\`\`\`sh
python3 scripts/workspace-witness-drill-audit.py verify \
  --old-ledger /trusted/old-v1-ledger.json \
  --old-ledger-sha256 PIN_OLD_LEDGER \
  --trusted-old-package /trusted/old-v1-package.json \
  --trusted-old-package-sha256 PIN_OLD_PACKAGE \
  --consent /trusted/three-party-consent.json \
  --consent-sha256 PIN_CONSENT \
  --receiver-id independent-recipient \
  --source-key-id source-signer \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-receiver \
  --outgoing-ack-public-key /trusted/old-receiver.pub.pem \
  --incoming-ack-key-id new-receiver \
  --incoming-ack-public-key /trusted/new-receiver.pub.pem \
  --trusted-latest-package /trusted/latest-signed-v2-package.json \
  --trusted-latest-package-sha256 PIN_V2_PACKAGE \
  --expected-bridge-sha256 PIN_V2_BRIDGE \
  --minimum-sequence 42 \
  --challenge-hex PIN_ISSUED_CHALLENGE \
  --approved-bridge /trusted/canonical-v2-bridge.json \
  --origin-report /trusted/signed-origin-observer.json \
  --origin-report-sha256 PIN_ORIGIN_REPORT \
  --origin-public-key /trusted/origin-observer.pub.pem \
  --origin-observer-id origin-observer-01 \
  --recovery-report /trusted/signed-recovery-observer.json \
  --recovery-report-sha256 PIN_RECOVERY_REPORT \
  --recovery-public-key /trusted/recovery-observer.pub.pem \
  --recovery-observer-id recovery-observer-02 \
  --registry /private-review/challenge-ledger \
  --registry-sha256 PIN_CONSUMED_REGISTRY_HEAD \
  --origin-store /private-origin/staging \
  --restored-store /private-restore/fresh-staging \
  --backup /trusted/cold-backup.json \
  --backup-sha256 PIN_COLD_BACKUP
\`\`\`

Replace every placeholder with an actual value retained outside the source under audit; the command requires private operator-controlled directories and verified Ed25519 public key PEM files.

On consistent evidence, \`verify\` returns a JSON report with \`status=offline-cryptographic-drill-consistent\`, \`release_gate=BLOCKED\`, \`physical_host_independence_proven=false\`, \`real_destructive_offhost_restore_proven=false\` and \`release_authorized=false\`. Its exit code is zero **only for internally consistent offline cryptographic evidence**.

\`release-gate\` accepts the same arguments, but **always returns a nonzero exit code and BLOCKED**. It cannot be accidentally used to approve deployment. This permanent block is deliberate while there is no separately verified real independent host and no reviewed production-compatible v2 receiver/key cutover.

Optional \`--stage-d-evidence /private/path --deployed-commit FULL_40_CHAR_SHA\` invokes the existing \`scripts/v1.1-release-readiness.sh\` gate read-only. If incomplete it reports \`BLOCKED_INCOMPLETE_OR_INVALID\`; if it passes it reports \`EVIDENCE_SCRIPT_VERIFIED_NOT_HOST_INDEPENDENCE\`. This supplemental Stage D check does **not** establish that two physical machines are different, nor elevate any NEXUS release authorization.

## Current Render observation (2026-11-15)

Read-only service inventory showed **one** NEXUS Docker web service on Render (\`nexus\`, free tier, one instance, Ohio) with \`autoDeploy=yes\` on \`main\`. Three further NEXUS entries are static sites (Studio, offline pilot and portable PWA preview), not independent v2 custodians.

A separate **Railway** project named \`NEXUS Stage D\` has preexisting \`nexus-stage-d\` (region \`sfo\`, mounted \`/data\` volume) and \`nexus-stage-d-restore\` (region \`us-west2\`, distinct mounted \`/data\` volume), as well as operator/runner services. The last reported deployments for both the main Stage D service and the recovery service were \`SLEEPING\` on inspection; the runner's last deployment was \`FAILED\`, and there was an unapplied staged change patch. The existence of different services, regions and volumes is a **deployment topology observation**, not proof of independent administration, durable live service availability, up-to-date committed data, successful restoration, or a verified v2 witness recipient. There is no permission in this stage to deploy or apply pending Railway configuration.

This is read-only metadata, **not** a credential, private server inspection, a guarantee of distinct failure domains, or a successful operational test. Do not assume a static site or an unverified sleeping Stage D restore service can act as an independent authoritative witness receiver.

## Remaining release blockers

- A separately administered second physical/virtual host and distinct failure domains, verified against real provider/operator evidence, not merely two Ed25519 keys or two local directories;
- Real externally retained encrypted backup, independently pinned current SHA-256/sequence and verified recovery after controlled destructive host loss;
- Real HTTPS/authenticated live service, provider replacement and absence observations according to Stage D;
- Versioned production v2 signer migration with exclusive durable activation, source controls, key revocation/compromise response, actual rollback testing and safety review;
- Explicit operator approval and production change management.

The test \`scripts/test-workspace-witness-v2-stager.py\` proves the integrated path with **ephemeral synthetic signing keys** and private same-runner fixtures; it is not a two-host recovery test. The included adversarial cases prove the proposed release gate cannot be made green by the synthetic drill or by fabricated/incomplete Stage D text.

No runtime credentials, real user records, server settings, autoDeploy configuration or production releases are changed.
