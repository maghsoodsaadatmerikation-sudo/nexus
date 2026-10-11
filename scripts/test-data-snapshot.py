#!/usr/bin/env python3
"""Corruption, extraction boundaries, preservation and recovery-window tests."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("data-snapshot.py")
spec = importlib.util.spec_from_file_location("snapshot", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nexus-snapshot-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "requests").mkdir()
        (self.source / "77.json").write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": "w"}, "events": []}))
        (self.source / "requests" / b"accepted".hex()).write_bytes(b"pending\n")
        (self.source / "requests" / b"uncertain".hex()).write_bytes(b"")
        self.archive = self.root / "snapshot.json"
        self.target = self.root / "restored"

    def tearDown(self):
        self.temporary.cleanup()

    def capture(self):
        snapshot.backup(self.source, self.archive)
        return json.loads(self.archive.read_text())

    def corrupted_restore(self, document):
        self.archive.write_text(json.dumps(document))
        with self.assertRaises((ValueError, OSError, TypeError, UnicodeError)):
            snapshot.restore(self.archive, self.target)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.root.glob(".nexus-restore-*")))

    def test_complete_round_trip_preserves_pending_and_uncertain_bytes(self):
        self.capture()
        self.assertEqual(snapshot.restore(self.archive, self.target), 3)
        original = {p.relative_to(self.source): p.read_bytes()
                    for p in self.source.rglob("*") if p.is_file()}
        restored = {p.relative_to(self.target): p.read_bytes()
                    for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(original, restored)
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o700)
        for name in restored:
            self.assertEqual(stat.S_IMODE((self.target / name).stat().st_mode), 0o600)

    def test_old_snapshot_does_not_preserve_later_request_ids(self):
        self.capture()
        later = self.source / "requests" / b"after-snapshot".hex()
        later.write_bytes(b"pending\n")
        snapshot.restore(self.archive, self.target)
        self.assertFalse((self.target / "requests" / later.name).exists())

    def test_corrupt_checksum_leaves_destination_absent(self):
        document = self.capture()
        document["files"][0]["sha256"] = "0" * 64
        self.corrupted_restore(document)

    def test_duplicate_file_paths_are_rejected(self):
        document = self.capture()
        document["files"].append(document["files"][0])
        self.corrupted_restore(document)

    def test_absolute_and_traversal_paths_never_extract(self):
        document = self.capture()
        for name in ["../escape", "/tmp/escape", "requests/../escape", "requests/x/y", ".env"]:
            with self.subTest(path=name):
                document["files"][0]["path"] = name
                self.corrupted_restore(document)
        self.assertFalse((self.root / "escape").exists())

    def test_invalid_marker_with_matching_hash_is_rejected(self):
        document = self.capture()
        record = next(r for r in document["files"] if r["path"].startswith("requests/"))
        record.update(data=base64.b64encode(b"executed").decode(), size=8,
                      sha256=hashlib.sha256(b"executed").hexdigest())
        self.corrupted_restore(document)

    def test_size_mismatch_is_rejected(self):
        document = self.capture()
        document["files"][0]["size"] += 1
        self.corrupted_restore(document)

    def test_invalid_base64_is_rejected(self):
        document = self.capture()
        document["files"][0]["data"] = "!"
        self.corrupted_restore(document)

    def test_existing_target_and_archive_are_preserved(self):
        self.capture()
        archive_bytes = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            snapshot.backup(self.source, self.archive)
        self.assertEqual(self.archive.read_bytes(), archive_bytes)
        self.target.mkdir()
        witness = self.target / "keep"
        witness.write_text("preserve")
        with self.assertRaises(ValueError):
            snapshot.restore(self.archive, self.target)
        self.assertEqual(witness.read_text(), "preserve")
        witness.unlink()
        with self.assertRaises(ValueError):
            snapshot.restore(self.archive, self.target)

    def test_unknown_source_file_and_missing_ledger_block_backup(self):
        secret = self.source / ".env"
        secret.write_text("private")
        with self.assertRaises(ValueError):
            snapshot.backup(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        secret.unlink()
        for marker in (self.source / "requests").iterdir():
            marker.unlink()
        (self.source / "requests").rmdir()
        with self.assertRaises(ValueError):
            snapshot.backup(self.source, self.archive)

    def test_symlink_file_and_archive_and_target_are_rejected(self):
        link = self.source / "11.json"
        link.symlink_to(self.source / "77.json")
        with self.assertRaises(OSError):
            snapshot.backup(self.source, self.archive)
        link.unlink()
        self.capture()
        archive_link = self.root / "link.json"
        archive_link.symlink_to(self.archive)
        with self.assertRaises(OSError):
            snapshot.restore(archive_link, self.target)
        self.target.symlink_to(self.root / "absent")
        with self.assertRaises(ValueError):
            snapshot.restore(self.archive, self.target)

    def test_output_inside_data_and_resource_overflow_are_rejected(self):
        with self.assertRaises(ValueError):
            snapshot.backup(self.source, self.source / "backup.json")
        with patch.object(snapshot, "MAX_FILES", 1):
            with self.assertRaises(ValueError):
                snapshot.backup(self.source, self.archive)
        with patch.object(snapshot, "MAX_BYTES", 4):
            with self.assertRaises(ValueError):
                snapshot.backup(self.source, self.archive)
        self.capture()
        with patch.object(snapshot, "MAX_BYTES", 4):
            with self.assertRaises(ValueError):
                snapshot.restore(self.archive, self.target)

    def test_duplicate_manifest_keys_are_rejected(self):
        self.archive.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaises(ValueError):
            snapshot.restore(self.archive, self.target)
        self.assertFalse(self.target.exists())

    def test_offline_flag_is_required_and_environment_is_not_captured(self):
        environment = dict(os.environ, NEXUS_API_TOKEN="snapshot-test-secret")
        command = [sys.executable, str(SCRIPT), "backup", str(self.source), str(self.archive)]
        denied = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse(self.archive.exists())
        result = subprocess.run(command + ["--offline"], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("snapshot-test-secret", self.archive.read_text() + result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
