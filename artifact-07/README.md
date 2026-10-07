# Artifact 07 — Public Exposure Safety Boundary

Status: **IMPLEMENTED / UNSEALED**

Artifact 07 adds bounded, process-local admission controls to `POST /v1/requests` before
constitutional delegation. These controls protect transport resources; they do not authorize
an action, mint capability, construct `AuthorizedRequest`, or alter Core policy.

## Fail-closed order

1. configured bearer authentication;
2. bounded body read;
3. fixed-window request-rate budget;
4. exact request-shape parsing;
5. request-id replay reservation;
6. tracked-request capacity budget;
7. constitutional delegation.

The defaults are 64 KiB per request body, 120 authenticated submissions per 60 seconds, and
10,000 tracked accepted requests per process. Production may lower or raise these positive
limits with `NEXUS_MAX_BODY_BYTES`, `NEXUS_RATE_LIMIT_REQUESTS`,
`NEXUS_RATE_LIMIT_WINDOW_SECONDS`, and `NEXUS_MAX_TRACKED_REQUESTS`.

Successful request ids remain reserved for the process lifetime. A delegate failure releases
the reservation and capacity slot so a legitimate retry can occur. Rate budget is consumed
after authentication and bounded body admission, including malformed authenticated requests.

## Authority boundary

`A_out <= A_in` remains invariant. Authentication and admission are not constitutional
authorization. Evidence of a rejected or accepted transport request is not authority. Only Core
policy can produce the unforgeable `AuthorizedRequest` consumed by the executor.

## Bootstrap versus Verify

Bootstrap executes the exact Artifact 07 tests and creates local evidence:

```sh
bash scripts/artifact-07-bootstrap.sh
```

Verify independently validates committed controls and an optional evidence bundle:

```sh
python3 scripts/verify-artifact-07.py
python3 scripts/verify-artifact-07.py artifact-07-output/artifact-07-evidence.tar.gz
```

Both pinned Cargo lockfiles and the exact commit are recorded. PASS evidence applies only to
that commit. It neither deploys production nor creates a Seal.

## Deliberate non-claims

This artifact does not claim distributed rate limiting, cross-instance or durable replay
defense, identity-specific fairness, denial-of-service immunity, clinical or legal validity,
organizational approval, production deployment, or Seal readiness.
