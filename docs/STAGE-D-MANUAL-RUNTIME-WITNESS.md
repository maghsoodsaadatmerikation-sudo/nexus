# Stage D — manually consented single-GET public runtime identity witness

Status: **implemented as an explicit operator tool; no live HTTP run in this change**.

This closes the *instrumentation gap* after the
[2026-11-17 read-only Railway metadata review](STAGE-D-PROVIDER-DRIFT-2026-11-17.md),
but it does **not** close the authentic release, independent backup or real
restore gates. The original `/data` mount, credentials, staged Railway patch,
GitHub release-intent checks and service state remain unchanged.

## What it separates

1. **Reviewed source SHA** — the exact 40-hex commit an operator reports
   from Railway's current service deployment metadata. Checkout only as
   candidate DATA; no scripts from that checkout run.
2. **Expected source-tree SHA-256** — computed independently from selected
   files at that exact candidate SHA, using the same deterministic file set
   as `scripts/source-tree-digest.sh`. The observer recomputes the digest
   without executing any historical candidate code.
3. **Public endpoint metadata** — one `GET` to the exact fixed URL
   `https://nexus-stage-d-production.up.railway.app/v1/runtime-identity`,
   with TLS verification, HTTPS-only transport, 6-second connection timeout,
   12-second total timeout, 4096-byte maximum, no retries, redirects,
   bearer token, cookie, form or POST. Returned JSON is only accepted with
   the exact three keys `schema`, `source_tree_sha256`, `authority`.
4. **Stale provider snapshot** — the previously recorded
   `9abbc067aad3ebbb0956432cf6682d2ea70e2824` is compared with the
   operator's current declared commit, but cannot establish it is still
   deployed. GitHub main at execution may also differ.

A successful exact digest comparison produces
`HTTP_METADATA_MATCH_ONLY`, **not** independent binary identification,
`PASS` for an end-to-end system, authorization to publish, or proof of
volume durability. The Rust service itself labels this endpoint
`non_authoritative_build_metadata`: the public JSON value can be absent,
stale or forged by a misconfigured/compromised host. A digest match provides
one useful non-secret, bounded witness, not cryptographic remote attestation.

## How an authorized operator runs it (optional)

Open [Stage D — Explicit One-GET Public Runtime Witness](../.github/workflows/stage-d-manual-public-runtime.yml)
in GitHub Actions and choose **Run workflow** on reviewed `main` *only*.

1. First inspect Railway's **current** `nexus-stage-d` deployment metadata
   and independently note the exact 40-character lower-case source commit.
   Do not use a different project of the same name.
2. Enter that commit as `reported_railway_source_sha`. It is an
   operator-supplied declaration, **not authenticated by this workflow**.
3. If and only if you authorize an HTTP request that **can wake a sleeping
   Railway service and may incur hosting usage**, type the exact confirmation
   `I_ACCEPT_ONE_PUBLIC_HTTPS_GET_MAY_WAKE_SERVICE` as `probe_consent`.
   Otherwise do not dispatch the workflow. No claim is made that the
   GET is free of charge.
4. The workflow checks input syntax first, checks out reviewed observer
   code separately from candidate source data, makes exactly one bounded
   public GET and writes one sanitized report artifact with a seven-day
   retention. It deletes the raw response file; it never uploads that body.
   A red job means the observation was missing/invalid/drifted, not that a
   production rollback is authorized.

Do not copy bearer tokens, user data, original volume contents or secrets
into workflow inputs. This is **not** an authenticated workspace probe.
The operation is explicitly opt-in because an apparently read-only GET may
wake a dormant service; GH Actions may also consume runner minutes. Without
consent, only local synthetic tests should run.

## Synthetic-only tests and acceptance boundary

```sh
python3 scripts/test_stage_d_manual_runtime_witness.py
```

The pull-request [safety CI](../.github/workflows/stage-d-manual-runtime-tests.yml)
tests the SHA-256 algorithm against the repository's native source-tree
digest, malicious candidate scripts not executing, symlink denial, corrupted
JSON, duplicate keys, invalid responses, 302/503 and transport failures,
truncated or oversized output, and permanent no-release flags. It **never**
requests the public Railway service.

All outcomes contain `production_release_authorized=false`,
`seal_granted=false`, `independent_runtime_execution_verified=false` and
`private_storage_or_restore_verified=false`. Even a matching response is
limited to public build metadata from the observed endpoint.

**Self-critique:** A correct identity JSON does not cryptographically bind
the service process to a GitHub commit; a compromised server may lie. The
2026-11-17 provider snapshot is dated. An operator could type the wrong SHA.
A source-tree digest excludes unlisted files and dynamic runtime configuration.
Source matching does not prove safe storage, migration, authenticated access,
cold restore, 24/7 availability, a free wake, or real Android acceptance.
Keep the separate release and recovery issues open. `A_out <= A_in`.
