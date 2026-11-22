# NEXUS Assistant: truthful capability disclosure (draft)

`GET /studio-api/assistant/capabilities` is a **read-only, authenticated**
configuration and source-inventory endpoint. It is not an AI inference API,
not a browser probe, not an action API, and not proof that a public deployment
contains a feature. It uses the same operator bearer credential as existing
Studio connections. Responses are JSON with `Cache-Control: no-store`.

The versioned response distinguishes:

- `source_defined_browser_surface_not_runtime_verified`: a reviewed route
  exists in Studio source; local runtime, hosted revision and user device have
  not been checked by this request.
- `configured_not_live_verified`: settings passed local validation; neither
  model reachability nor access to GitHub or Render is established.
- `not_configured`, `local_budget_exhausted` and
  `local_budget_unavailable`: model or connector operations cannot be
  offered as configured/ready. Provider-side quotas may still be exhausted.
- `not_implemented_in_this_gateway`: no autonomous background agent,
  unrestricted shell, native image/video generator or general web-search
  backend has been implemented by this transport layer.

Every capability explicitly reports `separate_user_review_required=true`
and `execution_observed=false`. Neither a workflow plan preview nor opening
the linked UI is evidence that an action succeeded. This endpoint performs
**zero provider calls** and discloses no credential, repository target,
Render service ID, user prompt, private file, or model endpoint URL.

The output is English-first machine-readable JSON, suitable for future
bilingual UI labeling. The connector and model readiness fields are only
local-configuration observations. Consumer applications must continue using
their own explicit consent screens, narrow permission checks, execution
receipts, and independently verified production health probes.

Run focused tests with:

```sh
cd nexus-cloud
python -m pytest tests/test_studio_capabilities.py -q
```

This feature is delivered on a stacked **draft** branch; it does not
authorize merging upstream drafts, deploying Render, adding paid services,
enabling provider keys, or claiming global availability.
