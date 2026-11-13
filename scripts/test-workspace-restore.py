#!/usr/bin/env python3
"""Private, loopback-only tests for single-workspace import hardening."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).with_name('workspace-restore.sh')
SNAPSHOT = {
    'schema_version': 1,
    'workspace': {'id': 'ci-restored', 'question': 'safely restored'},
    'events': [],
}
TOKEN = 'private-restore-token'


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root / 'snapshot.json'
        self.snapshot.write_text(json.dumps(SNAPSHOT))
        self.received = []
        self.status = 201

        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                count = int(self.headers.get('content-length', 0))
                body = self.rfile.read(count)
                parent.received.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(parent.status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')

            def log_message(self, *args):
                return

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def run_script(self, *, path=None, env_overrides=None):
        env = dict(os.environ,
                   NEXUS_BASE_URL=f'http://127.0.0.1:{self.server.server_port}',
                   NEXUS_API_TOKEN=TOKEN)
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(['bash', str(SCRIPT), str(path or self.snapshot)],
                              env=env, capture_output=True, text=True,
                              timeout=10, check=False)

    def test_success_uses_piped_header_and_single_http_import(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.received), 1)
        path, header, data = self.received[0]
        self.assertEqual(path, '/v1/workspaces/import')
        self.assertEqual(header, 'Bearer ' + TOKEN)
        self.assertEqual(json.loads(data), SNAPSHOT)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertIn('single-workspace import only', result.stdout)

    def test_remote_plain_http_must_not_receive_token(self):
        result = self.run_script(env_overrides={'NEXUS_BASE_URL': 'http://evil.example.org'})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.received, [])
        self.assertNotIn(TOKEN, result.stderr)

    def test_symlink_snapshot_is_rejected(self):
        alias = self.root / 'alias.json'
        alias.symlink_to(self.snapshot)
        result = self.run_script(path=alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.received, [])

    def test_hardlinked_snapshot_is_rejected(self):
        alias = self.root / 'hardlink.json'
        os.link(self.snapshot, alias)
        result = self.run_script(path=alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.received, [])

    def test_invalid_json_and_duplicate_members_are_rejected(self):
        for data in ('not json', '{"schema_version":1,"schema_version":2}',
                     '[]', '{"workspace":{"id":"x"}}'):
            with self.subTest(data=data):
                self.snapshot.write_text(data)
                self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.received, [])

    def test_failed_status_is_not_reported_as_restored(self):
        for status in (302, 401, 500):
            with self.subTest(status=status):
                self.status = status
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('restore accepted', result.stdout.lower())
                self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_invalid_token_is_never_forwarded(self):
        result = self.run_script(env_overrides={'NEXUS_API_TOKEN': 'bad\nheader'})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.received, [])

    def test_oversized_snapshot_does_not_hit_gateway(self):
        with self.snapshot.open('wb') as file:
            file.truncate(64 * 1024 * 1024 + 1)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.received, [])


if __name__ == '__main__':
    unittest.main()
