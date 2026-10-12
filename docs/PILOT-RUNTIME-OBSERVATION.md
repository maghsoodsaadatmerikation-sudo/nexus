# Observe the pilot without promotion authority

The historical runtime drift watch compares production with its old sealed
baseline. This observer instead compares a proposed candidate with the public
runtime and inspects current liveness, readiness and two credential-free GET
boundaries. It sends no token, request body, POST or provider mutation.

From an exact reviewed candidate checkout:

```sh
python3 scripts/test-observe-pilot-runtime.py
python3 scripts/observe-pilot-runtime.py \
  --origin https://nexus-stage-d-production.up.railway.app \
  --expected-digest "$(bash scripts/source-tree-digest.sh)"
```

Exit 0 means only the listed public checks were satisfied; exit 2 reports a
blocker. HTTPS redirects are not followed. Runtime identity bodies are bounded
at 16 KiB; other response bodies are neither read nor recorded. Transport failure
and malformed identity fail closed. The GET request ID is a fixed synthetic
observation name; no request is submitted or reserved.

A_out <= A_in and evidence != authority remain mandatory: self-reported matching
metadata cannot prove the deployed binary or authorize promotion. No change to
AuthorizedRequest, CT-001..020, Bootstrap/Verify separation, core or Cargo.lock.
This script's tests are observer verification, not constitutional Verify PASS.
No attestation or Seal is created. Authenticated POST 202 with ID and GET pending,
backup freshness, rollback and offline writer exclusion still require their own
executed evidence. Public checks never set promotion_ready to true.

The committed dated observation is a historical measurement, not a current
health guarantee. Full-data backup and authenticated runtime access remain the
known promotion prerequisites; this observer does not obtain either.
