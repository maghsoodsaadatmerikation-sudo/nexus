#!/usr/bin/env python3
"""Fully local synthetic encrypted Railway escrow tests. NO live secrets/network."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nexus_escrow_tests", ROOT / "stage-d-encrypted-escrow.py")
escrow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(escrow)
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
DEPLOY = "db2fd959-918e-49d5-b077-1ac74fac9a82"
RUNTIME = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"


class EncryptedEscrowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-escrow-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "private-copy"
        self.copy = self.root / "copied-data"
        self.report = self.root / "isolated-intake"
        self.out = self.base / "encrypted-output"
        self.copy.mkdir(parents=True)
        self.out.mkdir()
        (self.copy / "requests").mkdir()
        self.sentinel = "PRIVATE_SYNTHETIC_WORKSPACE_SENTINEL"
        (self.copy / "77.json").write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": "w"},
            "events": [], "test_marker": self.sentinel
        }))
        (self.copy / "requests" / "6163636570746564").write_bytes(b"pending\n")
        cli = [
            sys.executable, str(ROOT / "verify-offhost-volume-export.py"),
            "--export-root", str(self.copy),
            "--private-evidence-dir", str(self.report),
            "--volume-id", VOLUME, "--deployment-id", DEPLOY,
            "--runtime-commit", RUNTIME,
        ]
        subprocess.run(cli, check=True, capture_output=True, timeout=15)
        inspection = json.loads((self.report / "intake-report.json").read_text())
        self.receipt = {
            "schema": "nexus.railway-volume-readonly-capture.v1",
            "status": "PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS",
            "scope": "operator-authenticated-cli-download-to-private-directory",
            "target": {"project_id": "2ac7887b-d67a-48be-8a7b-bd54092893ae",
                       "environment_id": "56c4bc45-0e62-4aa9-832f-884bb1aa620c",
                       "service_id": "0032fc74-2c52-475d-b9df-9dca59237d93",
                       "volume_id": VOLUME},
            "cli_subcommand": "volume files download",
            "source_consistency": "NOT_VERIFIED_ATOMIC",
            "rust_core_audit": "not_evaluated",
            "rust_core_binary_identity": "not_verified",
            "rust_core_source_parity": "not_evaluated",
            "local_copy_scans_matched_archive": True,
            "post_intake_copy_archive_and_restore_rechecked": True,
            "provider_file_origin": "CLI_SELECTED_ID_NOT_INDEPENDENTLY_ATTESTED",
            "offsite_copy": "PRIVATE_PATH_OPERATOR_MUST_PRESERVE",
            "archive_sha256": inspection["snapshot_sha256"],
            "restored_quarantined": True,
            "independent_complete_production_backup": "NOT_PROVEN",
            "production_restart": "NOT_PERFORMED",
            "production_restore": "NOT_PERFORMED",
            "production_mutation": False,
            "seal": False,
            "authority": "none",
        }
        (self.report / "capture-receipt.json").write_text(json.dumps(self.receipt))
        self.key = self.base / "synthetic-private-key.pem"
        self.cert = self.base / "synthetic-public-cert.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-nodes", "-sha256", "-days", "1", "-keyout",
                        str(self.key), "-out", str(self.cert), "-subj",
                        "/CN=NEXUS Synthetic Local Test/"],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
        self.cert_sha = hashlib.sha256(self.cert.read_bytes()).hexdigest()

    def encrypt(self):
        with (patch.object(escrow, "CERT", self.cert),
              patch.object(escrow, "CERT_SHA256", self.cert_sha),
              contextlib.redirect_stdout(io.StringIO()) as console):
            escrow.create_escrow(self.root, self.out)
            self.assertNotIn(self.sentinel, console.getvalue())
        blob = self.out / "nexus-stage-d-private-capture.cms"
        report = self.out / "nexus-stage-d-ciphertext-receipt.json"
        self.assertTrue(blob.exists())
        self.assertTrue(report.exists())
        self.assertNotIn(self.sentinel.encode(), blob.read_bytes())
        return blob, json.loads(report.read_text())

    def decrypt(self, blob, private_key=None):
        return subprocess.run(
            ["openssl", "cms", "-decrypt", "-inform", "DER",
             "-in", str(blob), "-recip", str(self.cert),
             "-inkey", str(private_key or self.key)],
            capture_output=True, timeout=15)

    def test_offsite_workflow_is_manual_only_and_never_uploads_raw_data(self):
        workflow = (ROOT.parent / ".github/workflows/stage-d-encrypted-volume-capture.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertNotIn("  pull_request:", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("NEXUS_STAGE_D_RAILWAY_TOKEN", workflow)
        self.assertIn("confirm_volume:", workflow)
        self.assertIn("actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f", workflow)
        path_block = workflow.split("      - name: Upload ciphertext and sanitized receipt ONLY", 1)[1]
        path_block = path_block.split("      - name: Cleanup temporary plaintext", 1)[0]
        self.assertIn("nexus-stage-d-private-capture.cms", path_block)
        self.assertIn("nexus-stage-d-ciphertext-receipt.json", path_block)
        self.assertNotIn("copied-data", path_block)
        self.assertNotIn("nexus-private-data-snapshot.json", path_block)
        self.assertNotIn("isolated-intake", path_block)

    def test_repo_public_certificate_is_pinned_and_has_no_private_key(self):
        public = ROOT.parent / "docs/keys/stage-d-recovery-public-cert.pem"
        self.assertEqual(hashlib.sha256(public.read_bytes()).hexdigest(),
                         "b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091")
        self.assertIn(b"BEGIN CERTIFICATE", public.read_bytes())
        self.assertNotIn(b"PRIVATE KEY", public.read_bytes())

    def test_synthetic_full_snapshot_encrypted_and_authenticated_roundtrip(self):
        blob, report = self.encrypt()
        self.assertEqual(report["status"], "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED")
        self.assertEqual(report["ciphertext_sha256"],
                         hashlib.sha256(blob.read_bytes()).hexdigest())
        self.assertEqual(report["recipient_cert_sha256"], self.cert_sha)
        self.assertIs(report["release_authorized"], False)
        self.assertIs(report["seal"], False)
        self.assertEqual(report["authority"], "none")
        decrypted = self.decrypt(blob)
        self.assertEqual(decrypted.returncode, 0, decrypted.stderr.decode(errors="replace"))
        with tarfile.open(fileobj=io.BytesIO(decrypted.stdout), mode="r:") as archive:
            names = set(archive.getnames())
            self.assertEqual(names, set(escrow.EVIDENCE))
            snapshot = archive.extractfile("nexus-private-data-snapshot.json").read()
            # Snapshot records encode original workspace bytes as base64;
            # the plaintext sentinel is intentionally not directly in JSON.
            document = json.loads(snapshot)
            workspace_record = next(record for record in document["files"]
                                    if record["path"] == "77.json")
            workspace_bytes = base64.b64decode(workspace_record["data"], validate=True)
            self.assertIn(self.sentinel.encode(), workspace_bytes)
            self.assertEqual(hashlib.sha256(snapshot).hexdigest(),
                             self.receipt["archive_sha256"])
            self.assertNotIn("PRIVATE_SYNTHETIC_WORKSPACE_SENTINEL",
                             report.keys())

    def test_tampering_ciphertext_is_detected_by_gcm(self):
        blob, _ = self.encrypt()
        contents = bytearray(blob.read_bytes())
        contents[-18] ^= 1
        blob.write_bytes(contents)
        self.assertNotEqual(self.decrypt(blob).returncode, 0)

    def test_wrong_private_key_cannot_decrypt(self):
        blob, _ = self.encrypt()
        other_key = self.base / "other-key.pem"
        other_cert = self.base / "other-cert.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-nodes", "-sha256", "-days", "1", "-keyout",
                        str(other_key), "-out", str(other_cert), "-subj",
                        "/CN=Wrong Key/"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        self.assertNotEqual(self.decrypt(blob, other_key).returncode, 0)

    def test_wrong_recipient_certificate_is_rejected_before_output(self):
        with patch.object(escrow, "CERT", self.cert):
            with self.assertRaises(escrow.EscrowBlocked):
                escrow.create_escrow(self.root, self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_forged_seal_is_blocked_before_encryption(self):
        self.receipt["seal"] = True
        (self.report / "capture-receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaises(escrow.EscrowBlocked):
            escrow.validate_capture(self.root)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_forged_archive_digest_is_blocked(self):
        self.receipt["archive_sha256"] = "0" * 64
        (self.report / "capture-receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaises(escrow.EscrowBlocked):
            escrow.validate_capture(self.root)

    def test_symlinked_capture_receipt_is_blocked(self):
        original = self.report / "capture-receipt.json"
        moved = self.base / "forged.json"
        original.rename(moved)
        original.symlink_to(moved)
        with self.assertRaises(OSError):
            escrow.validate_capture(self.root)

    def test_hardlinked_private_evidence_is_blocked(self):
        original = self.report / "intake-report.json"
        os.link(original, self.base / "private-evidence-alias.json")
        with (patch.object(escrow, "CERT", self.cert),
              patch.object(escrow, "CERT_SHA256", self.cert_sha)):
            with self.assertRaises((escrow.EscrowBlocked, ValueError, OSError)):
                escrow.create_escrow(self.root, self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_will_not_encrypt_into_the_original_private_root(self):
        with (patch.object(escrow, "CERT", self.cert),
              patch.object(escrow, "CERT_SHA256", self.cert_sha)):
            with self.assertRaises(escrow.EscrowBlocked):
                escrow.create_escrow(self.root, self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
