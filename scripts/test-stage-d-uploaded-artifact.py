#!/usr/bin/env python3
"""Synthetic-only Stage D independent-runner ciphertext transfer regression tests."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_stage_d_retrieval_under_test", HERE / "verify-stage-d-uploaded-artifact.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
anchor = mod.anchor
RUN = "43000000055"
ATTEMPT = "2"
SHA = "a" * 40
ARTIFACT_ID = "123456789"
EVENT_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": anchor.REPO,
    "GITHUB_WORKFLOW_REF": anchor.WORKFLOW_REF,
    "GITHUB_RUN_ID": RUN,
    "GITHUB_RUN_ATTEMPT": ATTEMPT,
    "GITHUB_SHA": SHA,
}
NONCLAIMS = {
    "schema": "nexus.stage-d-encrypted-escrow.v1",
    "status": "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED",
    "content_claim": "local_structural_intake_only",
    "independent_live_restore": "not_evaluated",
    "railway_origin": "not_independently_attested",
    "release_authorized": False,
    "seal": False,
    "authority": "none",
    "recipient_cert_sha256": anchor.escrow.CERT_SHA256,
}


class IndependentDownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nexus-synthetic-artifact-redownload-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "retrieved-artifact"
        self.root.mkdir()
        self.cipher = self.root / anchor.CIPHERTEXT
        self.receipt = self.root / anchor.RECEIPT
        self.cipher.write_bytes(b"ONLY_SYNTHETIC_NOT_A_REAL_CMS_RECORD" + os.urandom(640))
        self.write_receipt()
        self.line = anchor.PREFIX + json.dumps(
            anchor.make_anchor(self.root, EVENT_ENV),
            sort_keys=True, separators=(",", ":")) + "\n"
        self.encoded = base64.b64encode(self.line.encode()).decode()

    def write_receipt(self):
        data = dict(NONCLAIMS)
        raw = self.cipher.read_bytes()
        data["ciphertext_sha256"] = hashlib.sha256(raw).hexdigest()
        data["ciphertext_bytes"] = len(raw)
        self.receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

    def check(self, transfer=None, run=RUN, attempt=ATTEMPT, sha=SHA, artifact_id=ARTIFACT_ID):
        return mod.verify_retrieval(
            self.root, transfer if transfer is not None else self.encoded,
            run, attempt, sha, artifact_id)

    def test_exact_retrieved_pair_matches_orig_anchor(self):
        result = self.check()
        self.assertEqual(result["status"], "INDEPENDENT_RUNNER_CIPHERTEXT_BYTES_MATCH")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["artifact_id"], int(ARTIFACT_ID))
        self.assertFalse(result["ciphertext_decrypted"])
        self.assertFalse(result["independent_production_backup"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["seal"])
        self.assertEqual(result["authority"], "none")

    def test_mismatched_run_id_attempt_and_commit_block(self):
        for kwargs in (
            {"run": str(int(RUN) + 1)},
            {"attempt": "3"},
            {"sha": "b" * 40},
            {"artifact_id": "0"},
            {"artifact_id": "-5"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.check(**kwargs)

    def test_bad_or_uncanonical_anchor_base64_blocks(self):
        values = ["", "\n", "not_base64!", self.encoded + "!", "A" * 8200,
                  self.encoded[:-1] + ("A" if self.encoded[-1] != "A" else "B"),
                  base64.b64encode(b"fake").decode()]
        for value in values:
            with self.subTest(encoded=value[:24]), self.assertRaises(ValueError):
                self.check(transfer=value)

    def test_ciphertext_change_even_with_updated_receipt_blocks(self):
        self.cipher.write_bytes(self.cipher.read_bytes() + b"CHANGED")
        self.write_receipt()
        with self.assertRaises(ValueError):
            self.check()

    def test_receipt_whitespace_change_blocks(self):
        receipt = json.loads(self.receipt.read_text())
        self.receipt.write_text(json.dumps(receipt, indent=4))
        with self.assertRaises(ValueError):
            self.check()

    def test_extra_file_or_subfolder_blocks(self):
        extra = self.root / "unexpected.txt"
        extra.write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            self.check()
        extra.unlink()
        extra.mkdir()
        with self.assertRaises(ValueError):
            self.check()

    def test_symlink_ciphertext_blocks(self):
        alternate = self.root / "cipher-original"
        self.cipher.rename(alternate)
        self.cipher.symlink_to(alternate)
        with self.assertRaises(ValueError):
            self.check()

    def test_hardlink_receipt_blocks(self):
        os.link(self.receipt, self.root.parent / "other-copy")
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_ciphertext_or_receipt_blocks(self):
        self.cipher.unlink()
        with self.assertRaises(ValueError):
            self.check()

    def test_forged_authority_in_transferred_anchor_blocks(self):
        forged = json.loads(self.line[len(anchor.PREFIX):])
        forged["release_authorized"] = True
        changed = anchor.PREFIX + json.dumps(forged, sort_keys=True) + "\n"
        with self.assertRaises(ValueError):
            self.check(transfer=base64.b64encode(changed.encode()).decode())

    def test_workflow_is_manual_only_and_retrieval_is_separate_job(self):
        workflow = (HERE.parent / ".github/workflows/stage-d-encrypted-volume-capture.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("\n  pull_request:", workflow)
        self.assertIn("  recheck-uploaded-ciphertext:", workflow)
        second = workflow.split("  recheck-uploaded-ciphertext:", 1)[1]
        self.assertIn("needs: encrypted-private-capture", second)
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", second)
        self.assertIn("artifact-ids:", second)
        self.assertIn("needs.encrypted-private-capture.outputs.artifact_id", second)
        self.assertIn("needs.encrypted-private-capture.outputs.anchor_b64", second)
        self.assertIn("scripts/verify-stage-d-uploaded-artifact.py", second)
        self.assertNotIn("secrets.", second)
        self.assertNotIn("volume files download", second)
        first = workflow.split("  encrypted-private-capture:", 1)[1].split(
            "  recheck-uploaded-ciphertext:", 1)[0]
        self.assertIn("outputs:", first)
        self.assertIn("id: capture_anchor", first)
        self.assertIn("id: upload_ciphertext", first)
        self.assertIn("steps.upload_ciphertext.outputs.artifact-id", first)
        self.assertLess(first.index("id: capture_anchor"), first.index("id: upload_ciphertext"))
        self.assertIn("if-no-files-found: error", first)

    def test_cli_real_runner_context_passes_only_nonsensitive_summary(self):
        env = dict(EVENT_ENV)
        env.update(
            EXPECTED_SHA=SHA, TRANSFER_ANCHOR_B64=self.encoded,
            TRANSFER_ARTIFACT_ID=ARTIFACT_ID,
            RETRIEVED_ARTIFACT_DIR=str(self.root))
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(mod.main(), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["run_id"], int(RUN))
        self.assertNotIn("ONLY_SYNTHETIC_NOT_A_REAL_CMS_RECORD", out.getvalue())
        self.assertNotIn(str(self.root), out.getvalue())

    def test_cli_provider_secret_and_wrong_context_block_without_output(self):
        env = dict(EVENT_ENV)
        env.update(EXPECTED_SHA=SHA, TRANSFER_ANCHOR_B64=self.encoded,
                   TRANSFER_ARTIFACT_ID=ARTIFACT_ID,
                   RETRIEVED_ARTIFACT_DIR=str(self.root))
        for mutation in ({"RAILWAY_TOKEN": "PRIVATE_SENTINEL"},
                         {"GITHUB_EVENT_NAME": "push"},
                         {"GITHUB_SHA": "b"*40}):
            with self.subTest(mutation=mutation), patch.dict(
                    os.environ, dict(env, **mutation), clear=True), \
                    contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(mod.main(), 1)
                self.assertEqual(out.getvalue(), "")
                self.assertNotIn("PRIVATE_SENTINEL", err.getvalue())
                self.assertNotIn(str(self.root), err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
