# Pilot 15 — English-first, extensible interface languages

The public standalone NEXUS workshop defaults to **English**, regardless of
browser language. English is also the manifest language and installation name.
The existing Rust browser client was already English; this milestone changes
the independently deployed static workshop, not the protected Railway host.

Choose **Interface language** to switch between complete English and Persian
catalogs. Direction changes between LTR and RTL. Input fields and workspace
text use their own automatic text direction. This changes interface labels,
validation/confirmation messages and report headings only. Existing question,
evidence, source identifiers, alternatives, judgments, drafts and passwords
remain byte-for-byte unchanged. No language event enters the workspace audit.
An open report gets new headings with the same committed content. Language
changes do not trigger encrypted-vault saving.

## Any additional language through a complete local pack

**Load a translation** accepts a local JSON language pack. There is no fixed
language whitelist. A canonical BCP 47 locale (including a private-use tag such
as `und-x-custom`) and explicit `ltr` or `rtl` direction support languages not
in the initial selector. Unicode text is retained. A pack supplies all **277**
interface messages and the exact English source-catalog SHA-256, preventing
partial or stale packs from silently mixing safety-critical meanings.

**Download English translation template** creates a file containing interface
text only, never workspace data, drafts or passwords. Translate its message
values, set locale/name/direction, retain its schema/source hash/keys, then
load the file. `web/locales/en.json` and `fa.json` are canonical reviewed
built-ins. Built-in English/Persian cannot be overwritten by an imported pack.
Custom packs are marked unreviewed, and English remains selectable.

This is an extensible translation mechanism, **not** a claim that ready-made,
reviewed translations already exist for every world language. Only English
and Persian are bundled in this milestone. No automatic translation API,
network request, translation account or new provider cost is introduced.
Language selection and imported packs last only for this open page; reloading
returns to English and custom packs must be loaded again. No new persistent
language or plaintext workspace store is created.

## Inert data and privacy

Pack size, root fields, catalog version/hash, locale, direction, exact keys and
string lengths are validated before activation. Malformed, incomplete, stale,
reserved-locale or oversized packs leave the interface/workspace intact.
Labels use textContent and safe attributes, never HTML or executable templates.
Inputs and private workspace views have `translate="no"` as an additional
browser hint; the app never invokes browser or external translation services.
User-controlled browser features remain outside the app's control.

## Acceptance and deployment

`build-ui-languages.py --check` verifies complete matching catalogs and the
embedded standalone copy, plus the exact worker HTML hash. Existing Persian
behavior witnesses now explicitly select Persian; a distinct English-first
witness tests default English, both directions, Unicode work preservation,
localized reports, inert custom labels, invalid packs, an unlisted locale,
secret-free template export, no network, and unchanged active ciphertext.

The installable app embeds both catalogs, retaining file:// and real offline
operation. Public identity, public-origin language behavior and offline
navigation require independent acceptance after deployment. No original
Railway access, new paid resources, automatic judgment or release Seal.

## Public promotion — 2026-11-12

All nine PR #117 workflows succeeded for exact head
`706e61de8da191123603a24c24f1302d105a6a64` before merge. Source
`795e1b3371b0674ee0d3abcdd9fd57ce27813cc1` was published on the existing
static site, Render deployment `dep-dbqr5nmi0phs73dggik0` reporting LIVE.
The public observers pin that source and separately check exact public assets,
English-first language behavior, Persian legacy workflows, and actual offline
reopening. Public language tests use synthetic Arabic/private-use packs only
to verify loading and direction; they are not bundled reviewed translations.
No real Android-device acceptance or real user-data translation is claimed.
