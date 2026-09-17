# NEXUS v2.0 — Constitutional Capability Delegation

Status: ENGINEERING CONTRACT / NOT SEALED

`A_child <= A_parent <= A_in`

## Claim

NEXUS v2.0 introduces a narrow, deterministic representation for delegating a subset of already-held authority. A delegation is evidence of bounded permission; it is not a new source of authority and it never converts evidence, MachineAnalysis, or provenance into HumanJudgment.

## Capability grant

A grant binds:

- immutable grant identifier;
- issuer and subject identifiers;
- parent authority and delegated authority;
- explicit action scope;
- issuance and expiry timestamps;
- immutable provenance identifier.

A grant is valid only when every requested action is inside its explicit scope, delegated authority is no greater than parent authority, the parent is no greater than request input authority, the grant has not expired, and its identifier has not been revoked.

## Fail-closed rules

Validation MUST reject:

1. authority amplification;
2. empty scope;
3. use outside scope;
4. expiry (`now >= expires_at`);
5. use before issuance;
6. revoked grants;
7. subject mismatch;
8. malformed or unsupported capability schema/version.

Unknown state is denial. No fallback may widen scope or authority.

## Revocation and audit

Revocation is monotonic for a grant identifier. A revoked identifier cannot become valid again by replaying an older grant. Grant issuance, validation outcome, and revocation are audit facts; audit evidence is non-authoritative and cannot itself authorize execution.

## Gateway boundary

The gateway may parse and transport a capability envelope but MUST NOT mint, widen, repair, infer, or silently substitute a grant. Enforcement remains inside the constitutional core before an `AuthorizedRequest` can reach execution.

## v2.0 verification contract

A v2.0 candidate is not complete until all of the following are real and recorded:

- deterministic positive tests for in-scope delegation;
- negative tests for amplification, empty scope, cross-scope use, expiry, pre-issuance use, revocation, subject mismatch, and unsupported schema;
- replay test proving revocation is monotonic;
- existing constitutional and product verification remains green;
- verification evidence and attestation are generated for the exact candidate;
- exact-candidate NEXUS Verification succeeds;
- if a production observation is part of the release claim, the real public observation succeeds and its runtime identity matches the sealed candidate;
- a separately authorized release mechanism seals the exact verified candidate.

## Non-claims

This contract does not authorize autonomous delegation, key management, third-party identity federation, paid infrastructure, production mutation, secret disclosure, or a release. It does not claim formal proof of security or correctness.

## Completion rule

No real verification -> no PASS -> no seal.
