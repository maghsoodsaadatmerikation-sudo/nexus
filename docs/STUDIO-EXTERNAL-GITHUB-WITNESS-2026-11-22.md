# NEXUS Studio GitHub witness: opt-in external recheck and separate Ed25519 signature

## Authority and threat boundary

The Studio gateway remains **non-authoritative**. After an explicitly reviewed and consented GitHub branch creation or text-file commit, it performs a same-provider readback and returns `witness_request` alongside its existing `receipt`. The request is a **source claim**, not an independent attestation. It contains repository, working-branch name, exact revision, optional file path and SHA-256 of the reviewed file bytes, a SHA-256 commitment to the approved review ID, and a copy of the already verified same-provider receipt. It does **not** contain the replacement file text, provider tokens, operator token, signing keys, or chat prompts.

The Studio connection receipt has an **Export audit request** action. It creates a local JSON file only on the operator's explicit click. No automatic upload, model call, clipboard permission or background witness connection is created. The export disappears when the private session is cleared or the user switches conversations. Failed/ambiguous provider writes offer no export and revoke previous write approval.

To get a genuinely distinct witness, a separate operator must run the CLI on **different infrastructure and account**, with a separately managed *read-only* GitHub credential and a private Ed25519 signing key unavailable to NEXUS. Running two processes/directories on one host or using the NEXUS operator's key does **not** establish custody independence. A signature proves only that the holder of the pinned key signed a specified external observation, not that the holder is genuinely independent, that GitHub is globally honest, that the source performed a human-reviewed action, or that the source did not later change.

The verifier contacts only `https://api.github.com` with **GET**, no redirects, hard-coded TLS host and certificate validation, bounded JSON, a pinned expected repository and exact branch revision. For a file, it independently checks the branch head, immutable commit tree, regular non-executable Git blob and exact SHA-256 file bytes. It rejects symlinks, modified bytes, truncated trees, mismatched revisions, malformed inputs and redirect/status errors. It never writes to GitHub.

## Off-host witness workflow

On the external witness machine, provision an Ed25519 key under an independent key-custody policy and independently pin its public key with the reviewing party:

```sh
openssl genpkey -algorithm Ed25519 -out /protected/witness-private.pem
chmod 600 /protected/witness-private.pem
openssl pkey -in /protected/witness-private.pem -pubout -out /trusted/witness-public.pem
```

The operator manually moves `nexus-github-audit-request.json` from the reviewed Studio session to that witness host over a chosen authenticated channel. Do not transfer a chat export or provider credential with it. For private GitHub repositories, provide a separately scoped **read-only** credential through the witness's own environment variable `NEXUS_GITHUB_WITNESS_TOKEN`; for public repositories the environment variable may be omitted.

```sh
python3 scripts/studio-github-external-witness.py check \
  --request /inbox/nexus-github-audit-request.json \
  --expected-repository example/nexus \
  --witness-id independent-org-1 \
  --key-id independent-key-2026-1 \
  --private-key /protected/witness-private.pem \
  --output /outbox/studio-witness-signed.json
```

The `check` operation stops without a success report if a remote read differs. It refuses to overwrite an existing output file. Retain the original request, signed report, witnessed revision and separately selected witness public key under a custody/retention policy.

On the recipient's own host, using a public key and witness identity pinned **out of band**:

```sh
python3 scripts/studio-github-external-witness.py verify \
  --request /inbox/nexus-github-audit-request.json \
  --expected-repository example/nexus \
  --report /inbox/studio-witness-signed.json \
  --expected-witness-id independent-org-1 \
  --trusted-key-id independent-key-2026-1 \
  --trusted-public-key /trusted/witness-public.pem
```

`verify` uses no network or credentials. It validates the exact reviewed-request SHA-256, report structure, externally pinned identity and public-key Ed25519 signature. It does **not** independently discover the latest branch revision, infer a globally trusted timestamp, grant commit/merge authority, or verify deployment. Keep independently retained signed reports and minimum accepted revisions if rollback/replay attacks are in scope.

## Tests and release status

`python3 scripts/test-studio-github-external-witness.py` runs offline against deterministic synthetic GitHub reads and locally generated Ed25519 test keys. It tests wrong branch heads, changed file bytes, symlink entries, truncated tree, forged signatures, duplicate JSON fields and identity mismatches. The root PR verifier invokes these tests without GitHub write credentials or a provisioned witness host.

The Cloud Adapter contract separately checks that source-only witness requests bind to approved operations and that no file contents or credentials are included. The real Chromium Studio test checks that valid receipts expose the manual download and fake/ambiguous receipts do not.

**Nothing in this feature provisions a real off-site auditor, signs a production observation, merges source code, publishes NEXUS, or upgrades a source-side receipt into independent authority.** The stacked PR is draft and commits use `[skip render]` to prevent automatic Render deployment.
