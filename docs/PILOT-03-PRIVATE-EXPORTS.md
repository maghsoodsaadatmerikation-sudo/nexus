# Pilot 03 — private, passphrase-encrypted offline exports

## Goal and product boundary

The public static pilot at https://nexus-offline-pilot.onrender.com/ is a
client-side decision workspace. It has no user accounts, server-side storage,
remote backup, data recovery service, signature or attested judgment. Pilot 03
protects **downloaded JSON content at rest** through optional passphrase
encryption and keeps explicit compatibility with the original offline exports.

It does not modify the existing Rust gateway, original Render Docker service,
or Railway's existing persistent volume.

## User workflow

1. Fill a question, claims, alternatives and (optionally) an explicit human
   decision. Nothing is sent to the server by the app. Unsaved browser state is
   lost on page reload.
2. Choose a **unique, long passphrase** (minimum 12 Unicode code points) and
   enter it twice in the "نگهداری امن‌تر فایل خروجی" section.
3. Choose **دریافت نسخهٔ رمزگذاری‌شده**. Save the resulting
   `nexus-protected-offline-....json` file privately, ideally separate from
   the passphrase. No plaintext JSON is created by this action.
4. To restore, enter the passphrase in **گذرواژهٔ بازکردن فایل رمزدار**, then
   click **بازکردن فایل قبلی** and select the protected JSON. The app decrypts,
   validates the offline workspace and only then replaces the current data
   (after a replacement confirmation when applicable). A wrong passphrase,
   tampered ciphertext, or invalid workspace leaves the current data unchanged.
5. The old plaintext `nexus-offline-....json` files continue to import as
   before. To download **new unencrypted JSON**, the user must deliberately
   click **خروجی JSON بدون رمز** and confirm the warning. Such files contain
   all entered text readable without authentication.

The passphrase cannot be reset, recovered or retrieved by NEXUS; losing it
means the encrypted file cannot be opened. Private browsing, Android download
permissions, lost devices, malware, guessable passwords, clipboard leakage,
screenshot capture and untrusted browsers remain threats.

## Precise encryption wire format

- Outer envelope schema: `nexus.offline-pilot.encrypted.v1`, distinct from
  plaintext `nexus.offline-pilot.v1`.
- Key derivation: Web Crypto API PBKDF2 with SHA-256, 310,000 iterations and
  a freshly generated 16-byte random salt on *every* export.
- Encryption: non-extractable AES-256-GCM key, fresh independent 12-byte
  random IV per export, 128-bit authentication tag, and fixed schema value
  as authenticated additional data.
- Ciphertext includes serialized full v1 offline workspace; the outer
  unencrypted JSON contains only encryption metadata and ciphertext, **not**
  the question, claim, decision or passphrase.
- Base64 is canonical and checked; exact known algorithm IDs, sizes and
  iterations are required when importing. Max encrypted file 450 kB;
  decryption and JSON validation are bounded. Missing WebCrypto/secure context
  fails closed — no automatic fallback to unencrypted export.
- The cleartext plaintext-export option remains explicitly available for
  compatibility and is **not** a secure copy.

Web Crypto is available in modern HTTPS contexts and may be available in
secure local-file contexts on some browsers. Unsupported browsers receive a
clear failure, not weakened cryptography.

## Reproducible evidence and self-critique

The existing `scripts/test-offline-pilot-browser.py` exercises real headless
Chromium in two viewport classes, using only synthetic data. Added assertions
cover too-short/mismatched passphrases, AES-GCM envelope metadata, exclusion of
plaintext/secret from the encrypted file, randomized salt/IV across exports,
failure on absent/wrong passphrases and tampered ciphertext, successful decrypt,
re-import and preservation of previous plaintext import/export and
non-authoritative decision rules. Runs do not upload or publish personal
workspaces, passphrases or generated ciphertext.

Security limitations and remaining gates:

1. **Strong cryptography does not protect weak passphrases.** PBKDF2 slows
   offline guessing but cannot prevent it. The tool cannot enforce password
   entropy, detect compromised phones or block local file copying.
2. **The page is delivered by the hosting provider.** A compromised future
   delivery of JavaScript could steal future passphrases or workspace contents
   even with correctly used AES-GCM. Static autoDeploy remains disabled and
   source identity is observed independently, but that does not prove all
   future sessions or supply end-to-end code attestation.
3. **No automatic backup.** Encryption does not replace the need to save and
   protect the file. The app still stores current content only in page memory.
4. **No production recovery claim.** An encrypted single-workspace file is
   neither a full Railway `/data` backup nor a tested restore of the durable
   gateway. These gates remain open on Issue #70.
5. **No machine authority.** NEXUS does not choose options or approve
   decisions. A user-entered rationale or origin reference is not proof of
   source accuracy. `A_out <= A_in`.

Public promotion is controlled and manual: CI verifies the candidate on PR,
Render static site has autoDeploy OFF, and after merging the owner manually
deploys the reviewed commit. A separate read-only HTTPS identity job then
compares the public site bytes against that committed source.
