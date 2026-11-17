#!/usr/bin/env python3
"""No-network synthetic Phase 35 test suite; no real CMS/backup/operator keys."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_owner_custody_under_test", ROOT / "verify-stage-d-owner-custody.py")
custody = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custody)
anchor = custody.anchor

RUN = "43000999021"
ATTEMPT = "1"
SHA = "a" * 40
RUN_CONTEXT = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": anchor.REPO,
    "GITHUB_WORKFLOW_REF": anchor.WORKFLOW_REF,
    "GITHUB_RUN_ID": RUN,
    "GITHUB_RUN_ATTEMPT": ATTEMPT,
    "GITHUB_SHA": SHA,
}


class OwnerReadbackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nexus-test-owner-custody-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.first = root / "first-copy"
        self.second = root / "second-copy"
        self.keep = root / "independent-log-export"
        for d in (self.first, self.second, self.keep):
            d.mkdir(mode=0o700)
        payload = b"SYNTHETIC_NON_CMS_REJECT_AS_REAL_BACKUP" + os.urandom(640)
        cipher = self.first / anchor.CIPHERTEXT
        cipher.write_bytes(payload)
        cipher.chmod(0o600)
        meta = {
            "schema": "nexus.stage-d-encrypted-escrow.v1",
            "status": "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED",
            "content_claim": "local_structural_intake_only",
            "independent_live_restore": "not_evaluated",
            "railway_origin": "not_independently_attested",
            "release_authorized": False,
            "seal": False,
            "authority": "none",
            "recipient_cert_sha256": anchor.escrow.CERT_SHA256,
            "ciphertext_sha256": hashlib.sha256(payload).hexdigest(),
            "ciphertext_bytes": len(payload),
        }
        receipt = self.first / anchor.RECEIPT
        receipt.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        receipt.chmod(0o600)
        for name in custody.ALLOWED:
            target = self.second / name
            shutil.copyfile(self.first / name, target)
            target.chmod(0o600)
        self.anchor_path = self.keep / "trusted-github-run-log-line.txt"
        line = anchor.PREFIX + json.dumps(
            anchor.make_anchor(self.first, RUN_CONTEXT), sort_keys=True, separators=(",", ":")) + "\n"
        self.anchor_path.write_text(line, encoding="utf-8")
        self.anchor_path.chmod(0o600)

    def simulate_distinct_filesystems(self):
        # The fixture uses two directories on one temporary filesystem.
        # This patch exercises downstream logic; it is NOT independent custody.
        original = custody.filesystem_identity
        return patch.object(custody, "filesystem_identity",
                            side_effect=lambda p: 7 if p == self.first else 8)

    def verify(self, **kwargs):
        values = {"first": self.first, "second": self.second,
                  "anchor_path": self.anchor_path,
                  "run_id": RUN, "run_attempt": ATTEMPT, "commit_sha": SHA}
        values.update(kwargs)
        return custody.verify_owner_copies(**values)

    def test_matching_synthetic_pairs_do_not_authorize_recovery_or_deploy(self):
        with self.simulate_distinct_filesystems():
            r = self.verify()
        self.assertEqual(r["status"], "TWO_FILESYSTEM_CIPHERTEXT_BYTES_MATCH")
        self.assertFalse(r["production_backup_complete"])
        self.assertFalse(r["deployment_authorized"])
        self.assertFalse(r["ciphertext_decrypted"])
        self.assertEqual(r["github_log_authenticity"], "operator_must_independently_verify")
        self.assertEqual(r["off_provider_administrative_independence"], "not_proven")

    def test_same_filesystem_is_rejected_without_simulation(self):
        with self.assertRaises(custody.CustodyBlocked):
            self.verify()

    def test_byte_swap_even_with_updated_receipt_is_rejected(self):
        cipher = self.second / anchor.CIPHERTEXT
        raw = cipher.read_bytes() + b"tampered"
        cipher.write_bytes(raw)
        receipt = self.second / anchor.RECEIPT
        obj = json.loads(receipt.read_text())
        obj["ciphertext_sha256"] = hashlib.sha256(raw).hexdigest()
        obj["ciphertext_bytes"] = len(raw)
        receipt.write_text(json.dumps(obj))
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()

    def test_modified_receipt_format_is_rejected(self):
        receipt = self.second / anchor.RECEIPT
        receipt.write_text(json.dumps(json.loads(receipt.read_text()), indent=2))
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()

    def test_run_id_attempt_and_commit_must_match_anchor(self):
        for replacement in ({"run_id": "43000999022"}, {"run_attempt": "2"},
                            {"commit_sha": "b" * 40}):
            with self.subTest(replacement=replacement), self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
                self.verify(**replacement)

    def test_private_permissions_and_links_are_required(self):
        self.anchor_path.chmod(0o644)
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()
        self.anchor_path.chmod(0o600)
        cipher = self.second / anchor.CIPHERTEXT
        cipher.chmod(0o644)
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()
        cipher.chmod(0o600)
        hardlink = self.second.parent / "hardlink"
        os.link(cipher, hardlink)
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()
        hardlink.unlink()
        cipher.rename(self.second / "real")
        cipher.symlink_to("real")
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()

    def test_missing_or_extra_file_rejected(self):
        (self.second / "unexpected").write_text("not permitted")
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()
        (self.second / "unexpected").unlink()
        (self.second / anchor.RECEIPT).unlink()
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()

    def test_anchor_cannot_be_replaced_with_self_consistent_forgery(self):
        data = json.loads(self.anchor_path.read_text()[len(anchor.PREFIX):])
        data["release_authorized"] = True
        self.anchor_path.write_text(anchor.PREFIX + json.dumps(data) + "\n")
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify()

    def test_same_directory_and_nested_copy_are_rejected(self):
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify(second=self.first)
        new = self.first / "nested"
        new.mkdir(mode=0o700)
        with self.simulate_distinct_filesystems(), self.assertRaises(ValueError):
            self.verify(second=new)

    def test_cli_failure_does_not_disclose_paths_or_input(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "verify-stage-d-owner-custody.py"),
             "--copy-a", str(self.first), "--copy-b", str(self.second),
             "--anchor-file", str(self.anchor_path),
             "--run-id", RUN, "--run-attempt", ATTEMPT,
             "--commit-sha", SHA],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertNotIn(str(self.first), proc.stderr)
        self.assertNotIn("SYNTHETIC_NON_CMS", proc.stderr)


if __name__ == "__main__":
    unittest.main()
