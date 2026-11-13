# Structural integrity repair — 13 November 2026

Reviewed baseline: `1b9f1dbc4544cfc608229cb7a8464e60f08aaf40`.
Scope: Rust workspace snapshots and repositories, their gateway integration,
and the Python cloud transport. This is a source repair, not a deployed release.

## Findings and repairs

| Finding | Failure before repair | Repair |
| --- | --- | --- |
| Divergent validation | Memory/import accepted missing provenance and repeated creation events that disk rejected | One shared snapshot validator, mapped to the existing durable error API |
| Mutable recorded history | A saved claim or alternative could change while event IDs remained identical; memory also accepted rollback | Both repositories require identical historical events and existing claim/alternative content prefixes; workspace metadata without update events is immutable across saves |
| Ambiguous identities | Repeated claim/alternative IDs were accepted; a disk file could contain another workspace ID | Reject empty/duplicate record IDs and a loaded ID that differs from the requested ID |
| Machine provenance laundering | A `MachineAnalysisRecorded` claim could be relabeled as human on import | Require machine origin and nonempty adapter/run IDs for these events; ordinary `ClaimAdded` continues supporting its existing origin types |
| Concurrent disk replacement | Two repository instances could validate against the same revision and overwrite through a shared temporary filename | Kernel advisory lock covers read/validate/replace, exclusive temporary files, cleanup on error, private temporary-file permissions on Unix, directory sync after rename on Unix |
| Unbounded snapshot loading | Arbitrarily large files were read fully before parsing | 16 MiB disk snapshot limit on loading and saving; reading stops after the limit plus one byte |
| Unbounded opaque cloud transport | Requests/responses were fully buffered without application limits | Stream and cap requests at 1 MiB and responses at 4 MiB; reject oversized declarations early; 30-second body deadlines; close upstream streams on errors; cap HTTPX connections |
| Transport semantic drift | Duplicate query values collapsed; decoded path delimiters could become query/fragment syntax | Preserve query multi-items; quote decoded paths; reject dot segments; preserve request content encoding and upstream authentication/retry headers |
| Unexpected decompression | Compressed upstream bodies could expand before a size check | Request identity encoding and reject encoded responses before decompression |

Successful delegated responses use `Cache-Control: no-store`. Redirects are not
followed, and upstream `Location` is not forwarded. Lifespan cleanup now closes
the HTTP client on exceptional shutdown as well as ordinary shutdown.

## Verification

Local environment: Rust 1.85.0, Python 3.13, locked dependencies, Linux.

| Check | Result |
| --- | --- |
| Three independent Rust reproductions against the original baseline | 3 failed: changed stored claims accepted by memory/disk; missing provenance accepted on import |
| Initial 12 cloud regression cases against the original baseline | 11 failed, 1 passed |
| `bash scripts/run_gates.sh` with the pinned toolchain | PASS: format, locked build/check, test compilation, dependency metadata, full tests, type boundary |
| Core test suite | 104 passed, including 11 new integrity tests |
| `cargo test --locked` in `artifact-05` | 54 passed, 1 pre-existing ignored ENOSPC test |
| `uv run --locked pytest -q` in `nexus-cloud` | 30 passed, including 15 new cases |
| Concurrent independent repository instances | Exactly one of 8 competing divergent writes succeeded; 7 were rejected; resulting snapshot was readable and no temporary file remained |

The existing compile-failure fixture was refreshed for Rust 1.85 diagnostic
wording: it still requires E0603, rejecting construction through the private
authorization module. Pre-existing Rust formatting was normalized in a separate
local commit so the existing formatting gate could pass. Dependency locks for
both the core and gateway include the new `fs2` OS-lock dependency.

## Compatibility and remaining boundaries

- Snapshot schema remains version 1. Valid append-only saves and unchanged
  repeated saves work. Previously accepted invalid histories now fail closed;
  no automatic history repair or relabeling is performed.
- Changing previously saved question/goal/values/constraints requires a future
  explicit audited update design, or creation of a separate workspace. The
  current schema has no event that can authenticate those edits.
- Advisory locking coordinates cooperating processes on a filesystem supporting
  OS locks. It is not distributed consensus or protection from a process that
  bypasses this repository. Keep the repository directory operator-controlled.
- These snapshots are not cryptographically signed. An actor able to rewrite
  the entire storage tree remains outside this repair's integrity guarantee.
- Directory-sync failure after rename can return an error after bytes became
  visible. Retry the same snapshot or reload before making another decision.
  Power-loss durability, actual ENOSPC, Windows replacement semantics, physical
  Android behavior and multi-host shared storage were not tested here.
- The cloud limits are per request; they are not a complete ingress admission
  or denial-of-service protection system. Compressed core responses now fail
  with 502; ordinary identity responses retain their bytes and status.
- Pytest reports one existing Starlette/httpx deprecation warning.

## Android artifact lineage checked

The retrieved Stage 27 APK contains `assets/nexus/index.html` with SHA-256
`e70cae8bdec3a40507056ed5c37ceaf9c948bc8e9ba8334964d275a526f83914`,
matching its current evidence JSON. The recovered Stage 24 HTML hash differs:
`cf1940cee5cbf3f3ecdfd7248f2e02271d08106269a154f7f7df3266433d5287`.
They are separate artifacts and cannot be treated as the same source revision.

The Stage 27 evidence explicitly records no actual Android hardware/emulator
test, no native Internet permission and an ephemeral test signing certificate;
its schema still carries the Stage 25 name. These are outstanding mobile
release/lineage issues. This repair does not rebuild or replace that APK, change
its evidence, deploy a service, satisfy Stage D or establish independent
production attestation.
