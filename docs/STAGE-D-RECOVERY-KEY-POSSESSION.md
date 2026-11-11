# Stage D — Owner-held recovery-key possession check

**Status: implementation and synthetic tests only. The owner-held key has NOT been inspected; original Railway /data has NOT been downloaded or recovered.** No new paid infrastructure, production operation, token, deployment, release, or Seal is involved.

## The recovery risk

The manual Stage D capture encrypts a private NEXUS snapshot to the pinned public certificate at docs/keys/stage-d-recovery-public-cert.pem. Knowing a public encryption recipient does NOT establish that the owner retains the matching private key. A successful download and encryption could otherwise create an irrecoverable backup.

This stage adds a local-only cryptographic recovery-key challenge and an explicit manual acknowledgement before the first provider download. The workflow checks the acknowledgement, but **does not cryptographically verify the operator's private key**. The key is never requested, transferred to, or stored in GitHub/Railway/ChatGPT/CI.

## Owner-controlled local proof

On a trusted owner-controlled device with Python 3 and OpenSSL installed (Linux or, where compatible, Android Termux with private application storage), locate the **existing matching private RSA key** outside the repository. Its file must be an absolute, non-symlinked, unlinked regular file owned by the operator, with mode 0600 or 0400. Do not put it on Android shared storage that cannot enforce file permissions. Do not transmit its contents or passphrase to a cloud runner or chat.

From the NEXUS checkout, run this command, changing only the local key path:

    python3 scripts/verify-stage-d-recovery-key.py \
      --private-key "$HOME/nexus-private/stage-d-recovery-private-key.pem"

The tool hashes and pins the repository's exact public certificate, generates a fresh random 48-byte synthetic challenge, encrypts it with OpenSSL CMS AES-256-GCM, decrypts it with the supplied private key, and checks byte-for-byte equality. It rejects mismatched keys, unsafe key permissions, symlink/hardlinks, an altered certificate, repository-local keys, and CI execution. No Railway credentials or network are needed; no real workspace or Volume data are used. Only a generic PASS or BLOCKED result is emitted. Private-key files and file paths are never printed.

An encrypted/agent-dependent private key that cannot be used noninteractively is BLOCKED by this specific tool; do not send its passphrase to the workflow. A newly generated key CANNOT decrypt data addressed to the pinned public certificate. If the matching owner key is unavailable, DO NOT run the production capture. Establish a new, independently tested recipient and its private custody through a separately reviewed code revision before ever encrypting production bytes; never silently rotate the public certificate.

## Manual capture acknowledgement

The existing manual-only workflow NEXUS Stage D — Manual Encrypted Volume Capture now requires the additional input confirm_recovery_key to contain exactly:

    I VERIFIED MY STAGE D RECOVERY KEY LOCALLY

Enter this text ONLY after the real owner-held key has passed the private local challenge. Missing or incorrect acknowledgement halts the job before Railway access, as does missing original Volume confirmation or wrong credential scope.

**Self-critique:** this input is only a human declaration, NOT a cryptographic proof received by GitHub. No CI or app connector can prove actual custody of the owner key. A local challenge proves decryptability at the moment of execution; it does not prove that the owner will preserve the key, the encrypted artifact, or independently restore the real backing data.

## Tested boundaries and acceptance

CI generates only disposable synthetic keys, including a wrong-key pair. It tests correct decryptability, wrong key, changed recipient, public certificate used as key, insecure permissions, symlink, hardlink, relative path, and cloud-runner prohibition. The actual owner private key never enters GitHub Actions.

The later live acceptance still needs a legitimate Railway credential, read-only original Volume export, owner-controlled off-provider ciphertext preservation, a genuine offline decrypt/isolated restore, origin and source-consistency assessment, and an independent human witness. None is asserted by this stage. Keep Issue #70 open; preserve A_out <= A_in.
