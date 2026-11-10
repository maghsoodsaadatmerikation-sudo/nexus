#!/usr/bin/env python3
"""Offline source-file parity guard for the exact *observed* Railway Rust revision.

Compares selected direct Rust workspace/serialization source modules and the
pinned toolchain to Git blob identities independently read from the original
deployment's public Git commit. Does not authenticate a production binary,
a Railway deployment, the supplied validator executable, or private data.
No network, user data, or credentials.
"""
import argparse
import hashlib
from pathlib import Path
import stat

# Exact Railway deployed source observed through the connected provider.
DEPLOYED_COMMIT = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"
# Verified Git blob OIDs for THIS commit, not for arbitrary current main.
# Other crate modules and Cargo.lock are intentionally NOT asserted equal.
SOURCE_BLOBS = {
    "src/workspace.rs": "40e4f90247df21a68bf197452fe25a3393b0697e",
    "src/workspace_persistence.rs": "070d8bdb1790bbf7b9d80a2c0d64c5c54c141a5f",
    "src/epistemic.rs": "7dbc4c3a195715da25913c5e570b2b6ee522473a",
    "src/analysis.rs": "50a56cdb06913efb29143cd9260efcd769a072e4",
    "rust-toolchain.toml": "c1e056341ae53ab62167ba45f4376342218a138e",
}
MAX_SOURCE_BYTES = 1024 * 1024


class ParityError(ValueError):
    pass


def check(repo_root: Path, runtime_commit: str) -> int:
    if runtime_commit != DEPLOYED_COMMIT:
        raise ParityError("unsupported supplied runtime source revision")
    root = Path(repo_root).absolute()
    if not root.is_dir() or root != root.resolve():
        raise ParityError("noncanonical local source root")
    for relative, expected_blob in SOURCE_BLOBS.items():
        file = root / relative
        try:
            meta = file.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise ParityError("unsafe source file")
            if meta.st_size > MAX_SOURCE_BYTES:
                raise ParityError("source file exceeds bound")
            data = file.read_bytes()
        except OSError:
            raise ParityError("source file unavailable") from None
        if len(data) > MAX_SOURCE_BYTES:
            raise ParityError("source file exceeds bound")
        # Git SHA-1 object ID: sha1("blob " + decimal_length + NUL + raw bytes).
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()
        if blob != expected_blob:
            raise ParityError("local Rust workspace source differs from pinned commit")
    return len(SOURCE_BLOBS)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument("--runtime-commit", required=True)
    args = cli.parse_args()
    try:
        count = check(args.repo_root, args.runtime_commit)
    except ParityError:
        print("STAGE D RUST SOURCE PARITY: BLOCKED (unsupported or mismatched local source)")
        return 1
    print(f"STAGE D RUST SOURCE PARITY: PASS ({count} selected Git blobs; NOT binary attestation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
