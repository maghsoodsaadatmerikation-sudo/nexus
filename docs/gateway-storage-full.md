# Bounded real ENOSPC witness

Canonical Verify runs `verify-storage-full.py` using a separate disposable Docker
container and an 8 MiB private tmpfs. There is no host data mount. Filling stops
at the kernel ENOSPC error; `df` must report zero available bytes. Cleanup removes
only the container created by this invocation. Bootstrap grants no such evidence.

The witness accepts a prior request (202 with ID, GET pending), fills the volume,
and verifies authenticated admission returns 503 `request_store_unavailable`.
The reservation now writes and syncs the non-accepted prefix `p` before
calling the delegate. On full tmpfs an empty inode can still be created, but
writing this prefix fails first. The empty marker and GET indeterminate are
checked; retry returns 409. A separate RecordingDelegate test on a verified
8 MiB tmpfs proves zero delegate calls for this reservation-write ENOSPC,
then exactly one fresh admission after repair. This does not guarantee that
later I/O or fsync failures cannot occur after delegation, nor provide rollback
or exactly-once external side effects. Legacy empty and prefix markers remain
compatible and indeterminate on reopen.

Removing only the filler allows a fresh request to return 202/pending. The failed
ID remains blocked. Restarting the gateway child process on the SAME mount
recovers both accepted requests and the indeterminate reservation; all reject
replay. Restarting a tmpfs container would lose the mount and is deliberately
not used as persistence evidence. This is process-restart evidence, not durable
hardware or power-loss evidence, nor a claim about all filesystem ENOSPC behavior.

Liveness and quarantine-only readiness remain 200 during this failure. Admission
is the relevant check. Authentication remains before mutation. A_out <= A_in,
evidence != authority, AuthorizedRequest, CT-001..020 and both pinned Cargo.lock
files remain unchanged. Attestation binds evidence; no new Seal or production
availability follows from this synthetic drill.
