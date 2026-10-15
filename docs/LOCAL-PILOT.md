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

For an actual local workspace, start the bundled supervisor:

```bash
python3 run-local-pilot.py
```

It creates an owner-only state directory at `~/.local/share/nexus-local-pilot`,
with a persistent 256-bit random token in `api-token` (mode 0600), a separate
`data` directory and an advisory operator lock. It prints the loopback URL and
token file path, never the token. Read that file locally and enter the token in
the browser's in-memory API token field. Do not share the token or commit it.
Use Ctrl-C to stop; restarting the same command retains token and data.
`--state-dir /private/path` selects a different installation, `--port 3001`
selects another loopback port, and `--binary /path/to/nexus` selects an executable.
No option binds a public interface.

The launcher rejects insecure existing directories/files and token symlinks
without repairing or replacing them. A second cooperating launcher cannot use
the same state directory, even on a different port. The child inherits the lock
so forcibly killing its supervisor does not let another launcher admit a writer
while the old child is alive. Do not delete the lock file. If needed, stop the
gateway PID printed at startup before restarting; stale file existence alone
does not block a launch. A raw binary invocation or privileged filesystem actor
can bypass this advisory guard: one process per data directory remains required.

For recovered data, install it offline into an absent `STATE_DIR/data` following
the full-data recovery procedure. The state directory and restored data must be
owned by the current user and owner-only. The launcher reports
`recovery-quarantined` for readiness 503, permits authenticated inspection, and
never removes the recovery marker or acknowledges replay risk. Stopping and
restarting preserves quarantine. `ready` indicates the gateway readiness probe,
not storage health, execution completion or production readiness.

The real-process CI witness checks token permissions/persistence and absence from
launcher output, duplicate launch rejection, lock retention by an orphan child,
request persistence and quarantine, plus rejection of insecure state and symlink
tokens. Its result is `launcher-acceptance.json` in the package.

Do not interpret a fresh empty workspace as recovery of an existing deployment.
Use a local filesystem. This is not permanent hosting and does not keep running
after its host stops. No production credentials or data enter CI.

## Complete offline backup and quarantined restore

Stop the foreground launcher with Ctrl-C. Stop every other writer as well,
including any gateway started directly. Then choose a new archive name in a
private directory outside the data directory:

```bash
mkdir -m 700 -p "$HOME/nexus-backups"
python3 run-local-pilot.py --backup "$HOME/nexus-backups/nexus-data.json" --offline
```

The operation holds the same advisory lock as the launcher. It fails while a
cooperating gateway or orphan child is alive; it does not stop them automatically.
`--offline` remains your explicit assertion that **all** writers are stopped,
not proof against raw binary invocations or privileged actors. A missing source
fails without creating an empty installation. Existing archives are never replaced;
use a new name for the next backup. The archive captures supported workspace data
and the request ledger together, excluding the operator token and lock. It is
plaintext mode 0600; store a copy independently of this host, with appropriate
access controls. This command does not encrypt, sign, authenticate or upload it.

Restore to a separate owner-only state directory with no existing `data` target:

```bash
python3 run-local-pilot.py --state-dir "$HOME/nexus-recovery" --restore "$HOME/nexus-backups/nexus-data.json" --offline
python3 run-local-pilot.py --state-dir "$HOME/nexus-recovery"
```

Restore validates the whole archive before publishing data, refuses an existing
target and always writes the recovery quarantine marker. It does not copy or
replace tokens; a fresh state gets a new private token only when started. Expect
`recovery-quarantined`, authenticated inspection and write rejection with 503.
Snapshot-captured request IDs retain their recorded status; later IDs are not
recovered. Never interpret `pending` as completed execution. No automatic resume
or replay-risk acknowledgment is performed. Maintenance does not require a
gateway executable or compiler; the bundled Python snapshot tool is sufficient.

For the explicit resumption procedure and recovery-point limits, see
`docs/full-data-recovery.md` in the source repository. The maintenance witness
checks live/orphan writer exclusion, offline assertion, missing-source and
overwrite rejection, token exclusion, restored GET pending and write quarantine.
Its fixtures are synthetic and raw archives are never uploaded by this workflow.

A Railway volume must still be exported independently; this package contains no
production data. A checksum establishes byte integrity, not trust or authority.
A_out <= A_in, evidence != authority, AuthorizedRequest,
CT-001..020 and Bootstrap versus Verify separation remain required; both
Cargo.lock files are unchanged. No new release authority is introduced.
