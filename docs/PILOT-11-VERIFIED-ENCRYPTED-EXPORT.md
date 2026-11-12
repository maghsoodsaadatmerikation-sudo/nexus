# Pilot 11 — owner-verifiable encrypted export (mobile, zero server authority)

## Practical problem and scope

A browser can create an encrypted JSON Blob and offer it for download, but
**creating the Blob does not prove that the file was saved, is present in
Downloads, can be decrypted, or matches the currently recorded workspace**.
This gap matters when the browser-local opt-in vault can disappear on Android,
device replacement or browser storage clearance.

Pilot 11 adds a **separate file-picker verification** on the existing standalone
HTML page. This is an explicit, local user action; it does not contact the Rust
gateway, change a workspace, create a server backup, or claim external custody.

## Human test sequence on mobile

1. Open `https://nexus-offline-pilot.onrender.com/` after its exact-source
   deployment is verified. Use a fictional test question or the one-click demo;
   avoid sensitive clinical or personal information for initial acceptance.
2. Record a question (plus claims, alternatives, and an explicit judgment only
   if desired) and choose a strong unique passphrase for
   **دریافت نسخهٔ رمزگذاری‌شده**.
3. Download the protected `nexus-protected-*.json` file, verify that the
   device/Downloads folder actually contains the downloaded file, and keep
   the passphrase separate.
4. In **آزمایش بازیابی فایل دانلودشده**, enter the passphrase and explicitly
   select that *downloaded file* via the browser's file picker.
5. Read the result:
   - **Exact match**: the selected encrypted file decrypted, passed the
     offline-v1 import validator and matched the **currently committed**
     workspace data. Unsaved form drafts are not compared.
   - **Valid but different**: the selected file decrypted and validated,
     but represents older content or another workspace. It is not a
     verified current backup.
   - **Rejected**: wrong passphrase, tampering, wrong schema, unsupported
     browser crypto or file-size/validation error. No contents or original
     workspace are changed.
6. The app clears the recovery password and file input after every completed
   attempt. A new encrypted export or a committed workspace edit invalidates
   the old match label. Keep a separate off-browser copy; the test is not a
   promise that a file or password will survive a later device failure.

## Security and implementation

- New action **only reads a user-picked file**, size-bounded at
  `MAX_ENCRYPTED_FILE`, decrypts with existing WebCrypto AES-256-GCM with
  authenticated v1 envelope, and checks using existing `validate()`. No new
  format, key, account, localStorage field, network, logging, hash disclosure,
  server write, or dependency is introduced.
- Does **not** assign `state`, trigger `render()`, fabricate audit records,
  leak a passphrase to the page URL, or change current judgment. The existing
  file **import** is a deliberately separate action and remains unchanged.
- Status is deliberately transient: proof is limited to a specific selected
  file, password, moment in time, and currently *committed* workspace; it is
  not an independent timestamped audit or evidence of origin.
- The browser test expands from 40 to **46 checks per viewport**. It selects
  ciphertext with a separate file input (not the original Blob), proves exact
  match and no mutation, rejects wrong keys/tampered/plaintext files, refuses
  to reuse a prior success after exporting newer ciphertext, and labels an
  older valid file correctly after a new workspace.
- Existing real Chromium offline test and synthetic disposable Rust bridge
  must pass in GitHub CI. Public live-browser Pilot 10 acceptance is pinned
  separately to the currently **deployed** source, and must be updated after
  independent public-byte verification of this version.

## Exact limitations

This helps one person establish **portable encrypted-file recoverability
from a copy already on their device**. It is not proof of off-device storage,
a successful download (until the user picks the actual file), current
server-side Rust workspace backup, full original Railway volume backup,
independent clean-host restore, authenticated human Rust use, production Seal,
or safety from device compromise. Existing zero-cost and human-authority
boundary `A_out <= A_in` remains unchanged.

Original Railway recovery remains tracked in
[Issue #104](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/104),
and first authenticated human pilot remains
[Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70).

## Deployment and exact-source evidence (2026-11-12)

The existing static Render service `nexus-offline-pilot` reported LIVE for
deployment `dep-dbqooirrjlhs73a1cvdg` at source `ed13887699b49a8494a3178e426ad9192e14d57e`,
after PR #105 merged with six exact-head checks passing. The independent
pinned HTTPS identity and real-Chromium live-run checks are maintained by the
following documentation/observer update; a provider LIVE label alone is not
independent content or Android-device acceptance.

The first non-cache-cleared deployment `dep-dbqolejbc2fs73e0mha0`
returned provider LIVE while the public GET still returned a different
SHA-256. The existing static service was redeployed with a cleared build
cache as `dep-dbqooirrjlhs73a1cvdg`; the independent exact-byte
HTTPS verifier then returned SUCCESS. Never equate provider LIVE with
observed public bytes or silently call failed static identity checks PASS.
