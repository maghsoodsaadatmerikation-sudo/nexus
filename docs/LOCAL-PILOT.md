# Local pilot without a Rust or Docker installation

Status: DEVELOPMENT / UNSEALED. Linux x86_64 only.

The `NEXUS Local Pilot` workflow builds a static musl executable using the same
digest-pinned Rust image and locked dependencies as the repository. It uploads
an Actions artifact only after a real loopback HTTP witness succeeds. This is
a development executable, not a release, Seal, attestation or provider backup.
PR artifacts describe the exact checked-out verification commit, which can be
GitHub's synthetic merge commit; inspect `build.txt` and the run before use.

Download `nexus-local-pilot-linux-x86_64` from the intended successful workflow
run. Unzip it into a fresh directory, then:

```bash
sha256sum -c nexus-local-pilot-linux-x86_64.tar.gz.sha256
mkdir pilot
tar -xzf nexus-local-pilot-linux-x86_64.tar.gz -C pilot
cd pilot
python3 verify-local-pilot.py ./nexus
```

This witness creates only temporary synthetic data. It checks POST /v1/requests
returns 202 with a request_id, GET preserves pending, restart keeps the ledger,
duplicate submission returns 409, and offline restoration quarantines writes
with 503 across another restart. It never resumes a recovered data directory.
`pending` records acceptance, not completed execution. See `acceptance.json`
for the workflow result. Python 3 and an executable filesystem are required.

For a separate local workspace, choose a new private directory and token:

```bash
umask 077
mkdir nexus-data
export NEXUS_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export NEXUS_DATA_DIR="$PWD/nexus-data"
export NEXUS_BIND_ADDR=127.0.0.1:3000
./nexus
```

Keep the token private. Do not expose the listener publicly or interpret a fresh
empty workspace as recovery of an existing deployment. Use one process per data
directory on a local filesystem. This is not permanent hosting and does not keep
running after its host stops. No production credentials or data enter CI.

For existing data, stop all writers and follow `docs/full-data-recovery.md` in
the source repository. A Railway volume must still be exported independently;
this package contains no production data. A checksum establishes byte integrity,
not trust or authority. A_out <= A_in, evidence != authority, AuthorizedRequest,
CT-001..020 and Bootstrap versus Verify separation remain required; both
Cargo.lock files are unchanged. No new release authority is introduced.
