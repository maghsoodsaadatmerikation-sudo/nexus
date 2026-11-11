#!/usr/bin/env python3
"""Offline encrypted NEXUS escrow recovery into a NEW quarantined directory.

Requires an operator-held PRIVATE RSA key and an encrypted .cms plus its
sanitized receipt. No Railway, GitHub API, login, upload or production write.
A success proves local authenticated decryption + structural byte round-trip,
NOT Railway provenance, atomic live capture, live service restore or a Seal.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

from private_subprocess_env import child_env

REPO = Path(__file__).resolve().parent.parent
MAX_CIPHER = 65 * 1024 * 1024
MAX_PLAINTEXT_TAR = 65 * 1024 * 1024
MAX_RECEIPT = 32 * 1024

def load_script(filename, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

snapshot = load_script("data-snapshot.py", "nexus_encrypted_recovery_snapshot")
escrow = load_script("stage-d-encrypted-escrow.py", "nexus_encrypted_recovery_escrow")
capture = load_script("capture-railway-volume-readonly.py", "nexus_encrypted_recovery_capture")

class RecoveryBlocked(ValueError):
    pass

def require(condition):
    if not condition:
        raise RecoveryBlocked("encrypted recovery precondition or evidence failed")

def strict_json(raw):
    return json.loads(raw, object_pairs_hook=snapshot.unique_object)

def private_regular(path, limit):
    """Require stable, no-follow regular files in canonical directories."""
    require(path.is_absolute() and path.parent.is_dir() and
            path.parent == path.parent.resolve())
    return snapshot.read_regular(path, limit)

def validate_paths(ciphertext, receipt, key, destination):
    for path in (ciphertext, receipt, key, destination):
        require(path.is_absolute() and path.parent.is_dir() and
                path.parent == path.parent.resolve())
    require(destination.parent != REPO and
            not destination.is_relative_to(REPO) and
            not REPO.is_relative_to(destination))
    require(not destination.exists() and not destination.is_symlink())
    require(not key.is_relative_to(REPO) and key != ciphertext and key != receipt)
    # Only a trusted private owner directory may hold decrypted workspaces.
    folder = destination.parent.stat()
    require(stat.S_ISDIR(folder.st_mode) and
            folder.st_uid == os.getuid() and
            stat.S_IMODE(folder.st_mode) & 0o077 == 0)
    key_info = key.lstat()
    require(stat.S_ISREG(key_info.st_mode) and key_info.st_nlink == 1 and
            key_info.st_uid == os.getuid() and
            stat.S_IMODE(key_info.st_mode) & 0o077 == 0 and
            128 <= key_info.st_size <= 65536)

def require_receipt(raw, ciphertext_bytes):
    data = strict_json(raw)
    fixed = {
        "schema": "nexus.stage-d-encrypted-escrow.v1",
        "status": "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED",
        "content_claim": "local_structural_intake_only",
        "independent_live_restore": "not_evaluated",
        "railway_origin": "not_independently_attested",
        "release_authorized": False,
        "seal": False,
        "authority": "none",
        "recipient_cert_sha256": escrow.CERT_SHA256,
        "ciphertext_sha256": hashlib.sha256(ciphertext_bytes).hexdigest(),
        "ciphertext_bytes": len(ciphertext_bytes),
    }
    require(type(data) is dict and set(data) == set(fixed))
    for k, v in fixed.items():
        require(type(data[k]) is type(v) and data[k] == v)

def decrypt_authenticated(verified_ciphertext, key, private_home):
    """Authenticate the EXACT ciphertext bytes already hashed and checked.

    Pass immutable bytes on stdin: reopening a pathname after its SHA check
    would permit a file-swap race between receipt validation and AES-GCM.
    """
    process = subprocess.run(
        ["openssl", "cms", "-decrypt", "-inform", "DER",
         "-recip", str(escrow.CERT), "-inkey", str(key)],
        input=verified_ciphertext,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=90, check=False,
        env=child_env(railway_download=False, private_home=private_home),
    )
    require(process.returncode == 0 and
            0 < len(process.stdout) <= MAX_PLAINTEXT_TAR)
    return process.stdout

def parse_three_files(plaintext):
    """Never extract untrusted tar members to disk."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:") as archive:
        for index, member in enumerate(archive):
            require(index < len(escrow.EVIDENCE) and
                    member.name in escrow.EVIDENCE and
                    member.name not in files and member.isfile() and
                    not member.issym() and not member.islnk() and
                    not member.pax_headers and member.size <= escrow.MAX_EVIDENCE)
            fileobj = archive.extractfile(member)
            require(fileobj is not None)
            data = fileobj.read(escrow.MAX_EVIDENCE + 1)
            require(len(data) == member.size)
            files[member.name] = data
    require(set(files) == set(escrow.EVIDENCE))
    require(sum(map(len, files.values())) <= escrow.MAX_EVIDENCE)
    return files

def validate_inner_reports(files, archive_digest, file_count):
    intake = strict_json(files["intake-report.json"])
    expected = {
        "schema": "nexus.offhost-volume-intake.v1",
        "status": "STRUCTURAL_REHEARSAL_PASS",
        "volume_id": capture.VOLUME,
        "deployment_id": capture.DEPLOYMENT,
        "runtime_commit": capture.RUNTIME,
        "provider_identity": "operator_supplied_unverified",
        "copy_provenance": "unverified",
        "production_volume_contents": "not_directly_observed",
        "source_consistency": "not_verified",
        "local_copy_scans_matched_archive": True,
        "local_copy_check": "before_archive_and_after_restored_bytes",
        "rust_core_audit": "not_evaluated",
        "rust_core_binary_identity": "not_verified",
        "rust_core_source_parity": "not_evaluated",
        "post_rust_source_archive_and_restore_rechecked": False,
        "independent_railway_backup": "not_proven",
        "live_survival": "not_evaluated",
        "live_recovery": "not_evaluated",
        "file_count": file_count,
        "snapshot_sha256": archive_digest,
        "isolated_byte_roundtrip": True,
        "restored_quarantined": True,
        "authority": "none",
    }
    require(type(intake) is dict and set(intake) == set(expected))
    for k, v in expected.items():
        require(type(intake[k]) is type(v) and intake[k] == v)

    received = strict_json(files["capture-receipt.json"])
    expected_capture = {
        "schema": "nexus.railway-volume-readonly-capture.v1",
        "status": "PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS",
        "scope": "operator-authenticated-cli-download-to-private-directory",
        "target": {
            "project_id": capture.PROJECT,
            "environment_id": capture.ENVIRONMENT,
            "service_id": capture.SERVICE,
            "volume_id": capture.VOLUME,
        },
        "cli_subcommand": "volume files download",
        "source_consistency": "NOT_VERIFIED_ATOMIC",
        "rust_core_audit": "not_evaluated",
        "rust_core_binary_identity": "not_verified",
        "rust_core_source_parity": "not_evaluated",
        "local_copy_scans_matched_archive": True,
        "post_intake_copy_archive_and_restore_rechecked": True,
        "provider_file_origin": "CLI_SELECTED_ID_NOT_INDEPENDENTLY_ATTESTED",
        "offsite_copy": "PRIVATE_PATH_OPERATOR_MUST_PRESERVE",
        "archive_sha256": archive_digest,
        "restored_quarantined": True,
        "independent_complete_production_backup": "NOT_PROVEN",
        "production_restart": "NOT_PERFORMED",
        "production_restore": "NOT_PERFORMED",
        "production_mutation": False,
        "seal": False,
        "authority": "none",
    }
    require(type(received) is dict and set(received) == set(expected_capture))
    require(received == expected_capture)

def validate_quarantined_tree(root, records):
    """Independent post-restore path and exact byte check; no resumption."""
    expected = dict(records)
    expected.pop(snapshot.RECOVERY_MARKER, None)
    names = set()
    dirs = set()
    for i, path in enumerate(root.rglob("*")):
        require(i <= snapshot.MAX_FILES + 2 and not path.is_symlink())
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            dirs.add(name)
        else:
            names.add(name)
    require(dirs == {"requests"} and
            names == set(expected) | {snapshot.RECOVERY_MARKER})
    for name, data in expected.items():
        require(snapshot.read_regular(root / name, snapshot.MAX_BYTES) == data)
    require(snapshot.read_regular(root / snapshot.RECOVERY_MARKER,
                                  len(snapshot.RECOVERY_BYTES)) == snapshot.RECOVERY_BYTES)

def recover(ciphertext, receipt, key, destination):
    validate_paths(ciphertext, receipt, key, destination)
    encrypted = private_regular(ciphertext, MAX_CIPHER)
    receipt_bytes = private_regular(receipt, MAX_RECEIPT)
    require_receipt(receipt_bytes, encrypted)
    require(hashlib.sha256(private_regular(escrow.CERT, 16384)).hexdigest()
            == escrow.CERT_SHA256)
    # Never write partial or unauthenticated decryption output to disk.
    plaintext = decrypt_authenticated(encrypted, key, destination.parent)
    files = parse_three_files(plaintext)
    digest = hashlib.sha256(files["nexus-private-data-snapshot.json"]).hexdigest()
    # Validate exact independently reported non-authority claims before stage.
    inner = strict_json(files["nexus-private-data-snapshot.json"])
    require(type(inner) is dict and
            inner.get("schema") == snapshot.SCHEMA and
            inner.get("authority") == "none" and
            inner.get("consistency") == "offline-caller-asserted" and
            type(inner.get("files")) is list and
            len(inner["files"]) <= snapshot.MAX_FILES)
    validate_inner_reports(files, digest, len(inner["files"]))

    old_umask = os.umask(0o077)
    staging = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=".nexus-offline-recovery-",
                                        dir=destination.parent))
        archive = staging / "verified-snapshot.json"
        with archive.open("xb") as handle:
            handle.write(files["nexus-private-data-snapshot.json"])
            handle.flush()
            os.fsync(handle.fileno())
        archive.chmod(0o600)
        records = snapshot.validated_records(archive)
        require(len(records) == len(inner["files"]))
        candidate = staging / "candidate"
        snapshot.restore(archive, candidate)
        validate_quarantined_tree(candidate, records)
        # Reject post-check file replacement before publishing any success:
        # the same exact ciphertext and sanitized receipt must still be
        # present after OpenSSL authentication and isolated restore.
        require(private_regular(ciphertext, MAX_CIPHER) == encrypted and
                private_regular(receipt, MAX_RECEIPT) == receipt_bytes)
        # The only destination publication is a kernel no-replace rename,
        # after all authenticated and post-restore checks have succeeded.
        require(not destination.exists() and not destination.is_symlink())
        snapshot.publish_directory_no_replace(candidate, destination)
        snapshot.sync_directory(destination.parent)
    finally:
        os.umask(old_umask)
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    print("ENCRYPTED ESCROW OFFLINE QUARANTINED RESTORE: PASS"
          " (no Railway origin, live recovery, consistency or Seal claim)")
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciphertext", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        return recover(args.ciphertext, args.receipt,
                       args.private_key, args.destination)
    except (OSError, ValueError, TypeError, UnicodeError,
            subprocess.SubprocessError, tarfile.TarError):
        # No secret content, identifiers, file paths or OpenSSL errors in logs.
        print("ENCRYPTED ESCROW OFFLINE RESTORE: BLOCKED", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
