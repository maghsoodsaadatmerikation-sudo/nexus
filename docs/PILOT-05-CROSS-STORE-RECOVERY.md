# Pilot 05 — cold-copy full-data restore into a separate gateway instance

## Goal

Close the **synthetic recovery rehearsal** gap that remains after the
standalone mobile pilot and the private Railway volume download helper. The
original `scripts/readonly-verification.sh` exercises full-data snapshots,
quarantine and restart within a single disposable witness. Pilot 05 adds a
**two-container / two-storage-root** scenario, including an actual copy OUT
of a stopped container, a corrupt-archive refusal, recovery in a fresh
container, protected access and explicit replay-risk acknowledgment.

**This is not a true independent off-provider backup test.** Both Docker
instances run on the same ephemeral GitHub Actions runner. It is not
a fresh Railway deployment, a second cloud provider, a production export,
a live human trial, or an atomic snapshot of a changing volume.

## Reproducible test

The isolated CI workflow is
`.github/workflows/pilot-05-cross-store.yml`, launching
`scripts/pilot-05-synthetic-cross-store.py` after a
digest-pinned Rust gateway image build from the checked-out revision.

It **requires** `GITHUB_ACTIONS=true`,
`NEXUS_P05_DISPOSABLE=true`, a numeric `GITHUB_RUN_ID`, and
the absence of environment variables for Railway, Render or any existing
NEXUS API credential. Only ephemeral, freshly generated synthetic credentials
are used to access `127.0.0.1` inside the CI job. No external host is
contacted by the runner script. Docker builds may fetch build dependencies;
the test itself makes no Railway API requests.

The distinct stages are:

1. Launch the Rust gateway in a disposable source container, with a
   synthetic bind-mounted volume. Verify `/readyz`, create a workspace with
   explicit source provenance, add a claim and an alternative; confirm no
   judgment appears before an explicit judgment request. Create a request
   ledger entry.
2. Fetch the authenticated snapshot and its SHA-256 digest, stop **all
   source writers**, copy the source directory out of the **stopped**
   container using `docker cp`, remove that source container and move its
   volume path out of reach of the restored instance.
3. Run the existing `scripts/data-snapshot.py backup --offline` against
   the cold copy. Verify archive structure. Tamper with a separate archive's
   SHA-256 field and confirm that restoring the tampered archive fails
   without creating a destination.
4. Restore the intact archive with the original gateway UID/GID into a
   **different storage root**. Verify the quarantine marker was created.
   Launch a new gateway container using only the restored root.
5. Verify its real HTTP server answers liveness `200`, readiness `503`,
   gives the same fully populated authorized workspace and request ledger,
   blocks writes while quarantined, and refuses unauthenticated reads.
6. Stop the restored gateway, explicitly acknowledge replay risk on **this
   synthetic fixture only**, remove the recovery marker while offline and
   restart. Verify readiness `200`, exact canonical workspace hash,
   rejection of missing/wrong bearer, duplicate request conflict `409`,
   and success for a novel request.
7. Restart the recovered container again and prove both the original
   workspace and the new request survive. Upload only an aggregate
   sanitized JSON report (synthetic digest, booleans and explicit nonclaims),
   **never** a data snapshot, token, private path or workspace text.

## Proven claims and self-critique

What a **PASS** supports: this exact Rust gateway build and existing
`data-snapshot.py` can accept a **synthetic cold copy** originating in a
separately stopped Docker container, create a quarantined full snapshot,
restore it into another storage root and serve its exact authenticated
workspace and request ledger after a fresh container and process restart.

What a PASS does **not** establish:

- that the source Railway `/data` files were observed or backed up;
- atomic capture from a live, mutating production filesystem;
- an off-provider encrypted durable backup in storage controlled by the user;
- preservation of request IDs created after the recovery point;
- independent physical-machine, host or cloud-provider recovery;
- human-authenticated mobile acceptance of the live Rust gateway;
- durable production readiness, a Seal or extra decision authority.

The existing tool in
[Stage D read-only CLI capture](STAGE-D-READONLY-CLI-CAPTURE.md)
still depends on a trusted owner-authenticated Railway CLI and private
off-provider storage. Connected Railway tools currently allow metadata reads
but not live volume-file download. Never try to satisfy the real-world
recoverability gate by copying CI fixtures to the public GitHub repository.

**Decision gate:** Issue #70 stays open until the real original source is
copied consistently, independently authenticated, retained off-provider and
restored under a separately observed human-authorized lifecycle. Existing
staged production paths and volume mounts must remain unchanged. Invariant:
`A_out <= A_in`.
