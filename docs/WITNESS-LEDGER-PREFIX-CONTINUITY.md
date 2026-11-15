# Signed witness-ledger prefix consistency (read-only)

NEXUS already validates each Ed25519 receipt and signed recipient acknowledgment and supports an independently pinned latest checkpoint. A separately transported **candidate ledger** can nonetheless be a different, internally valid history. Checking only its final sequence is not a historical continuity proof.

The offline command `scripts/workspace-witness-ledger-prefix.py` compares the **entire signed prefix** of a retained baseline ledger with a newer candidate ledger, verifies **every receipt and acknowledgment in both ledgers**, and checks the candidate's exact latest independently preserved signed package. It requires no service credentials, private keys or network calls, and does not modify either input ledger. Cryptographic inspection may use temporary scratch files.

## Trust inputs

Obtain these artifacts from **separate custody or transport paths** and approve their SHA-256 digests independently of the files being checked:

- An already accepted v1 `custodian.json` **baseline** (must contain at least one acknowledgment), with its exact byte SHA-256.
- A newer proposed `custodian.json` **candidate**, with its exact byte SHA-256.
- The separately retained **latest receipt + signed acknowledgment package** for that candidate, with its exact byte SHA-256.
- Receiver ID, source signer ID and its PEM public key, recipient signer ID and its PEM public key, plus an independently retained minimum sequence (at least the known baseline length).

No secret or private key is an input. All file paths must refer to regular, non-hardlinked files (not symlinks); every JSON key must be unique. Use isolated, operator-reviewed files; do not point this verifier at an actively mutating production volume and presume it is an atomic snapshot.

## Read-only example

```sh
python3 scripts/workspace-witness-ledger-prefix.py \
  --baseline-ledger /independent/baseline-custodian.json \
  --baseline-sha256 APPROVED_BASELINE_FILE_SHA256 \
  --candidate-ledger /transport/candidate-custodian.json \
  --candidate-sha256 APPROVED_CANDIDATE_FILE_SHA256 \
  --trusted-latest-package /independent/latest-package.json \
  --trusted-package-sha256 APPROVED_EXACT_PACKAGE_SHA256 \
  --receiver-id known-independent-receiver \
  --source-key-id approved-source-signer \
  --source-public-key /trusted/source.pem \
  --ack-key-id approved-recipient-signer \
  --ack-public-key /trusted/recipient.pem \
  --minimum-sequence 42
```

On success, stdout is a small machine-readable `nexus.offsite.ledger-prefix-proof.v1` report with baseline and candidate sequence, new-acknowledgment count, exact file hashes and last acknowledgment digest. Refusal is nonzero and goes to stderr; no replacement ledger or output file is created. A candidate **must extend** the baseline by at least one new acknowledgment; equality is not a successful upgrade.

The verifier refuses changed signer identities, invalid signatures, source-state replays, rewritten historical receipts, validly signed alternate forks, missing latest checkpoints, stale sequence floors, noncanonical/ambiguous JSON, missing files, symlinks and hardlinks.

## Critical limits

This proves **signed prefix consistency under the independently supplied keys, hashes and checkpoint**. It **does not prove** the baseline or latest checkpoint was actually kept independently, that the source state is current, that a remote host is physically independent, that external storage is immutable, or that a deployment is safe. A compromised signer can sign another history; out-of-band custody and non-equivocation checks remain essential. It does **not** rotate keys, modify v1 history or authorize recovery, import, production release, network calls or a change to NEXUS runtime trust. A v2 key-epoch migration requires separate design, review and approvals.

CI uses disposable fake identities and files only. Run `python3 scripts/test-workspace-witness-ledger-prefix.py` for the adversarial fixture. This capability should be evaluated alongside the receiver custody, cold-backup recovery and three-party consent procedures, not substituted for them.
