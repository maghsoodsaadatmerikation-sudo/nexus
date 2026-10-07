# Artifact 06 — Synthetic Reality Lab

Status: **IMPLEMENTED / UNSEALED**

Artifact 06 turns the existing constitutional Core and Artifact 05 HTTP Gateway into a
repeatable synthetic verification exercise. It does not add production routes, policy,
clinical meaning, legal authority, or deployment authority.

## Boundary

The Lab verifies the canonical `CT-001..020` controls and the existing HTTP contract:

- valid `POST /v1/requests` returns `202` with a request id;
- accepted ids are readable through `GET /v1/requests/{id}`;
- unknown ids return `404`;
- missing or incorrect transport credentials return `401` before parsing, lookup, or delegation;
- authority-like transport fields fail closed;
- no capability, revocation, authorization, or policy-mutation route exists;
- machine evidence does not create human judgment.

The invariant is `A_out <= A_in`. Evidence is not authority. Authentication is not
authorization. `AuthorizedRequest` remains a Core boundary and cannot be forged by the
Gateway or the Lab.

## Bootstrap versus Verify

Bootstrap executes tests and creates a new local evidence bundle:

```sh
bash scripts/artifact-06-bootstrap.sh
```

Verify is read-only with respect to repository sources. It validates the committed Lab
contract and, when given a bundle, checks its manifest, digests, test results, and non-claims:

```sh
python3 scripts/verify-artifact-06.py
python3 scripts/verify-artifact-06.py artifact-06-output/artifact-06-evidence.tar.gz
```

The evidence bundle records the exact commit and both pinned Cargo lockfiles. A successful
Lab run is verification evidence only. It does not confer PASS on another commit and does
not make this artifact sealed.

## Deliberate non-claims

The Lab does not claim clinical validity, legal authority, organizational approval, replay
protection, rate limiting, payload-size enforcement, public deployment readiness, or Seal
readiness. Those remain explicit future gates rather than inferred properties.
