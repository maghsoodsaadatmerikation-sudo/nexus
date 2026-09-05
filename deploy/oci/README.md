# NEXUS v1.1 — Durable OCI deployment

This deployment target exists to close Stage D with real persistent-storage evidence. It does not modify the immutable `v1.0.0` seal.

## Required infrastructure

- OCI Always Free eligible compute in the tenancy home region.
- Persistent boot/block storage in the Always Free allowance.
- Ubuntu or Oracle Linux with Docker Engine and the Compose plugin.
- Public HTTPS terminated by an operator-managed reverse proxy or load balancer.
- TCP 3000 MUST NOT be exposed publicly; the compose contract binds it to loopback only.

Oracle documents Always Free compute and a combined 200 GB boot/block-volume allowance in the home region. Capacity and account eligibility remain external provider facts and must be checked when provisioning.

## Host layout

- repository: `/opt/nexus`
- durable workspace data: `/var/lib/nexus`
- operator backups: `/var/backups/nexus`
- Stage D evidence directory: operator-held storage independent of the host under test
- runtime token: supplied only as environment/secret material; never committed

## Deploy

```sh
sudo mkdir -p /opt/nexus /var/lib/nexus /var/backups/nexus
sudo chown -R "$USER":"$USER" /opt/nexus /var/lib/nexus /var/backups/nexus
git clone https://github.com/maghsoodsaadatmerikation-sudo/nexus.git /opt/nexus
cd /opt/nexus
export NEXUS_API_TOKEN='REPLACE_WITH_A_LONG_RANDOM_SECRET'
docker compose -f deploy/oci/docker-compose.yml up -d --build
```

Do not put the real bearer token in `.env`, shell history, repository files, screenshots, CI logs, or release evidence.

## Stage D evidence procedure

Use `scripts/stage-d-evidence.sh` as the authoritative harness. The evidence directory MUST be stored independently of the host under test.

Required sequence:

1. **Preflight** — prove HTTPS liveness and fail-closed bearer authentication.
   ```sh
   export NEXUS_BASE_URL='https://YOUR_PUBLIC_ORIGIN'
   export NEXUS_API_TOKEN='YOUR_OPERATOR_TOKEN'
   bash scripts/stage-d-evidence.sh preflight /path/to/external-evidence
   ```
2. Create an authenticated witness workspace on the durable host.
3. **Capture** — bind the witness snapshot to the exact deployed 40-character commit.
   ```sh
   export NEXUS_WORKSPACE_ID='YOUR_WITNESS_WORKSPACE_ID'
   export NEXUS_DEPLOYED_COMMIT='40_CHARACTER_DEPLOYED_COMMIT_SHA'
   bash scripts/stage-d-evidence.sh capture /path/to/external-evidence
   ```
4. Perform a real service/container replacement without deleting the persistent data volume.
5. **Record replacement** using a sanitized provider/operator event identifier and UTC timestamp, bound to the same deployed commit.
   ```sh
   export NEXUS_REPLACEMENT_EVENT_ID='provider-or-operator-event-id'
   export NEXUS_REPLACEMENT_AT_UTC='YYYY-MM-DDTHH:MM:SSZ'
   export NEXUS_REPLACEMENT_COMMIT="$NEXUS_DEPLOYED_COMMIT"
   bash scripts/stage-d-evidence.sh record-replacement /path/to/external-evidence
   ```
6. **Verify survival** — the post-replacement workspace must be JSON-equivalent to the captured snapshot.
   ```sh
   bash scripts/stage-d-evidence.sh verify-survival /path/to/external-evidence
   ```
7. Perform the destructive recovery exercise only after the external capture is safe: remove the witness backing state while preserving the evidence directory.
8. **Verify absence** — the authenticated witness lookup must return the expected `404` / `workspace_not_found`, proving destructive removal was actually observed.
   ```sh
   export NEXUS_DESTRUCTIVE_EVENT_ID='provider-or-operator-destructive-event-id'
   export NEXUS_DESTRUCTIVE_AT_UTC='YYYY-MM-DDTHH:MM:SSZ'
   bash scripts/stage-d-evidence.sh verify-absence /path/to/external-evidence
   ```
9. **Restore and verify** — restore the captured snapshot and require exact JSON equivalence.
   ```sh
   bash scripts/stage-d-evidence.sh restore-verify /path/to/external-evidence
   ```
10. Run the Stage E readiness gate and Stage F candidate generator against the completed Stage D evidence pack for the exact deployed commit and independently confirmed successful NEXUS Verification run.

Stage D is closed only when the harness records PASS for preflight, capture, survival, destructive absence, and restore, with the lifecycle evidence and exact commit/snapshot bindings intact.

## Constitutional boundary

Host health, persistence, TLS, authentication and recovery are operational claims only. They do not establish epistemic correctness and do not increase machine authority. `A_out <= A_in` remains unchanged.
