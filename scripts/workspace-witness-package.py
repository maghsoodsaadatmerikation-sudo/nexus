#!/usr/bin/env python3
"""Build, install and verify a root-owned NEXUS witness custodian code bundle.

No third-party service, SSH host, receiver account, signing key or mutable
runtime state is created. Install requires root and an independently approved
SHA-256 commitment to the exact bundle; an in-repo hash is not trust evidence.
Only allowlisted standalone Python files are included, never private keys.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys

SCHEMA = "nexus.offsite.custodian-code-bundle.v1"
INSTALL_SCHEMA = "nexus.offsite.custodian-install-record.v1"
SOURCES = (
    "workspace-attestation.py",
    "workspace-trust.py",
    "workspace-offsite-witness.py",
    "workspace-witness-custodian.py",
    "workspace-witness-recovery.py",
    "workspace-witness-host.py",
)
MAX_BUNDLE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 96 * 1024
HEX_SHA = re.compile(r"[a-f0-9]{64}\Z")


class PackageError(Exception):
    pass


def fail(message):
    raise PackageError(message)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("duplicated JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: fail("non-finite JSON"))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise PackageError("invalid bounded package JSON") from exc


def read_regular(path, limit, *, owner=None, no_write=False):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags), "rb") as stream:
        meta = os.fstat(stream.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                or meta.st_size < 1 or meta.st_size > limit
                or (owner is not None and meta.st_uid != owner)
                or (no_write and meta.st_mode & 0o022)):
            fail("input has unsafe ownership, links, permissions or size")
        content = stream.read(limit + 1)
    if not content or len(content) > limit:
        fail("input exceeds bounded size")
    return content


def check_root_ancestry(path):
    if not path.is_absolute() or path == Path("/") or ".." in path.parts:
        fail("destination must be an absolute, non-root, normalized path")
    if str(path) != os.path.normpath(str(path)):
        fail("destination must not contain redundant components")
    current = Path("/")
    for part in path.parts[1:]:
        current /= part
        meta = current.lstat()
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0
                or meta.st_mode & 0o022):
            fail("installation ancestry must be root-owned and non-writable")
    return path


def write_exclusive(path, content, mode=0o644):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(path, mode, follow_symlinks=False)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def output_parent(path):
    if not path.is_absolute():
        fail("output path must be absolute")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        fail("output parent missing or unsafe")
    return parent


def build(args):
    source = args.source_dir
    if not source.is_absolute() or not source.is_dir():
        fail("explicit absolute source directory required")
    if args.output.resolve() in source.resolve().parents:
        fail("bundle cannot overwrite or be created inside executable source tree")
    contents = []
    for name in SOURCES:
        raw = read_regular(source / name, MAX_SOURCE_BYTES)
        contents.append({
            "name": name, "sha256": digest(raw),
            "content_base64": base64.b64encode(raw).decode("ascii"),
        })
    raw_bundle = canonical({"schema": SCHEMA, "files": contents})
    if len(raw_bundle) > MAX_BUNDLE_BYTES:
        fail("source package exceeds bounded size")
    output_parent(args.output)
    write_exclusive(args.output, raw_bundle, 0o600)
    print("NEXUS WITNESS BUNDLE CREATED: sha256=" + digest(raw_bundle) +
          " (digest must be independently approved before root installation)")


def decode_bundle(path, expected_sha):
    if not HEX_SHA.fullmatch(expected_sha):
        fail("independently approved lowercase SHA-256 is required")
    raw = read_regular(path, MAX_BUNDLE_BYTES)
    if digest(raw) != expected_sha:
        fail("bundle differs from independently approved digest")
    bundle = load_json(raw)
    if (not isinstance(bundle, dict) or set(bundle) != {"schema", "files"}
            or bundle["schema"] != SCHEMA
            or not isinstance(bundle["files"], list)
            or len(bundle["files"]) != len(SOURCES)):
        fail("invalid code bundle schema")
    extracted = []
    for i, record in enumerate(bundle["files"]):
        if (not isinstance(record, dict)
                or set(record) != {"name", "sha256", "content_base64"}
                or record["name"] != SOURCES[i]
                or not isinstance(record["sha256"], str)
                or not HEX_SHA.fullmatch(record["sha256"])
                or not isinstance(record["content_base64"], str)):
            fail("unexpected code bundle entry")
        try:
            blob = base64.b64decode(record["content_base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PackageError("noncanonical source file encoding") from exc
        if (not blob or len(blob) > MAX_SOURCE_BYTES
                or digest(blob) != record["sha256"]
                or base64.b64encode(blob).decode("ascii") != record["content_base64"]):
            fail("code bundle entry differs from committed digest")
        extracted.append((record["name"], blob, record["sha256"]))
    if raw != canonical(bundle):
        fail("noncanonical code bundle serialization")
    return extracted


def record_for(extracted, bundle_sha):
    return {
        "schema": INSTALL_SCHEMA,
        "bundle_sha256": bundle_sha,
        "files": [{"name": n, "sha256": checksum} for n, _, checksum in extracted],
    }


def ensure_root():
    if os.name != "posix" or os.geteuid() != 0:
        fail("installation requires explicit administrator/root execution")


def install(args):
    ensure_root()
    if not args.destination.is_absolute():
        fail("installation destination must be absolute")
    check_root_ancestry(args.destination.parent)
    if os.path.lexists(args.destination):
        fail("installation destination already exists; never overwrite a deployment")
    extracted = decode_bundle(args.bundle, args.trusted_sha256)
    parent = args.destination.parent
    scratch = parent / (".nexus-custodian-" + secrets.token_hex(12))
    os.mkdir(scratch, 0o700)
    try:
        for name, raw, _ in extracted:
            write_exclusive(scratch / name, raw, 0o644)
        write_exclusive(scratch / "install.json",
                        canonical(record_for(extracted, args.trusted_sha256)), 0o644)
        os.chmod(scratch, 0o755)
        # Parent is root-owned, non-group-writable and already checked.
        if os.path.lexists(args.destination):
            fail("destination appeared during installation")
        os.rename(scratch, args.destination)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
    print("NEXUS WITNESS CODE INSTALLED: pinned digest, root ownership; no SSH/account/key deployed")


def verify(args):
    check_root_ancestry(args.destination)
    if not HEX_SHA.fullmatch(args.trusted_sha256):
        fail("trusted bundle hash required")
    manifest_raw = read_regular(args.destination / "install.json", 8192,
                                owner=0, no_write=True)
    manifest = load_json(manifest_raw)
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema", "bundle_sha256", "files"}
            or manifest["schema"] != INSTALL_SCHEMA
            or manifest["bundle_sha256"] != args.trusted_sha256
            or not isinstance(manifest["files"], list)
            or len(manifest["files"]) != len(SOURCES)
            or manifest_raw != canonical(manifest)):
        fail("invalid or untrusted installed code manifest")
    for i, item in enumerate(manifest["files"]):
        if (not isinstance(item, dict) or set(item) != {"name", "sha256"}
                or item["name"] != SOURCES[i]
                or not isinstance(item["sha256"], str)
                or not HEX_SHA.fullmatch(item["sha256"])):
            fail("unexpected installed source identity")
        raw = read_regular(args.destination / SOURCES[i], MAX_SOURCE_BYTES,
                           owner=0, no_write=True)
        if digest(raw) != item["sha256"]:
            fail("installed script digest mismatch")
    found = {entry.name for entry in args.destination.iterdir()}
    if found != set(SOURCES) | {"install.json"}:
        fail("unexpected installed executable, symlink or file")
    # A self-contained manifest is not an independent trust anchor. The
    # operator must supply the originally approved bundle bytes on every
    # verification; otherwise attacker-edited files+manifest could agree.
    extracted = decode_bundle(args.bundle, args.trusted_sha256)
    if record_for(extracted, args.trusted_sha256) != manifest:
        fail("installed manifest differs from independently approved bundle")
    print("NEXUS WITNESS CODE VERIFIED: root-owned, exact hashes, approved bundle reference")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    builder = subs.add_parser("build")
    builder.add_argument("--source-dir", type=Path, required=True)
    builder.add_argument("--output", type=Path, required=True)
    installer = subs.add_parser("install")
    installer.add_argument("--bundle", type=Path, required=True)
    installer.add_argument("--trusted-sha256", required=True)
    installer.add_argument("--destination", type=Path, required=True)
    checker = subs.add_parser("verify")
    checker.add_argument("--destination", type=Path, required=True)
    checker.add_argument("--trusted-sha256", required=True)
    checker.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        {"build": build, "install": install, "verify": verify}[args.action](args)
    except (PackageError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("NEXUS WITNESS INSTALLATION DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
