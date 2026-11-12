# Optional MCP app connections

Development feature stacked on optional chat history (#132). No production
connection, deployment, third-party account login or authorization is claimed.

## User flow

From `/research-chat` choose **Apps**, or open `/connections`. The page makes no
request automatically. Enter the NEXUS gateway token, then explicitly load the
operator's catalog from NEXUS. This does not contact any external app. Select an
app, enable it for this tab, choose an approved read tool, enter a JSON object,
review the destination/tool/arguments preview, and approve that exact read once.
Consent is consumed at dispatch, including errors. Editing arguments, changing
app/tool/language or changing the token revokes consent. Changing apps requires
enabling the new app; token changes clear the catalog and previous app data.

Only the explicit arguments leave NEXUS. No conversation, history, workspace,
gateway token, source passages or account identity is attached to the remote call.
If a user deliberately enters private data in arguments, that data is shared.
Responses are displayed as inert, unverified external data, not executed as HTML,
instructions, human judgment or policy. Results can be explicitly downloaded as
plaintext after confirmation; the token is excluded from this export.

Disconnect aborts the browser wait and clears the token, catalog, choices,
arguments and result from the page. There are no saved grants or background
subscriptions. Already-dispatched reads may finish remotely; cancellation does not
prove remote cancellation. Calls are never retried automatically. Each approved
read creates a short-lived MCP session; DELETE cleanup is best effort, including
on protocol errors and timeouts. User choices reset on reload. English and Persian
interfaces are included. No localStorage/sessionStorage or history writes occur.

## Operator setup

Default is no configured apps and no external network calls. Set
`NEXUS_CONNECTIONS_CONFIG` to a UTF-8 JSON file mounted on the gateway. The file is
bounded to 64 KiB and is validated before listening. Invalid configuration fails
startup without printing the manifest, endpoints or credentials. Example
(illustrative placeholder, not a live app):

```json
{
  "apps": [{
    "id": "reviewed-library",
    "title": "Reviewed library",
    "endpoint": "https://library.example.org/mcp",
    "bearer_env": "NEXUS_PLUGIN_LIBRARY_TOKEN",
    "tools": [{
      "name": "lookup",
      "description": "Read one catalog record",
      "input_schema": {"type": "object", "properties": {"record": {"type": "string"}}, "required": ["record"]},
      "read_only": true
    }]
  }]
}
```

Omit `bearer_env` for an unauthenticated public MCP endpoint. Credential variables
must start with `NEXUS_PLUGIN_` and contain only uppercase ASCII, digits and `_`.
Credentials remain on the server and are sent only to that app's pinned endpoint;
they are not returned in the catalog. There is no OAuth flow, token refresh,
per-user account binding or automatic third-party revocation in this version.
A configured credential is available to holders of the gateway token; deploy only
in a trusted single-user/operator domain with least-privilege app credentials.
Do not treat a shared gateway token as separate user accounts.

At most eight apps and 16 tools per app are accepted. Every tool must have a unique
name, an object input schema and explicit `read_only: true`. The operator must audit
the real tool and restrict the credential remotely. A remote `readOnlyHint` is not
trusted and cannot expand the catalog. The gateway checks the exact app/tool
allowlist and an 8 KiB object argument limit; full JSON Schema validation is the
remote tool's responsibility. Schema is displayed for review. This version does
not enable write/send/delete tools, local subprocesses, arbitrary plugin code,
stdio servers, arbitrary browser-supplied endpoints or unrestricted webhooks.

## MCP transport and boundaries

Supported protocol version: `2025-06-18`, Streamable HTTP POST with JSON and bounded
SSE responses (LF/CRLF). Each call negotiates the exact version with `initialize`,
advertises no optional client capabilities, sends `notifications/initialized`,
and invokes exactly one approved `tools/call`. There is no remote tool discovery
or automatic agent invocation. Server instructions are ignored; sampling,
elicitation, roots, server-initiated requests, older SSE transports and version
fallback are not supported. Unknown versions and malformed/mismatched JSON-RPC
responses fail closed. Tool `isError` and other data remain visible inside the
unverified result; successful transport is not a successful factual conclusion.

Endpoints must be fixed public DNS HTTPS on port 443, without userinfo, query,
fragment, IP literals or local/internal hostnames. DNS is bounded to four seconds;
non-public IPv4 answers are rejected and public IPv4 addresses are pinned for the
entire invocation and cleanup, retaining TLS hostname validation. IPv6-only
endpoints are unsupported in this first version. No environment proxies,
redirects, cookies, retries or disabled TLS checks are used. DNS rebinding cannot
redirect the later tool request to a newly resolved private address.

Remote responses are bounded to 128 KiB; each HTTP request has a four-second
limit, the protocol operation a 16-second limit, cleanup two seconds, and at most
two app calls run concurrently. Authentication precedes request body polling.
Existing gateway body/deadline, shared rate, execution capacity and recovery
quarantine boundaries apply. Catalog/results/errors have `Cache-Control: no-store`.
Browser connections are same-origin only. The constitutional core and workspaces
are not delegated to or mutated by this route.

## Validation

Gateway/unit tests cover default-off behavior, exact approved arguments, allowlist,
capacity, malformed inputs, unknown history/credential fields, credential aliases,
unsafe destinations, private/reserved addresses, MCP initialization order, version
rejection, JSON-RPC IDs/errors/server requests, SSE fragmentation and inert data.
HTTP tests cover authentication-before-body, no-store, body/rate/quarantine and
no core/workspace mutations. Real Chromium acceptance uses synthetic apps on
narrow/wide layouts, explicit per-call consent, consent revocation, exact data
sharing, inert markup, export, no retries, late results, disconnect and Persian UI.
No real third-party credential, live account access or provider availability is
proven by these synthetic tests.

Primary protocol references:
- https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
