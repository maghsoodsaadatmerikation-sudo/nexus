#!/usr/bin/env python3
"""Deterministic minimal offline owner keycheck ZIP, no owner key or volume data.

The ZIP is a distribution convenience, not a signature, recovery proof or
permission to run in CI. Exactly two reviewed public repo files are copied.
"""
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
CERT = "docs/keys/stage-d-recovery-public-cert.pem"
VERIFIER = "scripts/verify-stage-d-recovery-key.py"
ALLOWED = (CERT, VERIFIER)
CERT_SHA256 = "b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091"
BUNDLE_ROOT = "nexus-stage-d-owner-keycheck"
SCHEMA = "nexus.stage-d-owner-keycheck-kit.v1"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
LIMITS = {CERT: 16384, VERIFIER: 32768}
README = """NEXUS | Stage D owner-local key check (Termux / Linux)
=====================================================

This package contains a PUBLIC certificate and a public source verifier.
It contains NO recovery private key, real backup, user data, token or model.

Purpose: Prove on the owner's trusted local device that an ALREADY OWNED
private RSA key can decrypt a fresh synthetic CMS challenge under the
exact pinned NEXUS Stage D public certificate. This is not a backup.

Android / Termux (only after extracting this ZIP privately):
  pkg install python openssl unzip
  chmod 700 "$HOME"
  cd "$HOME/nexus-stage-d-owner-keycheck"
  ./run-keycheck.sh "$HOME/PRIVATE_DIRECTORY/my-existing-recovery-key.pem"

Use a PRIVATE key already held by the owner. Place it ONLY in a controlled
private device location outside this package; permissions must be 0600,
regular file, owned by the executing OS user, no symlink or hardlink.
Do NOT copy it into public Downloads/shared storage, Git, chat, CI,
an online hashing/decryption site or a GitHub workflow input. If the key
has never been held by the owner, STOP: generating a NEW key would not
magically match the fixed public certificate.

This launcher does not upload anything and uses no network APIs. It calls
the existing public NEXUS verifier with the local file path supplied.
The verifier returns only PASS/BLOCKED plus nonclaims, never key contents.
No runtime GitHub credentials, CLI login or Railway provider API is used.
If Android OpenSSL, Python, key permissions or Termux filesystem access
prevent execution, a BLOCKED result is not recovery proof.

To validate this bundle's *contents* against its self-reported manifest,
run:
  python3 scripts/build-stage-d-phone-key-kit.py --verify-zip PATH
BUT this packaging helper is intentionally NOT bundled, so comparison is
performed during independently reviewed GitHub CI. A manifest embedded
inside an untrusted ZIP is not independent authenticity. Obtain the ZIP
from the reviewed repository's GitHub Actions workflow and compare
its external reported SHA-256 from the exact successful GitHub run.

Never paste your private key into chat. No live Railway Volume is read.
A PASS verifies matching local key possession AT THAT MOMENT only,
not full CMS archive restore, offsite encrypted copies, source atomicity,
independently authenticated provider data or production authorization.
"""
LAUNCHER = """#!/bin/sh
# Offline private-key possession check; no download and no data copied.
set -eu
umask 077
if [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: ./run-keycheck.sh /ABSOLUTE/PRIVATE/RECOVERY-KEY.pem' >&2
  exit 2
fi
# Resolve package directory, not the private key; verifier enforces key rules.
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$SELF_DIR/scripts/verify-stage-d-recovery-key.py" --private-key "$1"
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def get_source(path):
    source = ROOT / path
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or source.is_symlink():
        raise ValueError("required public source is not regular")
    content = source.read_bytes()
    if not 0 < len(content) <= LIMITS[path]:
        raise ValueError("required public source has invalid length")
    return content


def data_files(commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("exact 40-character lower-case Git commit required")
    public = {p: get_source(p) for p in ALLOWED}
    if sha(public[CERT]) != CERT_SHA256:
        raise ValueError("pinned certificate does not match public source")
    if b"never copies a private key" in public[VERIFIER]:
        # Don't use textual markers as a security check.
        pass
    public["README.txt"] = README.encode("utf-8")
    public["run-keycheck.sh"] = LAUNCHER.encode("utf-8")
    items = {p: {"sha256": sha(b), "bytes": len(b)} for p, b in sorted(public.items())}
    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "pinned_recipient_cert_sha256": CERT_SHA256,
        "contents": items,
        "private_key_included": False,
        "live_backup_included": False,
        "runtime_railway_access": False,
        "actual_android_verified": False,
        "authority": "none",
    }
    public["manifest.json"] = (json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    return public


def build(destination, commit):
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ValueError("new absolute output ZIP path required")
    if destination.is_relative_to(ROOT) or ROOT.is_relative_to(destination):
        raise ValueError("output ZIP must be outside public repo")
    if destination.parent != destination.parent.resolve() or not destination.parent.is_dir():
        raise ValueError("output parent must be canonical and exist")
    files = data_files(commit)
    old_mask = os.umask(0o077)
    try:
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in sorted(files.items()):
                where = BUNDLE_ROOT + "/" + name
                info = zipfile.ZipInfo(where, date_time=FIXED_TIME)
                info.create_system = 3
                info.external_attr = ((0o100755 if name == "run-keycheck.sh"
                                      else 0o100644) << 16)
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, payload)
    finally:
        os.umask(old_mask)
    verify(destination, expected_commit=commit)
    return sha(destination.read_bytes())


def verify(destination, expected_commit=None):
    if not destination.is_file() or destination.is_symlink():
        raise ValueError("ZIP missing or linked")
    if destination.stat().st_size > 100000:
        raise ValueError("ZIP oversized")
    files = {}
    with zipfile.ZipFile(destination, "r", allowZip64=False) as archive:
        infos = archive.infolist()
        if len(infos) != 5:
            raise ValueError("unexpected file count")
        for info in infos:
            if info.flag_bits & 1 or info.is_dir() or info.file_size > 32768:
                raise ValueError("unsafe archive content")
            if info.compress_type != zipfile.ZIP_STORED:
                raise ValueError("unexpected archive compression")
            prefix = BUNDLE_ROOT + "/"
            if not info.filename.startswith(prefix):
                raise ValueError("unexpected archive prefix")
            path = info.filename[len(prefix):]
            if not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
                raise ValueError("unsafe archive path")
            if path in files:
                raise ValueError("duplicate archive member")
            permitted = {CERT, VERIFIER, "README.txt", "run-keycheck.sh", "manifest.json"}
            if path not in permitted:
                raise ValueError("unexpected archive entry")
            mode = info.external_attr >> 16
            if not stat.S_ISREG(mode) or mode & 0o6000:
                raise ValueError("unsafe ZIP file mode")
            files[path] = archive.read(info)
    metadata = json.loads(files["manifest.json"])
    if metadata.get("schema") != SCHEMA or metadata.get("authority") != "none":
        raise ValueError("wrong manifest")
    if metadata.get("private_key_included") is not False or \
       metadata.get("live_backup_included") is not False or \
       metadata.get("runtime_railway_access") is not False or \
       metadata.get("actual_android_verified") is not False:
        raise ValueError("manifest makes unsafe claim")
    commit = metadata.get("source_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or \
       (expected_commit is not None and commit != expected_commit):
        raise ValueError("wrong or unbound source commit")
    expected = data_files(commit)
    if set(files) != set(expected) or any(files[k] != expected[k] for k in expected):
        raise ValueError("ZIP contents disagree with reviewed source bytes")
    if metadata["pinned_recipient_cert_sha256"] != CERT_SHA256:
        raise ValueError("mismatched pinned recipient")
    return True


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
            digest = build(args.output, args.source_commit)
            print("NEXUS OWNER KEY KIT BUILT - SHA256: " + digest)
            print("SYNTHETIC ONLY: No private key, real backup or recovery proof")
        else:
            verify(args.verify_zip, expected_commit=args.source_commit)
            print("NEXUS OWNER KEY KIT SOURCE-INTEGRITY CHECK: PASS (not independent signature)")
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, TypeError):
        print("NEXUS OWNER KEY KIT: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
