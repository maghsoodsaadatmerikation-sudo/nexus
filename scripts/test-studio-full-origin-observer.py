#!/usr/bin/env python3
"""Offline acceptance tests for the complete read-only public asset observer."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_complete_public_observer", HERE / "studio-full-origin-observer.py"
)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
COMMIT = "a" * 40


def ancillary_png_chunk(raw):
    """Create a different PNG container with identical RGBA pixels."""
    payload = b"NEXUS\x00synthetic-nonpersonal"
    tag = b"tEXt"
    chunk = (struct.pack(">I", len(payload)) + tag + payload
             + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))
    index = raw.rfind(b"\x00\x00\x00\x00IEND")
    if index < 0:
        raise ValueError("source PNG has no final IEND")
    assert observer.pixel_digest(raw, 192, 192)
    result = raw[:index] + chunk + raw[index:]
    assert observer.pixel_digest(result, 192, 192) == observer.pixel_digest(raw, 192, 192)
    return result


class CompleteObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = observer.gate.source_assets()
        assert len(cls.assets) == len(observer.FILES) == 20

    def inspect(self, fetch=None):
        return observer.inspect_assets(
            self.assets, COMMIT,
            fetch=fetch or (lambda name: self.assets[name]),
        )

    def test_all_twenty_source_assets_are_accounted_for_but_never_authorize_deployment(self):
        result = self.inspect()
        self.assertEqual(result["schema"], observer.SCHEMA)
        self.assertEqual(result["status"], "SOURCE_MATCH_ONLY")
        self.assertEqual(result["reviewed_public_files"], 20)
        self.assertEqual(result["observed_public_files"], 20)
        self.assertEqual({x["path"] for x in result["assets"]}, set(observer.FILES))
        self.assertTrue(all(x["status"] == "MATCH" for x in result["assets"]))
        self.assertIn("pdf/pdf.worker.min.mjs", {x["path"] for x in result["assets"]})
        self.assertIn("pdf/LICENSE-pdfjs.txt", {x["path"] for x in result["assets"]})
        self.assertIn("vendor/astronomy-2.1.19.min.js", {x["path"] for x in result["assets"]})
        self.assertFalse(result["source_manifest_verified"])
        self.assertTrue(result["read_only"])
        for field in (
            "render_deploy_id_verified", "public_browser_verified",
            "real_android_device_verified", "provider_model_available_verified",
            "rollback_provider_artifact_verified", "production_promotion_authorized",
            "provider_mutation", "private_user_data_seen",
        ):
            self.assertIs(result[field], False)
        self.assertEqual(result["authority"], "none")

    def test_hidden_pdf_worker_drift_is_detected_not_mistaken_for_nine_asset_match(self):
        def changed(name):
            return b"tampered-pdf-worker" if name == "pdf/pdf.worker.min.mjs" else self.assets[name]
        result = self.inspect(changed)
        self.assertEqual(result["status"], "PUBLIC_SOURCE_DRIFT")
        self.assertEqual([x for x in result["assets"] if x["status"] == "DRIFT"],
                         [{"path": "pdf/pdf.worker.min.mjs", "status": "DRIFT"}])
        self.assertEqual(result["observed_public_files"], 20)

    def test_new_astronomy_asset_drift_blocks_complete_source_claim(self):
        name = "vendor/astronomy-2.1.19.min.js"
        result = self.inspect(lambda path: b"tampered" if path == name else self.assets[path])
        self.assertEqual(result["status"], "PUBLIC_SOURCE_DRIFT")
        self.assertEqual([x for x in result["assets"] if x["status"] == "DRIFT"],
                         [{"path": name, "status": "DRIFT"}])

    def test_orchestra_module_drift_blocks_complete_source_claim(self):
        name = "studio-orchestra.js"
        result = self.inspect(lambda path: b"tampered" if path == name else self.assets[path])
        self.assertEqual(result["status"], "PUBLIC_SOURCE_DRIFT")
        self.assertEqual([x for x in result["assets"] if x["status"] == "DRIFT"],
                         [{"path": name, "status": "DRIFT"}])

    def test_unreachable_pdf_module_blocks_complete_source_claim(self):
        def missing(name):
            if name == "pdf/studio-pdf.mjs":
                raise TimeoutError("synthetic private exception content")
            return self.assets[name]
        result = self.inspect(missing)
        self.assertEqual(result["status"], "INCOMPLETE_PUBLIC_OBSERVATION")
        self.assertEqual([x for x in result["assets"] if x["status"] == "UNREACHABLE"],
                         [{"path": "pdf/studio-pdf.mjs", "status": "UNREACHABLE"}])
        self.assertNotIn("synthetic private exception", json.dumps(result))

    def test_icons_require_real_rgba_identity_not_container_bytes(self):
        png = ancillary_png_chunk(self.assets["icons/nexus-192.png"])
        result = self.inspect(lambda name:
                              png if name == "icons/nexus-192.png" else self.assets[name])
        self.assertEqual(result["status"], "SOURCE_MATCH_ONLY")
        self.assertEqual([x for x in result["assets"] if x["status"] == "PIXEL_MATCH"],
                         [{"path": "icons/nexus-192.png", "status": "PIXEL_MATCH"}])
        result = self.inspect(lambda name:
                              b"not-a-png" if name == "icons/nexus-192.png" else self.assets[name])
        self.assertEqual(result["status"], "PUBLIC_SOURCE_DRIFT")

    def test_fixed_origin_allowlist_mime_and_response_size_limits(self):
        with self.assertRaises(ValueError):
            observer.fetch_live("../keys.env")
        with self.assertRaises(ValueError):
            observer.fetch_live("pdf/private-file")
        self.assertEqual(observer.mime_types("pdf/pdf.worker.min.mjs"),
                         {"text/javascript", "application/javascript"})
        self.assertEqual(observer.mime_types("pdf/LICENSE-pdfjs.txt"), {"text/plain"})
        self.assertEqual(observer.mime_types("manifest.json"),
                         {"application/json", "application/manifest+json"})
        self.assertEqual(observer.gate.ORIGIN,
                         "https://nexus-studio-merikation.onrender.com/")
        self.assertEqual(observer.asset_limit("pdf/pdf.worker.min.mjs"), 1300000)

    def test_invalid_unverified_assets_and_sha_rejected_before_network(self):
        calls = []
        def trap(name):
            calls.append(name)
            raise AssertionError("never contact external service on bad source inventory")
        with self.assertRaises(ValueError):
            observer.inspect_assets({"index.html": b"fake"}, COMMIT, fetch=trap)
        with self.assertRaises(ValueError):
            observer.inspect_assets(self.assets, "main", fetch=trap)
        with self.assertRaises(ValueError):
            observer.inspect_assets({**self.assets, "pdf/pdf.worker.min.mjs": b""},
                                    COMMIT, fetch=trap)
        self.assertEqual(calls, [])

    def test_only_verified_manifest_and_zip_can_claim_reviewed_source(self):
        with tempfile.TemporaryDirectory(prefix="nexus-full-public-observer-") as temp:
            root = Path(temp)
            archive = root / "candidate.zip"
            manifest = root / "candidate.json"
            observer.gate.build(archive, manifest, COMMIT)
            calls = []
            def synthetic(name):
                calls.append(name)
                return self.assets[name]
            result = observer.observe_verified(archive, manifest, COMMIT, fetch=synthetic)
            self.assertEqual(result["status"], "SOURCE_MATCH_ONLY")
            self.assertTrue(result["source_manifest_verified"])
            self.assertEqual(calls, list(observer.FILES))
            with self.assertRaises(ValueError):
                observer.observe_verified(archive, manifest, "b" * 40, fetch=synthetic)
            self.assertEqual(len(calls), 20)
            tampered = json.loads(manifest.read_text())
            tampered["assets"]["pdf/pdf.worker.min.mjs"]["sha256"] = "b" * 64
            manifest.write_text(json.dumps(tampered))
            with self.assertRaises(ValueError):
                observer.observe_verified(archive, manifest, COMMIT, fetch=synthetic)
            self.assertEqual(len(calls), 20)

    def test_complete_observer_workflow_is_readonly_and_reports_drift_not_go(self):
        workflow = (HERE.parent / ".github/workflows/studio-static-source-release.yml").read_text()
        self.assertIn("studio-full-origin-observer.py", workflow)
        self.assertIn("test-studio-full-origin-observer.py", workflow)
        self.assertIn("nexus-studio-public-all-assets.json", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("RENDER_API_KEY: $", workflow)
        self.assertNotIn("trigger_deploy", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
