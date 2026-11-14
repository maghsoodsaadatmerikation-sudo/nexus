#!/usr/bin/env python3
"""Negative fixtures for an isolated, unprivileged static NEXUS preview."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).with_name("prepare-portable-pwa-preview.py")
spec = importlib.util.spec_from_file_location("preview_build", SOURCE)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

HEAD = "a" * 40


class StaticPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nexus-preview-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.target = self.root / "published"

    def built(self):
        report = preview.build(self.target, HEAD)
        self.assertEqual(report["status"], "PUBLIC_STATIC_PREVIEW_VERIFIED")
        return report

    def blocked(self, action):
        with self.assertRaises(preview.KIT.KitBlocked):
            action()

    def test_source_bound_public_only_site(self):
        report = self.built()
        self.assertEqual(report["files"], 9)
        self.assertEqual(report["deployable_path"], "nexus/")
        self.assertFalse(report["private_data_included"])
        self.assertFalse(report["production_deployed"])
        self.assertFalse(report["release_authorized"])
        self.assertEqual(report["authority"], "none")
        self.assertEqual(preview.verify(self.target, HEAD), report)

    def test_root_landing_is_a_static_link_to_nested_app(self):
        self.built()
        landing = (self.target / "index.html").read_text()
        self.assertIn('href="./nexus/"', landing)
        self.assertIn("default-src 'none'", landing)
        self.assertNotIn("<script", landing)

    def test_pwa_has_correct_scope_and_signed_source_claims_absent(self):
        self.built()
        manifest = json.loads((self.target / "nexus/manifest.json").read_text())
        self.assertEqual(manifest["start_url"], "./")
        self.assertEqual(manifest["scope"], "./")
        receipt = json.loads((self.target / "nexus/PWA-KIT.json").read_text())
        self.assertEqual(receipt["source_revision"], HEAD)
        self.assertFalse(receipt["private_data"])
        self.assertFalse(receipt["release_authorized"])
        self.assertFalse(receipt["production_deployed"])
        self.assertIn("register('./service-worker.js'",
                      (self.target / "nexus/index.html").read_text())

    def test_privacy_preserving_mobile_diagnostics_are_pinned_to_app(self):
        self.built()
        diag = (self.target / "nexus/device-check.html").read_text("utf-8")
        app = (self.target / "nexus/index.html").read_bytes()
        self.assertIn(preview.KIT.digest(app), diag)
        self.assertNotIn("__NEXUS_SHELL_SHA256__", diag)
        for fragment in (
            "connect-src 'none'", "worker-src 'none'", "form-action 'none'",
            "nexus.device-readiness.self-report.v1",
            "owner_self_attestation", "private_information_collected:false",
            "production_recovery_verified:false", "release_authorized:false",
            "navigator.serviceWorker.getRegistration("
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, diag)
        for forbidden in ("navigator.serviceWorker.register(", "fetch(",
                          "XMLHttpRequest", "sendBeacon(", "userAgent",
                          "navigator.geolocation", "localStorage.setItem(",
                          "navigator.mediaDevices.getUserMedia("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, diag)

    def test_tampering_with_diagnostic_page_fails_verification(self):
        self.built()
        path = self.target / "nexus/device-check.html"
        path.write_bytes(path.read_bytes() + b"unreviewed")
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_missing_device_check_page_blocks_publication(self):
        self.built()
        (self.target / "nexus/device-check.html").unlink()
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_two_source_distinct_commits_refuse_as_same_preview(self):
        self.built()
        self.blocked(lambda: preview.verify(self.target, "b" * 40))

    def test_public_app_html_tamper_blocks_verification(self):
        self.built()
        f = self.target / "nexus/index.html"
        f.write_bytes(f.read_bytes() + b"tampering")
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_worker_tamper_blocks_verification(self):
        self.built()
        file = self.target / "nexus/service-worker.js"
        file.write_bytes(file.read_bytes() + b"\n/* changed */")
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_extra_file_blocks_unsafe_publication(self):
        self.built()
        (self.target / "nexus/private.json").write_text('{"private":"bad"}')
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_missing_manifest_blocks_verification(self):
        self.built()
        (self.target / "nexus/PWA-KIT.json").unlink()
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_symbolic_link_to_private_file_is_rejected(self):
        self.built()
        private = self.root / "outside.txt"
        private.write_text("PRIVATE_TEST_ONLY")
        (self.target / "nexus/extra.txt").symlink_to(private)
        self.blocked(lambda: preview.verify(self.target, HEAD))

    def test_existing_publication_cannot_be_overwritten(self):
        self.built()
        self.blocked(lambda: preview.build(self.target, HEAD))

    def test_invalid_source_revision_refused(self):
        self.blocked(lambda: preview.build(self.target, "bad-sha"))

    def test_no_model_no_runtime_credentials_or_gateway(self):
        self.built()
        page = (self.target / "nexus/index.html").read_text()
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn('Authorization: Bearer ', page)
        self.assertNotIn("https://nexus-7l8e.onrender.com", page)

    def test_source_artifacts_are_unmodified(self):
        source = preview.KIT.SRC.read_bytes()
        expected = preview.KIT.payloads()
        self.built()
        self.assertEqual(preview.KIT.SRC.read_bytes(), source)
        self.assertEqual(preview.KIT.payloads(), expected)

    def test_preview_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            self.target.symlink_to(outside, target_is_directory=True)
            self.blocked(lambda: preview.build(self.target, HEAD))


if __name__ == "__main__":
    unittest.main()
