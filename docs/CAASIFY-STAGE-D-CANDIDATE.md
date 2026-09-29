# Caasify Stage D candidate — unverified

Status: **CANDIDATE ONLY**. This document is an operator plan, not deployment evidence or a Seal claim. The provider advertises Dockerfile builds, persistent volumes, generated HTTPS hostnames, encrypted secrets, and no card requirement for its time-limited offer. These are provider claims, not NEXUS observations. Source: https://caasify.com/container-hosting (checked 2026-09-29). The promotional zero-price period is advertised to end 2026-12-31; check the actual account terms before provisioning or leaving resources active.

## Provisioning checklist

1. In an account controlled by the operator, connect this repository and pin the exact 40-character commit to deploy. Do not rely on a moving `main` reference. Require an independently successful **NEXUS Verification** run for that commit.
2. Build the repository root `Dockerfile`. Configure one replica, container port `3000`, and a provider-managed public HTTPS hostname. Confirm from outside that port `3000` itself is not publicly reachable; do not assume the provider's default ingress is private.
3. Attach a provider persistent volume at `/data`. Configure `NEXUS_DATA_DIR=/data`; the Dockerfile already uses this default. Verify that a genuine service replacement reattaches the same volume. Disable multi-replica scaling for the single-writer file repository.
4. Set `NEXUS_API_TOKEN` as a private provider secret, never in the repository, command history, evidence pack, or public build logs. Generate it on the operator side. The container already binds `0.0.0.0:3000` behind the managed ingress.
5. Keep the independent evidence directory outside this service and volume. GitHub Codespaces can provide an operator terminal from a browser, but is not the durable host; its evidence files must be exported before its retention window ends.

## Run only after observing the real host

From a checkout of the **exact deployed commit**, use `docs/STAGE-D-EVIDENCE.md` and `scripts/stage-d-evidence.sh`. Set `NEXUS_BASE_URL` to the observed HTTPS hostname and `NEXUS_API_TOKEN` privately. Run `preflight`, then create/select a witness workspace and run `capture` with `NEXUS_DEPLOYED_COMMIT`.

Replace the actual service/container through the provider, preserving the mounted volume and **without restoring**. Record the provider replacement event and UTC time, then run `verify-survival`. For the separate destructive exercise, make the witness backing state absent while retaining the independent backup; run `verify-absence` to observe HTTP 404. Only then run `restore-verify`. Finish with `scripts/v1.1-release-readiness.sh` against the complete evidence pack and exact commit. Check the linked NEXUS Verification run independently.

If the provider cannot attach a persistent volume at `/data`, cannot expose HTTPS while keeping the application port private, cannot replace the service while retaining the volume, or cannot demonstrate destructive absence and restoration, **stop**. Record the failed contract item; do not reinterpret a health check, CI smoke, or provider marketing as Stage D PASS.

No resource has been provisioned or tested by this document. Stage D and any new Seal remain **PENDING** until the twelve criteria in `docs/STAGE-D-EVIDENCE.md` are satisfied by concrete evidence.
