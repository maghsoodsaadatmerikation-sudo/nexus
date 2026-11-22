# Operation-level credential gates (v2)

NEXUS Studio now describes nine source-defined external/model operations separately. The gateway distinguishes configured read credentials from independently configured GitHub branch and file-write credentials. Configured **never** means live or permitted by a provider. Every operation has `permission_verified=false`, `execution_observed=false`, `receipt_observed=false` and demands a separate reviewed action, plus its own resulting evidence.

The signed-in, token-authenticated GET endpoint makes **no external provider call**, serializes **no secrets**, target IDs, repositories or service names, and remains non-cacheable. Branch-creation and file-commit are the only entries flagged as potentially mutating an account; read and preview are not. Explicit approval of a separate tool action is still mandatory. This is neither a permission check nor an execution receipt.

Protocol `schema_version=2` is intentionally fail-closed for old v1 clients. The Studio UI and Chromium witness must be updated alongside this change and all static SRI and offline assets rebuilt before merge. All changes remain on a draft stacked PR and are marked `[skip render]`.
