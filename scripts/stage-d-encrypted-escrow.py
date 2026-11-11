#!/usr/bin/env python3
"""Encrypt an already-validated, private NEXUS capture for off-provider custody.

Never talks to Railway. This is the final local step after the separate
read-only operator-authenticated CLI copy. Only ciphertext + redacted metadata
may be uploaded. No Seal, provenance attestation or atomic backup claim.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
CERT = REPO / "docs/keys/stage-d-recovery-public-cert.pem"
CERT_SHA256 = "b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091"
EVIDENCE = ("nexus-private-data-snapshot.json", "intake-report.json", "capture-receipt.json")
MAX_EVIDENCE = 64 * 1024 * 1024 + 64 * 1024
EXPECTED_RECEIPT_KEYS = {
    "schema", "status", "scope", "target", "cli_subcommand",
    "source_consistency", "rust_core_audit", "rust_core_binary_identity",
    "rust_core_source_parity", "local_copy_scans_matched_archive",
    "post_intake_copy_archive_and_restore_rechecked", "provider_file_origin",
    "offsite_copy", "archive_sha256", "restored_quarantined",
    "independent_complete_production_backup", "production_restart",
    "production_restore", "production_mutation", "seal", "authority",
}


class EscrowBlocked(ValueError):
    pass


def require(ok, reason=None):
    # Do not interpolate paths, metadata, command stderr, or private values
    # into a user-facing failure. Reasons are fixed literals for developers.
    if not ok:
        raise EscrowBlocked("private capture, recipient or encrypted output did not meet the exact contract")


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_evidence_dir(directory):
    require(directory.is_dir() and not directory.is_symlink() and
            directory == directory.resolve(), "untrusted private evidence directory")
    total = 0
    for name in EVIDENCE:
        path = directory / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                "invalid evidence file type")
        total += info.st_size
        require(total <= MAX_EVIDENCE, "private evidence is oversized")
    return total


def encrypt_fixed_evidence(directory, cert, destination):
    """Stream only three fixed validated evidence files into RSA/CMS AES-GCM.

    Never put plaintext tar or workspace files in a GitHub artifact directory.
    The final ciphertext is published only after BOTH tar and OpenSSL succeed.
    """
    inspect_evidence_dir(directory)
    require(cert.is_file() and not cert.is_symlink() and
            sha256_file(cert) == CERT_SHA256, "untrusted recipient certificate")
    require(destination.is_absolute() and not destination.exists() and
            not destination.is_symlink(), "ciphertext destination is unsafe")
    require(destination.parent.is_dir() and
            destination.parent == destination.parent.resolve() and
            not destination.is_relative_to(directory) and
            not destination.is_relative_to(REPO), "ciphertext must be outside private data and checkout")
    temp_fd, temp_name = tempfile.mkstemp(prefix=".nexus-encrypted-", dir=destination.parent)
    os.close(temp_fd)
    temp = Path(temp_name)
    try:
        os.chmod(temp, 0o600)
        tar = subprocess.Popen(
            ["tar", "-C", str(directory), "-cf", "-", *EVIDENCE],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        try:
            crypt = subprocess.Popen(
                ["openssl", "cms", "-encrypt", "-aes-256-gcm", "-binary",
                 "-stream", "-outform", "DER", "-out", str(temp), str(cert)],
                stdin=tar.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            tar.stdout.close()
            crypt_ok = crypt.wait(timeout=90) == 0
            tar_ok = tar.wait(timeout=90) == 0
        finally:
            if tar.poll() is None:
                tar.kill()
                tar.wait()
        require(crypt_ok and tar_ok and temp.stat().st_size > 256,
                "encryption was incomplete")
        # Check for late evidence mutation before publishing the ciphertext.
        inspect_evidence_dir(directory)
        os.link(temp, destination, follow_symlinks=False)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
    finally:
        temp.unlink(missing_ok=True)
    return {"ciphertext_sha256": sha256_file(destination),
            "recipient_cert_sha256": CERT_SHA256,
            "ciphertext_bytes": destination.stat().st_size}


def validate_capture(root):
    require(root.is_absolute() and root.is_dir() and not root.is_symlink() and
            root == root.resolve() and not root.is_relative_to(REPO),
            "private capture root not eligible")
    capture_spec = importlib.util.spec_from_file_location(
        "nexus_escrow_capture", Path(__file__).with_name("capture-railway-volume-readonly.py"))
    capture = importlib.util.module_from_spec(capture_spec)
    capture_spec.loader.exec_module(capture)
    source = root / "copied-data"
    report_dir = root / "isolated-intake"
    inspected, digest = capture.validate_final_private_receipt(
        source, report_dir, rust_requested=False)
    receipt_path = report_dir / "capture-receipt.json"
    # A symlinked or hard-linked receipt is never trusted: open the inode
    # without following paths, then reject mutable/shared or oversized files.
    fd = os.open(receipt_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                info.st_size <= 32768, "invalid private capture receipt")
        original = os.read(fd, 32769)
        require(len(original) == info.st_size, "private capture receipt changed")
    finally:
        os.close(fd)
    def distinct(pairs):
        result = {}
        for key, val in pairs:
            require(key not in result, "duplicate private receipt key")
            result[key] = val
        return result
    receipt = json.loads(original, object_pairs_hook=distinct)
    require(type(receipt) is dict and set(receipt) == EXPECTED_RECEIPT_KEYS,
            "private capture receipt schema not recognized")
    expected = {
        "schema": "nexus.railway-volume-readonly-capture.v1",
        "status": "PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS",
        "scope": "operator-authenticated-cli-download-to-private-directory",
        "target": {"project_id": capture.PROJECT, "environment_id": capture.ENVIRONMENT,
                   "service_id": capture.SERVICE, "volume_id": capture.VOLUME},
        "cli_subcommand": "volume files download",
        "source_consistency": "NOT_VERIFIED_ATOMIC",
        "rust_core_audit": "not_evaluated",
        "rust_core_binary_identity": "not_verified",
        "rust_core_source_parity": "not_evaluated",
        "local_copy_scans_matched_archive": True,
        "post_intake_copy_archive_and_restore_rechecked": True,
        "provider_file_origin": "CLI_SELECTED_ID_NOT_INDEPENDENTLY_ATTESTED",
        "offsite_copy": "PRIVATE_PATH_OPERATOR_MUST_PRESERVE",
        "archive_sha256": digest,
        "restored_quarantined": True,
        "independent_complete_production_backup": "NOT_PROVEN",
        "production_restart": "NOT_PERFORMED",
        "production_restore": "NOT_PERFORMED",
        "production_mutation": False,
        "seal": False,
        "authority": "none",
    }
    require(receipt == expected, "private receipt disagrees with fresh source validation")
    return report_dir, digest


def create_escrow(root, output_dir):
    require(output_dir.is_absolute() and output_dir.is_dir() and
            output_dir == output_dir.resolve() and not output_dir.is_relative_to(root),
            "encrypted artifact directory must be separate")
    evidence, digest = validate_capture(root)
    ciphertext = output_dir / "nexus-stage-d-private-capture.cms"
    meta = output_dir / "nexus-stage-d-ciphertext-receipt.json"
    require(not ciphertext.exists() and not meta.exists() and
            not ciphertext.is_symlink() and not meta.is_symlink(),
            "encrypted artifact already exists")
    try:
        output = encrypt_fixed_evidence(evidence, CERT, ciphertext)
        # Do not allow report/archive substitution during the upload handoff.
        fresh_evidence, fresh_digest = validate_capture(root)
        require(fresh_evidence == evidence and digest == fresh_digest and
                sha256_file(evidence / EVIDENCE[0]) == digest,
                "private capture changed while encrypting")
        sanitized = {
            "schema": "nexus.stage-d-encrypted-escrow.v1",
            "status": "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED",
            "content_claim": "local_structural_intake_only",
            "independent_live_restore": "not_evaluated",
            "railway_origin": "not_independently_attested",
            "release_authorized": False,
            "seal": False,
            "authority": "none",
            **output,
        }
        with meta.open("x", encoding="utf-8") as out:
            json.dump(sanitized, out, sort_keys=True, indent=2)
            out.write("\n")
        meta.chmod(0o600)
    except Exception:
        ciphertext.unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
        raise
    print("ENCRYPTED ESCROW CREATED: private structural copy only; source atomicity and live restore NOT PROVEN")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--encrypted-output-dir", type=Path, required=True)
    args = p.parse_args()
    try:
        return create_escrow(args.private_root, args.encrypted_output_dir)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        # Never print secret tokens, private workspace IDs, names or paths.
        print("ENCRYPTED ESCROW: BLOCKED (no successful backup claim)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
