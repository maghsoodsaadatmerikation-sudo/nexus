# Offline operator trust registry and monotonic witness ledger

This stage builds **local operator-side public-key trust** on top of the detached
Ed25519 witness in [DETACHED-WORKSPACE-ATTESTATION.md](DETACHED-WORKSPACE-ATTESTATION.md).

It is **not** a NEXUS runtime authorization, a production trust anchor, or a
signed machine-history import feature. The HTTP gateway continues to reject
machine-history uploads. No private signing key enters the trust registry.

## Operator workflow

Requires Python 3, OpenSSL with Ed25519 support and a POSIX local filesystem
supporting flock, atomic rename and fsync. Choose a protected local directory
which you own and do not synchronize to an untrusted service.

```sh
python3 scripts/workspace-trust.py init \
  --state-dir /private/nexus-operator-trust

# Validate public-key fingerprints and custody *out of band*.
python3 scripts/workspace-trust.py enroll \
  --state-dir /private/nexus-operator-trust \
  --key-id issuer-2026-a \
  --public-key /private/approved-issuer.pub.pem

python3 scripts/workspace-trust.py status \
  --state-dir /private/nexus-operator-trust

# inspect is read-only, and DOES NOT prevent a replay.
python3 scripts/workspace-trust.py inspect \
  --state-dir /private/nexus-operator-trust \
  --snapshot /private/export.json \
  --attestation /private/export.attestation.json \
  --workspace-id original-workspace-id

# record verifies a signature and consumes the revision once.
# It records only an *offline witness*, NOT an imported Workspace.
python3 scripts/workspace-trust.py record \
  --state-dir /private/nexus-operator-trust \
  --snapshot /private/export.json \
  --attestation /private/export.attestation.json \
  --workspace-id original-workspace-id

# Rotation requires a DISTINCT new Ed25519 public key.
python3 scripts/workspace-trust.py rotate \
  --state-dir /private/nexus-operator-trust \
  --old-key-id issuer-2026-a \
  --new-key-id issuer-2027-b \
  --new-public-key /private/approved-next-issuer.pub.pem

# Revocation prevents fresh offline approvals.
python3 scripts/workspace-trust.py revoke \
  --state-dir /private/nexus-operator-trust \
  --key-id issuer-2027-b
```

**Manual enrollment is a security-critical operator action.** The program
checks that a public key is a canonical Ed25519 SubjectPublicKeyInfo and pins
its SHA-256 fingerprint. A new key ID cannot overwrite an existing ID;
duplicate keys under aliases are rejected. The only supported role is
`offline_witness`. An attacker cannot declare a `runtime_import` or privileged
role in the registry.

## State and replay properties

A single versioned `trust-state.json` file holds the pinned public keys,
active/revoked state and one monotonic event-history checkpoint per workspace.
Every command obtains a POSIX exclusive lock on the *directory descriptor*,
checks operator ownership and private permissions and strict JSON structure,
and changes the whole state in one fsynced atomic rename. The registry
cannot self-initialize after deletion/corruption. Symlinks, hardlinked
registry files, wrong ownership and nonprivate mode fail closed.
The state file and directory use modes 0600 and 0700 respectively.

A successfully signed snapshot can be **recorded once**. A future witness for
the same workspace must add at least one event, have contiguous integer
sequence numbers starting from zero, and preserve the canonical JSON digest
of the previously recorded event prefix. This rejects replay, lower revisions
and event-history rewriting. Multiple processes serialized by the directory
lock cannot both record the same revision. Witness recording is atomic
*inside this operator state file*, not across the HTTP gateway.

A revoked key stops verification of **new** records even if its old
signatures were valid at signing time. Earlier recorded event checkpoints
survive rotation. Revocation is permanent; use a new key ID and new key pair.

## Explicit remaining security limitations

- This is a **local, cooperative, operator-owned trust anchor**. A hostile
  process with operator-account privileges or the ability to replace,
  restore or delete the entire trust directory can roll back its state.
  Production requires an independently anchored monotonic witness.
- The ledger preserves the **event prefix**, not full semantic workspace
  validity. A future signed snapshot can rewrite claim content while
  extending events and must still undergo strict Rust semantic checks.
- A signature does not establish that a machine adapter really executed,
  when it executed, or whether its sources are true.
- `inspect` is read-only; only `record` advances anti-replay state.
  Neither operation grants machine-history HTTP import authority.
- Bounded limits: 16 MiB snapshot, 8 KiB attestation, 2 MiB trust file,
  64 immutable keys and 2,048 checkpointed workspaces.
- Key changes are single-operator actions, not authenticated multi-admin
  approvals. Backup, OS security, key custody and recovery remain separate.
- Directory locking is POSIX-only; don't assume it works across arbitrary
  multi-host shared filesystem deployments.

## Tests

`python3 scripts/test-workspace-trust.py` generates real disposable Ed25519
keys; tests enrollment, key substitution, revocation, atomic rotation,
append-only event history, replay, rollback, forks, and a two-process race
for the same revision. It also rejects registry corruption, symlink/hardlink
replacement, privilege escalation, weakened permissions and implicit
re-initialization. CI uses synthetic data only; no production actions.
