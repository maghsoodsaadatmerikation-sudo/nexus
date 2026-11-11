#!/usr/bin/env python3
"""Offline, synthetic tests: never contact Railway or use real customer bytes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent

def load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, ROOT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

anchor = load("stage-d-run-log-anchor.py", "nexus_run_anchor_test_target")
fixtures = load("test-stage-d-encrypted-escrow.py", "nexus_run_anchor_test_fixtures")
RUN_ID, ATTEMPT, SHA = 43000000000, 2, "a"*40
RUN_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": anchor.REPO,
    "GITHUB_WORKFLOW_REF": anchor.WORKFLOW_REF,
    "GITHUB_RUN_ID": str(RUN_ID),
    "GITHUB_RUN_ATTEMPT": str(ATTEMPT),
    "GITHUB_SHA": SHA,
}

class LogAnchorTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.EncryptedEscrowTests(
            methodName="test_repo_public_certificate_is_pinned_and_has_no_private_key")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.blob, self.receipt = fixture.encrypt()
        self.outdir = fixture.out
        self.receipt_file = self.outdir / anchor.RECEIPT
        self.blob_file = self.outdir / anchor.CIPHERTEXT
        self.patch_cert = unittest.mock.patch.object(
            anchor.escrow, "CERT_SHA256", fixture.cert_sha)
        self.patch_cert.start()
        self.addCleanup(self.patch_cert.stop)

    def canonical_line(self, env=None):
        return anchor.PREFIX + json.dumps(
            anchor.make_anchor(self.outdir, env or RUN_ENV),
            sort_keys=True, separators=(",", ":"))

    def match(self, line=None, run=RUN_ID, attempt=ATTEMPT, sha=SHA):
        return anchor.verify(self.outdir, line or self.canonical_line(),
                             run, attempt, sha)

    def test_exact_run_log_matches_ciphertext_and_receipt_no_authority(self):
        line = self.canonical_line()
        self.assertNotIn(self.f.sentinel, line)
        self.assertNotIn(str(self.f.key), line)
        result = self.match(line)
        self.assertEqual(result["status"], "LOG_ANCHOR_LOCAL_FILE_MATCH_ONLY")
        self.assertEqual(result["github_job_success"], "not_independently_checked")
        self.assertEqual(result["authentic_log_origin"], "operator_must_check_in_github")
        self.assertEqual(result["railway_provider_origin"], "not_independently_attested")
        self.assertIs(result["seal"], False)

    def test_missing_github_workflow_context_refused(self):
        for k in RUN_ENV:
            with self.subTest(key=k):
                env = dict(RUN_ENV)
                env.pop(k)
                with self.assertRaises(anchor.AnchorBlocked):
                    anchor.make_anchor(self.outdir, env)

    def test_wrong_workflow_or_event_refused(self):
        for name, bad in (("GITHUB_EVENT_NAME", "push"),
                          ("GITHUB_REF", "refs/heads/other"),
                          ("GITHUB_WORKFLOW_REF", "attacker/workflow@refs/heads/main"),
                          ("GITHUB_REPOSITORY", "somebodyelse/nexus"),
                          ("GITHUB_ACTIONS", "false")):
            with self.subTest(name=name):
                with self.assertRaises(anchor.AnchorBlocked):
                    anchor.make_anchor(self.outdir, dict(RUN_ENV, **{name: bad}))

    def test_invalid_run_identifier_or_sha_refused(self):
        for name, bad in (("GITHUB_RUN_ID", "0"), ("GITHUB_RUN_ATTEMPT", "-1"),
                          ("GITHUB_RUN_ID", "1.0"), ("GITHUB_RUN_ATTEMPT", "1\nBAD"),
                          ("GITHUB_SHA", "abcd"), ("GITHUB_SHA", "A"*40)):
            with self.subTest(name=name):
                with self.assertRaises(anchor.AnchorBlocked):
                    anchor.make_anchor(self.outdir, dict(RUN_ENV, **{name: bad}))

    def test_expected_run_attempt_and_commit_all_checked(self):
        line = self.canonical_line()
        for run, attempt, sha in ((RUN_ID+1, ATTEMPT, SHA),
                                  (RUN_ID, ATTEMPT+1, SHA),
                                  (RUN_ID, ATTEMPT, "b"*40)):
            with self.assertRaises(anchor.AnchorBlocked):
                self.match(line, run, attempt, sha)

    def test_ciphertext_swap_with_matching_updated_receipt_refused(self):
        line = self.canonical_line()
        changed = self.blob_file.read_bytes() + b"post-upload-change"
        self.blob_file.write_bytes(changed)
        report = json.loads(self.receipt_file.read_text())
        report["ciphertext_sha256"] = hashlib.sha256(changed).hexdigest()
        report["ciphertext_bytes"] = len(changed)
        self.receipt_file.write_text(json.dumps(report))
        with self.assertRaises(anchor.AnchorBlocked):
            self.match(line)

    def test_receipt_format_swap_refused_even_when_ciphertext_unchanged(self):
        line = self.canonical_line()
        self.receipt_file.write_text(json.dumps(json.loads(self.receipt_file.read_text()), indent=4))
        with self.assertRaises(anchor.AnchorBlocked):
            self.match(line)

    def test_forged_release_authority_refused(self):
        data = json.loads(self.canonical_line()[len(anchor.PREFIX):])
        data["release_authorized"] = True
        with self.assertRaises(anchor.AnchorBlocked):
            self.match(anchor.PREFIX + json.dumps(data))

    def test_unrecognized_extra_field_refused(self):
        data = json.loads(self.canonical_line()[len(anchor.PREFIX):])
        data["provider_origin_verified"] = True
        with self.assertRaises(anchor.AnchorBlocked):
            self.match(anchor.PREFIX + json.dumps(data))

    def test_duplicate_anchor_json_key_refused(self):
        with self.assertRaises(ValueError):
            self.match(self.canonical_line()[:-1] + ',"seal":true}')

    def test_symlink_ciphertext_refused(self):
        original = self.outdir / "cipher-original"
        self.blob_file.rename(original)
        self.blob_file.symlink_to(original)
        with self.assertRaises((anchor.AnchorBlocked, OSError)):
            anchor.make_anchor(self.outdir, RUN_ENV)

    def test_hardlinked_ciphertext_refused(self):
        os.link(self.blob_file, self.outdir / "cipher-hardlink")
        # Shared no-hardlink reader raises SnapshotError(ValueError).
        # That is the intended fail-closed behavior.
        with self.assertRaises(ValueError):
            anchor.make_anchor(self.outdir, RUN_ENV)

    def test_symlink_receipt_refused(self):
        original = self.outdir / "receipt-original"
        self.receipt_file.rename(original)
        self.receipt_file.symlink_to(original)
        with self.assertRaises((anchor.AnchorBlocked, OSError)):
            anchor.make_anchor(self.outdir, RUN_ENV)

    def test_ambient_secrets_and_private_file_paths_not_in_log(self):
        env = dict(RUN_ENV, RAILWAY_TOKEN="SECRET_PROVIDER_SENTINEL",
                   NEXUS_API_TOKEN="SECRET_APP_SENTINEL",
                   GITHUB_TOKEN="SECRET_GITHUB_SENTINEL",
                   PYTHONPATH="/private/work")
        line = self.canonical_line(env)
        for secret in ("SECRET_PROVIDER_SENTINEL", "SECRET_APP_SENTINEL",
                       "SECRET_GITHUB_SENTINEL", "/private/work", self.f.sentinel):
            self.assertNotIn(secret, line)

    def test_workflow_emits_after_encryption_before_upload(self):
        workflow = (ROOT.parent / ".github/workflows/stage-d-encrypted-volume-capture.yml").read_text()
        a = workflow.index("      - name: Encrypt only three validated private evidence files")
        b = workflow.index("      - name: Anchor non-secret ciphertext digest to this GitHub run log")
        c = workflow.index("      - name: Upload ciphertext and sanitized receipt ONLY")
        self.assertTrue(a < b < c)
        self.assertIn("scripts/stage-d-run-log-anchor.py emit", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertNotIn("  pull_request:", workflow)
        self.assertIn("RAILWAY_TOKEN", workflow[b:c])

    def test_cli_bad_context_does_not_print_private_files(self):
        env = dict(os.environ)
        env.update(RUN_ENV)
        env["GITHUB_REF"] = "refs/heads/wrong"
        result = subprocess.run([sys.executable, str(ROOT / "stage-d-run-log-anchor.py"),
                                 "emit", "--encrypted-dir", str(self.outdir)],
                                env=env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(str(self.f.base), result.stderr)
        self.assertNotIn(self.f.sentinel, result.stderr)

if __name__ == "__main__":
    unittest.main(verbosity=2)
