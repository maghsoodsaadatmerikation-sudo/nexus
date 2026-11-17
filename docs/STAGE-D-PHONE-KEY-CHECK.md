# Phase 39 — Offline owner recovery-key proof on Android/Termux

**Scope:** An independently downloadable, deterministic ZIP containing only the pinned **public Stage D recovery certificate**, the existing **key verification source**, a shell launcher and plain-language instructions. GitHub Actions uses a genuine ephemeral RSA keypair only for synthetic acceptance; the package **does not contain any private key** and does not read the original Railway Volume.

## Purpose and real remaining dependency

The manual encrypted Stage D capture workflow requires the owner to honestly confirm `I VERIFIED MY STAGE D RECOVERY KEY LOCALLY`. Its existing verifier `scripts/verify-stage-d-recovery-key.py` can encrypt a fresh random CMS challenge to the pinned public certificate and prove that a separately owner-held private key really decrypts it. Previously, running this from a phone required a full Git checkout and extra implementation dependencies. This phase publishes a two-file public-only verification kit for a user with a trusted private Termux installation.

**An owner with no matching private key must STOP.** Creating a fresh RSA key does not make it match the Stage D certificate already pinned into the existing encryption workflow. A synthetic CI keypair never counts as owner possession of the actual key. Ask the legitimate key custodian to recover the originally generated matching key through an approved private channel; never paste any private key into ChatGPT, GitHub, Railway, CI, or a web page.

## Obtain the package

1. In the repository open [Actions / NEXUS Stage D Owner Phone Keycheck Kit](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/stage-d-phone-key-kit.yml) and select a **successful run on `main`**. The ZIP is available as the artifact `nexus-stage-d-owner-phone-keycheck`, together with its SHA-256 sidecar. The workflow's exact source SHA and upload run establish the audited distribution context; an internal manifest is **not an independently signed attestation**.
2. Download the public-only artifact on the phone and extract the inner `nexus-stage-d-owner-phone-keycheck.zip` to a trusted private Termux directory. The ZIP contains exactly `docs/keys/stage-d-recovery-public-cert.pem`, `scripts/verify-stage-d-recovery-key.py`, `run-keycheck.sh`, `README.txt`, and `manifest.json`. The archive is reproducible byte-for-byte for the same commit and same source tree.
3. If using Termux, install Python, OpenSSL and unzip through its normal package manager. These downloads are public dependencies; **the verification command itself uses no network**. Extract only the reviewed package in `$HOME`. Do not copy the key into Android shared Downloads or any publicly synchronized cloud directory.

```sh
pkg install python openssl unzip
cd "$HOME"
unzip /path/to/nexus-stage-d-owner-phone-keycheck.zip
cd nexus-stage-d-owner-keycheck
# The existing RSA PRIVATE key must already be held securely, outside this folder.
chmod 600 "$HOME/private-key-dir/original-stage-d-private-key.pem"
./run-keycheck.sh "$HOME/private-key-dir/original-stage-d-private-key.pem"
```

The key path must be absolute, canonical, a single-owner regular file with no symlinks/hardlinks or group/other permissions, and outside both the public repository and the kit. The verifier locally checks the exact pinned certificate SHA-256 and performs an actual OpenSSL CMS encrypt/decrypt of a fresh random 48-byte challenge. It discards the temporary challenge and reports only `LOCAL RECOVERY KEY PROOF: PASS` or `BLOCKED`. It does not inspect or use any Railway secret.

**Android warning:** Real Termux versions, sandbox access to private key files, Android storage permissions, native OpenSSL and personal device performance have **not** been physically tested. In particular the different offline **data-restoration** tool requires Linux-specific atomic no-replace directory rename; success of this keycheck does **not** prove Termux can restore a CMS-backed NEXUS snapshot. Do not move actual confidential NEXUS workspaces into an unreviewed Android application.

## CI and packaging boundaries

- Deterministic packager: `scripts/build-stage-d-phone-key-kit.py`. It explicitly allowlists the two public source files, verifies the certificate's pinned SHA-256, stores fixed ZIP timestamps and modes, includes a manifest bound to the exact GitHub SHA and rejects pre-existing output or any output under the repository.
- Dedicated CI `stage-d-phone-key-kit.yml` runs without Railway credentials or key material. It invokes `scripts/test-stage-d-phone-key-kit.py` to test deterministic output, integrity and unexpected entries, wrong source SHA, and a genuine OpenSSL CMS challenge using only a new synthetic RSA keypair **outside the archive**. It also verifies that a mismatched key and insecure key permissions fail.
- The package contains no production token, private key, user backup, authenticated capture transcript, model or runtime provider access. GitHub artifacts expire after 30 days; operators must obtain a fresh exact-source artifact or preserve the public package, not confuse this retention with backup custody.

## Sequence toward a real recoverable deployment

After and only after an **actual owner-local matching-key PASS**, the legitimate owner can configure an appropriate private Railway token in GitHub Settings and manually run the [encrypted capture workflow](../.github/workflows/stage-d-encrypted-volume-capture.yml) with the original Volume ID and freshly checked provider deployment/source pins documented in [Phase 38](STAGE-D-LIVE-CAPTURE-TARGET.md). A real run may be denied by Railway permissions, provider plan restrictions or source drift. No service restart/replace is an automatic fallback.

A successful capture must additionally yield an independently retained ciphertext + receipt, exact GitHub run-log anchor, and a separate authenticated **isolated decrypt+restore on a trusted compatible private host**. The user-held private key should never be copied to cloud CI, GitHub issues or the ChatGPT conversation. The original `/data` volume remains unmodified. Neither a keyproof nor a synthetic CI pass grants Stage D Seal, pilot readiness or production cutover. `A_out <= A_in`.
