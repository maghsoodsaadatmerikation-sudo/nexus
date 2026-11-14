#!/usr/bin/env python3
"""Synthetic regression suite for scoped, HTTPS-only portable NEXUS PWA."""
from __future__ import annotations
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("build-portable-pwa-kit.py")
spec = importlib.util.spec_from_file_location("portable_pwa", SCRIPT)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)
COMMIT = "a" * 40


def mutated(original, change=None, extra=None, mode=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as src, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            new = copy.copy(item)
            if item.filename == mode:
                new.external_attr = 0o120777 << 16
            value = src.read(item.filename)
            if change is not None and item.filename == change[0]:
                value = change[1]
            dst.writestr(new, value)
        if extra:
            dst.writestr(extra, b"not allowed")
    return output.getvalue()


class PortablePwaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zip = kit.build_bytes(COMMIT)

    def reject(self, raw, commit=COMMIT):
        with self.assertRaises((kit.KitBlocked, ValueError, UnicodeError)):
            kit.inspect_bytes(raw, commit)

    def test_complete_scoped_installable_package(self):
        report = kit.inspect_bytes(self.zip, COMMIT)
        self.assertEqual(report["status"], "VERIFIED_PORTABLE_PWA_PACKAGE")
        self.assertEqual(report["files"], 7)
        self.assertFalse(report["production_deployed"])
        self.assertFalse(report["release_authorized"])
        self.assertEqual(report["authority"], "none")

    def test_zip_is_byte_reproducible(self):
        self.assertEqual(self.zip, kit.build_bytes(COMMIT))

    def test_app_is_relocated_without_out_of_scope_registration(self):
        pieces = kit.payloads()
        html = pieces["index.html"].decode()
        self.assertIn('href="./manifest.json"', html)
        self.assertIn("register('./service-worker.js'", html)
        self.assertIn("scope:'./'", html)
        self.assertIn("getRegistration(new URL('./',location.href).href)", html)
        self.assertNotIn("navigator.serviceWorker.register('/service-worker.js'", html)
        self.assertNotIn("getRegistration('/')", html)
        self.assertIn("connect-src 'none'", html)

    def test_worker_install_works_on_any_https_origin_not_insecure_http(self):
        html = kit.payloads()["index.html"].decode()
        self.assertIn(
            "const allowedInstallOrigin=window.isSecureContext&&\n"
            "    (location.protocol==='https:'||\n"
            "     (location.protocol==='http:'&&\n"
            "      (location.hostname==='127.0.0.1'||location.hostname==='localhost')));",
            html)
        self.assertNotIn(
            "(location.hostname==='nexus-offline-pilot.onrender.com'||",
            html)
        self.assertNotIn("location.protocol==='file:'", html)

    def test_worker_scope_and_cache_do_not_intercept_sibling_paths(self):
        worker = kit.payloads()["service-worker.js"].decode()
        self.assertIn("const ENTRY=new URL('./',self.location.href).href;", worker)
        self.assertIn("const PREFIX='nexus-portable-'+encodeURIComponent(", worker)
        self.assertIn("target.pathname", worker)
        self.assertIn("new URL('index.html',ENTRY).pathname", worker)
        self.assertIn("req.mode!=='navigate'", worker)
        self.assertIn("req.method!=='GET'", worker)
        self.assertNotIn("nexus-app-shell-", worker)
        self.assertNotIn("localStorage", worker)
        self.assertNotIn("indexedDB", worker)
        self.assertNotIn("/v1/", worker)

    def test_manifest_has_relative_scope_and_icons(self):
        manifest = json.loads(kit.payloads()["manifest.json"])
        self.assertEqual(manifest["start_url"], "./")
        self.assertEqual(manifest["scope"], "./")
        self.assertEqual(manifest["display"], "standalone")
        self.assertTrue(all(item["src"].startswith("./icons/")
                            for item in manifest["icons"]))

    def test_source_hash_changes_after_relative_path_adapter(self):
        source = kit.SRC.read_bytes()
        adapted = kit.payloads()["index.html"]
        self.assertNotEqual(source, adapted)
        self.assertIn(kit.digest(adapted), kit.payloads()["service-worker.js"].decode())

    def test_manifest_binds_source_revision_and_no_release_authority(self):
        with zipfile.ZipFile(io.BytesIO(self.zip)) as archive:
            metadata = json.loads(archive.read("nexus/PWA-KIT.json"))
        self.assertEqual(metadata["source_revision"], COMMIT)
        self.assertFalse(metadata["private_data"])
        self.assertFalse(metadata["production_deployed"])
        self.assertFalse(metadata["android_device_tested"])
        self.assertFalse(metadata["release_authorized"])

    def test_tampered_html_is_rejected_even_with_valid_zip_crc(self):
        with zipfile.ZipFile(io.BytesIO(self.zip)) as archive:
            changed = archive.read("nexus/index.html") + b"tamper"
        self.reject(mutated(self.zip, change=("nexus/index.html", changed)))

    def test_tampered_worker_or_icon_is_rejected(self):
        for name in ("nexus/service-worker.js", "nexus/icons/nexus-192.png"):
            with zipfile.ZipFile(io.BytesIO(self.zip)) as z:
                mutated_bytes = z.read(name) + b"changed"
            with self.subTest(name=name):
                self.reject(mutated(self.zip, change=(name, mutated_bytes)))

    def test_injected_release_authorization_is_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.zip)) as z:
            metadata = json.loads(z.read("nexus/PWA-KIT.json"))
        for field in ("release_authorized", "production_deployed", "private_data"):
            with self.subTest(field=field):
                fake = dict(metadata, **{field: True})
                self.reject(mutated(self.zip, change=(
                    "nexus/PWA-KIT.json", json.dumps(fake).encode())))

    def test_wrong_commit_or_different_hash_is_rejected(self):
        self.reject(self.zip, "b" * 40)

    def test_unknown_or_duplicate_or_path_traversal_rejected(self):
        for path in ("nexus/private.json", "nexus/../private.json",
                     "nexus/index.html", "other/index.html"):
            with self.subTest(path=path):
                self.reject(mutated(self.zip, extra=path))

    def test_archive_symlink_or_zip_bomb_refused(self):
        self.reject(mutated(self.zip, mode="nexus/index.html"))
        self.reject(b"x" * (kit.MAX_ARCHIVE + 1))
        self.reject(b"not-a-zip")

    def test_no_replace_and_safe_read(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "site.zip"
            kit.publish(dest, self.zip)
            self.assertEqual(kit.read_zip(dest), self.zip)
            with self.assertRaises((kit.KitBlocked, FileExistsError)):
                kit.publish(dest, b"bad")
            self.assertEqual(dest.read_bytes(), self.zip)

    def test_symlinked_and_hardlinked_archives_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dest = root / "site.zip"
            dest.write_bytes(self.zip)
            symlink = root / "symlink.zip"
            symlink.symlink_to(dest)
            with self.assertRaises(OSError):
                kit.read_zip(symlink)
            second = root / "hardlink.zip"
            second.hardlink_to(dest)
            with self.assertRaises(kit.KitBlocked):
                kit.read_zip(dest)

    def test_source_anchor_drift_fails_not_silently_builds(self):
        source = kit.SRC.read_bytes()
        swapped = source.replace(b'href="/manifest.json"',
                                 b'href="./manifest.json"', 1)
        self.assertNotEqual(source, swapped)
        with self.assertRaises(kit.KitBlocked):
            kit.payloads(source=swapped)

    def test_invalid_package_source_commit_rejected(self):
        with self.assertRaises(kit.KitBlocked):
            kit.build_bytes("short")

    def test_refuse_non_pwa_or_non_html_input(self):
        with self.assertRaises(kit.KitBlocked):
            kit.payloads(source=b"not an app")


if __name__ == "__main__":
    unittest.main()
