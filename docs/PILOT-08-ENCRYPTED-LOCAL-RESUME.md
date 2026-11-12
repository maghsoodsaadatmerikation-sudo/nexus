# Pilot 08 — opt-in encrypted local resume (candidate; not production promotion)

## Problem and safety boundary

The public free static pilot is an ephemeral browser decision workspace: closing its tab can lose everything since the last explicit export. Pilot 08 adds a **separate, opt-in browser-local encrypted checkpoint** as a usability bridge for Android users without a computer, server or paid account.

This does not touch the Rust gateway, original Railway service/volume, original host, credential scopes, historical release/Seal, provider backups, or human decision authority. `A_out <= A_in`.

## Exact scope

- No browser storage is used at all before the operator explicitly enables local resume **after a question has been registered**.
- The operator sets and confirms a 12–256 Unicode-character passphrase. Browser WebCrypto derives a nonextractable AES-256-GCM key via PBKDF2-SHA-256 (310,000 iterations, fresh 16-byte salt). The passphrase is cleared from the form; no passphrase, derived key or plaintext workspace is stored in localStorage.
- Each **committed change** generates new AES-GCM ciphertext using a fresh 12-byte IV, authenticated with the distinct schema `nexus.offline-pilot.local-encrypted.v1`. Only metadata, salt, IV and ciphertext are stored. Unsubmitted form drafts are not backed up.
- Saves are serialized in order. A generation counter cancels queued old-workspace writes after starting a new workspace, pausing or deleting the checkpoint. A storage/quota failure disables subsequent autosave and tells the user to export an independent protected file.
- On reload the key is gone; a passphrase is required to authenticate, decrypt and fully validate the stored v1 workspace. Wrong passphrases, tampering and invalid structure do not replace active work. Deleting the local checkpoint requires a separate explicit confirmation.
- Starting a new workspace pauses autosave but **preserves the previously encrypted checkpoint**; this prevents an empty new workspace from silently destroying the last checkpoint. An operator may deliberately enable a new encrypted checkpoint, with explicit overwrite confirmation.
- The pre-existing downloaded encrypted JSON export/import remains separate, with a different schema and key derivation. It is still the recommended user-controlled backup.

## Recovery and privacy limitations

1. The browser origin, profile and its localStorage quota determine availability. Private tabs, browser cleanup, phone loss, or switching URLs/devices may destroy local data. No promise of cross-device sync or permanent backup is made.
2. Browser JavaScript necessarily sees the **decrypted workspace while open**. Device compromise, modified hosting JavaScript, extensions and keylogging are out of scope. This feature does not make clinical or other high-risk entries suitable for shared devices.
3. PBKDF2 does not make weak passphrases unguessable. A wrong key produces an authentication error with no fallback to plaintext.
4. Browser-only checkpoints are not independent evidence, authenticated provenance, original provider Volume data, a restorable production backup, a verified Rust audit, human acceptance, or Seal.
5. No background tab/OS scheduling reliability is promised. Wait for the explicit encrypted checkpoint confirmation and continue exporting files at major milestones.
6. The public Render static service has `autoDeploy=off`. **Do not describe the feature as available at the public URL until a reviewed candidate has been explicitly deployed and independent HTTPS exact-byte identity revalidated.** A merge without promotion can make the main-branch static identity observer fail.

## Verification and release gate

`python3 scripts/test-offline-pilot-browser.py` uses real Chromium in mobile and desktop viewport classes with disposable profiles and fully synthetic workspaces. It checks opt-in-only storage, absence of plaintext/key in stored JSON, authenticated restoration, rejection of wrong keys and tampering, pause-on-new, no unexpected overwrites, explicit deletion and zero network calls.

Release sequence: required PR checks SUCCESS on exact head; independent review; explicitly promote this source to the **existing** Render static service only when authorized; verify exact public HTML hash and browser acceptance; update main/reference provenance only with observed evidence. Do not deploy/modify Railway to ship this feature. Issue #70 (authenticated first-human gateway pilot) and #66 (original-volume recoverability) remain open.
