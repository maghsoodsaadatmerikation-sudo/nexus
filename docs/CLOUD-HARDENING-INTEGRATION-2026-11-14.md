# Cloud boundary hardening integration — 14 November 2026

## What is combined
This **draft, source-only** branch composes the exact reviewed source files
from two independently passing candidates based on the same main revision
`b7855b1a1bb9f3776e8f24b682d124cbe334543e`:

| PR | Exact source head | Concern |
| --- | --- | --- |
| #195 | `b001aa78f6e8235ecf9dc0fdd282c6dad2397fe9` | Studio consent JSON, provider outputs and sensitive header ambiguity |
| #196 | `d5895593e56fb56e981828242ec8734c515e1ed8` | Cloud-to-core HTTP framing, body-size identity and mandatory Python contract in protected PR job |

The seven changed source paths do **not overlap**. They were copied as
existing **Git blob objects**, not regenerated source. Their SHA identities
are pinned in `integration/cloud-boundary-195-196-manifest.json`.
The read-only verifier recomputes Git blob IDs from source bytes and rejects
missing/changed files, unexpected input records, duplicate JSON keys and
contradictory production authority. Its CI tests mutate the manifest to
verify fail-closed behavior. Git blob SHA-1 is an object identity check, not
a digital signature or an independent production attestation.

## Verification required before further action
- `NEXUS Cloud Boundary Source Integration` verifies exact source bytes.
- `NEXUS Cloud Adapter Verification` executes the full frozen Python suite.
- `NEXUS PR Verification / readonly-verification` runs the frozen Python
  cloud and Studio suite *unconditionally*, and then the existing core,
  gateway, durable state and release-boundary gates.
- The Studio, Verify and other exact-head checks must also finish without
  failure before treating the composite as an engineering candidate.

## Known limitations / release block
This branch does not contain every open NEXUS feature PR. Other draft stacks,
including #170 and #191, remain separate and must be independently reconciled.
The live GitHub ruleset 20870033 still has
`strict_required_status_checks_policy=false`. The production Render
auto-deployment and independent complete offsite recovery acceptance remain
unresolved. **DO NOT merge, deploy, claim Stage D, or publish release
attestations** from these source-only checks. No real workspace data, provider
credentials, hosted service settings, or existing release evidence was changed.

## Architectural next action
After production safeguards are established, integrate verified, disjoint
changes in small batches, preserving an explicit source-to-commit manifest,
then require a fresh main-base verification. Do not substitute a successful
synthetic CI test for a real on-provider restore, or merge long stacked PRs
without checking their exact dependency revisions.
