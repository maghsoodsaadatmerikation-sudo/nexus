#!/usr/bin/env python3
"""Synthetic-only adversarial tests; no production GET or Railway mutations."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
MODULE_FILE = ROOT / "scripts/stage_d_manual_runtime_witness.py"
spec = importlib.util.spec_from_file_location("stage_d_manual", MODULE_FILE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA_OLD = "a" * 40
SHA_MAIN = "b" * 40
SHA_SNAPSHOT = "c" * 40
DIGEST = "d" * 64


def response(digest: str = DIGEST) -> bytes:
    return json.dumps({"schema": "nexus.runtime-identity.v1",
                       "source_tree_sha256": digest,
                       "authority": "non_authoritative_build_metadata"}).encode()


def compare(body=None, code="200", exit_code=0, expected=DIGEST,
            candidate=SHA_OLD, main=SHA_MAIN, snapshot=SHA_SNAPSHOT):
    return m.assess(expected_digest=expected,
                    public_body=response() if body is None else body,
                    http_status=code, transport_exit=exit_code,
                    deployed_source_sha=candidate, observer_main_sha=main,
                    reported_source_snapshot_sha=snapshot)


class TestManualRuntimeWitness(unittest.TestCase):
    def test_metadata_digest_match_never_release(self):
        r = compare()
        self.assertEqual(r["status"], "HTTP_METADATA_MATCH_ONLY")
        self.assertTrue(r["exact_digest_match"])
        self.assertFalse(r["observer_main_matches_operator_source"])
        self.assertFalse(r["operator_source_matches_dated_provider_snapshot"])
        for k in ("production_release_authorized", "seal_granted",
                  "production_mutation", "independent_runtime_execution_verified",
                  "actual_deployment_sha_cryptographically_proven",
                  "private_storage_or_restore_verified"):
            self.assertIs(r[k], False)
        self.assertEqual(r["authority"], "none")

    def test_even_all_git_shas_match_public_build_is_not_release(self):
        r = compare(candidate=SHA_MAIN, main=SHA_MAIN, snapshot=SHA_MAIN)
        self.assertEqual(r["status"], "HTTP_METADATA_MATCH_ONLY")
        self.assertTrue(r["observer_main_matches_operator_source"])
        self.assertTrue(r["operator_source_matches_dated_provider_snapshot"])
        self.assertFalse(r["production_release_authorized"])

    def test_bad_http_and_transport_cannot_pass(self):
        for code, exit_code in (("302", 0), ("404", 0), ("503", 0),
                                ("000", 28), ("200", 18)):
            with self.subTest(code=code, exit_code=exit_code):
                r = compare(code=code, exit_code=exit_code)
                self.assertEqual(r["status"], "HTTP_IDENTITY_MISSING_INVALID_OR_DRIFT")
                self.assertFalse(r["exact_digest_match"])

    def test_reject_wrong_public_schema_auth_digest_and_extra_keys(self):
        base = json.loads(response())
        variants = (
            dict(base, schema="nexus.fake"),
            dict(base, authority="owner"),
            dict(base, source_tree_sha256="0" * 64),
            dict(base, source_tree_sha256="unavailable"),
            dict(base, private_secret="NEVER_ECHO_PRIVATE_SENTINEL"),
            ["not", "an", "identity"],
        )
        for payload in variants:
            with self.subTest(payload=str(payload)[:100]):
                r = compare(body=json.dumps(payload).encode())
                self.assertEqual(r["status"], "HTTP_IDENTITY_MISSING_INVALID_OR_DRIFT")
                self.assertFalse(r["production_release_authorized"])

    def test_never_print_or_accept_unbounded_corrupt_untrusted_body(self):
        for body in (b"", b"x" * (m.MAX_RESPONSE_BYTES + 1), b"\xff",
                     b"NEVER_ECHO_PRIVATE_SENTINEL", b'{"x": NaN}',
                     b'{"schema":"x","schema":"y"}', response()+response()):
            with self.subTest(size=len(body)):
                self.assertIsNone(m.public_identity(body))
                r = compare(body=body)
                self.assertNotIn("NEVER_ECHO_PRIVATE_SENTINEL", json.dumps(r))
                self.assertFalse(r["exact_digest_match"])

    def test_invalid_source_ids_and_status_rejected(self):
        for field,value in (("candidate",".."),("main","f"*64),
                            ("snapshot","g"*40),("expected","bad"),
                            ("code","200\n"),("exit_code",-1)):
            with self.subTest(field=field):
                kwargs={field:value}
                with self.assertRaises(m.Rejected):
                    compare(**kwargs)

    def test_source_tree_digest_matches_repository_native_algorithm(self):
        actual = m.source_tree_digest(ROOT)
        native = subprocess.check_output(
            ["bash", "scripts/source-tree-digest.sh"], cwd=ROOT,
            timeout=30, text=True).strip()
        self.assertEqual(actual, native)
        self.assertRegex(actual, r"^[a-f0-9]{64}$")

    def test_disposable_candidate_untrusted_script_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for filename in m.INPUTS:
                target=root/filename
                target.parent.mkdir(exist_ok=True,parents=True)
                if filename in ("src", "artifact-05", "web"):
                    target.mkdir()
                    (target/"file.txt").write_text(filename)
                else:
                    target.write_text("ECHO_SENTINEL_SHOULD_NOT_EXECUTE")
            sentinel = root/"SENTINEL_EXECUTION"
            (root/"scripts/source-tree-digest.sh").write_text(
                "#!/bin/sh\n"+"touch "+str(sentinel)+"\n")
            value=m.source_tree_digest(root)
            self.assertRegex(value, r"^[a-f0-9]{64}$")
            self.assertFalse(sentinel.exists())

    def test_symlink_in_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for filename in m.INPUTS:
                target=root/filename
                target.parent.mkdir(exist_ok=True,parents=True)
                if filename in ("src","artifact-05","web"):
                    target.mkdir()
                    (target/"known.txt").write_text("synthetic")
                else:
                    target.write_text("synthetic")
            (root/"src/evil").symlink_to(root/"Cargo.toml")
            with self.assertRaises(m.Rejected):
                m.source_tree_digest(root)

    def test_cli_sanitizes_bad_input_and_does_not_print_body(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            body=p/"PRIVATE_FILENAME_NEVER_PRINT.json"
            body.write_bytes(b"SECRET_NEVER_PRINT")
            out=p/"report.json"
            cmd=[sys.executable,str(MODULE_FILE),"--candidate-root",str(ROOT),
                 "--response-file",str(body),"--http-status","200",
                 "--curl-exit","0","--deployed-source-sha",SHA_OLD,
                 "--main-sha",SHA_MAIN,"--snapshot-source-sha",SHA_SNAPSHOT,
                 "--report",str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(out.read_text())["status"],
                             "HTTP_IDENTITY_MISSING_INVALID_OR_DRIFT")
            self.assertNotIn("SECRET_NEVER_PRINT",result.stdout+result.stderr+out.read_text())
            self.assertNotIn("PRIVATE_FILENAME",result.stdout+result.stderr)
            out.unlink()
            body.write_bytes(b"X"*(m.MAX_RESPONSE_BYTES+1))
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,2)
            self.assertFalse(out.exists())

    def test_manual_workflow_has_no_automatic_network_trigger(self):
        workflow=(ROOT / ".github/workflows/stage-d-manual-public-runtime.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:",workflow)
        self.assertNotIn("\n  schedule:",workflow)
        self.assertNotIn("\n  pull_request:",workflow)
        self.assertIn("I_ACCEPT_ONE_PUBLIC_HTTPS_GET_MAY_WAKE_SERVICE",workflow)
        self.assertIn("curl --silent --show-error",workflow)
        self.assertIn("--max-time 12",workflow)
        self.assertIn("--max-redirs 0",workflow)
        self.assertIn("https://nexus-stage-d-production.up.railway.app/v1/runtime-identity",
                      workflow)
        self.assertIn("persist-credentials: false",workflow)
        self.assertIn("production_mutation",str(m.assess(expected_digest=DIGEST,
            public_body=response(),http_status="200",transport_exit=0,
            deployed_source_sha=SHA_OLD,observer_main_sha=SHA_MAIN,
            reported_source_snapshot_sha=SHA_SNAPSHOT)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
