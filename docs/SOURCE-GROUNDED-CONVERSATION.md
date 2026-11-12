# Source-grounded NEXUS conversation

Development feature, stacked on PR #130. No deployment or release seal claimed.

## Use

On the Rust gateway, open `/research-chat` (also linked from the workspace home).
Supply the private gateway token in this page only; it is never persisted or
exported. English is the default; Persian labels and RTL layout are included.
Ask a question, add a reviewed HTTPS source passage, or explicitly approve a
query to Wikipedia + DuckDuckGo Instant Answers. Only that query and the selected
Wikipedia language are passed to the search backend. Messages, manual passages,
workspace data and credentials are not sent to either provider.

Each answer contains short selected source passages with server-assigned citation
IDs, original URLs, origin labels and retrieval times where available. Retrieval
time is not publication date. Cached sources on follow-ups are explicitly labeled
client-supplied prior excerpts, never falsely presented as fresh retrieval. A
manual passage is user-supplied even when it names a reputable source. Explicitly added passages take priority at the response cap; this is not a
truth ranking. Multiple passages from one URL are not independent corroboration; different passages are
retained so changes or disagreement are visible rather than overwritten.

Up to the last 16 conversation messages can provide context; oldest pairs are
trimmed from the request at a 60,000-byte client budget, keeping the latest message. 40 exchanges are kept in
tab memory only. Changing the token or clearing the session discards that context.
A separately confirmed transcript download is unencrypted and excludes the token.
Search approval is consumed at dispatch, including failed or cancelled requests.
Replies arriving after cancellation, clear, token or language change are discarded.
Typing a new message while an answer is pending does not lose the unsent text.

## Epistemic and authority boundary

Mode: `retrieval_assisted_extractive`. This is a real retrieval-and-excerpt answer
path, not an LLM, general reasoning engine or full web-results aggregator. Source
text is untrusted data. No source instruction, assistant-history text or answer
can change policy, populate human judgment, execute an action or modify a workspace.
Every selected factual passage references a returned source and stays marked not
independently verified. No evidence yields an explicit insufficient-evidence answer,
not a generated factual guess. The follow-up prompt separates human values,
alternatives, consequences and final human judgment from retrieved passages.

Wikipedia is searchable English/Persian reference content. DuckDuckGo's official
Instant Answer interface has limited topic coverage and is not its full ranked
web-results feed. Provider failures and empty results are displayed individually.
Manual reviewed passages can originate from any search engine; no paid API key is
required. Availability of external providers is not a deployment-readiness proof.

## Transport and resource limits

`POST /v1/research-chat` uses the existing authentication-before-body, shared rate,
body cap/deadline, recovery quarantine and execution-concurrency boundaries. It
returns `Cache-Control: no-store`. No CORS permission, cookies, analytics, source
scripts or remote model are added. Browser CSP allows API connections to its own
origin only. The installed offline workshop keeps `connect-src 'none'` unchanged.

Only fixed Wikipedia/Instant Answer endpoints are fetched, without redirects,
remote cookies, a Referer or NEXUS bearer credentials. Result/source URLs are never
automatically fetched. Public HTTPS citations exclude credentials, IP literals,
nonstandard ports and local/internal host suffixes. External response bytes are
capped at 128 KiB, each call at 10 seconds, both together at 11 seconds, with two
concurrent research operations. Requests accept at most 16 messages of 1,500
characters, a 250-character query, and six combined reviewed/cached passages of
2,000 characters. Up to eight sources and four 25-word/300-character passages
are returned. Duplicate identical passages are collapsed. Truncated quotations carry an explicit
ellipsis and a structured truncation flag; source text itself remains unchanged.

`NEXUS_WEB_RESEARCH_ENABLED=false` disables provider calls while retaining manual
source responses. The executable enables the capability by default, but makes no
provider request without per-request query consent. Library `AppState` defaults
to no provider backend, so existing synthetic/offline embeddings do not gain
network access. Proxy/extra trust are explicit operator-only settings:
`NEXUS_SEARCH_PROXY_URL` and optional public PEM `NEXUS_SEARCH_CA_FILE`. Chat input
cannot set either. Automatic environment proxy discovery is disabled. Native
platform trust is used; certificate verification is never disabled.

## Validation and integration

Unit/HTTP tests cover consent before provider access, exact approved query only,
no network when search is off, origin-preserving follow-up context, invalid URLs
and system roles, source instructions remaining data, bounded quotations,
duplicate citations, missing evidence, provider parsing, authentication before
body polling, no-store, body caps and no core delegation/workspace mutation.
A real Chromium fixture tests English/Persian, mobile/desktop, citations, XSS,
query consent reset, private export, draft preservation and late-response races.
All provider fixtures are synthetic and require no production credentials.

The existing production recovery and automatic-deployment holds remain. Mainline
and static pilot are not modified by publishing this branch. A live provider
canary is a separate observation and cannot replace private-host recovery proof.

Primary API references:
- https://www.mediawiki.org/wiki/API:Search
- https://www.mediawiki.org/wiki/Extension:TextExtracts
- https://github.com/duckduckgo/duckduckgo-publisher/blob/master/share/site/duckduckgo/api.tx
