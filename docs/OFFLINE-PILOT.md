# NEXUS Offline Pilot — a usable single-file mobile prototype

**Scope:** offline, one-person decision-structuring prototype; no Rust engine,
public static HTML only, no authorization, no automated machine decision, no
provider-backed persistence. This is not a production deployment or an
authenticated single-host NEXUS service.

## Use from an Android phone or desktop

The file is [web/offline-pilot.html](../web/offline-pilot.html). Download **the
HTML file itself** from the repository and open it in a browser capable of
running local HTML. A code preview is not the app; a rendered offline file is.
The independently verified public static entrypoint is
https://nexus-offline-pilot.onrender.com/ . Render reported LIVE for Pilot 11 deployment
`dep-dbqooirrjlhs73a1cvdg` on source commit
`ed13887699b49a8494a3178e426ad9192e14d57e`; the independent
static HTTPS observer checks exact bytes. This is not an authenticated
Rust service.

1. In Pilot 09, optionally choose **آزمایش با نمونهٔ ساختگی**
   for a one-click fictional example with no human judgment, then **کارگاه جدید**
   to clear the demonstration. See [Pilot 09](PILOT-09-GUIDED-FIRST-RUN.md).
   Otherwise, enter a real question, a goal, constraints and values;
   press **ثبت مسئله**.
2. Record externally sourced claims with source identifiers and uncertainty,
   options with possible consequences, and review them independently.
3. Only your click on **ثبت تصمیم من** can create a human judgment.
4. Prefer **دریافت نسخهٔ رمزگذاری‌شده** with a unique 12+ character
   passphrase entered twice. Keep the protected downloaded file in private
   storage and the passphrase separately; without the passphrase the file
   cannot be recovered. **خروجی JSON بدون رمز** needs explicit confirmation
   and creates readable plaintext — it is not a protected backup.
5. Later, enter the protected file passphrase first, then select
   **بازکردن فایل قبلی**. Both original plaintext offline v1 and the new
   authenticated encrypted envelope can be opened; corrupt files and wrong
   passphrases leave existing data unchanged. See
   [Pilot 03 private exports](PILOT-03-PRIVATE-EXPORTS.md) for the exact
   format, threats and limitations. An **explicit opt-in encrypted browser checkpoint** can preserve committed work across reloads on the same browser, if local storage is available. It is distinct from and less portable than the downloadable protected file; it has no server backup. See [Pilot 08](PILOT-08-ENCRYPTED-LOCAL-RESUME.md).

Before relying on an encrypted export, use **آزمایش بازیابی فایل دانلودشده** (Pilot 11): select the actual file from Downloads and re-enter its passphrase. The app checks decryptability/structure and reports exact current-state equality, valid-but-different content, or rejection. It does not import or modify the active workspace. This is not a full Railway backup or proof of off-device custody. See [Pilot 11 recovery check](PILOT-11-VERIFIED-ENCRYPTED-EXPORT.md).

The original offline JSON files are not Rust gateway-compatible
`nexus.data-snapshot.v1` or server `DecisionWorkspace` backup; do
not import it through the production workspace restore endpoint or represent it
as an independent Railway volume backup. It lacks the request ledger,
gateway authentication, cryptographic audit checks and provider continuity.

## What the file can and cannot do

The page is a dependency-free Persian RTL HTML document with a restrictive
Content Security Policy, no image or network requests, and
explicit export/import. Pilot 08 source only writes encrypted local browser
storage after the user's explicit opt-in; without that consent, the app remains
memory-only. It displays user-supplied strings as text rather than
injecting HTML, validates source requirements for external evidence, enforces
bounded form/input limits, and tracks a basic event history. The history is
**not cryptographically attested** and cannot be treated as independent
provenance, historical proof, an authorized request, or proof of recovery.

The core constitutional principle remains: evidence does not become authority,
machine notes do not become human judgment, and execution authorization is not
present in this demo (`A_out <= A_in`).

## Real-browser verification

`python3 scripts/test-offline-pilot-browser.py` opens the unmodified product
in real headless Chromium at a narrow and a wide viewport, in private temporary
profiles. It checks question/goal/constraints, missing-source rejection,
escaped evidence, non-authoritative machine analysis, options, explicit
judgment, plaintext/export compatibility, WebCrypto AES-GCM encryption,
nonce/salt randomness, wrong passphrase and tamper rejection, encrypted
restoration, corruption rejection, opt-in encrypted browser checkpoint,
deliberate deletion, and an **actual document reload** followed by password
re-entry; zero network calls. The program exercises only synthetic user content; CI never
receives real personal data, operator tokens, or Railway resources.

The test report means **only a standalone file prototype was exercised**.
Actual Android hands-on usability, server data durability, public GitHub Pages,
a production-authenticated session, independently verifiable provider backups
and multiuser privacy are not proven.

## Next verified decision

The hosted product remains the actual NEXUS Rust/browser stack described in
[the first-user acceptance contract](PILOT-01-FIRST-USER.md). Offline use is an
interim, no-cost access path, **not** permission to restart/deploy the original
Railway service with an attached production volume. Use Issue #70 to track the
real-host pilot and restore/backup gaps. No paid services are required for the
offline HTML or its standard public-repository CI tests.
