#!/usr/bin/env python3
"""Real local HTTP + public ZIP tamper tests, no credentials/real user data."""
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
import zipfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "build-studio-phone-local.py"
spec = importlib.util.spec_from_file_location("nexus_local_studio_builder", SCRIPT)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)
COMMIT = "b" * 40


class StudioLocalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nexus-studio-local-ci-synthetic-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.zip = self.root / "studio.zip"

    def bundle(self):
        return kit.build(self.zip, COMMIT)

    def extract(self):
        out = self.root / "extract"
        out.mkdir()
        with zipfile.ZipFile(self.zip) as archive:
            archive.extractall(out)
        return out / kit.BUNDLE

    def test_reproducible_public_only_package(self):
        digest = self.bundle()
        second = self.root / "second.zip"
        self.assertEqual(digest, kit.build(second, COMMIT))
        self.assertEqual(self.zip.read_bytes(), second.read_bytes())
        self.assertTrue(kit.verify(self.zip, exact_commit=COMMIT))
        with zipfile.ZipFile(self.zip) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 23)
            self.assertIn(kit.BUNDLE + '/vendor/astronomy-2.1.19.min.js', names)
            self.assertEqual(
                set(names),
                {kit.BUNDLE + "/" + n for n in kit.SOURCE_NAMES + (kit.CHECK_NAME,
                    "run-local.py", "README.txt", "source-manifest.json")})
            receipt = json.loads(archive.read(kit.BUNDLE + "/source-manifest.json"))
            self.assertEqual(receipt["source_commit"], COMMIT)
            self.assertEqual(len(receipt["assets"]), 20)
            check = archive.read(kit.BUNDLE + "/" + kit.CHECK_NAME)
            self.assertIn(receipt["assets"]["index.html"]["sha256"].encode(), check)
            self.assertIn(receipt["assets"]["service-worker.js"]["sha256"].encode(), check)
            self.assertNotIn(b"__APP_SHA256__", check)
            self.assertIn(b"personal_data_collected:false", check)
            self.assertTrue(receipt["loopback_only"])
            self.assertFalse(receipt["private_user_data_included"])
            self.assertFalse(receipt["model_weights_included"])
            self.assertFalse(receipt["production_deploy_performed"])
            self.assertFalse(receipt["android_device_verified"])
            self.assertEqual(receipt["authority"], "none")
            shell = archive.read(kit.BUNDLE + "/run-local.py")
            self.assertIn(b'("127.0.0.1", args.port)', shell)
            self.assertNotIn(b'("0.0.0.0", args.port)', shell)
            self.assertNotIn(b"RAILWAY_API_TOKEN", shell)
            self.assertNotIn(b"requests.post", shell)
            self.assertIn(b"def do_POST(self)", shell)

    def test_unsafe_revision_or_existing_output_blocks(self):
        for commit in ("main", "f" * 39, "", "C" * 40):
            with self.subTest(commit=commit):
                with self.assertRaises(ValueError):
                    kit.build(self.zip, commit)
                self.assertFalse(self.zip.exists())
        self.zip.write_bytes(b"previous-user-file")
        with self.assertRaises(ValueError):
            kit.build(self.zip, COMMIT)
        self.assertEqual(self.zip.read_bytes(), b"previous-user-file")

    def test_tampered_zip_extra_file_and_wrong_commit_refused(self):
        self.bundle()
        with zipfile.ZipFile(self.zip) as archive:
            entries = {i.filename: archive.read(i) for i in archive.infolist()}
        altered = self.root / "altered.zip"
        with zipfile.ZipFile(altered, "w") as archive:
            for name, data in entries.items():
                if name.endswith("/device-check.html"):
                    data += b"<script>UNREVIEWED</script>"
                archive.writestr(name, data)
        with self.assertRaises(ValueError):
            kit.verify(altered)
        with zipfile.ZipFile(altered, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
            archive.writestr(kit.BUNDLE + "/secret/private-key.pem", b"synthetic")
        with self.assertRaises(ValueError):
            kit.verify(altered)
        with self.assertRaises(ValueError):
            kit.verify(self.zip, exact_commit="f" * 40)

    def run_server(self, location):
        # Disposable loopback port, no listening on external interfaces.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(
            ["python3", str(location / "run-local.py"), "--port", str(port)],
            cwd=self.root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: self.close_server(process))
        for _ in range(80):
            if process.poll() is not None:
                raise AssertionError("package server exited without startup")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=.3) as response:
                    if response.status == 200:
                        return port, process
            except (OSError, urllib.error.URLError):
                time.sleep(.08)
        raise AssertionError("localhost server never became ready")

    @staticmethod
    def close_server(proc):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=4)
        else:
            proc.communicate(timeout=3)

    def test_http_serves_exact_public_assets_and_refuses_requests(self):
        self.bundle()
        folder = self.extract()
        port, proc = self.run_server(folder)
        for name in ("/", "/index.html", "/manifest.json", "/service-worker.js",
                     "/device/device-ui.js", "/device/model-manifest.json",
                     "/icons/nexus-192.png", "/device-check.html",
                     "/vendor/astronomy-2.1.19.min.js", "/studio-composer-ui.js"):
            with self.subTest(name=name):
                url = f"http://127.0.0.1:{port}{name}"
                with urllib.request.urlopen(url, timeout=3) as response:
                    data = response.read()
                    expected = folder / ("index.html" if name == "/" else name.lstrip("/"))
                    self.assertEqual(data, expected.read_bytes())
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.status, 200)
        for name in ("/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd",
                     "/run-local.py", "/source-manifest.json", "/?force=1",
                     "/index.html?secret=1", "/device/unknown.js"):
            with self.subTest(name=name):
                c = HTTPConnection("127.0.0.1", port, timeout=3)
                c.request("GET", name)
                response = c.getresponse()
                self.assertEqual(response.status, 404)
                c.close()
        conn = HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("POST", "/index.html", body=b"SYNTHETIC")
        self.assertEqual(conn.getresponse().status, 405)
        conn.close()
        self.assertIsNone(proc.poll())

    def test_asset_mutation_before_server_boot_blocks_and_never_listens(self):
        self.bundle()
        folder = self.extract()
        (folder / "index.html").write_bytes(b"TAMPERED PUBLIC APP")
        result = subprocess.run(
            ["python3", str(folder / "run-local.py"), "--port", "8765"],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertNotIn("TAMPERED", result.stderr)
        self.assertNotIn("ready", result.stdout)

    def test_incorrect_port_blocks(self):
        self.bundle()
        folder = self.extract()
        result = subprocess.run(
            ["python3", str(folder / "run-local.py"), "--port", "2"],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
