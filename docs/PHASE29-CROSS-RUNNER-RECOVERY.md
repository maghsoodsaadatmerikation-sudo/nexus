# Phase 29 — cross-runner synthetic offline receipt recovery

## A separate runner boundary

Phase 28 removed the source Docker volume and restored on a second volume
under the **same Docker host**. Phase 29 adds a stricter acceptance using two
separate GitHub Actions jobs and disposable runners connected only through the
GitHub artifact service. The receiver has no access to the exporter's private
temporary filesystem and checks out the producer's exact source commit SHA.

The producer creates **only fixed synthetic, non-sensitive values** and a
finished one-use approval record in a private 0700 operator root, then exports
an unencrypted offline snapshot. The archive is a test artifact — never upload
a real user's workspace, credentials, production backup or other private
information to this workflow.

The producer passes the archive SHA-256, workspace-manifest SHA-256 and commit
SHA through GitHub job outputs; the receiver obtains ZIP bytes through the
separate upload/download artifact service, pinned to this workflow's artifact
ID. This tests two distinct channels under **one GitHub administrator**,
not independently signed publisher identity, independent backup custody or
multi-provider resilience.

## Checks on the receiving runner

1. A wrong whole-archive SHA is denied before any restored files appear.
2. A wrong independently passed workspace SHA is denied before any writes.
3. A modified synthetic ZIP must be rejected even if the caller recalculates
   and supplies a matching **new** outer ZIP digest.
4. Restored workspace content, file hashes and consumed approval receipts
   must match the source report exactly.
5. The consumed approval cannot be used again; no job is restarted.
6. A second restore into an existing root is denied without overwriting files.
7. No Unix socket or operator transport token is restored.
8. Only fixed synthetic bytes are transferred; jobs receive read-only GitHub
   repository permissions. No model execution, user data, Docker socket,
   production release, external service or deployment is authorized.

The synthetic CI harness requires the literal approval switch
--approve-synthetic-ci; it never exports user workspaces and is not a general
production backup feature. GitHub artifacts expire after one day. The test
archive is **plaintext**: confidentiality is not provided by these checks.

## What it does NOT prove

Both runner machines are operated by GitHub and share the same code and
organization authority. The experiment does not prove storage survival after
loss of GitHub credentials, an independent organization's control, hardware
or power-loss recovery, encryption and key recovery, hostile same-UID
isolation, publisher authenticity or production service readiness.
Real operator backup files must NEVER be uploaded to this CI.

The existing local offline snapshot tool remains explicit and unencrypted.
Human review of independent durable storage, encrypted transport/storage,
key custody, host process audits and service restart is required before
production promotion. PR #244 remains Draft, unmerged and undeployed.
Preserve the authority rule A_out <= A_in.
