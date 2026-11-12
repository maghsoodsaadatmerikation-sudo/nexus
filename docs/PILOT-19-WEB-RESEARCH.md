# Pilot 19 — Consent-gated Internet research and search

## Scope and public truth

NEXUS is still an English-first/Persian, no-cost, static, standalone offline
decision workspace. Pilot 19 adds a **Web research** desk with 15 preconfigured
public search destinations: Google, Bing, DuckDuckGo, Brave Search, Ecosia,
Startpage, Qwant, Mojeek, Yahoo, Yandex, Swisscows, Baidu, Google Scholar,
PubMed and Wikipedia. Public search URL patterns were cross-checked against
search-engine preferences and search URL documentation. Providers may change
their formats and may have jurisdictional or browser restrictions.

The user can also supply an additional **HTTPS search template** containing
one `{searchTerms}` query parameter, and can explicitly open any normal public
HTTPS website URL. This is an *extensible navigation catalog*, not a claim of
licensing, API access, coverage or success for every search engine worldwide.

## What happens on a search

1. The user types the query manually. NEXUS never extracts a query from
   any private workspace question, claims, drafts, passwords or file contents.
2. NEXUS constructs the intended HTTPS search URL locally, checks its syntax
   and destination, and asks confirmation before any external navigation.
3. Only after consent, the user's own browser opens the provider in a new tab
   with `noopener noreferrer` and no referrer. A visible vetted link remains
   in the NEXUS page if a popup/new-tab action is blocked.
4. The external website, *not NEXUS*, processes the query, returns results,
   and may use its own cookies, tracking, local rules, paywall, ads and ranking.
   A provider may be unavailable or may reject automated-looking search URLs.
5. If the user personally verifies a result, they can paste a public HTTPS
   source URL and a <=2,000 character passage into NEXUS. A distinct action
   copies these values into a **claim draft**, setting
   `origin=external_evidence`, `uncertainty=unknown`. The user must still
   explicitly register the draft. No source is independently verified or
   automatically classified as factual.

NEXUS does **not** perform in-app SERP scraping, live aggregation, unattended
browsing, full-page downloading, remote model summarization, cross-origin
network fetching or searches across every engine in one batch. Genuine
programmatic results would require a separately reviewed server/CORS-capable
API integration, appropriate provider terms/keys and distinct explicit user
consent. Such integration is **not** implemented or claimed here.

## Security and privacy boundaries

- Existing `connect-src 'none'` stays unchanged: application JavaScript does
  not make background requests, even to a search provider. Navigation happens
  only on user choice, in the browser. App operation itself still works offline;
  external search necessarily requires Internet connectivity.
- Enforce HTTPS and reject credentials, fragments, private/localhost/IP hosts,
  port overrides, unsupported protocols and malformed/oversized URLs.
  This is intentionally conservative; it does not certify the trustworthiness
  of *every* allowed public website or prevent phishing.
- A custom engine must contain exactly one `{searchTerms}` marker as an
  entire query parameter value; it cannot inject dynamic host/path segments.
  Custom templates and queries stay in the active page session only.
- Never render third-party HTML in an iframe or via `innerHTML`.
  Evidence drafts use `value` for inert text, without auto-committing or
  altering an existing human judgment/audit trail.
- No search history is persisted by NEXUS's application code. Browser or
  external search-provider history/cookies are outside that guarantee.
- The original Rust gateway, protected Railway host and Railway volume are
  neither read nor mutated by this static browser component.
- Search results and user-supplied excerpts remain **unverified**.
  `A_out <= A_in` is preserved: external content is not decision authority.

## Acceptance and deployment

`scripts/build-ui-languages.py --check` must verify the source embedded
web-research module, bilingual complete 429-message catalogs and the matching
public service-worker SHA-256. `node --check web/web-research-core.js` must
pass. `scripts/test-web-research-browser.py` exercises synthetic URL
construction, Unicode query isolation, confirmation and cancellation, 8 unsafe
custom templates, HTTPS URL safety, manual source draft boundaries, secure
external link attributes, language switching, no workspace mutation,
no automatic requests and no local plaintext persistence in *real Chromium* on
two layouts. These tests deliberately stub third-party navigations, so they do
not claim external search engine uptime or actual third-party results.

Require all exact-head CI checks to pass before a reviewed merge; then
manually deploy *only* the existing static Render site at the merged commit
and run separate public HTTPS byte-identity, real Chromium and actual offline
reopen acceptance before making a public-rollout claim. No new paid service,
unattended permissions, Rust production mutation or release seal.
