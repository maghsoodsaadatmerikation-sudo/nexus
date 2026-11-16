#!/usr/bin/env python3
"""Reproducible NEXUS local-operator pilot bundle (not a production installer).

Only enumerated, audited sources are packaged; all bundle and installed files
have digest checks. A SHA-256 supplied via the *same untrusted bundle* cannot
authenticate a publisher: install requires an independently obtained digest.
No root, Docker, network, auto-execution, workspace import or upgrade occurs.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile

SCHEMA = "nexus.operator.distribution.v1"
MANIFEST = "bundle-manifest.json"
MAX_FILE_BYTES = 131072
MAX_ARCHIVE_BYTES = 2097152
SHA = re.compile(r"[0-9a-f]{64}\Z")
FILES = tuple(sorted((
    "nexus-cloud/agent_workspace.py",
    "nexus-cloud/engineering_agent.py",
    "nexus-cloud/agent_journal.py",
    "nexus-cloud/agent_host_census.py",
    "nexus-cloud/agent_chat_handoff.py",
    "nexus-cloud/agent_research.py",
    "nexus-cloud/agent_rootless_probe.py",
    "nexus-cloud/agent_rootless_job.py",
    "nexus-cloud/agent_operator_service.py",
    "nexus-cloud/agent_operator_pilot.py",
    "scripts/nexus-operator-pilot.py",
    "scripts/nexus-operator-service.py",
    "scripts/nexus-rootless-job.py",
    "scripts/nexus-chat-engineering.py",
    "scripts/nexus-engineering-plan.py",
    "scripts/nexus-agent-workspace.py",
    "scripts/nexus-rootless-probe.py",
    "scripts/nexus-operator-distribution.py",
    "scripts/nexus-operator-launch.py",
    "scripts/rootless-sandbox-probe.c",
    "docs/PHASE16-ROOTLESS-OPERATOR-JOBS.md",
    "docs/PHASE20-DOCKER-CLEANUP-FENCE.md",
    "docs/PHASE21-OPERATOR-PILOT-ACCEPTANCE.md",
    "docs/PHASE23-VERIFIED-FIRST-RUN.md",
    "docs/PHASE24-SIDE-BY-SIDE-REVIEW.md",
)))
assert len(FILES) == len(set(FILES))


class DistributionDenied(ValueError):
    """Reject unsafe or ambiguous input without executing source."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _unique(pairs):
    value = {}
    for name, field in pairs:
        if name in value:
            raise DistributionDenied("duplicate-json-key")
        value[name] = field
    return value


def _load_json(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DistributionDenied("invalid-bundle-manifest") from exc
    if not isinstance(value, dict) or _json(value) != raw:
        raise DistributionDenied("noncanonical-bundle-manifest")
    return value


def _info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def _manifest(blobs: dict[str, bytes]) -> bytes:
    return _json({
        "schema": SCHEMA,
        "platform": "linux-nonroot-operator-pilot",
        "minimum_python": "3.13",
        "authenticated": False,
        "source_files": [
            {"path": name, "sha256": _sha(blobs[name]), "bytes": len(blobs[name])}
            for name in FILES
        ],
    })


def _read_source(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise DistributionDenied("source-root-missing")
    result = {}
    for name in FILES:
        file = root / name
        st = file.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
            raise DistributionDenied("source-not-regular-or-too-large")
        if any((root / Path(*Path(name).parts[:i])).is_symlink()
               for i in range(1, len(Path(name).parts))):
            raise DistributionDenied("source-parent-is-symlink")
        data = file.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise DistributionDenied("source-too-large")
        result[name] = data
    return result


def build(root: Path, archive: Path) -> dict:
    """Create a deterministic, stored-only ZIP; refuse clobbering output."""
    sources = _read_source(root)
    manifest = _manifest(sources)
    if not archive.parent.is_dir() or archive.is_symlink() or archive.exists():
        raise DistributionDenied("bundle-output-must-be-new")
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            with zipfile.ZipFile(stream, "w", allowZip64=False) as bundle:
                for name in FILES:
                    bundle.writestr(_info(name), sources[name])
                bundle.writestr(_info(MANIFEST), manifest)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        archive.unlink(missing_ok=True)
        raise
    report = verify(archive)
    if report["file_count"] != len(FILES):
        raise DistributionDenied("bundle-file-count")
    return report


def verify(archive: Path, *, expected_sha256: str | None = None) -> dict:
    """Validate all bytes, names, entry types, lengths, hashes and manifest.

    Internal hashes ensure integrity only; authenticity requires a trusted,
    out-of-band expected ZIP SHA-256 supplied by the operator.
    """
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or not SHA.fullmatch(expected_sha256)
    ):
        raise DistributionDenied("invalid-expected-archive-sha")
    st = archive.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_ARCHIVE_BYTES:
        raise DistributionDenied("unsafe-or-oversized-archive")
    raw_zip = archive.read_bytes()
    digest = _sha(raw_zip)
    if expected_sha256 is not None and digest != expected_sha256:
        raise DistributionDenied("archive-sha-mismatch")
    with zipfile.ZipFile(archive, "r", allowZip64=False) as bundle:
        infos = bundle.infolist()
        names = [i.filename for i in infos]
        if (len(names) != len(FILES) + 1 or len(set(names)) != len(names)
                or set(names) != set(FILES) | {MANIFEST}):
            raise DistributionDenied("unexpected-bundle-entry")
        for info in infos:
            mode = (info.external_attr >> 16)
            if (info.flag_bits & 1 or info.compress_type != zipfile.ZIP_STORED
                    or info.file_size > MAX_FILE_BYTES or
                    info.compress_size != info.file_size or
                    not stat.S_ISREG(mode) or (mode & 0o777) != 0o600):
                raise DistributionDenied("unsafe-bundle-entry")
        manifest_bytes = bundle.read(MANIFEST)
        obj = _load_json(manifest_bytes)
        if (set(obj) != {"schema", "platform", "minimum_python",
                         "authenticated", "source_files"}
                or obj["schema"] != SCHEMA
                or obj["platform"] != "linux-nonroot-operator-pilot"
                or obj["minimum_python"] != "3.13"
                or obj["authenticated"] is not False
                or not isinstance(obj["source_files"], list)
                or len(obj["source_files"]) != len(FILES)):
            raise DistributionDenied("invalid-bundle-manifest")
        expected = []
        for name in FILES:
            payload = bundle.read(name)
            expected.append({"path": name, "sha256": _sha(payload),
                             "bytes": len(payload)})
        if obj["source_files"] != expected:
            raise DistributionDenied("bundle-manifest-hash-mismatch")
    return {
        "status": "verified",
        "schema": SCHEMA,
        "archive_sha256": digest,
        "manifest_sha256": _sha(manifest_bytes),
        "file_count": len(FILES),
        "publisher_authenticated": False,
        "archive_digest_matched": expected_sha256 is not None,
        "production_ready": False,
        "authority": "none",
    }


def _private_parent(parent: Path) -> None:
    """Reject symlink ancestors; final install parent must be 0700 and owned."""
    if not parent.is_absolute() or ".." in parent.parts or parent == Path("/"):
        raise DistributionDenied("invalid-install-parent")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in parent.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise DistributionDenied("install-parent-must-be-private-0700")
    finally:
        os.close(fd)


def _installed_snapshot(destination: Path) -> tuple[dict, dict[str, dict], str]:
    """Verify the COMPLETE installed tree before returning content hashes.

    The private parent/installation and canonical manifest must be safe.
    Never import, execute or write into the installation.
    """
    if not destination.is_absolute() or ".." in destination.parts:
        raise DistributionDenied("invalid-installed-path")
    _private_parent(destination.parent)
    st = destination.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
            or st.st_mode & 0o077):
        raise DistributionDenied("installation-directory-unsafe")
    metadata = destination / MANIFEST
    mst = metadata.lstat()
    if (not stat.S_ISREG(mst.st_mode) or mst.st_uid != os.getuid()
            or mst.st_nlink != 1 or mst.st_mode & 0o077
            or mst.st_size > MAX_FILE_BYTES):
        raise DistributionDenied("installed-manifest-unsafe")
    manifest_bytes = metadata.read_bytes()
    obj = _load_json(manifest_bytes)
    if (set(obj) != {"schema", "platform", "minimum_python",
                     "authenticated", "source_files"}
            or obj["schema"] != SCHEMA
            or obj["platform"] != "linux-nonroot-operator-pilot"
            or obj["minimum_python"] != "3.13"
            or obj["authenticated"] is not False
            or not isinstance(obj["source_files"], list)
            or len(obj["source_files"]) != len(FILES)):
        raise DistributionDenied("invalid-installed-manifest")
    current = {}
    for node in destination.rglob("*"):
        rel = node.relative_to(destination).as_posix()
        st = node.lstat()
        if stat.S_ISDIR(st.st_mode):
            if st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise DistributionDenied("installed-directory-unsafe")
            continue
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_nlink != 1 or st.st_mode & 0o077
                or st.st_size > MAX_FILE_BYTES):
            raise DistributionDenied("installed-file-unsafe")
        current[rel] = {"path": rel, "sha256": _sha(node.read_bytes()),
                        "bytes": st.st_size}
    if set(current) != set(FILES) | {MANIFEST}:
        raise DistributionDenied("installed-files-changed")
    if obj["source_files"] != [current[name] for name in FILES]:
        raise DistributionDenied("installed-file-digest-mismatch")
    return obj, current, _sha(manifest_bytes)


def installed_verify(destination: Path, *, expected_manifest_sha256: str | None = None) -> dict:
    """Verify installed files, optionally against an INDEPENDENT trust digest."""
    if expected_manifest_sha256 is not None and (
            not isinstance(expected_manifest_sha256, str)
            or not SHA.fullmatch(expected_manifest_sha256)):
        raise DistributionDenied("invalid-expected-manifest-sha")
    _, _, actual_sha = _installed_snapshot(destination)
    if expected_manifest_sha256 is not None and actual_sha != expected_manifest_sha256:
        raise DistributionDenied("installed-manifest-anchor-mismatch")
    return {"status": "installed-integrity-verified", "schema": SCHEMA,
            "manifest_sha256": actual_sha, "file_count": len(FILES),
            "manifest_anchor_matched": expected_manifest_sha256 is not None,
            "publisher_authenticated": False, "production_ready": False,
            "authority": "none"}


def compare_installed(current: Path, candidate: Path, *,
                      expected_candidate_manifest_sha256: str,
                      expected_current_manifest_sha256: str | None = None) -> dict:
    """Non-mutating side-by-side review; no upgrades, rollback or self-update.

    The candidate must be pinned to an independently supplied manifest digest.
    This is not a publisher signature or an authorization to promote it.
    """
    if (not isinstance(expected_candidate_manifest_sha256, str)
            or not SHA.fullmatch(expected_candidate_manifest_sha256)):
        raise DistributionDenied("candidate-manifest-sha-required")
    if current == candidate:
        raise DistributionDenied("distinct-installations-required")
    # Snapshot each installation once. Re-reading files after verification
    # would introduce a needless TOCTOU window and inconsistent comparison.
    _, old_entries, old_sha = _installed_snapshot(current)
    _, new_entries, new_sha = _installed_snapshot(candidate)
    if (expected_current_manifest_sha256 is not None
            and (not SHA.fullmatch(expected_current_manifest_sha256)
                 or old_sha != expected_current_manifest_sha256)):
        raise DistributionDenied("previous-manifest-anchor-mismatch")
    if new_sha != expected_candidate_manifest_sha256:
        raise DistributionDenied("candidate-manifest-anchor-mismatch")
    changed = [name for name in FILES
               if old_entries[name]["sha256"] != new_entries[name]["sha256"]]
    return {
        "status": "review-required" if changed else "same-file-content",
        "schema": "nexus.operator.upgrade-review.v1",
        "previous_manifest_sha256": old_sha,
        "candidate_manifest_sha256": new_sha,
        "candidate_manifest_anchor_matched": True,
        "previous_manifest_anchor_matched": expected_current_manifest_sha256 is not None,
        "file_count": len(FILES),
        "changed_file_count": len(changed),
        "changed_paths": changed,
        "unchanged_file_count": len(FILES) - len(changed),
        "files_changed_by_review": False,
        "data_migrated": False,
        "upgrade_authorized": False,
        "publisher_authenticated": False,
        "production_ready": False,
        "authority": "none",
    }


def _publish_no_replace(stage: Path, destination: Path) -> None:
    """Linux renameat2(RENAME_NOREPLACE): no destination-clobber race.

    Refuse platforms without this Linux syscall; never fall back to os.rename.
    Same-UID adversaries and unsafe parent replacement are outside the pilot.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, 'renameat2', None)
    if renameat2 is None:
        raise DistributionDenied("atomic-no-replace-unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                          ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    # AT_FDCWD=-100, RENAME_NOREPLACE=1
    if renameat2(-100, os.fsencode(stage), -100, os.fsencode(destination), 1):
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise DistributionDenied("destination-exists-no-overwrite")
        raise DistributionDenied("atomic-install-publication-denied")


def install(archive: Path, destination: Path, *, expected_sha256: str) -> dict:
    """Install only after operator-supplied independent archive digest.

    Never replace a prior install; never import or execute package code.
    """
    if os.getuid() == 0 or not sys.platform.startswith("linux"):
        raise DistributionDenied("install-needs-nonroot-linux")
    if sys.version_info < (3, 13):
        raise DistributionDenied("install-needs-python-313")
    if not destination.is_absolute() or ".." in destination.parts:
        raise DistributionDenied("invalid-install-destination")
    _private_parent(destination.parent)
    if os.path.lexists(destination):
        raise DistributionDenied("destination-exists-no-overwrite")
    report = verify(archive, expected_sha256=expected_sha256)
    stage = Path(tempfile.mkdtemp(prefix=".nexus-pilot-stage-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive, "r") as bundle:
            for name in (*FILES, MANIFEST):
                output = stage / name
                output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
                try:
                    with os.fdopen(fd, "wb", closefd=False) as dst:
                        dst.write(bundle.read(name))
                        dst.flush()
                    os.fsync(fd)
                finally:
                    os.close(fd)
        installed_verify(stage)
        _private_parent(destination.parent)
        _publish_no_replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"status": "installed-not-executed",
            "archive_sha256": report["archive_sha256"],
            "file_count": report["file_count"],
            "publisher_authenticated": False,
            "archive_digest_matched": True,
            "production_ready": False, "authority": "none",
            "next_command": "python -I -B <installed>/scripts/nexus-operator-launch.py doctor"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify", "install", "verify-installed", "compare-installed"))
    parser.add_argument("--source", type=Path, help="NEXUS source root for build")
    parser.add_argument("--archive", type=Path, help="ZIP archive for build/verify/install")
    parser.add_argument("--output", type=Path, help="New ZIP output for build")
    parser.add_argument("--destination", type=Path, help="Private new installation directory")
    parser.add_argument("--expected-sha256", help="Independent SHA-256 of complete ZIP")
    parser.add_argument("--expected-manifest-sha256", help="Independent SHA-256 of installed manifest for verification")
    parser.add_argument("--current", type=Path, help="Existing private installation to compare")
    parser.add_argument("--candidate", type=Path, help="New, separately installed candidate")
    parser.add_argument("--expected-candidate-manifest-sha256", help="Independent candidate manifest SHA-256")
    args = parser.parse_args(argv)
    try:
        if args.action == "compare-installed":
            if (not args.current or not args.candidate
                    or not args.expected_candidate_manifest_sha256
                    or args.source or args.archive or args.output
                    or args.destination or args.expected_sha256):
                raise DistributionDenied("invalid-compare-options")
            result = compare_installed(
                args.current, args.candidate,
                expected_current_manifest_sha256=args.expected_manifest_sha256,
                expected_candidate_manifest_sha256=args.expected_candidate_manifest_sha256)
        elif args.action == "build":
            if (not args.source or not args.output or args.archive or
                    args.destination or args.expected_sha256 or
                    args.expected_manifest_sha256 or args.current or args.candidate
                    or args.expected_candidate_manifest_sha256):
                raise DistributionDenied("invalid-build-options")
            result = build(args.source, args.output)
        elif args.action == "verify":
            if (not args.archive or args.source or args.output or args.destination
                    or args.expected_manifest_sha256 or args.current or args.candidate
                    or args.expected_candidate_manifest_sha256):
                raise DistributionDenied("invalid-verify-options")
            result = verify(args.archive, expected_sha256=args.expected_sha256)
        elif args.action == "install":
            if (not args.archive or not args.destination or not args.expected_sha256
                    or args.source or args.output or args.current or args.candidate
                    or args.expected_candidate_manifest_sha256
                    or args.expected_manifest_sha256):
                raise DistributionDenied("invalid-install-options")
            result = install(args.archive, args.destination,
                             expected_sha256=args.expected_sha256)
        else:
            if (not args.destination or args.source or args.output
                    or args.archive or args.expected_sha256 or args.current
                    or args.candidate or args.expected_candidate_manifest_sha256):
                raise DistributionDenied("invalid-installed-verify-options")
            result = installed_verify(args.destination,
                     expected_manifest_sha256=args.expected_manifest_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile,
            zipfile.LargeZipFile, UnicodeError) as exc:
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "authority": "none", "production_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
