# Studio model JSON boundary hardening — 14 November 2026

## Reproduced failure in the default branch

The previous `Completion.model_validate_json` accepted a JSON object with duplicate
`consent` fields, using the last value. Standard Python JSON decoding did the
same for duplicate provider `content` or `finish_reason` fields. Two actors
examining the same bytes could disagree about what was consented to or returned.
The previous Content-Type prefix check also accepted invalid media types such as
`application/json-fake`.

## Repair in this isolated source branch

- Decode UTF-8 only; reject duplicate decoded JSON keys recursively, including
  `\\u`-escaped aliases. Reject non-standard JSON constants.
- Validate the unambiguous result against the existing strict Pydantic schema;
  retain explicit `consent: true`, the exact configuration ID, source roles,
  bounded input and non-authoritative model policy.
- Apply identical JSON parsing rules to the upstream model's response so
  ambiguous duplicate `content` / `finish_reason` fields cannot be published.
- Reject duplicate authentication and Content-Type headers, and require a single
  exact `application/json` media type with at most a UTF-8 charset declaration.
- Add tests for consent contradictions, escaped/nested duplicates, invalid
  encoding/media headers, repeated sensitive HTTP headers, ambiguous provider
  responses, and successful recovery after rejected input/output.

## Scope and limits

This changes only the optional cloud Studio model bridge, its tests and this
document. It does not alter Rust authority, existing workspace schemas, secrets,
repository rulesets, production service state, or historical evidence. The
model provider still has no tools and cannot execute actions. It does not
authenticate the *human act* of consent or the provenance of client-supplied
conversation history; it enforces an unambiguous wire representation of the
existing opt-in contract.

This source PR is not a deployment or a verified production release. Until
production freeze/restore and required-check freshness controls are resolved,
keep this as a draft and do not merge or deploy it as a side effect.
