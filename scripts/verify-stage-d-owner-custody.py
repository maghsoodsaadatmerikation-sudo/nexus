#!/usr/bin/env python3
"""Local, read-only two-filesystem custody readback for Stage D ciphertext.

This validates two separately stored ciphertext/receipt pairs against one
operator-retained exact GitHub run-log anchor. It never contacts Railway or
GitHub and never proves administrative/off-provider independence, private key
possession, decryption, recovery, or release authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_owner_custody_log_anchor", HERE / "stage-d-run-log-anchor.py")
anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)

SCHEMA = "nexus.stage-d-owner-custody-readback.v1"
ALLOWED = frozenset((anchor.CIPHERTEXT, anchor.RECEIPT))


class CustodyBlocked(ValueError):
    pass


def require(condition):
    if not condition:
        raise CustodyBlocked("owner ciphertext custody readback precondition failed")


def private_dir(path: Path):
    """Reject alias or group-readable working directories before reading data."""
    require(path.is_absolute() and path.is_dir() and not path.is_symlink() and
            path == path.resolve(strict=True))
    meta = path.stat()
    require(stat.S_ISDIR(meta.st_mode) and meta.st_uid == os.getuid() and
            stat.S_IMODE(meta.st_mode) & 0o077 == 0)


def private_file(path: Path, limit: int):
    """No-follow, no hardlinks and owner-only file mode; content bound by anchor."""
    require(path.is_absolute() and path.parent == path.parent.resolve(strict=True))
    meta = path.lstat()
    require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and
            meta.st_uid == os.getuid() and
            stat.S_IMODE(meta.st_mode) & 0o077 == 0 and
            0 < meta.st_size <= limit)
    return anchor.canonical_read(path, limit)


def exact_pair(directory: Path):
    private_dir(directory)
    require({p.name for p in directory.iterdir()} == ALLOWED)
    private_file(directory / anchor.CIPHERTEXT, anchor.MAX_CIPHER)
    private_file(directory / anchor.RECEIPT, anchor.MAX_JSON)


def filesystem_identity(directory: Path):
    # Distinct st_dev is a local filesystem separation signal, NOT proof
    # of a separate machine, provider, administrator, geographical site,
    # real backup custody, or an independent trust root.
    return directory.stat().st_dev


def verify_owner_copies(first: Path, second: Path, anchor_path: Path,
                        run_id: str, run_attempt: str, commit_sha: str):
    require(anchor.SHA.fullmatch(commit_sha) is not None)
    expected_run = anchor.positive_int(run_id)
    expected_attempt = anchor.positive_int(run_attempt)
    require(first != second and first not in second.parents and second not in first.parents)
    private_dir(first)
    private_dir(second)
    require(filesystem_identity(first) != filesystem_identity(second))
    require(anchor_path.parent != first and anchor_path.parent != second)
    private_dir(anchor_path.parent)
    original_line = private_file(anchor_path, anchor.MAX_ANCHOR).decode("utf-8")
    require(original_line.startswith(anchor.PREFIX))
    exact_pair(first)
    exact_pair(second)
    one = anchor.verify(first, original_line, expected_run, expected_attempt, commit_sha)
    two = anchor.verify(second, original_line, expected_run, expected_attempt, commit_sha)
    require(one.get("status") == two.get("status") == "LOG_ANCHOR_LOCAL_FILE_MATCH_ONLY")
    one_cipher, one_receipt, _ = anchor.read_cipher_receipt(first)
    two_cipher, two_receipt, _ = anchor.read_cipher_receipt(second)
    require(one_cipher == two_cipher and one_receipt == two_receipt)
    # Recheck local identity and the original anchor after all reads.
    require(filesystem_identity(first) != filesystem_identity(second))
    require(private_file(anchor_path, anchor.MAX_ANCHOR).decode("utf-8") == original_line)
    exact_pair(first)
    exact_pair(second)
    return {
        "schema": SCHEMA,
        "status": "TWO_FILESYSTEM_CIPHERTEXT_BYTES_MATCH",
        "run_id": expected_run,
        "run_attempt": expected_attempt,
        "commit_sha": commit_sha,
        "ciphertext_sha256": hashlib.sha256(one_cipher).hexdigest(),
        "file_pairs_checked": 2,
        "different_local_filesystem_ids": True,
        "github_log_authenticity": "operator_must_independently_verify",
        "github_workflow_success": "operator_must_independently_verify",
        "railway_volume_origin": "not_verified",
        "snapshot_consistency": "not_verified",
        "off_provider_administrative_independence": "not_proven",
        "private_recovery_key_possession": "not_evaluated",
        "ciphertext_decrypted": False,
        "isolated_restore": "not_performed",
        "production_backup_complete": False,
        "live_recovery": "not_performed",
        "deployment_authorized": False,
        "production_mutation": False,
        "seal": False,
        "authority": "none",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy-a", type=Path, required=True)
    parser.add_argument("--copy-b", type=Path, required=True)
    parser.add_argument("--anchor-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--commit-sha", required=True)
    args = parser.parse_args()
    try:
        result = verify_owner_copies(
            args.copy_a, args.copy_b, args.anchor_file,
            args.run_id, args.run_attempt, args.commit_sha)
    except (CustodyBlocked, ValueError, OSError, TypeError, UnicodeError):
        # Never print ciphertext, file paths, account metadata, or secrets.
        print("STAGE D OWNER CUSTODY READBACK: BLOCKED (no backup or release claim)",
              file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
