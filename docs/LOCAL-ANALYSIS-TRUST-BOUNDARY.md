# Local analysis provenance boundary

## Problem and correction

The previous `POST /v1/workspaces/{id}/analysis` accepted a complete
`AnalysisBatch` over the user-authenticated HTTP interface. A caller
could nominate `adapter_id`, `run_id`, observation text, IDs, uncertainty,
and sources, then receive an event labeled `MachineAnalysisRecorded`.
A bearer token authorizes a user request; it does **not** authenticate the
identity or execution of a machine-analysis adapter.

This endpoint now accepts **only** this request:

```json
{"kind":"question_probe"}
```

The gateway rejects unknown fields and unsupported kinds. In particular, the
old body with `adapter_id`, `run_id`, and `observations` is not silently
converted into a machine record. An invalid body returns HTTP 422 with no
workspace mutation. Ordinary auth and restore-quarantine checks still run
before a delegate is called.

The Rust gateway now creates a fresh UUIDv4 run identifier on each call
and executes the checked-in `LocalQuestionProbe` implementation against
the current workspace state inside the durable mutation transaction.
Neither a claimed provider identity nor a claimed observation can cross
this HTTP trust boundary as generated output.

## What the local algorithm actually does

- Adapter ID: `nexus-local-question-probe-v1`.
- One bounded rule-based *question* about disconfirming the workspace's
  stated question (up to 240 Unicode characters of the original).
- Classification: `UncertaintyNote`, high uncertainty.
- No retrieved documents, verified sources, network requests, external
  providers, language-model inference, or autonomous actions.
- No human judgment is produced. The user remains the decision-maker.

The analysis event and claim are saved only after the server has produced
them, with the event provenance set to
`machine:nexus-local-question-probe-v1:<server-generated-run-uuid>`.

## Existing data and other input paths

Existing snapshots and the workspace schema are unchanged. Existing
`MachineAnalysisRecorded` history continues to satisfy the format and
history-consistency checks. Other clients may still submit *user-reported*
AI output as an ordinary external-evidence claim through
`POST /v1/workspaces/{id}/claims`; it must **not** declare machine
origin through that generic claim route.

The import endpoint can still receive user-supplied reconstructed snapshots.
Their event ID formats do not prove authorship or cryptographic authenticity.
This change therefore strengthens the **server execution path**, not the
provenance of arbitrary imported history. Server-side signed attestations
with independently managed verification keys would be a separate feature.

## Regression gates

- Old caller-defined `AnalysisBatch` bodies, extra provenance fields,
  unsupported kinds, and absent kinds must all return 422 and not mutate
  an existing workspace.
- A genuine local run generates a server-minted UUIDv4, correctly bound
  adapter/run provenance, high uncertainty, no external source IDs, and no
  human judgment. A second run has a distinct ID and appends to history.
- The core question probe has a bounded output, rejects empty run IDs,
  and never claims that its question is verified evidence.
- Durable Rust, HTTP, private import, browser, and offline CI must pass
  before merging. No provider deployment or private data operation is
  authorized by this change.
