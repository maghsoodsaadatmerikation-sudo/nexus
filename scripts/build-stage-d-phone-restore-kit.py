#!/usr/bin/env python3
"""Deterministic minimal offline recovery ZIP; no private data or Railway client."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = "nexus-stage-d-offline-recovery"
CERT = "docs/keys/stage-d-recovery-public-cert.pem"
CERT_SHA = "b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091"
PROJECT = "2ac7887b-d67a-48be-8a7b-bd54092893ae"
ENVIRONMENT = "56c4bc45-0e62-4aa9-832f-884bb1aa620c"
SERVICE = "0032fc74-2c52-475d-b9df-9dca59237d93"
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
DEPLOYMENT = "32cdcb2b-c03c-4a6f-b028-27a9977717ce"
RUNTIME = "9abbc067aad3ebbb0956432cf6682d2ea70e2824"
REQUIRED = ("scripts/restore-stage-d-encrypted-escrow.py",
            "scripts/data-snapshot.py",
            "scripts/private_subprocess_env.py")
SCHEMA = "nexus.stage-d-offline-recovery-kit.v1"
FIXED = (2020, 1, 1, 0, 0, 0)
README = """NEXUS Stage D | Private offline quarantined restore
==================================================

This public-only package contains NO real backup, owner private key,
tokens, Railway connection or original workspace data.

Requirements: previously preserved real .cms encrypted file and exact
receipt .json; the ALREADY-HELD matching private RSA key; a trusted
private Linux or Termux environment with Python and OpenSSL.
Install public Termux dependencies: pkg install python openssl unzip
Extract this package into Termux private HOME, never shared Downloads.
Use a NEW destination under an existing private owner-only directory.

./restore-local.sh /ABS/COPY.cms /ABS/receipt.json /ABS/private-key.pem /ABS/NEW-QUARANTINE

Existing output is never overwritten. The RSA key must already exist
outside this package as a regular single-link file with owner-only 0600
permissions. Never upload it or plaintext backups to GitHub/ChatGPT.
The .cms and receipt must be genuine files retained independently
by the owner; the package cannot determine their provider provenance.
The output includes .nexus-recovery-required and MUST NOT be directly
mounted into a running NEXUS server or treated as authorized resume.

PASS means authenticated local decryption of the supplied data and a
byte-exact isolated quarantined restoration. It does NOT prove live
Railway provenance, atomic backup capture, owner custody, original
workspace completeness, production restore or release authority.
Physical Android compatibility has NOT been established in CI.
Missing Linux renameat2 support must BLOCK, never downgrade safety.
"""
LAUNCHER = r"""#!/bin/sh
set -eu
umask 077
if [ "$#" -ne 4 ]; then
  printf '%s\n' 'Usage: ./restore-local.sh /ABS/cipher.cms /ABS/receipt.json /ABS/key.pem /ABS/NEW-QUARANTINE' >&2
  exit 2
fi
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$HERE/scripts/restore-stage-d-encrypted-escrow.py" \
  --ciphertext "$1" --receipt "$2" --private-key "$3" --destination "$4"
"""


def hash_of(data):
    return hashlib.sha256(data).hexdigest()


def reviewed_source(name):
    p = ROOT / name
    st = p.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or
            p.is_symlink() or not 0 < st.st_size <= 60000):
        raise ValueError("public source not regular or oversized")
    return p.read_bytes()


def exact_constant(code, name, value):
    if code.splitlines().count(name + ' = "' + value + '"') != 1:
        raise ValueError("reviewed Stage D source constants changed")


def package_files(commit):
    if not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("exact source commit required")
    capture = reviewed_source("scripts/capture-railway-volume-readonly.py").decode()
    escrow = reviewed_source("scripts/stage-d-encrypted-escrow.py").decode()
    for k, v in (("PROJECT", PROJECT), ("ENVIRONMENT", ENVIRONMENT), ("SERVICE", SERVICE),
                 ("VOLUME", VOLUME), ("DEPLOYMENT", DEPLOYMENT), ("RUNTIME", RUNTIME)):
        exact_constant(capture, k, v)
    exact_constant(escrow, "CERT_SHA256", CERT_SHA)
    if escrow.splitlines().count(
            'EVIDENCE = ("nexus-private-data-snapshot.json", "intake-report.json", "capture-receipt.json")') != 1 or \
       escrow.splitlines().count("MAX_EVIDENCE = 64 * 1024 * 1024 + 64 * 1024") != 1:
        raise ValueError("evidence contract changed")
    files = {name: reviewed_source(name) for name in REQUIRED}
    files[CERT] = reviewed_source(CERT)
    if hash_of(files[CERT]) != CERT_SHA or b"PRIVATE KEY" in files[CERT]:
        raise ValueError("public recipient certificate changed")
    # Constants-only shims satisfy the reviewed restore module imports.
    # The Railway client/download and escrow-encryption entrypoints are NOT
    # copied into the owner recovery ZIP.
    files["scripts/capture-railway-volume-readonly.py"] = (
        '# Original provider identifiers only; no CLI or provider network code.\n'
        + f'PROJECT = "{PROJECT}"\nENVIRONMENT = "{ENVIRONMENT}"\nSERVICE = "{SERVICE}"\n'
        + f'VOLUME = "{VOLUME}"\nDEPLOYMENT = "{DEPLOYMENT}"\nRUNTIME = "{RUNTIME}"\n'
    ).encode()
    files["scripts/stage-d-encrypted-escrow.py"] = (
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parent.parent\n"
        + f'CERT = REPO / "{CERT}"\n'
        + f'CERT_SHA256 = "{CERT_SHA}"\n'
        + 'EVIDENCE = ("nexus-private-data-snapshot.json", "intake-report.json", "capture-receipt.json")\n'
        + "MAX_EVIDENCE = 64 * 1024 * 1024 + 64 * 1024\n"
    ).encode()
    files["README.txt"] = README.encode()
    files["restore-local.sh"] = LAUNCHER.encode()
    manifest = {
        "schema": SCHEMA, "source_commit": commit,
        "pinned_recipient_cert_sha256": CERT_SHA,
        "pinned_project": PROJECT, "pinned_environment": ENVIRONMENT,
        "pinned_service": SERVICE,
        "pinned_original_volume": VOLUME,
        "pinned_deployment": DEPLOYMENT,
        "pinned_runtime": RUNTIME,
        "private_key_included": False, "real_backup_included": False,
        "railway_client_included": False, "android_hardware_verified": False,
        "production_restore_authorized": False, "authority": "none",
        "contents": {k: {"bytes": len(v), "sha256": hash_of(v)}
                     for k, v in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    return files


def verify_zip(path, exact_commit=None):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 120000:
        raise ValueError("archive missing or oversized")
    with zipfile.ZipFile(path, "r", allowZip64=False) as archive:
        infos = archive.infolist()
        allowed = set(package_files("a" * 40))
        if len(infos) != len(allowed):
            raise ValueError("unexpected entry count")
        data = {}
        for info in infos:
            prefix = BUNDLE + "/"
            if not info.filename.startswith(prefix):
                raise ValueError("unknown archive prefix")
            member = info.filename[len(prefix):]
            if member not in allowed or member in data or ".." in PurePosixPath(member).parts or \
               info.is_dir() or info.compress_type != zipfile.ZIP_STORED or info.file_size > 60000 or \
               not stat.S_ISREG(info.external_attr >> 16):
                raise ValueError("unexpected or unsafe archive entry")
            data[member] = archive.read(info)
    manifest = json.loads(data["manifest.json"])
    commit = manifest.get("source_commit")
    if not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit) or \
       (exact_commit is not None and commit != exact_commit):
        raise ValueError("archive source commit differs")
    if data != package_files(commit):
        raise ValueError("archive differs from reviewed exact source")
    return True


def build(output, commit):
    if not output.is_absolute() or output.exists() or output.is_symlink() or \
       output.is_relative_to(ROOT) or ROOT.is_relative_to(output) or \
       not output.parent.is_dir() or output.parent != output.parent.resolve():
        raise ValueError("new outside-repository absolute ZIP path required")
    files = package_files(commit)
    old = os.umask(0o077)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as z:
            for name, payload in sorted(files.items()):
                zi = zipfile.ZipInfo(BUNDLE + "/" + name, date_time=FIXED)
                zi.create_system = 3
                zi.external_attr = ((0o100755 if name == "restore-local.sh" else 0o100644) << 16)
                zi.compress_type = zipfile.ZIP_STORED
                z.writestr(zi, payload)
    finally:
        os.umask(old)
    verify_zip(output, exact_commit=commit)
    return hash_of(output.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--output", type=Path)
    modes.add_argument("--verify-zip", type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    try:
        if args.output:
            if not args.source_commit:
                raise ValueError("source commit required")
            print("STAGE D OFFLINE RECOVERY KIT BUILD SHA256:",
                  build(args.output, args.source_commit))
        else:
            verify_zip(args.verify_zip, exact_commit=args.source_commit)
            print("STAGE D OFFLINE RECOVERY KIT: SOURCE INTEGRITY PASS (not independent signature)")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        print("STAGE D OFFLINE RECOVERY KIT: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
