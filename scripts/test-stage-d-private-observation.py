#!/usr/bin/env python3
"""Disposable HTTP and offline tests for Stage D private evidence collection."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPTS = Path(__file__).resolve().parent
HELPER = SCRIPTS / "stage-d-private-observation.py"
spec = importlib.util.spec_from_file_location("stage_d_private_test", HELPER)
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

TOKEN = "synthetic-private-bearer"
WID = "test-stage-d"
WORKSPACE = {
    "schema_version": 1,
    "workspace": {"id": WID, "question": "synthetic witness"},
    "events": [],
}
ABSENCE = {"error": "workspace_not_found"}


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "private"
        self.folder.mkdir(mode=0o700)
        self.target = self.folder / "observation.json"
        self.calls = []
        self.status = 200
        self.response_body = json.dumps(WORKSPACE).encode()
        self.content_type = "application/json"
        self.encoding = None
        self.cache_control = "no-store"
        self.response_length = None
        self.redirect_location = "http://127.0.0.1/unsafe"

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.calls.append((self.path, self.headers.get("Authorization")))
                self.send_response(owner.status)
                self.send_header("Content-Type", owner.content_type)
                if owner.encoding:
                    self.send_header("Content-Encoding", owner.encoding)
                if owner.cache_control:
                    self.send_header("Cache-Control", owner.cache_control)
                if owner.status in (301, 302, 307):
                    self.send_header("Location", owner.redirect_location)
                n = len(owner.response_body) if owner.response_length is None \
                    else owner.response_length
                self.send_header("Content-Length", str(n))
                self.end_headers()
                try:
                    self.wfile.write(owner.response_body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def invoke(self, mode: str, *, destination=None, env_add=None):
        env = dict(os.environ, NEXUS_BASE_URL=f"http://127.0.0.1:{self.server.server_port}",
                   NEXUS_WORKSPACE_ID=WID, NEXUS_API_TOKEN=TOKEN)
        if env_add:
            env.update(env_add)
        return subprocess.run(
            [sys.executable, str(HELPER), mode, str(destination or self.target)],
            env=env, capture_output=True, text=True,
            check=False, timeout=10,
        )

    def assert_blocked(self, mode: str = "absence"):
        result = self.invoke(mode)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertNotIn(TOKEN, result.stderr + result.stdout)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_private_valid_snapshot_succeeds(self):
        result = self.invoke("snapshot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.target.read_text()), WORKSPACE)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(list(self.folder.iterdir()), [self.target])
        self.assertEqual(self.calls, [("/v1/workspaces/" + WID, "Bearer " + TOKEN)])
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_private_exact_404_witness_succeeds(self):
        self.status = 404
        self.response_body = json.dumps(ABSENCE).encode()
        result = self.invoke("absence")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.target.read_bytes()), ABSENCE)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(self.calls, [("/v1/workspaces/" + WID, "Bearer " + TOKEN)])
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_absence_never_accepts_200(self):
        self.assert_blocked()

    def test_absence_rejects_wrong_404_body(self):
        self.status = 404
        for body in (b'{"error":"other"}', b"[]", b"not-json",
                     b'{"error":"workspace_not_found","error":"other"}',
                     b'{"error":"workspace_not_found","extra":true}'):
            with self.subTest(body=body):
                self.response_body = body
                self.assert_blocked()

    def test_absence_rejects_redirect_or_server_error(self):
        for code in (302, 307, 500, 401):
            with self.subTest(code=code):
                self.status = code
                self.response_body = b'{"error":"workspace_not_found"}'
                self.assert_blocked()

    def test_absence_rejects_cacheable_html_or_encoded_body(self):
        self.status = 404
        self.response_body = json.dumps(ABSENCE).encode()
        self.cache_control = None
        self.assert_blocked()
        self.cache_control = "no-store"
        self.content_type = "text/html"
        self.assert_blocked()
        self.content_type = "application/json"
        self.encoding = "gzip"
        self.assert_blocked()

    def test_absence_rejects_oversized_and_wrong_body_length(self):
        self.status = 404
        self.response_body = json.dumps(ABSENCE).encode()
        for length in (513, 1):
            with self.subTest(length=length):
                self.response_length = length
                self.assert_blocked()
        self.response_length = None
        self.response_body = b" " * 513
        self.assert_blocked()

    def test_existing_file_never_overwritten(self):
        self.status = 404
        self.response_body = json.dumps(ABSENCE).encode()
        self.target.write_bytes(b"valuable prior observation")
        result = self.invoke("absence")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), b"valuable prior observation")
        self.assertEqual(list(self.folder.iterdir()), [self.target])

    def test_existing_symlink_never_followed_or_replaced(self):
        self.status = 404
        self.response_body = json.dumps(ABSENCE).encode()
        outside = self.folder / "outside"
        outside.write_bytes(b"private")
        self.target.symlink_to(outside)
        result = self.invoke("absence")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_bytes(), b"private")
        self.assertTrue(self.target.is_symlink())

    def test_invalid_workspace_id_blocks_before_network(self):
        result = self.invoke("absence", env_add={"NEXUS_WORKSPACE_ID": "../outside"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls, [])

    def test_remote_plaintext_url_is_rejected(self):
        result = self.invoke("absence", env_add={
            "NEXUS_BASE_URL": "http://untrusted.example.org",
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls, [])

    def test_bad_token_never_reaches_http(self):
        result = self.invoke("snapshot", env_add={"NEXUS_API_TOKEN": "bad\nheader"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls, [])

    def test_optimized_python_remains_fail_closed(self):
        result = subprocess.run(
            [sys.executable, "-O", str(HELPER), "absence", str(self.target)],
            env={"NEXUS_BASE_URL": "https://example.org",
                 "NEXUS_WORKSPACE_ID": "../unsafe",
                 "NEXUS_API_TOKEN": TOKEN},
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)

    def test_shell_evidence_root_and_secretless_argv_controls_exist(self):
        source = (SCRIPTS / "stage-d-evidence.sh").read_text()
        self.assertIn("set -o noclobber", source)
        self.assertIn("umask 077", source)
        self.assertIn("stage-d-private-observation.py", source)
        self.assertEqual(source.count('stage-d-private-observation.py'), 3)
        self.assertNotIn('-H "authorization: Bearer ', source)
        self.assertIn("info.st_mode & 0o077", source)

    def test_private_output_writer_rejects_link_collision(self):
        self.target.write_bytes(b"unreplaceable")
        with self.assertRaises(stage.backup.BackupBlocked):
            stage.write_private_new(json.dumps(ABSENCE).encode(), self.target)
        self.assertEqual(self.target.read_bytes(), b"unreplaceable")


if __name__ == "__main__":
    unittest.main()
