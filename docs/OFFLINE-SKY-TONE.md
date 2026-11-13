# Offline sky calculations and general presentation style

Studio bundles the unmodified MIT-licensed Astronomy Engine 2.1.19 by Don Cross.
Its code and coefficients are served inside the standalone HTML: no CDN, API,
provider key, browser geolocation or user birth profile is needed at runtime.
After the page has been obtained, the calculation/guide path can run offline.
This is numerical local computation, not an LLM guessing planetary positions.

## Source and numerical framework

- Upstream source: https://github.com/cosinekitty/astronomy/tree/v2.1.19
- File: `source/js/astronomy.browser.min.js`, copied into `web/vendor/` unchanged.
- SHA256: `f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6`.
- Original MIT notice is retained in the code/bundle and a separate license file.
  The deterministic builder verifies the exact vendor hash. No upstream code is
  loaded dynamically, and no Swiss Ephemeris AGPL code is incorporated.

For ten bodies, the adapter evaluates `Ecliptic(GeoVector(body, date, true)).elon`:
Earth-centered, light-time/aberration-corrected true ecliptic of date, expressed
as tropical longitude. It is an approximate ephemeris, not a byte-identical
replacement for Swiss Ephemeris/JPL. Longitude speed uses a centered one-hour
finite difference with circular wrapping. Offline natal/transit buttons use the
exact explicitly offset-qualified input instant, retain `computed` provenance
and keep the existing apply/store/personalization choices separate. Existing live
and imported profiles remain readable; local snapshots are labeled with their
own engine rather than falsely attributed to a website.

General style uses device UTC and one cached five-minute bucket. Returned data
are copied so callers cannot mutate the shared cache. The cache contains only
public general sky data; arbitrary natal calculations do not enter that cache.
Missing engine, unsupported clock/range or a computation failure yields ordinary
neutral style, with no invented sky state. Inputs remain bounded to 1900–2050
through the existing instant validator. Houses, Ascendant, MC, sidereal systems,
exact event searches and a full time-zone/DST resolver are still out of scope.

## Explicit editorial rule

This is an owner-selected creative style heuristic. Planetary configurations do
not establish a user's feelings, personality, diagnosis, intentions or outcomes.
The computation and the heuristic are separate functions, allowing inspection,
unit testing or replacement of the style rule without altering the ephemeris.

The fixed mapping is:

| Condition | Presentation preference |
| --- | --- |
| Moon's tropical sign in fire / earth / air / water group | Measured encouragement / practical steps / clarity / restrained warmth |
| Mars–Saturn or Moon–Saturn within 3° of conjunction, square or opposition | Calm, patient wording takes priority |
| Otherwise Venus–Jupiter within 3° of conjunction, sextile or trine | Restrained warmth |
| Mercury daily longitude speed negative | An extra preference for precise wording and a useful ambiguity recap |

These associations are editorial choices, not validated psychological or causal
rules. They never set probabilities, confidence, diagnoses, facts, advice,
recommendations, user beliefs or external actions. Explicit user tone/language/
format preferences and the question take priority. The local reflection guide
only adds a brief stylistic opening; its complete ordinary guide text is retained.
For a model, a bounded presentation instruction is inserted into the reviewed
context; an instruction is not a proof of a model's behavior or factual fidelity.

## Quiet replies, visible controls

General tone adaptation defaults on for Studio users in the current tab, as
requested by the owner. It is independent of personal natal personalization,
which remains off by default. The local-sky settings show the mechanism, expose
its current numerical calculation and rule, and provide an off switch. Turning
it off invalidates a prepared model-send approval and restores ordinary style.
The setting is tab-scoped, not silently stored in a project or an account.

Replies do not append an astrology announcement or tone-provenance paragraph.
The model receives only the chosen presentation instruction, not general sky
coordinates or personal birth information for this general feature. Its exact
review displays style mode, calculation instant and engine identifier; the
instruction requires candid answers if the user asks how tone is selected.
Nothing promises to conceal the mechanism from settings or to give a false
explanation. Explicitly requested personal astrology remains a separate feature
and may still include its requested symbolic report in the response.

## Verification

- The bundled engine was compared with 20 previously captured provider positions
  at J2000 and 2026-11-13 12:00 UTC. Observed maximum longitude difference was
  about 0.003361°; all are below the regression bound 0.01°. Speed differences
  are below 0.001°/day. These two instants are not full-range certification.
- The single existing JPL J2000 Sun reference differs by about 0.000171° from
  this engine. It is a numerical check, not evidence for astrology meanings.
- 78 new offline checks cover vendor integrity, actual calculations, reference
  bounds, copy-isolated cache, explicit style rules, disabled/missing-engine
  fallback, unchanged local guide content, no birth-data inclusion, local profile
  normalization and zero fetch calls in the computation path.
- Dedicated real Chromium acceptance blocks website fetches while computing
  natal/transit charts and generating neutral/adapted local guides. It also
  exercises opt-out, exact-context approval invalidation, no automatic astrology
  announcement, Persian labels and synthetic model transport. Model output in
  that test is a fixture, not evidence about a real model's reasoning quality.
- Existing Studio, personal-astrology, code-sandbox and gateway checks remain
  required before release. A real generative model is still not provisioned.
