# Synthetic cross-runner disaster recovery

Status: **candidate / not a live backup / not an operational release**.

## Failure mode addressed

Existing Pilot 05 verifies a cold whole-volume restore between Docker
containers with different storage directories on **one GitHub runner**.
The two-runner transport witness separately transfers **fake ciphertext
bytes**, without running a Rust gateway on the receiving runner.
Neither alone shows that the actual offline workspace + request-ledger
archive can be transferred and recovered in a clean second CI job.

This new witness combines these boundaries while retaining the distinction
between synthetic CI and production recovery.

## Workflow

`.github/workflows/pilot-cross-runner-recovery.yml` performs two
GitHub-hosted jobs. Both check out the exact triggering SHA with no persisted
GitHub credentials and build the pinned Rust Docker image independently.

1. **Synthetic source:** start a disposable Rust gateway bound to localhost
   using an ephemeral synthetic bearer. Create one synthetic workspace,
   append a claim, submit one request, and confirm that human judgment was
   not created and the request is pending. **Stop the only gateway writer.**
   Use `data-snapshot.py backup --offline` to produce a complete synthetic
   workspace/request-ledger archive. Validate structure and produce a
   redacted, no-authority receipt with SHA-256 of archive and canonical
   workspace JSON. Upload exactly these two **synthetic** files with
   one-day retention. No token, real data, or production volume is uploaded.
2. **Synthetic recipient:** new GitHub runner with a fresh filesystem;
   download only the source job's immutable artifact ID and validate
   receipt shape, expected exact SHA and archive digest. Corrupt a disposable
   copy and verify that restore rejects it without publishing a directory.
   Restore the legitimate archive to a new local directory, using the
   runtime UID/GID; verify persistent recovery quarantine. Independently
   rebuild the gateway and start it against the restored directory.
   Verify authenticated byte-equivalent workspace JSON, preserved pending
   request, missing-bearer refusal, and 503 quarantine on writes.
   Stop all writers, explicitly acknowledge replay risk **only for synthetic
   data**, resume, restart and verify existing request replay is rejected
   and a new synthetic request can be accepted.

Each job fails without real GitHub Actions context, a disposable flag, a
matching checked-out commit, or in the presence of Render/Railway/NEXUS
operator credentials. All requests are to local loopback only; redirects
and proxies are disabled. No production Docker volume is mounted. The
produced report has booleans and synthetic commit SHA but no workspace
content, request ID, token or operator data.

## Scope and limits

- Two distinct ephemeral GitHub Actions **job runners**, not proof of
  different geographic hosts, independent cloud providers, user-owned
  devices, durable offsite custody, or separate administrative control.
- The transferred archive is unencrypted because its content is
  **synthetic only**. It must NEVER be used to transfer actual user data.
  Production private archives require encrypted out-of-band storage,
  independently held keys and an independently witnessed restore.
- No claim that the original Railway `/data` volume has been read, backed
  up, snapshotted consistently, restored or verified.
- A passing CI test does not authorize main merge, Render auto-deploy,
  production restore, a Seal or customer launch. Problems #154 and #168
  remain separate blockers.

## Verify

The workflow is triggered by this source, script and Docker/Rust changes.
It requires separate successful source and recipient jobs. Local pure
contract smoke test:

```bash
python3 scripts/pilot-cross-runner-recovery.py self-test
```

Full exercise requires GitHub-hosted disposable Linux runners with Docker
and uses only the synthetic data generated within the job. Existing
same-runner Pilot 05 and encrypted-escrow tests remain required separately.

`A_out <= A_in`; machine evidence does not create human release authority.
