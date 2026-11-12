# Pilot 10 — Real public-origin browser acceptance (synthetic and read-only)

## Why this step

Pilot 11 is actually hosted at https://nexus-offline-pilot.onrender.com/ .
Prior `scripts/verify-public-static-pilot.py` established only **public HTML identity**;
`scripts/test-offline-pilot-browser.py` exercised **file://** under Chrome.
Those are independent proofs, but neither alone demonstrates that **real Chromium
loaded and interacted with the production HTTPS origin**. This step closes that
*browser-delivery* evidence gap without any private authenticated Rust deployment.

## Actual test contract

`.github/workflows/pilot-10-public-browser.yml` runs with **GitHub-hosted
disposable Chromium** at narrow and wide viewports, on manual dispatch, relevant
script changes and a once-weekly read-only schedule (Monday 06:23 UTC).
The workflow:

1. Requires checked-out standalone HTML to match exact previously published
   source `ed13887699b49a8494a3178e426ad9192e14d57e`.
   **Source candidate != deployed code** must fail, never be silently promoted.
2. Independently GETs the exact public URL without redirects or credentials,
   checks HTTP 200 and `text/html`, then requires byte-for-byte SHA-256 match
   with the pinned deployed HTML and CSP/schema markers. Node repeats the
   same check before launching Chromium.
3. Launches fresh headless Chrome profiles with **no user browser data**,
   remotely debugs them only over `127.0.0.1`, visits the actual HTTPS URL,
   observes real browser `Document` responses, fetches a genuine Chromium
   network response body, and checks its SHA-256 against source.
4. Injects the **same synthetic JavaScript witness already used by the
   isolated 46-check acceptance suite** via DevTools, not by editing the
   deployed site. Its synthetic exercise includes one-click fictional onboarding,
   refusal to overwrite, external-source validation, optional AES-GCM
   encrypted file/checkpoint, wrong-password and tamper rejection, actual
   page reload with password re-entry and explicit user judgment semantics.
5. Rejects unexpected browser HTTP(S) requests and non-GET methods; only
   the exact initial/reloaded document and a browser-internal same-origin
   favicon request are allowed. Reports zero attempted app-side fetch/XHR,
   two successful HTTPS document loads, and a strict source hash.
6. Destroys each temporary browser profile. Artifacts contain only labels,
   counts, hashes, source identity and boolean claims, **no workspace JSON,
   plaintext synthetic export, credentials or real user information**.

The six local negative fixtures reject non-200/redirect/MIME/body drift
and unexpected network hosts and POST requests. The app's CSP must continue
to deny external connections. No production API call is issued by this test.

## Evidentiary boundary and fail-closed gates

- **PASS means:** an independent CI runner actually loaded the published HTTPS
  page in two real Chromium viewport classes and completed the fully synthetic
  46-check local workflow (including actual browser document reload), with
  source bytes and network behavior checked.
- **PASS does not mean:** real Android hardware acceptance; actual person
  acceptance; availability SLA; accessibility audit; multiuser identity;
  authentic evidence provenance; a Rust gateway session; an original Railway
  volume export; recoverability from an off-host production backup; permission
  to start/restart/redeploy the original Railway data service; a new Release or
  Seal. `A_out <= A_in`.
- Browser-installed extensions, compromised OS or hostile hosting scripts can
  still read data while decrypted. Browser-local checkpoints do not substitute
  for user-held encrypted export or independently recovered production data.
- This is read-only as to *servers*. The only writes are harmless synthetic
  in-memory/browser-profile actions, erased along with the ephemeral CI profile.
- GitHub Actions quotas are provider-dependent; the once-weekly schedule is
  intentionally low frequency. No new paid account, provider service, storage
  volume or monthly subscription is created.

## Production recovery blocker (not bypassed)

The original Railway service `nexus-stage-d` remains pinned to source
`3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`, with the original
volume `cc47a350-6c7e-4487-89d9-c4b390f94884` attached at `/data`.
The connected provider surface exposes the attachment but **not** actual
volume files, off-provider backup or recovery-key contents. Earlier operator
research recorded an expired trial, no available existing snapshot, and
potential paid backup requirements; the current billing/backup state must be
revalidated before any mutation.

Do not assert an independently restorable original-volume backup on this
evidence. The authenticated human pilot is still tracked in
[Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70).
The historical runtime-observability [Issue #66](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/66)
has been **closed for the observability milestone**, not because all backing
data recovery requirements were satisfied.
