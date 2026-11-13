# Stage 29 — Human-steered multi-source research dossier

**Not autonomous ChatGPT Deep Research.** This is an explicitly approved
multi-query provenance notebook on the development NEXUS gateway.
It reuses the existing POST /v1/research-chat source provider boundary.
There is no model inference, arbitrary crawler, browser navigation agent,
server-side database, account login or new network host.

## Actual behavior

1. Open /research-workbench on an authenticated NEXUS development gateway.
2. Enter the gateway token (not saved), research question, and exactly one
   public search query, then approve that query only.
3. Search once; NEXUS supplies bounded excerpts from configured Wikipedia
   and DuckDuckGo Instant Answers adapters. Only the approved query and
   selected language leave NEXUS for the search providers; the top-level
   question is sent to the NEXUS gateway only.
4. Inspect each returned source title, HTTPS URL, provider, origin, excerpt,
   and retrieved date (never misidentified as publication date).
5. Repeat separately approved searches up to four times. Consents are
   consumed at dispatch; no automatic provider call or repeating search.
6. Add your own interpretations and contradictions. Download an explicitly
   confirmed UNENCRYPTED Markdown report, with source URLs, original query,
   source IDs, uncertainty and provider-status fields.

No automatic data/token persistence. Token change or Clear removes the
in-tab dossier, cancellation invalidates late replies. Errors never
fabricate sources, conclusions or statistical confidence.

## Limits and security

- Four user-approved searches, not autonomous multistep inference or
  independent fact-checking.
- Query max 250 Unicode characters, question max 1000.
- Existing gateway auth-before-body, response no-store, bounded provider
  fetches, rate limits and offline/production separation retained.
- Accepts only schema nexus.research-chat.v1 with authority none and
  judgment_changed=false. At most eight source records per query.
- HTTPS external URLs are checked before linking, with no internal host,
  IP-literal, HTTP, embedded credentials or nonstandard port.
- Excerpts and source text display as inert DOM text, not executable HTML.
- Sources keep provider/origin metadata and retrieval timestamps.
- Sources and user notes are exported as plaintext Markdown, never hidden
  gateway credentials or workspace secrets.
- English/Persian support, RTL direction, explicit per-query approval.
- Not bundled into the zero-INTERNET Android APK; gateway-only tool.

## Tests and nonclaims

Real Chromium test: scripts/test-stage29-research-workbench-browser.py
validates narrow and wide viewports, separate consent, no auto network,
hostile URL/markup rejection, cancellation, source attribution,
report export and bilingual UI using synthetic mock data.
This does not prove public-provider availability, source authenticity
or ChatGPT-level Deep Research. No Railway or Render mutation,
paid account, or GitHub Pages activation. Human final judgment remains
human and A_out <= A_in.