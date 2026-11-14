#!/usr/bin/env python3
"""Fail-closed read-only provenance gate for the composited NEXUS candidate.

Git blob identities establish exact inherited upstream source and explicitly
record new candidate-owned source identities. They are NOT signatures, runtime
assurance or release authority.
The intentionally merged Rust files are validated by Cargo/HTTP regression.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

# Pinned source heads: cloud PR #197 7f8b0703ef74c02b71290af9556a080dd90c90aa;
# auth PR #198 4e95bfc1ed0c70ebdcb37a7330106c1434753e36;
# runtime PR #202 a000aafa7e14e4dfee391639526c0df98cd75128.
EXPECTED_BLOBS = {
    "nexus-cloud/main.py": "bfd6bcae1dc38d7f767322113cf30058b421257e",
    "nexus-cloud/studio_model.py": "44fd937737c08b15fa3af265ef4e675de39167a0",
    "nexus-cloud/tests/test_delegated_header_identity.py": "cbf1da67917f29668fa155e8470a22ddfd117881",
    "nexus-cloud/tests/test_studio_model.py": "7522dbded3fc4935a9789b3a25ae46e4fb42a75f",
    "docs/CLOUD-HEADER-CARDINALITY-2026-11-14.md": "73857d6fc248202280ba661fe2ab2249a195dcb1",
    "docs/STUDIO-JSON-BOUNDARY-2026-11-14.md": "1018752b319b14d99168e44633bfce1a477151db",
    "docs/GATEWAY-AUTH-HEADER-IDENTITY-2026-11-14.md": "337362089373faeb33061b041505e2d5e417c9ab",
    "artifact-05/src/main.rs": "67d0283cc374b63d78d15f9cfe7138b72f2173e1",
    "artifact-05/src/request_store.rs": "e988175dfeccaab1b2adfda0af096541647d7302",
    "artifact-05/src/workspace_api.rs": "e33f1bd77821ed05c0431d8dc4a117f07237ee66",
    "src/workspace_persistence.rs": "12b0c8198aec596825147160c6f78cc2c6af815e",
    "docs/gateway-health.md": "01151f0409a1805c3dc228c8c5440cb7f5b80a82",
    "scripts/verify-storage-failure-http.py": "7d51a52eadafdc4f9aee3eed549c14b85f562e6b",
    # PR #188 exact unmodified freeze-preflight source:
    "scripts/production-freeze-preflight.py": "67004efa104f9932bcf262e53c8e497c8fd81d4d",
    "scripts/test-production-freeze-preflight.py": "1802953a0671bef7464bc5f18eaf58759570686f",
    "docs/PRODUCTION-FREEZE-PREFLIGHT.md": "758da07b0c7d4d9b605626d9aab3a3c814fe8db9",
    ".github/workflows/production-freeze-preflight.yml": "e5e14092b1685b9246a31324f0c45983308ecb59",
    # PR #189 exact unmodified synthetic recovery source:
    "scripts/pilot-cross-runner-recovery.py": "b4113ca9d7301dd48510a8433c681e2376d739a9",
    "docs/PILOT-CROSS-RUNNER-RECOVERY.md": "bd76958b5beeb363ed11f29b775bf794a28c19c4",
    ".github/workflows/pilot-cross-runner-recovery.yml": "07688b9ef3cfbef7ae79611f37c17bb1a4833b45",
    # Candidate-owned, reviewable volume-identity additions; they are NOT
    # claimed to be unchanged upstream PR #202 source. Startup/backup behavior
    # must also pass mandatory Rust/Python and live HTTP synthetic checks.
    "artifact-05/src/volume_identity.rs": "834ae8414f50e294b7f8b478b1582f550e936dac",
    "scripts/data-snapshot.py": "437b4c5ee90ca013ae8aaee84184035b0b06ddd7",
    "scripts/enroll-new-volume.py": "9cd129563ff0339726137c744059bb05166b2b9a",
    "scripts/test-enroll-new-volume.py": "0e348cdc432ec0ff3cd3a05b12d2858c2ce034aa",
    "scripts/test-volume-identity-gateway.py": "8b488adc4ac7868f24692ef65eb96eed7ce56310",
    "scripts/test-data-snapshot.py": "7e73645cdcbcd3436ac729c6c913f8d821f6dcf0",
}

# Source files modified *only* to compose upstream Rust fixes. Mandatory Rust
# contract tests test these behaviors; textual presence checks catch omission.
REQUIRED_RUST_TOKENS = {
    "artifact-05/src/lib.rs": (
        "headers.get_all(header::AUTHORIZATION)",
        "bearer_token_eq(provided.as_bytes(), expected.as_bytes())",
        'health_response(StatusCode::SERVICE_UNAVAILABLE, "workspace_unavailable")',
        'health_response(StatusCode::SERVICE_UNAVAILABLE, "storage_unavailable")',
        'health_response(StatusCode::SERVICE_UNAVAILABLE, "admission_unavailable")',
        'safety_error(StatusCode::SERVICE_UNAVAILABLE, "volume_identity_unavailable")',
        'fn check_runtime_volume_identity(&self) -> bool',
    ),
    "artifact-05/tests/http_contract.rs": (
        "duplicate_authorization_headers_never_authorize_rust_gateway",
        "a_single_exact_bearer_still_authorizes_without_prefix_equivalence",
        "invalid_runtime_bearer_tokens_fail_at_configuration_not_during_requests",
        "runtime_readiness_tracks_pinned_storage_loss_replacement_and_recovery",
        "capacity_exhaustion_disables_readiness_not_liveness_or_status",
    ),
}


def git_blob_identity(contents: bytes) -> str:
    preamble = b"blob " + str(len(contents)).encode("ascii") + b"\x00"
    return hashlib.sha1(preamble + contents).hexdigest()


def read_bounded_file(relative: str) -> bytes:
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or symlinked pinned source: " + relative)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("oversized pinned source: " + relative)
    return path.read_bytes()


def verify() -> None:
    for name, expected in EXPECTED_BLOBS.items():
        actual = git_blob_identity(read_bounded_file(name))
        if actual != expected:
            raise ValueError("source identity mismatch: " + name)
    for name, tokens in REQUIRED_RUST_TOKENS.items():
        source = read_bounded_file(name).decode("utf-8")
        for token in tokens:
            if source.count(token) != 1:
                raise ValueError("missing/ambiguous integrated Rust guard: " + name)
    if git_blob_identity(b"abc") != "f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f":
        raise ValueError("Git blob identity algorithm changed")
    print("COMPOSED SOURCE IDENTITY: PASS (no deployment or release authority)")


if __name__ == "__main__":
    if len(sys.argv) != 1:
        sys.exit("unsupported arguments")
    try:
        verify()
    except (ValueError, OSError, UnicodeError) as exc:
        print("COMPOSED SOURCE IDENTITY: FAIL - " + str(exc), file=sys.stderr)
        sys.exit(1)
