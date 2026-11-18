#!/usr/bin/env python3
"""Real localhost + deterministic Android NEXUS Studio/Motion packaging tests."""
from __future__ import annotations

import hashlib
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nexus_combined_mobile_kit", ROOT / "scripts/build-nexus-mobile-local.py"
)
kit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit)
COMMIT = "b" * 40


class MobileKitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nexus-mobile-motion-real-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / "nexus-mobile-local.zip"

    def build(self):
        return kit.build(self.bundle, COMMIT)

    def extract(self):
        dest = self.root / "unpacked"
        dest.mkdir()
        with zipfile.ZipFile(self.bundle) as archive:
            archive.extractall(dest)
        return dest / kit.BUNDLE

    def test_exact_source_bound_reproducible_zip_without_secrets(self):
        receipt = self.build()
        second = self.root / "repeat.zip"
        self.assertEqual(receipt["sha256"], kit.build(second, COMMIT)["sha256"])
        self.assertEqual(self.bundle.read_bytes(), second.read_bytes())
        self.assertEqual(kit.verify(self.bundle, COMMIT)["source_commit"], COMMIT)
        with zipfile.ZipFile(self.bundle) as archive:
            names = archive.namelist()
            expected = set(kit.base.SOURCE_NAMES + (
                kit.base.CHECK_NAME, "run-local.py", "README.txt", "source-manifest.json"
            )) | set(kit.EXTRA)
            self.assertEqual(len(names), len(expected))
            self.assertEqual(set(names), {kit.BUNDLE + "/" + n for n in expected})
            manifest = json.loads(archive.read(kit.BUNDLE + "/" + kit.MANIFEST))
            self.assertEqual(set(manifest["assets"]), set(kit.MOTION) | {kit.PAGE})
            self.assertEqual(manifest["source_commit"], COMMIT)
            self.assertFalse(manifest["private_user_data_included"])
            self.assertFalse(manifest["android_hardware_verified"])
            launcher = archive.read(kit.BUNDLE + "/" + kit.LAUNCHER_NAME)
            self.assertIn(b'("127.0.0.1", args.port)', launcher)
            self.assertNotIn(b'("0.0.0.0", args.port)', launcher)
            self.assertIn(b"assets.update(load_motion())", launcher)
            self.assertIn(b"LOCAL PUBLIC PACKAGE VERIFICATION BLOCKED", launcher)
            self.assertNotIn(b"requests.post", launcher)

    def test_source_revisions_or_existing_user_output_denied(self):
        for candidate in ("main", "A" * 40, "b" * 39, ""):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                kit.build(self.bundle, candidate)
            self.assertFalse(self.bundle.exists())
        self.bundle.write_bytes(b"existing user data")
        with self.assertRaises(ValueError):
            kit.build(self.bundle, COMMIT)
        self.assertEqual(self.bundle.read_bytes(), b"existing user data")

    def test_modified_zip_entry_wrong_commit_and_extra_file_rejected(self):
        self.build()
        with zipfile.ZipFile(self.bundle) as archive:
            files = [(f.filename, archive.read(f)) for f in archive.infolist()]
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(tampered, "w") as archive:
            for name, payload in files:
                if name.endswith("/motion/motion-core.js"):
                    payload += b"// unreviewed injection"
                archive.writestr(name, payload, compress_type=zipfile.ZIP_STORED)
        with self.assertRaises(ValueError):
            kit.verify(tampered, COMMIT)
        with self.assertRaises(ValueError):
            kit.verify(self.bundle, "f" * 40)
        with zipfile.ZipFile(tampered, "w") as archive:
            for name, payload in files:
                archive.writestr(name, payload, compress_type=zipfile.ZIP_STORED)
            archive.writestr(kit.BUNDLE + "/secret/credentials", b"synthetic")
        with self.assertRaises(ValueError):
            kit.verify(tampered)

    def start_server(self, home: Path):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        p = subprocess.Popen(
            ["python3", str(home / "run-nexus.py"), "--port", str(port)],
            cwd=self.root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(lambda: self.stop_server(p))
        for _ in range(80):
            if p.poll() is not None:
                out, err = p.communicate()
                raise AssertionError("local server stopped before ready: " + err.decode()[-100:])
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/apps.html",
                                             timeout=.35) as response:
                    if response.status == 200:
                        return port
            except (OSError, urllib.error.URLError):
                time.sleep(.08)
        raise AssertionError("loopback server did not start")

    @staticmethod
    def stop_server(p):
        if p.poll() is None:
            p.terminate()
            try:
                p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate(timeout=5)
        else:
            p.communicate(timeout=2)

    def test_live_loopback_studio_motion_and_deny_all_unknown_paths(self):
        self.build()
        home = self.extract()
        port = self.start_server(home)
        allowed = {
            "/apps.html": "apps.html",
            "/": "index.html",
            "/index.html": "index.html",
            "/service-worker.js": "service-worker.js",
            "/manifest.json": "manifest.json",
            "/device-check.html": "device-check.html",
            "/motion/": "motion/index.html",
            "/motion/index.html": "motion/index.html",
            "/motion/motion-core.js": "motion/motion-core.js",
            "/motion/motion-ui.js": "motion/motion-ui.js",
        }
        for url, relative in allowed.items():
            with self.subTest(url=url):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{url}",
                                             timeout=4) as result:
                    self.assertEqual(result.status, 200)
                    self.assertEqual(result.read(), (home / relative).read_bytes())
                    self.assertEqual(result.headers["X-Content-Type-Options"], "nosniff")
                    self.assertEqual(result.headers["Cache-Control"], "no-store")
                    if url.endswith("/") or url.endswith(".html"):
                        self.assertIn("text/html", result.headers["Content-Type"])
        for path in ("/source-manifest.json", "/motion-integrity.json",
                     "/run-nexus.py", "/run-local.py", "/README-NEXUS.txt",
                     "/motion/../run-local.py", "/motion/index.html?check=1",
                     "/%2e%2e/%2e%2e/etc/passwd", "/unknown", "/motion",
                     "/motion/secret-user-file.mp3"):
            with self.subTest(path=path):
                conn = HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("GET", path)
                response = conn.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                conn.close()
        for method in ("POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                conn = HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request(method, "/motion/", body=b"SYNTHETIC")
                response = conn.getresponse()
                self.assertEqual(response.status, 405)
                response.read()
                conn.close()
        self.assertIn(b"motion/", (home / "apps.html").read_bytes())

    def test_tampered_motion_or_studio_refuses_to_start(self):
        self.build()
        home = self.extract()
        for name in ("motion/motion-ui.js", "index.html"):
            original = (home / name).read_bytes()
            (home / name).write_bytes(original + b"UNREVIEWED")
            proc = subprocess.run(
                ["python3", str(home / "run-nexus.py"), "--port", "18765"],
                capture_output=True, timeout=10,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(b"BLOCKED", proc.stderr)
            self.assertNotIn(b"ready", proc.stdout)
            (home / name).write_bytes(original)

    def test_changing_integrity_manifest_blocks_server(self):
        self.build()
        home = self.extract()
        path = home / "motion-integrity.json"
        path.write_text('{"schema":"fake"}', encoding="utf-8")
        result = subprocess.run(
            ["python3", str(home / "run-nexus.py"), "--port", "18765"],
            capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"BLOCKED", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
