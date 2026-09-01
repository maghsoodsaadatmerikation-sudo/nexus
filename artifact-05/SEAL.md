# Artifact 05 — Verification Seal

Status: SEALED

This record seals Artifact 05 only to the verified evidence below. It does not grant authority, alter policy, or expand the HTTP gateway boundary.

## Verified boundary

- Verified commit: `efc79c6ce6631e7187b677a5b60e4e7c39e67550`
- GitHub Actions run: `33534569941`
- Workflow: `NEXUS Verification`
- Docker reference: `rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e`
- Gate 0: PASS
- Gate 1: PASS
- Gate 2: PASS
- Gate 3: PASS

## Independent evidence checks

- Artifact 05 `Cargo.lock` SHA-256: `1a3ad9b041b7319e1d08bca92128eb21b44924fd9a5cf07e2f4b9d4bd29cbea4`
- Artifact 05 `Cargo.toml` SHA-256: `0dd027de829cedf5b229745124c990dc72dc9233ac23bf4ee733102b32136bdd`
- Artifact 05 source + tests aggregate SHA-256: `e52991b625d27a99870c9fe34debbcd4d60f58039230654d6319a024fc35f2a8`
- Attested bundle SHA-256: `d9af77e75b578b93be0056879d1d0452e55a0a4da6aa5e62abe73462fd5eec9c`
- Uploaded artifact ZIP SHA-256: `9f2f18673d3d5a55b7140d8567fd5946c7c99705a4ba3feee396b8a8f6cf1fd9`
- GitHub attestation ID: `44472952`
- Rekor log index: `2678330642`

The manifest and extracted bundle were independently re-hashed after download and matched the recorded Cargo.lock, Cargo.toml, and source-tree digests.

## Constitutional scope

Artifact 05 remains transport-only: parse, shape validation, envelope construction, delegation, and serialization. Authorization, denial, interpretation, execution, policy mutation, and authority amplification remain outside the gateway boundary.
