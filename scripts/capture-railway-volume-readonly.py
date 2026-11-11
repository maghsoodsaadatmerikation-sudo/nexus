#!/usr/bin/env python3
"""Explicit, private, read-only Railway volume copy + isolated structural intake.

Default is PLAN-ONLY. This DOES NOT run in CI with a production credential.
Never upload data, plaintext or backup artifacts to this public repository.
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
from private_subprocess_env import child_env

PROJECT = "2ac7887b-d67a-48be-8a7b-bd54092893ae"
ENVIRONMENT = "56c4bc45-0e62-4aa9-832f-884bb1aa620c"
SERVICE = "0032fc74-2c52-475d-b9df-9dca59237d93"
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
DEPLOYMENT = "db2fd959-918e-49d5-b077-1ac74fac9a82"
RUNTIME = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"
REPO_ROOT = Path(__file__).resolve().parent.parent
INTAKE = Path(__file__).with_name("verify-offhost-volume-export.py")
MAX_COPY_FILES = 20_000
PINNED_CLI_VERSION = "5.71.0"


class CaptureBlocked(ValueError):
    pass


def require(value, reason):
    if not value:
        raise CaptureBlocked(reason)


def protected_target(root):
    """Reject repo, symlinks, existing destinations and misleading relative paths."""
    require(root.is_absolute(), "private root must be absolute")
    require(not root.exists() and not root.is_symlink(), "private root must not exist")
    parent = root.parent
    require(parent.is_dir() and not parent.is_symlink(), "private parent unavailable")
    require(parent == parent.resolve(), "private parent contains a symlink")
    require(not root.is_relative_to(REPO_ROOT), "private root inside public repository")
    require(not REPO_ROOT.is_relative_to(root), "private root contains public repository")
    require(root.name not in (".", "..", ""), "unsafe destination")
    return root


def permitted_download_command(railway_bin, target):
    """One exact non-mutating subcommand, for an exact known original volume."""
    return [
        str(railway_bin), "volume", "--project", PROJECT,
        "--environment", ENVIRONMENT, "--service", SERVICE,
        "files", "--volume", VOLUME,
        "download", "/", str(target), "--concurrency", "1",
    ]


def validate_railway_cli(railway_bin):
    """Fail closed on an unverified binary or mismatched real CLI grammar.

    These commands are all help/version; they must never open a volume,
    send a production request, read workspace bytes or modify files.
    The official v5.71.0 artifact is hash-pinned in CI.
    """
    require(railway_bin.is_file() and not railway_bin.is_symlink(),
            "Railway CLI executable is missing")
    require(os.access(railway_bin, os.X_OK), "Railway CLI not executable")
    require(railway_bin.is_absolute(), "Railway CLI path must be absolute")
    require(railway_bin.parent.resolve() == railway_bin.parent,
            "Railway CLI directory must not resolve through symlinks")
    commands = (
        ([str(railway_bin), "--version"], ("railway", PINNED_CLI_VERSION)),
        ([str(railway_bin), "volume", "files", "--help"],
         ("download", "--volume")),
        (permitted_download_command(railway_bin, "/nonexistent/nexus-no-file-copy")
         + ["--help"], ("--concurrency", "download")),
    )
    # --version and --help never need the Railway token; keep every
    # ambient provider/CI credential out of these parser subprocesses.
    clean_environment = child_env(railway_download=False)
    for stage, (cmd, required_tokens) in enumerate(commands):
        try:
            probe = subprocess.run(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=clean_environment, check=False, timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CaptureBlocked("Railway CLI local grammar preflight failed") from None
        content = probe.stdout.decode("utf-8", "replace").lower()
        require(probe.returncode == 0 and
                all(token.lower() in content for token in required_tokens),
                "Railway CLI version or download syntax unsupported (stage " +
                str(stage + 1) + ", exit " + str(probe.returncode) + ")")
    return True


def require_regular_copy(root):
    """Reject symlink/pipes/device/hard-link or path escape in downloaded tree."""
    require(root.is_dir() and not root.is_symlink(), "no copied directory")
    require(root == root.resolve(), "copied directory escaped private root")
    total = 0
    for path in root.rglob("*"):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode), "symlink in copied volume")
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                "non-regular content in copied volume")
        if stat.S_ISREG(info.st_mode):
            require(info.st_nlink == 1, "hard-linked file in copied volume")
            total += 1
            require(total <= MAX_COPY_FILES, "too many files in copied volume")
    return total


def validate_final_private_receipt(copy, report_dir, rust_requested):
    """Revalidate child evidence and private bytes at the final receipt boundary.

    The child succeeded earlier, but neither its exit code nor an old PASS
    report proves that bytes and origin metadata are still the same when this
    parent script signs off. No provider access or private paths are logged.
    """
    require(report_dir.is_dir() and not report_dir.is_symlink()
            and report_dir == report_dir.resolve(),
            "private intake directory is not canonical")
    # Reuse the validated archive and file grammar, but perform new reads in
    # the parent *after* the child has exited. This is temporal corroboration,
    # not an independent implementation or atomic Railway snapshot.
    spec = importlib.util.spec_from_file_location("nexus_final_private_intake", INTAKE)
    private = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(private)
    archive = report_dir / "nexus-private-data-snapshot.json"
    report_file = report_dir / "intake-report.json"
    require(archive.lstat().st_nlink == 1 and report_file.lstat().st_nlink == 1,
            "private evidence hard link is not permitted")
    raw_report = private.snapshot.read_regular(report_file, 32768)
    inspection = json.loads(raw_report, object_pairs_hook=private.snapshot.unique_object)
    require(isinstance(inspection, dict), "private intake report is invalid")
    required = {
        "schema": "nexus.offhost-volume-intake.v1",
        "status": "STRUCTURAL_REHEARSAL_PASS",
        "volume_id": VOLUME,
        "deployment_id": DEPLOYMENT,
        "runtime_commit": RUNTIME,
        "provider_identity": "operator_supplied_unverified",
        "copy_provenance": "unverified",
        "production_volume_contents": "not_directly_observed",
        "source_consistency": "not_verified",
        "independent_railway_backup": "not_proven",
        "live_survival": "not_evaluated",
        "live_recovery": "not_evaluated",
        "isolated_byte_roundtrip": True,
        "restored_quarantined": True,
        "local_copy_scans_matched_archive": True,
        "authority": "none",
    }
    for key, expected in required.items():
        require(type(inspection.get(key)) is type(expected) and
                inspection[key] == expected, "private intake report field disagrees")
    audit_expected = {
        "rust_core_audit": ("pass_operator_supplied_rust_binary"
                            if rust_requested else "not_evaluated"),
        "rust_core_binary_identity": ("operator_supplied_unverified"
                                      if rust_requested else "not_verified"),
        "rust_core_source_parity": ("pass_selected_pinned_git_blobs"
                                    if rust_requested else "not_evaluated"),
        "post_rust_source_archive_and_restore_rechecked": bool(rust_requested),
    }
    for key, expected in audit_expected.items():
        require(type(inspection.get(key)) is type(expected) and
                inspection[key] == expected, "private Rust audit claim disagrees")
    # Deny undeclared authority or release claims in the child report, even
    # when the expected status fields appear to be correct.
    require(set(inspection) == set(required) | set(audit_expected) |
            {"file_count", "snapshot_sha256", "local_copy_check"},
            "private intake report schema disagrees")
    require(inspection["local_copy_check"] ==
            "before_archive_and_after_restored_bytes",
            "private source-copy scan contract disagrees")

    archive_bytes = private.snapshot.read_regular(archive, private.snapshot.MAX_BYTES)
    digest = hashlib.sha256(archive_bytes).hexdigest()
    records = private.snapshot.validated_records(archive)
    require(inspection.get("snapshot_sha256") == digest and
            type(inspection.get("file_count")) is int and
            inspection["file_count"] == len(records),
            "private archive digest or file count disagrees")
    expected = dict(records)
    source_manifest = {name: (len(data), hashlib.sha256(data).hexdigest())
                       for name, data in records}
    # Must match both archive and live local source after the child report.
    require_regular_copy(copy)
    require(private.local_copy_manifest(copy) == source_manifest,
            "copied source changed after private intake")
    expected.pop(private.snapshot.RECOVERY_MARKER, None)
    restored = report_dir / "isolated-restore-rehearsal"
    private.verify_quarantined_restore(restored, expected)
    # Final read prevents certifying a stale archive or source at receipt time.
    require(hashlib.sha256(private.snapshot.read_regular(
                archive, private.snapshot.MAX_BYTES)).hexdigest() == digest and
            private.local_copy_manifest(copy) == source_manifest and
            private.snapshot.read_regular(report_file, 32768) == raw_report,
            "private archive, source or report changed during final receipt validation")
    private.verify_quarantined_restore(restored, expected)
    return inspection, digest


def execute(args):
    root = protected_target(args.private_root)
    if not args.execute:
        print("PLAN ONLY — no Railway access, download or backup was attempted.")
        print("Target: original NEXUS Stage D volume; mode: readonly-directory-download")
        print("Requires: authenticated Railway CLI session and a NEW private off-repo destination.")
        print("Does NOT prove capture consistency, provider identity or real restore.")
        return 0

    require(os.environ.get("RAILWAY_TOKEN") or os.environ.get("RAILWAY_API_TOKEN"),
            "authenticated CLI environment not configured")
    # Refuse to create a private destination until the real binary accepts
    # the exact pinned version, command option order and --help grammar.
    validate_railway_cli(args.railway_bin)
    require(INTAKE.is_file(), "isolated structural intake is missing")
    previous_umask = os.umask(0o077)
    try:
        root.mkdir(mode=0o700)
        copy = root / "copied-data"
        report_dir = root / "isolated-intake"
        # No --overwrite, no CLI upload/delete/restore, no network call beyond
        # the authenticated Railway CLI's user-approved directory download.
        cmd = permitted_download_command(args.railway_bin, copy)
        try:
            result = subprocess.run(
                cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False, timeout=1200,
                env=child_env(railway_download=True),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CaptureBlocked("volume download did not complete") from None
        require(result.returncode == 0, "volume download failed")
        require_regular_copy(copy)
        verify = [
            sys.executable, str(INTAKE),
            "--export-root", str(copy),
            "--private-evidence-dir", str(report_dir),
            "--volume-id", VOLUME,
            "--deployment-id", DEPLOYMENT,
            "--runtime-commit", RUNTIME,
        ]
        if args.rust_validator_bin is not None:
            verify.extend(["--rust-validator-bin", str(args.rust_validator_bin)])
        try:
            check = subprocess.run(
                verify, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False, timeout=90,
                env=child_env(railway_download=False, private_home=root),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CaptureBlocked("isolated structural verification did not finish") from None
        require(check.returncode == 0, "isolated structural verification failed")
        inspection, archive_digest = validate_final_private_receipt(
            copy, report_dir, rust_requested=args.rust_validator_bin is not None)
        receipt = {
            "schema": "nexus.railway-volume-readonly-capture.v1",
            "status": "PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS",
            "scope": "operator-authenticated-cli-download-to-private-directory",
            "target": {"project_id": PROJECT, "environment_id": ENVIRONMENT,
                       "service_id": SERVICE, "volume_id": VOLUME},
            "cli_subcommand": "volume files download",
            "source_consistency": "NOT_VERIFIED_ATOMIC",
            "rust_core_audit": inspection.get("rust_core_audit", "not_evaluated"),
            "rust_core_binary_identity": inspection["rust_core_binary_identity"],
            "rust_core_source_parity": inspection["rust_core_source_parity"],
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
        receipt_path = report_dir / "capture-receipt.json"
        with receipt_path.open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
        receipt_path.chmod(0o600)
        print("PRIVATE READ-ONLY CAPTURE + STRUCTURAL REHEARSAL: PASS")
        print("Provider provenance, atomic capture, production recovery: NOT VERIFIED.")
        return 0
    finally:
        os.umask(previous_umask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--railway-bin", type=Path, default=Path("/usr/local/bin/railway"))
    parser.add_argument("--rust-validator-bin", type=Path,
                        help="optional operator-built Rust durable-audit executable for copied data")
    parser.add_argument("--execute", action="store_true", help="Operator opts in to CLI download")
    args = parser.parse_args()
    try:
        return execute(args)
    except (CaptureBlocked, ValueError, OSError, UnicodeError) as e:
        # Intentionally never echo paths, credentials, downloaded names or data.
        print("PRIVATE READ-ONLY CAPTURE: BLOCKED — " +
              (str(e) if isinstance(e, CaptureBlocked) else type(e).__name__),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
