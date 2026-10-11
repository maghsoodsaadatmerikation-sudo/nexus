# NEXUS single-host pilot completion contract

Scope: one operator, one Rust gateway process, local persistent storage, existing
browser workspace, authenticated HTTP admission and independent offline backups.
This is a finite usable pilot, not completion of every possible NEXUS feature.
A_out <= A_in, evidence != authority and the AuthorizedRequest boundary remain
mandatory. CT-001..020 and pinned Cargo.lock files must stay verified. Bootstrap
prepares fixtures; only executed Verify evidence can establish PASS. A successful
attestation does not grant release intent, Seal or production-promotion authority.

## Acceptance gates

| Gate | Required evidence |
| --- | --- |
| Constitutional and transport boundaries | Exact-commit core self-audit, CT map, Gateway and authentication contracts |
| Installable single host | Both committed Compose paths resolve the repository Dockerfile, reject absent token, bind only loopback and mount writable /data |
| Usable epistemic flow | Real authenticated workspace creation, source-bearing evidence, alternatives and machine analysis; judgment remains null until an explicit human action |
| Request admission | POST returns 202 with ID; GET pending; replay returns 409 |
| Replacement continuity | Compose force-recreates the container and retains identical workspace snapshot and request marker |
| Recovery | Existing full-data backup/restore, write quarantine, explicit offline acknowledgment and restart witnesses |
| Storage failure | Missing-ledger repair and real bounded ENOSPC before delegation; conservative indeterminate recovery |
| Evidence | Canonical exact-commit Verify, self-audit, bundle and attestation; no secrets or private snapshots uploaded |
| Public promotion | Exact verified source pin, independent current backup, unchanged existing /data, rollback anchor, terminal provider SUCCESS and authenticated runtime acceptance |

`verify-single-host.py` executes the install/use/replacement gates with synthetic
fixtures in fresh `nexus-acceptance-<run-id>-<index>` Compose projects. It never
records a real human judgment. Its cleanup deletes only its newly created CI
project volumes and private temporary bind data. Never use its disposable data
as a production backup or run it on an occupied operator installation.

## Operator entrypoint

Check out the exact commit whose canonical Verify and attestation you reviewed.
Set a long random private NEXUS_API_TOKEN without storing it in repository files
or shell history, then run from the repository root:

```sh
docker compose -f deploy/stage-d-self-hosted.compose.yaml up -d --build
```

Open http://127.0.0.1:3000 and enter the token in the browser's in-memory field.
Create a workspace, add sources and uncertainty, compare alternatives, and record
your own judgment only when you choose. Download a workspace JSON export for
portability; use the full-data snapshot procedure for operational recovery.

Compose `down` preserves the named data volume. Do not use `down --volumes` on
operator data. Recovery requires all writers stopped; see full-data-recovery.md.
Container health inherits Dockerfile `/livez`; separately inspect `/readyz` for
recovery quarantine. Neither probe promises storage health or successful actions.
OCI is an optional existing-host recipe, not permission to provision paid compute.
Its explicit bind directory must remain durable and its HTTPS boundary is
operator/provider managed; local Compose tests do not prove public HTTPS.

## Completion limits

The repository's v2.5.0 Seal remains an immutable earlier transport boundary.
Later verified main commits must not be represented as that sealed binary.
Provider metadata alone does not prove authenticated runtime behavior. A current
full-volume backup and rollback anchor are required before promoting a newer
executable; never treat historical workspace JSON as a fresh full-data backup.

Distributed admission, external identity federation, hardware/power-loss proofs,
durable executor completion, automatic retry resolution and universal security
remain outside this single-host pilot. Pending means accepted, not completed.
