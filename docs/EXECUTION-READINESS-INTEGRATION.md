# NEXUS execution-readiness: four-PR integrated candidate

Status: **source-only, draft, unsealed, no deployment authority**.

## Objective and inputs

Four independently tested changes are now assembled against base
`b7855b1a1bb9f3776e8f24b682d124cbe334543e`, without changing
`main`, a release tag, provider services, or private user data.

| Source | Original exact candidate | Preserved boundaries |
| --- | --- | --- |
| #187 | `92bc3879bd102d0e9c05bdbc4bad8203af572c4c` | bounded public liveness and readiness response validation |
| #188 | `851e68aec2416bd6a54ea3a0e734e0205347c685` | fail-closed review of observed Render/GitHub production freeze configuration |
| #189 | `e0660f330ee80f6ed12db44730cb594cc7bf5703` | synthetic offline full-data recovery between two independent GitHub Actions jobs |
| #190 | `ede84d8bd3c98429e389feca656cee892eeaf14f` | bounded no-proxy/no-redirect Stage D operator bearer transport |

The actual 16 source files and their original Git blob SHA-1 identities are
listed in `integration/execution-readiness-manifest.json`. This is an
auditable source-tree identity record, not a signature or provider attestation.

The single overlapping path, `.github/workflows/pr-verify.yml`, is
**manually reconciled**, retaining all of these primary required checks:

- `scripts/test-observe-pilot-runtime.py`
- `scripts/test-production-freeze-preflight.py`
- `scripts/test-stage-d-operator-transport.py`
- `scripts/verify-execution-readiness-assembly.py` and
  `scripts/test-execution-readiness-assembly.py`

All other candidate file contents must remain byte-for-byte identical to
their recorded originals. A later semantic edit must be a separately reviewed
candidate, not an unnoticed substitution of one source blob.

## Executable integrated acceptance

`scripts/verify-execution-readiness-assembly.py` checks all pinned blob
identities and the reconciled required CI checks. It blocks changed or
duplicated paths, mismatched PR commit bindings, missing or elevated workflow
permissions, and any assertion that source-only evidence authorizes release.
Its negative regression suite exercises deliberately mutated private copies.

`.github/workflows/execution-readiness-integration.yml` runs an
unprivileged source provenance proof and all three security suites in
one isolated job. The existing `readonly-verification` still executes
its full Rust/Docker/transport/durability suite with the same exact candidate.
The new `pilot-cross-runner-recovery.yml` separately checks the actual
synthetic cold archive transfer to a distinct GitHub runner with Rust re-build,
quarantine, ledger and replay checks. The standalone freeze and operator
workflows also run on changed source paths.

One successful CI run is evidence about the **checked commit only**, not
about a later merge commit, a moving source branch, or live production.

## Explicit hold and next release gates

1. The legacy live Render service can still auto-deploy `main`;
   provider-side manual-deploy/freeze settings must be independently
   changed and read back (#154).
2. GitHub ruleset 20870033 still needs strict up-to-date required status
   checks enabled by an authorized repository operator (#168).
3. An encrypted independent complete offsite backup of the actual
   Railway `/data` volume, with exact inventory and isolated restore
   witness, is **not established**. Synthetic cross-runner data never
   substitute for this proof.
4. A human operational release decision remains separate from
   passing source verification. Do not merge or deploy this draft until
   the above blockers are independently resolved.

`A_out <= A_in`: source evidence is not production or human release
authority. No new paid resource, production restart, destructive restore,
credential access or Seal is in scope.
