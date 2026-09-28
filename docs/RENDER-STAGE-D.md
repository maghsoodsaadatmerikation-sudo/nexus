# Render Stage D Durable-Host Runbook

This runbook is a provider-specific execution profile for `docs/STAGE-D-EVIDENCE.md`. It is operational evidence only; it does not expand NEXUS epistemic authority and does not by itself authorize a release.

## Provisioned shape

The repository root `render.yaml` defines a single paid Docker web service in Frankfurt with:

- one service instance,
- a 1 GB persistent disk mounted at `/data`,
- `NEXUS_DATA_DIR=/data`,
- `NEXUS_BIND_ADDR=0.0.0.0:3000`,
- public HTTPS managed by Render,
- repository deploys gated on passing GitHub checks,
- `NEXUS_API_TOKEN` supplied interactively as a secret (`sync: false`).

The service intentionally remains single-instance because the NEXUS workspace store is local durable state. Do not add horizontal scaling while this persistence model is in use.

## 1. Create the durable service

1. In Render, create a new Blueprint from this repository after `render.yaml` is merged to `main`.
2. Keep the Blueprint pointed at `main`.
3. When Render asks for `NEXUS_API_TOKEN`, provide a long operator-held random secret. Never commit it.
4. Confirm the service is using the paid `0.5c-512mb` plan and that the `nexus-data` disk is mounted at `/data`.
5. Wait for the deploy to become live and record the exact Git commit shown by the Render deploy in an independent operator note.
6. Confirm that the same 40-character commit has a successful `NEXUS Verification` run in GitHub Actions.

Do not start Stage D against a free/ephemeral service or against a deploy whose exact commit cannot be identified.

## 2. Prove HTTPS/auth boundary and create a witness

Set the public HTTPS endpoint and operator token on the operator machine:

```bash
export NEXUS_BASE_URL='https://<render-service>.onrender.com'
export NEXUS_API_TOKEN='<operator-held-secret>'
```

Run the machine-checkable transport preflight:

```bash
bash scripts/stage-d-evidence.sh preflight ./stage-d-evidence
```

This must prove public liveness plus exact HTTP 401 rejection for both missing and intentionally wrong bearer credentials. Do not continue unless `result-preflight.txt` says `Status: PASS`.

Create an authenticated witness workspace using a unique ID:

```bash
export NEXUS_WORKSPACE_ID="stage-d-$(date -u +%Y%m%dT%H%M%SZ)"
curl -fsS -X POST "$NEXUS_BASE_URL/v1/workspaces" \
  -H 'content-type: application/json' \
  -H "authorization: Bearer $NEXUS_API_TOKEN" \
  --data "{\"workspace_id\":\"$NEXUS_WORKSPACE_ID\",\"question\":\"Stage D durable persistence witness\",\"provenance_id\":\"stage-d:render\"}" \
  >/dev/null
```

## 3. Capture before replacement

Keep the evidence directory outside Render and outside the repository working tree used by the running service.

```bash
export NEXUS_DEPLOYED_COMMIT='<exact-40-character-render-deploy-commit>'
bash scripts/stage-d-evidence.sh capture ./stage-d-evidence
```

Do not continue unless `result-capture.txt` says `Status: PASS`.

## 4. Prove real service replacement survival

Trigger a real Render redeploy of the exact same verified commit. Do not restore anything.

After the replacement deploy is live, obtain or define a sanitized identifier that can be correlated with the Render deploy history. Record it with the exact commit and UTC timestamp:

```bash
export NEXUS_REPLACEMENT_EVENT_ID='<render-deploy-id-or-sanitized-operator-id>'
export NEXUS_REPLACEMENT_AT_UTC='<YYYY-MM-DDTHH:MM:SSZ>'
export NEXUS_REPLACEMENT_COMMIT="$NEXUS_DEPLOYED_COMMIT"
bash scripts/stage-d-evidence.sh record-replacement ./stage-d-evidence
```

Then prove survival without restore:

```bash
bash scripts/stage-d-evidence.sh verify-survival ./stage-d-evidence
```

Do not continue unless `result-survival.txt` says `Status: PASS` and `after-survival.json` is JSON-equivalent to `before.json`.

The lifecycle marker is corroboration; it does not replace the observed survival fetch. A mere application-process restart does not count as this phase.

## 5. Prove destructive absence

This phase must be separate from the survival test.

1. Open a shell on the **running paid service instance** from the Render Dashboard or `render ssh`.
2. Verify `/data` is the mounted persistence path.
3. Remove only the isolated Stage D witness backing state from `/data`. Do not perform this destructive test on unrelated production data.
4. Return to the independent operator machine and record the destructive event while requiring the authenticated API to prove the witness is absent:

```bash
export NEXUS_DESTRUCTIVE_EVENT_ID='<sanitized-destructive-test-id>'
export NEXUS_DESTRUCTIVE_AT_UTC='<YYYY-MM-DDTHH:MM:SSZ>'
bash scripts/stage-d-evidence.sh verify-absence ./stage-d-evidence
```

PASS requires exactly HTTP 404 with `workspace_not_found`. The harness stores the sanitized absence response plus `destructive-event.txt` and `result-absence.txt`.

Do not count an ephemeral Render shell as destructive evidence: it does not represent the live service instance and does not prove modification of the live mounted disk.

## 6. Restore and prove recovery

Only after `verify-absence` has passed, restore from the independently held snapshot:

```bash
bash scripts/stage-d-evidence.sh restore-verify ./stage-d-evidence
```

Do not continue unless `result-restore.txt` says `Status: PASS` and `after-restore.json` is JSON-equivalent to `before.json`.

## 7. Final release gates

Run the readiness gate against the same exact deployed commit:

```bash
bash scripts/v1.1-release-readiness.sh \
  ./stage-d-evidence \
  "$NEXUS_DEPLOYED_COMMIT"
```

Then create the offline release-candidate evidence only if readiness passes:

```bash
bash scripts/v1.1-release-candidate.sh \
  ./stage-d-evidence \
  "$NEXUS_DEPLOYED_COMMIT" \
  '<successful-NEXUS-Verification-run-id>'
```

A PASS here still does not justify moving an existing tag. `v1.1.0` may be created only after the complete Stage D evidence pack, the provider lifecycle corroboration, and the successful GitHub verification run have been independently checked.

## Evidence hygiene

Never store `NEXUS_API_TOKEN`, Render API keys, authorization headers, SSH private keys, or secret environment values in the Stage D evidence directory. Lifecycle IDs must use only the restricted character set accepted by the harness and must not contain credential-like terminology. Provider screenshots or deploy-history exports can be retained separately as human corroboration, while the release gate remains bound to the exact repository commit and NEXUS-generated network/content evidence.
