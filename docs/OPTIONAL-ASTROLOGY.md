# Optional project astrology and personal transits

NEXUS Studio can explicitly retrieve numerical planetary positions from the public
[On-line Astrology Positions API](https://app.on-lineastrology.com/api/), compare
transiting positions to natal positions locally, and optionally personalize its
local reflection guide or a reviewed model request. Nothing runs on page load.
A real generative model is still not provisioned by this feature.

## User workflow

1. Create/select a project. Open **Optional astrology & personal transits**.
2. Enter a Gregorian birth instant with an explicit historical UTC offset, such
   as `2000-01-01T16:30:00+04:30`, or its already-converted UTC value. Confirm that
   the time/offset is known. The sample is synthetic, never a user's default.
3. Review the exact natal request URL, then separately approve sending it once.
   Inspect the preview and apply the profile to the current project.
4. Select the transit instant, or choose current UTC; review and approve that
   separate request, inspect the contacts and apply the updated profile.
5. Turn on **Include the applied profile** for the next guide/model request.
   Model use still requires the normal exact-context review and send approval.
6. Explicitly save the session to retain the profile in the encrypted archive.
   Unapplied astrology previews block session save/export rather than being
   silently omitted. Remove the profile to stop future inclusion.

Changing project, locking or reopening an archive resets the personalization
checkbox to off. Data retrieval, applying a profile and personalizing a response
are distinct decisions. Declining any step does not quietly opt into another.
A raw JSON response from this API can also be imported locally, with the exact
instant checked; it remains marked **import**, not independently verified/live.

## Provider and numerical contract

Only this fixed HTTPS API host/path and ten fixed body codes are requested:
Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune and Pluto.
The two query parameters are `dt` (normalized UTC) and `bodies`. No name,
coordinates, conversation, memory, gateway token or project ID is added.
No cookies/credentials/referrer are sent, redirects are rejected, responses are
capped at 128,000 bytes and UI waiting time at 20 seconds. Only exact matching
instants, apparent geocentric ecliptic-of-date **tropical** coordinates, ten
unique known bodies and finite bounded numerical values are accepted. Errors
leave the applied profile intact; no alternate provider is contacted silently.

The provider sees the caller's IP and requested instant; GET URLs may enter its
logs. Attribution/documentation links remain visible. Calls are manual one-shot
calculations, with no background polling, bulk scraping or automatic per-message
refresh, respecting the provider's documented individual-request purpose.
Availability/CORS may vary; development observed HTTP 200 and CORS `*` for two
synthetic/reference instants. Other investigated APIs returning 403 were not
added as allegedly working connections.

The supported input range is 1900–2050 UTC. NEXUS does not guess an unknown birth
time, resolve historical daylight saving, convert Persian calendar dates, obtain
GPS coordinates, or infer a birthplace. Explicit offsets avoid silently using
the browser's timezone. This geocentric feature needs no coordinates; therefore
it does not calculate houses, Ascendant, MC, relocation, topocentric positions,
sidereal ayanamsa, dasha, asteroids or compatibility charts. Other providers or
formats require a reviewed adapter rather than parsing arbitrary website HTML.

The local contact engine uses shortest circular angular separation and the five
major angles 0°, 60°, 90°, 120°, 180°, with a user-selected orb of 0.25–5°.
It compares each transit body to fixed natal longitudes. Applying/separating is
the instantaneous angular-error derivative using the transit body's daily speed;
it is not an exact event-time/station search. The full contact list is visible;
model context takes the closest 20 by orb and reports omissions. Ranking by orb
is a display convention, not an evidence-based probability or significance score.

## Personalization and persistence

The optional `nexus.astrology.v1` record belongs to one Studio project and is
validated during archive import and state mutations. Its snapshots retain the
provider, zodiac, instant, retrieval time, acquisition kind and normalized
positions. Existing projects without this optional field retain their format.
Use a current Studio version to preserve this field; older clients that ignore
unknown fields are not suitable for editing these new profiles.

The profile is tab-only until explicitly saved/exported using the existing
AES-GCM/PBKDF2 archive. Deleting a profile updates the working project; explicitly
save again to update its persisted archive. Old transcripts, encrypted backups
and any earlier provider submissions are not erased by deleting this record.
Locking clears fields, previews, results and selections and discards late replies.
The records are not signed ephemeris certificates.

With personalization off, no profile is inserted into the model context and the
local guide remains neutral. The model context explicitly states that astrology
personalization is off, including for prior astrological passages. Earlier chat
text is still visible in the normal reviewed conversation path; turning off the
feature is not a promise to erase history. With personalization on, exact birth
time and location are omitted from the outgoing profile context, while selected
transit time, numerical positions and contacts remain personal data. The user
can inspect them before approving any model transmission.

The working local guide uses actual computed contacts with labeled symbolic
prompts and asks for direct observations and user values. It does not pretend to
be a free-form model. The optional model policy distinguishes numerical positions
from astrological interpretation and does not use astrology to diagnose or replace
evidence-based decisions. Interpretations are symbolic, not established causal
facts or guarantees about another person's intentions or future events.

## Verification

- 70 contract/state/crypto checks cover ISO dates and explicit offsets, leap dates,
  matching frame/time, invalid or missing bodies, byte/privacy bounds, circular
  separation, near-exact applying direction, stale/future-mode consent, omission
  of birth time, default-off context, encrypted round trip and record removal.
- Existing 44 Studio state/crypto and 31 research/chart checks pass locally.
- 28 model bridge tests pass locally; model replies in these tests are synthetic.
- Real development HTTPS responses for 2000-01-01 12:00 UTC and
  2026-11-13 12:00 UTC each parsed ten bodies successfully.
- A single independent JPL Horizons Sun comparison at JD 2451545.0 UTC gave
  280.3689092°, versus provider 280.36891867°: difference 0.00000947°. The stored
  reference is one numerical check, not full ephemeris validation or evidence
  supporting astrological interpretations.
- Dedicated real Chromium narrow/wide acceptance tests the actual UI, explicit
  requests, cancellation, neutral/personalized local guides, reviewed synthetic
  model transport, encrypted profile save/reopen, deletion, cross-project
  isolation and Persian labels. Network responses in browser CI are fixtures;
  those checks must not be described as live provider/model availability tests.

Primary documentation:
- https://app.on-lineastrology.com/api/?lang=en
- https://app.on-lineastrology.com/api/openapi.json
- https://ssd-api.jpl.nasa.gov/doc/horizons.html
- https://ssd.jpl.nasa.gov/horizons/manual.html

## Offline engine follow-up

The [offline sky module](OFFLINE-SKY-TONE.md) adds explicitly selected local natal/transit calculations, with `computed` provenance and a pinned bundled engine. Its general non-personal tone setting is separate from this document's opt-in natal feature. No website request is needed for that local path.
