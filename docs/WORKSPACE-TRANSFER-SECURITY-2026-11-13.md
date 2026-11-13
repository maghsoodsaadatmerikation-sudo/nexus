# Single-workspace transfer hardening — 13 November 2026

Status: **source-only engineering candidate**; not merged or deployed. These
commands are for an operator-held authenticated NEXUS endpoint and do not
replace the separate offline full-volume recovery/backup contract.

## Verified legacy weaknesses

The previous `workspace-backup.sh` used a predictable `<output>.tmp`
path and redirected the authenticated API response into it, then moved it
onto the requested final path. It did not privately constrain file mode
or reject existing output/symlink targets. The previous backup and restore
shell commands expanded the bearer token directly into curl's argv,
making the credential visible in process listings on affected hosts.

## Changes

- `workspace-backup.sh` now delegates to a standard-library Python exporter.
  Its credential stays in its in-process HTTP request headers, not an
  executable command argument, and is not printed.
- The exporter insists on an exact HTTPS origin, except explicit loopback
  HTTP for local testing, with no ambient proxy or HTTP redirects.
- It streams at most **64 MiB** into a randomly named private `0600`
  temporary file opened with `O_EXCL` in a pinned output directory. It
  checks the JSON schema shape and exact requested `workspace.id`, rejects
  duplicate JSON keys, and calls `fsync` before publication.
- An atomic hard link publishes to a new filename only; existing files,
  symlinks and names concurrently created during transfer are never
  overwritten. A second run must choose a **new output filename**.
- `workspace-restore.sh` now delegates to `workspace-restore.py`.
  It reads from a pinned file descriptor, rejects symlinks, hardlinks,
  duplicate keys and invalid schema shape, and enforces the **64 MiB** size
  limit. The exact validated bytes, not a second read of a mutable path,
  are POSTed in one in-process HTTP request with no redirect or proxy.
  A remote target must use HTTPS; only HTTP **201** is accepted.
- The existing offline recovery and constitutional authorization
  boundaries remain unchanged. A snapshot import still goes through
  the gateway's existing core revalidation.

## Verification

```sh
python3 scripts/test-workspace-backup.py
python3 scripts/test-workspace-restore.py
```

The 22 synthetic tests cover concurrent final-name creation,
symlinks, hardlinks, duplicate keys, malformed responses, output mode,
byte caps, unexpected statuses, HTTPS-origin hygiene, optimized Python
and two real loopback HTTP test servers. All tests use synthetic tokens
and disposable local files; no actual service is queried and no production
data is modified. These tests run within the read-only PR CI harness.

## Operator use

Keep the token outside shell history and repository files (for example,
enter it interactively using a private shell prompt and `export`).
Set `NEXUS_BASE_URL`, `NEXUS_API_TOKEN` and
`NEXUS_WORKSPACE_ID` and run:

```sh
bash scripts/workspace-backup.sh /private/backup/workspace-20261113.json
bash scripts/workspace-restore.sh /private/backup/workspace-20261113.json
```

The output parent must already exist. The output file must not exist.
Avoid broad shared folders and retain exports in separate **encrypted**
operator-controlled storage: `0600` protects local DAC access only, not
disk compromise, removable media loss, backups, snapshots or privileged
host observers. The import command can mutate the target NEXUS instance
and should **never** be run against production without a separately
reviewed restore plan. Tests invoke only disposable loopback servers.

## Residual limits / fail-closed behavior

- A one-workspace JSON export **does not** capture the request ledger,
  other workspaces, recovery marker, provider metadata or a consistent
  full-volume point-in-time snapshot. It is not proof of Stage D recovery.
- A running gateway may change that workspace while the GET is handled;
  this utility cannot stop writers or independently prove cross-store
  transaction consistency.
- Source-code changes do not reconfigure a live Render/Railway service.
- The import process holds up to 64 MiB in memory so the bytes validated
  are exactly the bytes sent; constrained mobile hosts may need a smaller
  private snapshot. A hostile actor with permission to rewrite the source
  directory or its ancestors still lies outside this local operator model.
  The gateway's snapshot validation, not the CLI file shape, remains the
  content-integrity and authorization boundary.
- Credentials remain in the running process memory and environment.
  No tool can guarantee confidentiality from the same OS account, root
  users, a compromised gateway, malware, crash dumps or hostile shell
  instrumentation.
- A filesystem without reliable hard links or directory/file `fsync`
  support fails the exporter closed. The Linux CI smoke does not establish
  equivalent Android/mobile filesystem behavior.
- Backup and restore are still separate operator commands. The
  production full-volume, off-provider encrypted recovery witness tracked
  in issue #154 remains outstanding. No release/Seal authority is granted.
