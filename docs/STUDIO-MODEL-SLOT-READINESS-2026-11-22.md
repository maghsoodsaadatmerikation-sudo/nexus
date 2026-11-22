# NEXUS Studio — independent model-slot readiness

## Problem and scope

NEXUS Studio supports up to three separately configured models, but the
authenticated `/studio-api/operator-readiness` endpoint previously described
only the primary model. This caused incomplete operator diagnostics when
preparing a secondary or tertiary route.

## New opt-in read-only endpoint usage

With the independent Studio operator bearer credential:

```http
GET /studio-api/operator-readiness?model_slot=secondary
Authorization: Bearer YOUR_STUDIO_OPERATOR_TOKEN
```

Accepted values are exactly `primary`, `secondary`, or `tertiary`.
Omitting `model_slot` preserves the existing primary-model response shape.
An explicit valid slot adds `model_slot` to the JSON response. Invalid,
blank, or duplicate selectors receive HTTP 422 **after** authentication.

The returned report includes configuration validity, model name, provider host,
adapter, stream setting, **shared** local attempt budget, and a readiness
status. The existing `READY_TO_TEST` status means only that local
configuration and remaining local budget allow an explicit test; **it does
not establish live provider availability, model quality, billing approval, or
production readiness**. A missing secondary/tertiary route reports
`NOT_CONFIGURED` instead of inheriting primary settings.

No network request is made to any model provider by readiness checks.
Provider secrets and the Studio operator token are never included in JSON.
Diagnostics still require a single exact authenticated bearer and are served
with `Cache-Control: no-store`.

## Offline regression

```sh
cd nexus-cloud
uv sync --frozen
uv run --frozen pytest -q tests/test_studio_slot_readiness.py tests/test_studio_model.py tests/test_studio_multi_model.py
```

Tests cover the untouched legacy primary shape, per-slot identity, missing
tertiary configuration, malformed selectors, duplicate parameters, failed
authentication, redaction and no budget consumption.

This is an operator experience improvement, not model provisioning, autonomous
tool use, provider billing approval, or a public hosting deployment.
