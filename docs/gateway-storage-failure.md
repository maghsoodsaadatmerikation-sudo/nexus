# Synthetic request ledger outage

Canonical Verify runs a live HTTP drill on its disposable CI data volume. It
moves the request ledger aside while the gateway is running, then restores it
and restarts the gateway. Bootstrap does not execute or confer this evidence.

Authenticated admission with an unavailable ledger returns 503
`request_store_unavailable`, never 202. A RecordingDelegate contract test proves
this reservation failure does not cross the AuthorizedRequest delegation
boundary. The failed ID stays indeterminate in memory and retry returns 409,
even after storage repair. A fresh ID after repair returns 202 with its ID and
GET returns pending. Restart retains the repaired ID and rejects its replay.

The missing-directory failure creates no durable marker: after restart the
failed ID returns 404 and may be admitted afresh. This is not an execution
retry guarantee. Empty or torn markers have a separate conservative recovery
contract. GET from process memory is not proof of current disk availability.

`/readyz` remains 200 during this drill: it reports the latched recovery
quarantine only. It is not a disk health or admission-success promise. The drill
does not simulate ENOSPC, hardware faults, or fsync failures after delegation,
and does not establish exactly-once execution or production availability.

Evidence is not authority; A_out <= A_in remains mandatory. CT-001..020 and
both pinned Cargo.lock files remain unchanged. Only current exact-commit
Verify results support PASS; this engineering witness does not grant Seal.
