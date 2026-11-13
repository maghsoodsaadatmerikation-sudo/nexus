#!/usr/bin/env python3
"""No-provider destructive regression tests for private workspace exports."""
from __future__ import annotations

import contextlib
import importlib.util
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

MODULE_PATH = Path(__file__).with_name("workspace-backup.py")
spec = importlib.util.spec_from_file_location("nexus_workspace_backup", MODULE_PATH)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
WORKSPACE_ID = "test-abc"
TOKEN = "private-ci-test-token"
SNAPSHOT = {
    "schema_version": 1,
    "workspace": {"id": WORKSPACE_ID, "question": "test private snapshot"},
    "events": [],
}


def content(document=SNAPSHOT):
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


class Response:
    def __init__(self, *, body=None, headers=None, status=200, url=None):
        self.body = io.BytesIO(content() if body is None else body)
        self.headers = headers if headers is not None else {"content-type": "application/json"}
        self.status = status
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body.read(size)

    def geturl(self):
        return self.url or "http://127.0.0.1:3000/v1/workspaces/test-abc"


class Opener:
    def __init__(self, response=None, hook=None):
        self.response = response or Response()
        self.hook = hook
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if self.hook is not None:
            self.hook()
        return self.response


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.file = self.dir / "snapshot.json"
        self.origin = "http://127.0.0.1:3000"

    def write(self, opener=None, path=None):
        return backup.write_backup(self.origin, WORKSPACE_ID, TOKEN,
                                   path or self.file, opener or Opener())

    def test_atomic_private_snapshot_and_no_auth_in_file(self):
        opener = Opener()
        self.write(opener)
        self.assertEqual(json.loads(self.file.read_bytes()), SNAPSHOT)
        self.assertEqual(stat.S_IMODE(self.file.stat().st_mode), 0o600)
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.timeout, 20)
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertNotIn(TOKEN.encode(), self.file.read_bytes())
        self.assertEqual(list(self.dir.iterdir()), [self.file])

    def test_existing_snapshot_never_overwritten(self):
        self.file.write_bytes(b"irreplaceable")
        with self.assertRaises(backup.BackupBlocked):
            self.write()
        self.assertEqual(self.file.read_bytes(), b"irreplaceable")
        self.assertEqual(list(self.dir.iterdir()), [self.file])

    def test_symlink_never_followed_or_replaced(self):
        outside = self.dir / "outside"
        outside.write_bytes(b"secret")
        self.file.symlink_to(outside)
        with self.assertRaises(backup.BackupBlocked):
            self.write()
        self.assertEqual(outside.read_bytes(), b"secret")
        self.assertTrue(self.file.is_symlink())

    def test_competing_create_mid_transfer_is_not_overwritten(self):
        def competitor():
            self.file.write_bytes(b"other writer")
        with self.assertRaises(FileExistsError):
            self.write(Opener(hook=competitor))
        self.assertEqual(self.file.read_bytes(), b"other writer")
        self.assertEqual(list(self.dir.iterdir()), [self.file])

    def test_non_json_and_wrong_id_never_published(self):
        for response in (
            Response(body=b"{invalid"),
            Response(body=content({"workspace": {"id": "other"},
                                   "schema_version": 1, "events": []})),
            Response(body=b'{"workspace":{"id":"test-abc","id":"other"},"schema_version":1,"events":[]}'),
            Response(body=b"[]"),
            Response(body=b""),
        ):
            with self.subTest(response=response):
                with self.assertRaises(backup.BackupBlocked):
                    self.write(Opener(response=response))
                self.assertEqual(list(self.dir.iterdir()), [])

    def test_bad_content_type_or_encoding_is_blocked(self):
        for headers in ({"content-type": "text/html"},
                        {"content-type": "application/json",
                         "content-encoding": "gzip"}):
            with self.subTest(headers=headers):
                with self.assertRaises(backup.BackupBlocked):
                    self.write(Opener(Response(headers=headers)))
                self.assertFalse(self.file.exists())

    def test_http_redirect_and_wrong_status_are_blocked(self):
        url = self.origin + "/v1/workspaces/" + WORKSPACE_ID
        for response in (Response(status=302), Response(url=url + "/moved"),
                         Response(status=401)):
            with self.subTest(response=response):
                with self.assertRaises(backup.BackupBlocked):
                    self.write(Opener(response))
                self.assertFalse(self.file.exists())

    def test_oversized_or_mismatched_lengths_are_blocked(self):
        for length in (str(backup.MAX_BYTES + 1), "not-an-integer", "0"):
            with self.subTest(length=length):
                with self.assertRaises(backup.BackupBlocked):
                    self.write(Opener(Response(headers={
                        "content-type": "application/json", "content-length": length})))
                self.assertFalse(self.file.exists())

    def test_insecure_remote_http_and_token_urls_are_blocked(self):
        for url in ("http://nexus.example.org", "https://nexus.example.org/path",
                    "https://user:secret@nexus.example.org", "https://nexus.example.org?x=1",
                    "https://nexus.example.org#fragment", "https://nexus.example.org:99999",
                    "https://nexus.example.org extra"):
            with self.subTest(url=url):
                with self.assertRaises(backup.BackupBlocked):
                    backup.origin_url(url)
        self.assertEqual(backup.origin_url("https://nexus.example.org/"),
                         "https://nexus.example.org")

    def test_symlinked_output_parent_is_refused(self):
        target = self.dir / "real"
        target.mkdir()
        (self.dir / "alias").symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):
            self.write(path=self.dir / "alias" / "snapshot.json")
        self.assertEqual(list(target.iterdir()), [])

    def test_optimized_python_cannot_ignore_invalid_environment(self):
        result = subprocess.run(
            [sys.executable, "-O", str(MODULE_PATH), str(self.file)],
            env={"NEXUS_BASE_URL": "https://bad.example.org",
                 "NEXUS_API_TOKEN": TOKEN, "NEXUS_WORKSPACE_ID": "../bad"},
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertNotIn(TOKEN, result.stderr)

    def test_real_loopback_gateway_mock_and_wrapper(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append((self.path, self.headers.get("Authorization")))
                response = content()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            local = f"http://127.0.0.1:{server.server_port}"
            env = dict(os.environ, NEXUS_BASE_URL=local,
                       NEXUS_WORKSPACE_ID=WORKSPACE_ID, NEXUS_API_TOKEN=TOKEN)
            shell = Path(__file__).with_name("workspace-backup.sh")
            result = subprocess.run(["bash", str(shell), str(self.file)],
                                    env=env, capture_output=True, text=True,
                                    timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(self.file.exists())
            self.assertEqual(observed, [("/v1/workspaces/test-abc", "Bearer " + TOKEN)])
            self.assertEqual(stat.S_IMODE(self.file.stat().st_mode), 0o600)
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
