# Artifact 05 — HTTP Gateway Contract v0.3

## Purpose

Artifact 05 exposes NEXUS transport surfaces without creating a second authority layer. It serves both the constitutional request boundary and the human Decision Workspace API.

## Boundary

The HTTP layer MAY:

- parse HTTP requests;
- validate required request shape through typed deserialization;
- translate wire enums into typed Core values;
- construct `RequestEnvelope` for constitutional requests;
- delegate workspace commands and queries to a `WorkspaceDelegate`;
- serialize transport responses;
- serve the same-origin human workspace client.

The HTTP layer MUST NOT:

- authorize or deny constitutional actions;
- interpret payload meaning;
- execute constitutional actions;
- mutate policy;
- increase authority;
- synthesize or implicitly populate `HumanJudgment`;
- rewrite audit history or provenance.

## Constitutional request contract

`POST /v1/requests` accepts a tagged Core action. Its required companion field depends on the action variant.

Reflect example:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "reflect",
  "subject": "opaque",
  "payload": "opaque"
}
```

A successfully delegated request returns `202 Accepted` and is represented as `pending` at the transport boundary. `GET /v1/requests/{id}` returns the transport-visible request status or `404` when unknown.

## Decision Workspace contract

The workspace API exposes typed read/write operations while persistence and audit semantics remain in the Epistemic Engine behind `WorkspaceDelegate`.

### Create

`POST /v1/workspaces`

```json
{
  "workspace_id": "optional-client-id",
  "question": "What should I examine?",
  "provenance_id": "human:owner"
}
```

Returns `201 Created` with the complete `WorkspaceSnapshot` including `schema_version`, `workspace`, and append-only `events`.

### Read

`GET /v1/workspaces/{id}` returns the persisted snapshot or `404`.

### Evidence

`POST /v1/workspaces/{id}/claims`

```json
{
  "text": "A claim",
  "origin": {"kind": "external_evidence", "source": "source:123"},
  "uncertainty": "medium",
  "provenance_id": "source:123"
}
```

Supported wire origins are `human`, `external_evidence`, and `machine_analysis`. Machine analysis is stored as an epistemic origin only; it gains no human authority.

### Alternatives

`POST /v1/workspaces/{id}/alternatives`

```json
{
  "label": "Option A",
  "consequences": ["Consequence 1"],
  "provenance_id": "human:owner"
}
```

### Explicit human judgment

`POST /v1/workspaces/{id}/judgment`

```json
{
  "decision": "Option A",
  "rationale": "Explicit human rationale",
  "provenance_id": "human:owner"
}
```

This route is the explicit transport action that requests a human-judgment transition. The Gateway does not infer or populate a judgment from claims, machine analysis, or alternatives. The Epistemic Engine records the previous/current transition and provenance in the append-only audit history.

Malformed JSON or malformed typed shapes are rejected by the HTTP extractor with `422 Unprocessable Entity` before reaching the delegate. Duplicate workspace creation returns `409`. Delegate unavailability returns `502`.

## Human web workspace

`GET /` serves `web/index.html` from the Gateway binary. The browser client uses same-origin workspace endpoints and displays claims, alternatives, explicit judgment, provenance, and audit history. The client does not maintain an independent authoritative workspace state; the rendered state comes from returned `WorkspaceSnapshot` values.

## Authority invariant

HTTP and the browser are not authority sources. Constitutional authorization remains exclusively inside the Core. Human judgment exists only after an explicit human transition, and machine-generated material remains non-authoritative epistemic content.

## Verification boundary

Artifact 05 verification hashes and bundles its Rust sources, tests, lockfile, manifest, and the served `web/index.html`. CI-generated evidence and attestation remain the only basis for a verified/sealed claim.
