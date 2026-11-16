#!/usr/bin/env python3
"""Explicit, offline operator workspace + finished-journal snapshot transfer.

No model-facing endpoint, daemon access, automatic retry, deployment, signing,
or claim of independent host custody. Restores to an EMPTY owner-private root.
A supplied SHA-256 pins bytes; it does not authenticate an archive publisher.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_workspace import Workspace, WorkspaceDenied, WORKSPACE_ID, safe_parts
from agent_journal import ApprovalJournal
from agent_operator_service import _root

SCHEMA = "nexus.operator.offline-snapshot.v1"
LIMIT = 32 * 1024 * 1024
MAX_JOURNALS = 64
SHA = re.compile(r"[0-9a-f]{64}\Z")


def deny(reason: str) -> None:
    raise WorkspaceDenied(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def read_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                deny("duplicate-snapshot-key")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=unique,
                            parse_constant=lambda _: deny("invalid-number"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise WorkspaceDenied("invalid-snapshot-json") from exc
    if type(result) is not dict:
        deny("snapshot-json-not-object")
    return result


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_root(root: Path) -> Path:
    if os.name != "posix" or not sys.platform.startswith("linux") or os.getuid() == 0:
        deny("snapshot-requires-unprivileged-linux")
    return _root(root)


def safe_name(name: str) -> None:
    if type(name) is not str or not WORKSPACE_ID.fullmatch(name):
        deny("invalid-snapshot-workspace")


def checked_archive(path: Path, expected_sha256: str) -> bytes:
    if type(expected_sha256) is not str or not SHA.fullmatch(expected_sha256):
        deny("expected-sha256-required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > LIMIT):
            deny("unsafe-snapshot-file")
        parts = []
        remaining = LIMIT + 1
        while remaining:
            data = os.read(fd, min(65536, remaining))
            if not data:
                break
            remaining -= len(data)
            parts.append(data)
        if remaining == 0:
            deny("snapshot-size-limit")
        raw = b"".join(parts)
    finally:
        os.close(fd)
    if sha(raw) != expected_sha256:
        deny("snapshot-sha256-mismatch")
    return raw


def safe_zip_members(bundle: zipfile.ZipFile) -> dict:
    members = {}
    for item in bundle.infolist():
        if (item.filename in members or item.filename.startswith("/")
                or "\\" in item.filename or item.filename.endswith("/")
                or ".." in item.filename.split("/")
                or item.compress_type != zipfile.ZIP_STORED or item.flag_bits & 1
                or item.file_size > LIMIT or item.compress_size != item.file_size):
            deny("unsafe-snapshot-zip")
        mode = (item.external_attr >> 16) & 0o170000
        if mode != stat.S_IFREG:
            deny("unsafe-snapshot-entry-mode")
        members[item.filename] = item
    return members


def export(root: Path, workspace: str, output: Path) -> dict:
    safe_name(workspace)
    root = private_root(root)
    if not (root / workspace).is_dir() or (root / workspace).is_symlink():
        deny("workspace-must-exist")
    ws = Workspace(root, workspace)
    with ws.operation_lock():
        journal = ApprovalJournal(ws)
        audit = journal.audit()
        if audit["status"] != "clear" or not 1 <= audit["finished_count"] <= MAX_JOURNALS:
            deny("snapshot-requires-finished-journal")
        manifest = ws.manifest()
        sources = {}
        for row in manifest["files"]:
            raw = ws.read(row["path"])
            if len(raw) != row["bytes"] or sha(raw) != row["sha256"]:
                deny("source-mutated-during-snapshot")
            sources["workspace/" + row["path"]] = raw
        receipts = []
        dirfd = journal._directory()
        try:
            filenames = sorted(os.listdir(dirfd))
        finally:
            os.close(dirfd)
        if len(filenames) != audit["finished_count"]:
            deny("journal-mutated-during-snapshot")
        for filename in filenames:
            digest = filename.removesuffix(".json")
            if filename != digest + ".json" or not SHA.fullmatch(digest):
                deny("unexpected-journal-entry")
            record = journal.read(digest)
            if record.get("state") != "finished":
                deny("unfinished-journal")
            data = canonical(record)
            if len(data) > 8192:
                deny("journal-too-large")
            sources["journal/" + filename] = data
            receipts.append({"digest": digest, "bytes": len(data), "sha256": sha(data)})
        if journal.audit()["status"] != "clear" or ws.manifest()["sha256"] != manifest["sha256"]:
            deny("source-changed-after-snapshot")
        metadata = {"schema": SCHEMA, "workspace": workspace,
                    "workspace_sha256": manifest["sha256"],
                    "files": manifest["files"], "directories": manifest["directories"],
                    "journals": receipts}
        sources["snapshot.json"] = canonical(metadata)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", allowZip64=False) as bundle:
            for filename, content in sorted(sources.items()):
                info = zipfile.ZipInfo(filename, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                bundle.writestr(info, content)
        data = buffer.getvalue()
        if len(data) > LIMIT:
            deny("snapshot-size-limit")
        parent = private_root(output.parent)
        if output.exists() or output.is_symlink():
            deny("snapshot-destination-exists")
        pfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=pfd)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(pfd)
        finally:
            os.close(pfd)
    return {"schema": SCHEMA, "status": "offline-snapshot-created",
            "snapshot_sha256": sha(data), "workspace_sha256": manifest["sha256"],
            "file_count": len(manifest["files"]), "finished_count": len(receipts),
            "publisher_authenticated": False, "authority": "none",
            "production_ready": False}


def validate(raw: bytes, workspace: str) -> tuple[dict, dict, dict]:
    with zipfile.ZipFile(io.BytesIO(raw), "r") as bundle:
        members = safe_zip_members(bundle)
        if "snapshot.json" not in members or members["snapshot.json"].file_size > 65536:
            deny("missing-snapshot-metadata")
        meta = read_json(bundle.read("snapshot.json"))
        if (set(meta) != {"schema", "workspace", "workspace_sha256", "files",
                          "directories", "journals"} or meta["schema"] != SCHEMA
                or meta["workspace"] != workspace):
            deny("snapshot-metadata-mismatch")
        files, directories, journals = meta["files"], meta["directories"], meta["journals"]
        if (type(files) is not list or type(directories) is not list
                or type(journals) is not list or len(files) > 200
                or len(directories) > 400 or not 1 <= len(journals) <= MAX_JOURNALS
                or len(files) + len(directories) > 400):
            deny("snapshot-limits")
        expected = {"snapshot.json"}
        filebytes, records = {}, {}
        seen = set()
        total_bytes = 0
        for row in files:
            if (type(row) is not dict or set(row) != {"path", "bytes", "sha256"}
                    or type(row["path"]) is not str or type(row["bytes"]) is not int
                    or not 0 <= row["bytes"] <= 1048576 or type(row["sha256"]) is not str
                    or not SHA.fullmatch(row["sha256"])):
                deny("snapshot-file-schema")
            path = row["path"]
            safe_parts(path)
            if path in seen:
                deny("duplicate-snapshot-path")
            seen.add(path)
            total_bytes += row["bytes"]
            if total_bytes > 20 * 1048576:
                deny("snapshot-data-limit")
            member = "workspace/" + path
            if member not in members or members[member].file_size != row["bytes"]:
                deny("snapshot-file-missing")
            content = bundle.read(member)
            if sha(content) != row["sha256"]:
                deny("snapshot-file-hash")
            filebytes[path] = content
            expected.add(member)
        seen_dirs = set()
        for path in directories:
            if type(path) is not str:
                deny("snapshot-directory-schema")
            safe_parts(path)
            if path in seen_dirs or path in seen:
                deny("snapshot-directory-overlap")
            seen_dirs.add(path)
        identity = {"version": 1, "files": sorted(files, key=lambda f: f["path"]),
                    "directories": sorted(directories)}
        if type(meta["workspace_sha256"]) is not str or sha(canonical(identity)) != meta["workspace_sha256"]:
            deny("snapshot-workspace-hash")
        seen_receipts = set()
        for row in journals:
            if (type(row) is not dict or set(row) != {"digest", "bytes", "sha256"}
                    or type(row["digest"]) is not str or not SHA.fullmatch(row["digest"])
                    or type(row["sha256"]) is not str or not SHA.fullmatch(row["sha256"])
                    or type(row["bytes"]) is not int or not 0 < row["bytes"] <= 8192):
                deny("snapshot-journal-schema")
            digest = row["digest"]
            if digest in seen_receipts:
                deny("duplicate-snapshot-journal")
            seen_receipts.add(digest)
            member = "journal/" + digest + ".json"
            if member not in members or members[member].file_size != row["bytes"]:
                deny("snapshot-journal-missing")
            content = bundle.read(member)
            record = read_json(content)
            if (sha(content) != row["sha256"] or record.get("schema") != 1
                    or record.get("plan_sha256") != digest
                    or record.get("workspace") != workspace
                    or record.get("state") != "finished"
                    or not isinstance(record.get("finished_utc"), str)
                    or record.get("result") not in {"complete", "execution-failed",
                          "step-denied", "post-state-unverifiable", "cancelled"}
                    or type(record.get("completed_steps")) is not int
                    or record["completed_steps"] < 0 or type(record.get("steps")) is not list):
                deny("snapshot-journal-invalid")
            records[digest] = content
            expected.add(member)
        if set(members) != expected:
            deny("unexpected-snapshot-members")
    return meta, filebytes, records


def restore(root: Path, workspace: str, archive: Path, expected_sha256: str) -> dict:
    safe_name(workspace)
    root = private_root(root)
    raw = checked_archive(archive, expected_sha256)
    meta, files, records = validate(raw, workspace)
    if any(root.iterdir()):
        deny("restore-root-must-be-empty")
    ws = Workspace(root, workspace)
    with ws.operation_lock():
        for path in sorted(meta["directories"], key=lambda p: (p.count("/"), p)):
            (ws.path / path).mkdir(parents=True, exist_ok=True, mode=0o700)
        for path, content in sorted(files.items()):
            ws.write(path, content, create_parents=True)
        journal = ApprovalJournal(ws)
        dfd = journal._directory(create=True)
        try:
            for digest, data in sorted(records.items()):
                fd = os.open(digest + ".json", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
                try:
                    with os.fdopen(fd, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fsync(dfd)
        finally:
            os.close(dfd)
        if (ws.manifest()["sha256"] != meta["workspace_sha256"]
                or journal.audit()["status"] != "clear"
                or journal.audit()["finished_count"] != len(records)):
            deny("restored-evidence-unverifiable")
        for digest in records:
            if canonical(journal.read(digest)) != records[digest]:
                deny("restored-journal-mismatch")
    return {"schema": SCHEMA, "status": "offline-snapshot-restored-not-executed",
            "workspace_sha256": meta["workspace_sha256"],
            "file_count": len(files), "finished_count": len(records),
            "replay_approvals_transferred": True, "jobs_restarted": False,
            "orphaned_processes_ruled_out": False, "publisher_authenticated": False,
            "authority": "none", "production_ready": False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("export", "restore"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--expected-sha256")
    p.add_argument("--approve-offline-export", action="store_true")
    p.add_argument("--approve-offline-restore", action="store_true")
    a = p.parse_args()
    try:
        if a.action == "export":
            if not a.approve_offline_export or a.approve_offline_restore or a.expected_sha256:
                deny("export-needs-explicit-approval")
            result = export(a.root, a.workspace, a.archive)
        else:
            if not a.approve_offline_restore or a.approve_offline_export or not a.expected_sha256:
                deny("restore-needs-explicit-approval-and-hash")
            result = restore(a.root, a.workspace, a.archive, a.expected_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, WorkspaceDenied, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "production_ready": False, "authority": "none"},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
