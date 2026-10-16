#!/usr/bin/env python3
"""Corruption, extraction boundaries, preservation and recovery-window tests."""
import base64
import errno
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
        self.assertEqual(snapshot.restore(self.archive, self.target), 4)
        original = {p.relative_to(self.source): p.read_bytes()
                    for p in self.source.rglob("*") if p.is_file()}
        restored = {p.relative_to(self.target): p.read_bytes()
                    for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(restored.pop(Path(snapshot.RECOVERY_MARKER)), snapshot.RECOVERY_BYTES)
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

    def test_quarantine_survives_a_second_backup_and_restore(self):
        self.capture()
        snapshot.restore(self.archive, self.target)
        second_archive = self.root / "second.json"
        second_target = self.root / "second-data"
        snapshot.backup(self.target, second_archive)
        snapshot.restore(second_archive, second_target)
        self.assertEqual((second_target / snapshot.RECOVERY_MARKER).read_bytes(), snapshot.RECOVERY_BYTES)

    def test_resume_requires_offline_and_explicit_risk_acknowledgment(self):
        self.capture()
        snapshot.restore(self.archive, self.target)
        marker = self.target / snapshot.RECOVERY_MARKER
        command = [sys.executable, str(SCRIPT), "resume", str(self.target)]
        for flags in [[], ["--offline"], ["--acknowledge-replay-risk"]]:
            result = subprocess.run(command + flags, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.exists())
        result = subprocess.run(command + ["--offline", "--acknowledge-replay-risk"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertTrue((self.target / "requests" / b"accepted".hex()).exists())

    def test_resume_rejects_missing_invalid_and_symlink_markers(self):
        self.capture()
        snapshot.restore(self.archive, self.target)
        marker = self.target / snapshot.RECOVERY_MARKER
        marker.write_bytes(b"untrusted")
        with self.assertRaises(ValueError):
            snapshot.resume(self.target)
        self.assertEqual(marker.read_bytes(), b"untrusted")
        marker.unlink()
        with self.assertRaises(OSError):
            snapshot.resume(self.target)
        witness = self.root / "private"
        witness.write_bytes(snapshot.RECOVERY_BYTES)
        marker.symlink_to(witness)
        with self.assertRaises(OSError):
            snapshot.resume(self.target)
        self.assertTrue(marker.is_symlink())
        self.assertEqual(witness.read_bytes(), snapshot.RECOVERY_BYTES)

    def test_corrupt_quarantine_record_leaves_destination_absent(self):
        document = self.capture()
        data = b"acknowledged"
        document["files"].append({"path": snapshot.RECOVERY_MARKER, "size": len(data),
                                 "sha256": hashlib.sha256(data).hexdigest(),
                                 "data": base64.b64encode(data).decode()})
        self.corrupted_restore(document)

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

    def test_last_moment_restore_collision_preserves_every_destination_kind(self):
        self.capture()
        archive_before = self.archive.read_bytes()
        publish = snapshot.publish_directory_no_replace
        for kind in ["empty-directory", "directory", "file", "symlink", "dangling-symlink"]:
            with self.subTest(kind=kind):
                target = self.root / kind
                outside = self.root / (kind + "-outside")
                outside.write_bytes(b"private-preserved-data")

                def race(stage, destination):
                    if kind in ("empty-directory", "directory"):
                        destination.mkdir()
                        if kind == "directory":
                            (destination / "keep").write_bytes(b"keep")
                    elif kind == "file":
                        destination.write_bytes(b"keep")
                    else:
                        destination.symlink_to(outside if kind == "symlink" else self.root / "absent")
                    before = destination.lstat()
                    try:
                        publish(stage, destination)
                    finally:
                        self.assertEqual(destination.lstat().st_ino, before.st_ino)

                with patch.object(snapshot, "publish_directory_no_replace", side_effect=race):
                    with self.assertRaises(snapshot.SnapshotError):
                        snapshot.restore(self.archive, target)
                self.assertEqual(outside.read_bytes(), b"private-preserved-data")
                if kind == "file":
                    self.assertEqual(target.read_bytes(), b"keep")
                elif kind == "directory":
                    self.assertEqual((target / "keep").read_bytes(), b"keep")
                elif kind == "empty-directory":
                    self.assertEqual(list(target.iterdir()), [])
                else:
                    self.assertTrue(target.is_symlink())
                self.assertFalse(list(self.root.glob(".nexus-restore-*")))
                self.assertEqual(self.archive.read_bytes(), archive_before)

    def test_restore_blocks_without_no_replace_platform_or_libc_support(self):
        self.capture()
        for context in [patch.object(snapshot.sys, "platform", "unsupported"),
                        patch.object(snapshot.ctypes, "CDLL", return_value=object())]:
            with context, patch.object(snapshot.os, "rename") as unsafe_fallback:
                with self.assertRaises(snapshot.SnapshotError):
                    snapshot.restore(self.archive, self.target)
                unsafe_fallback.assert_not_called()
            self.assertFalse(self.target.exists())
            self.assertFalse(list(self.root.glob(".nexus-restore-*")))

    def test_restore_kernel_publication_errors_never_fall_back_or_leave_staging(self):
        self.capture()
        for error in [errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.EACCES, errno.ENOSPC]:
            with self.subTest(error=error):
                with patch.object(snapshot.ctypes, "CDLL") as library, \
                     patch.object(snapshot.ctypes, "get_errno", return_value=error), \
                     patch.object(snapshot.os, "rename") as unsafe_fallback:
                    library.return_value.renameat2.return_value = -1
                    with self.assertRaises((snapshot.SnapshotError, OSError)):
                        snapshot.restore(self.archive, self.target)
                    unsafe_fallback.assert_not_called()
                self.assertFalse(self.target.exists())
                self.assertFalse(list(self.root.glob(".nexus-restore-*")))

    def test_sync_failure_before_publication_leaves_target_absent(self):
        self.capture()
        with patch.object(snapshot, "sync_directory", side_effect=OSError(errno.EIO, "injected")), \
             patch.object(snapshot, "publish_directory_no_replace") as publish:
            with self.assertRaises(OSError):
                snapshot.restore(self.archive, self.target)
            publish.assert_not_called()
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.root.glob(".nexus-restore-*")))

    def test_sync_failure_after_publication_keeps_quarantined_data_and_blocks_retry(self):
        self.capture()
        real_sync = snapshot.sync_directory

        def fail_parent(path):
            if path == self.target.parent:
                raise OSError(errno.EIO, "injected parent sync failure")
            real_sync(path)

        with patch.object(snapshot, "sync_directory", side_effect=fail_parent):
            with self.assertRaises(OSError):
                snapshot.restore(self.archive, self.target)
        self.assertEqual((self.target / snapshot.RECOVERY_MARKER).read_bytes(), snapshot.RECOVERY_BYTES)
        self.assertEqual((self.target / "77.json").read_bytes(), (self.source / "77.json").read_bytes())
        self.assertFalse(list(self.root.glob(".nexus-restore-*")))
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.restore(self.archive, self.target)

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

    def test_inspection_reports_aggregates_without_private_content_or_writes(self):
        private_id = "private-inspection-workspace"
        (self.source / (private_id.encode().hex() + ".json")).write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": private_id},
            "events": ["private-inspection-payload"]}))
        self.capture()
        before = {p.relative_to(self.root): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                  for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(self.archive)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "STRUCTURALLY_VALID")
        self.assertEqual(report["scope"], "snapshot_structure_only")
        self.assertEqual(report["file_count"], 4)
        self.assertEqual(report["workspace_count"], 2)
        self.assertEqual(report["requests"], {"pending": 1, "indeterminate": 1})
        self.assertFalse(report["captured_quarantine"])
        self.assertEqual(report["recovery_point"], "unknown")
        self.assertEqual(report["core_audit"], "not_checked")
        self.assertEqual(report["authenticity"], "not_verified")
        self.assertEqual(report["authority"], "none")
        for value in [private_id, "private-inspection-payload", "accepted", "uncertain",
                      str(self.root), private_id.encode().hex()]:
            self.assertNotIn(value, result.stdout + result.stderr)
        self.assertNotIn("PASS", result.stdout)
        after = {p.relative_to(self.root): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.target.exists())

    def test_inspection_keeps_all_torn_markers_indeterminate_and_reports_quarantine(self):
        for length in range(1, len(b"pending\n")):
            (self.source / "requests" / f"torn-{length}".encode().hex()).write_bytes(
                b"pending\n"[:length])
        (self.source / snapshot.RECOVERY_MARKER).write_bytes(snapshot.RECOVERY_BYTES)
        self.capture()
        report = snapshot.inspect_snapshot(self.archive)
        self.assertEqual(report["requests"], {"pending": 1, "indeterminate": 8})
        self.assertTrue(report["captured_quarantine"])
        self.assertEqual((self.source / snapshot.RECOVERY_MARKER).read_bytes(),
                         snapshot.RECOVERY_BYTES)

    def test_inspection_rejects_corruption_without_success_report(self):
        document = self.capture()
        document["files"][0]["sha256"] = "0" * 64
        self.archive.write_text(json.dumps(document))
        before = self.archive.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(self.archive)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("checksum mismatch", result.stderr)
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertFalse(self.target.exists())

    def test_inspection_rejects_mutation_arguments(self):
        self.capture()
        before = self.archive.read_bytes()
        for flags in [[str(self.target)], ["--owner", "10001:10001"], ["--offline"],
                      ["--acknowledge-replay-risk"]]:
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, str(SCRIPT), "inspect",
                    str(self.archive), *flags], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertFalse(self.target.exists())
                self.assertEqual(self.archive.read_bytes(), before)

    def test_comparison_reports_directional_replay_gap_and_marker_state_changes(self):
        extra = self.source / "requests" / b"private-reference-only".hex()
        extra.write_bytes(b"pending\n")
        self.capture()
        extra.unlink()
        (self.source / "requests" / b"accepted".hex()).unlink()
        (self.source / "requests" / b"uncertain".hex()).write_bytes(b"pending\n")
        (self.source / "requests" / b"private-candidate-only".hex()).write_bytes(b"pending\n")
        (self.source / "77.json").write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": "w"}, "events": ["private-payload"]}))
        (self.source / snapshot.RECOVERY_MARKER).write_bytes(snapshot.RECOVERY_BYTES)
        candidate = self.root / "candidate.json"
        snapshot.backup(self.source, candidate)
        report = snapshot.compare_snapshots(self.archive, candidate)
        self.assertEqual(report["requests"], {
            "reference_count": 3, "candidate_count": 2,
            "reference_ids_missing_from_candidate": 2,
            "candidate_ids_missing_from_reference": 1, "shared_count": 1,
            "shared_marker_bytes_changed": 1, "shared_pending_to_indeterminate": 0,
            "shared_indeterminate_to_pending": 1})
        self.assertEqual(report["workspaces"]["shared_bytes_changed"], 1)
        self.assertEqual(report["captured_quarantine"], {"reference": False, "candidate": True})
        reverse = snapshot.compare_snapshots(candidate, self.archive)
        self.assertEqual(reverse["requests"]["reference_ids_missing_from_candidate"], 1)
        self.assertEqual(reverse["requests"]["candidate_ids_missing_from_reference"], 2)
        self.assertEqual(reverse["requests"]["shared_pending_to_indeterminate"], 1)
        self.assertEqual(reverse["requests"]["shared_indeterminate_to_pending"], 0)

    def test_comparison_counts_workspace_loss_and_byte_changes_without_semantic_claims(self):
        self.capture()
        (self.source / "77.json").unlink()
        (self.source / "78.json").write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": "x"}, "events": []}))
        candidate = self.root / "candidate.json"
        snapshot.backup(self.source, candidate)
        report = snapshot.compare_snapshots(self.archive, candidate)
        self.assertEqual(report["workspaces"], {
            "reference_count": 1, "candidate_count": 1,
            "reference_ids_missing_from_candidate": 1,
            "candidate_ids_missing_from_reference": 1, "shared_bytes_changed": 0})

    def test_identical_comparison_does_not_claim_current_complete_or_authorized_recovery(self):
        self.capture()
        report = snapshot.compare_snapshots(self.archive, self.archive)
        self.assertEqual(report["status"], "STRUCTURALLY_VALID_COMPARISON")
        self.assertEqual(report["scope"], "two_snapshot_structure_only")
        self.assertEqual(report["requests"]["reference_ids_missing_from_candidate"], 0)
        self.assertEqual(report["requests"]["shared_marker_bytes_changed"], 0)
        self.assertEqual(report["chronology"], "not_inferred")
        self.assertEqual(report["recovery_point"], "unknown")
        self.assertEqual(report["core_audit"], "not_checked")
        self.assertEqual(report["authenticity"], "not_verified")
        self.assertEqual(report["authority"], "none")
        self.assertNotIn("PASS", json.dumps(report))

    def test_comparison_cli_preserves_archives_and_omits_ids_paths_and_private_content(self):
        private_id = "private-comparison-id"
        (self.source / (private_id.encode().hex() + ".json")).write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": private_id}, "events": ["private-comparison-content"]}))
        self.capture()
        candidate = self.root / "candidate.json"
        snapshot.backup(self.source, candidate)
        before = {p.relative_to(self.root): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                  for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), "compare", str(self.archive),
            str(candidate)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["authority"], "none")
        for value in [private_id, private_id.encode().hex(), "private-comparison-content",
                      "accepted", "uncertain", str(self.root)]:
            self.assertNotIn(value, result.stdout + result.stderr)
        after = {p.relative_to(self.root): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.target.exists())

    def test_comparison_validates_both_inputs_and_rejects_mutation_arguments(self):
        self.capture()
        candidate = self.root / "candidate.json"
        candidate.write_bytes(self.archive.read_bytes())
        corrupt = self.root / "corrupt.json"
        document = json.loads(self.archive.read_text())
        document["files"][0]["sha256"] = "0" * 64
        corrupt.write_text(json.dumps(document))
        before = {p: p.read_bytes() for p in (self.archive, candidate, corrupt)}
        inputs = [[corrupt, candidate], [self.archive, corrupt], [self.archive],
                  [self.archive, candidate, "--offline"],
                  [self.archive, candidate, "--owner", "10001:10001"],
                  [self.archive, candidate, "--acknowledge-replay-risk"]]
        for arguments in inputs:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(SCRIPT), "compare",
                    *map(str, arguments)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertFalse(self.target.exists())
                self.assertEqual(before, {p: p.read_bytes() for p in before})

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
