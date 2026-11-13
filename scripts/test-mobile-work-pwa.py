#!/usr/bin/env python3
"""Adversarial, fully local invariants for NEXUS mobile PWA build."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("stage23",ROOT/"scripts"/"build-mobile-work-pwa.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Stage23Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portable=m.portable_source()
        cls.assets=m.produce(cls.portable)

    def test_reproducible_all_outputs(self):
        self.assertEqual(m.produce(self.portable),self.assets)

    def test_user_approval_required_for_worker(self):
        html=self.assets["index.html"].decode()
        self.assertEqual(html.count("navigator.serviceWorker.register("),1)
        self.assertIn("byId('mobile-prepare').addEventListener('click'",html)
        self.assertIn('id="mobile-remove"',html)
        self.assertIn("window.confirm(",html)
        self.assertIn("isSecureContext",html)

    def test_no_private_api_transport(self):
        html=self.assets["index.html"].decode()
        sw=self.assets["service-worker.js"].decode()
        self.assertIn("connect-src 'none'",html)
        self.assertNotIn("fetch(",html)
        self.assertNotIn("/v1/workspaces",sw)
        self.assertNotIn("/v1/connections",sw)
        self.assertNotIn("indexedDB",sw)
        self.assertNotIn("localStorage",sw)
        self.assertNotIn("POST",sw)
        self.assertNotIn("Authorization",sw)

    def test_isolated_mobile_vault(self):
        html=self.assets["index.html"].decode()
        self.assertIn("indexedDB.open('nexus-private-work-mode-mobile-v23',1)",html)
        self.assertNotIn("indexedDB.open('nexus-private-work-mode',1)",html)
        self.assertIn("vault.backup",html)
        self.assertIn("vault.restore",html)

    def test_relative_scope_and_manifest(self):
        manifest=json.loads(self.assets["manifest.json"])
        self.assertEqual(manifest["scope"],"./")
        self.assertEqual(manifest["start_url"],"./")
        self.assertEqual(manifest["display"],"standalone")
        self.assertEqual({x["sizes"] for x in manifest["icons"]},{"192x192","512x512"})
        self.assertIn("new URL('./',self.location.href)",self.assets["service-worker.js"].decode())
        self.assertIn('href="./manifest.json"',self.assets["index.html"].decode())

    def test_every_public_asset_is_hash_pinned(self):
        sw=self.assets["service-worker.js"].decode()
        for path in ("index.html","manifest.json",*m.ICON_PATHS):
            self.assertIn(hashlib.sha256(self.assets[path]).hexdigest(),sw)
        self.assertIn("response.redirected",sw)
        self.assertIn("cache.put(url,response)",sw)
        self.assertIn("await verified(fallback,relative)",sw)

    def test_no_cache_of_private_content(self):
        sw=self.assets["service-worker.js"].decode()
        self.assertIn("request.method!=='GET'",sw)
        self.assertIn("url.search||url.hash",sw)
        self.assertIn("request.mode==='navigate'",sw)
        self.assertIn("const ALLOWED=['index.html','manifest.json'",sw)
        self.assertNotIn("event.request.clone()",sw)
        self.assertNotIn("caches.open('nexus-private",sw)

    def test_no_cross_app_cache_deletion(self):
        sw=self.assets["service-worker.js"].decode()
        page=self.assets["index.html"].decode()
        self.assertIn("key.startsWith('nexus-stage23-shell-')",sw)
        self.assertIn("key.startsWith('nexus-stage23-shell-')",page)
        self.assertNotIn("await caches.delete('nexus-app-shell",sw)

    def test_receipt_has_zero_claims_of_public_hosting(self):
        r=json.loads(self.assets[m.RECEIPT])
        self.assertEqual(r["status"],"STATIC_ARTIFACT_NOT_HOSTED")
        for field in ("actual_mobile_tested","public_deployment_proven",
                      "railway_original_volume_restored","release_seal",
                      "private_api_calls","background_worker_registration"):
            self.assertIs(r[field],False)
        self.assertEqual(r["assets"]["index.html"]["sha256"],
                         hashlib.sha256(self.assets["index.html"]).hexdigest())

    def test_fails_on_modified_html_transport(self):
        with self.assertRaises(m.Blocked):
            m.assemble_html(self.portable+b"fetch('/unexpected')")

    def test_fails_on_unreviewed_worker_injection(self):
        with self.assertRaises(m.Blocked):
            m.assemble_html(self.portable+b"navigator.serviceWorker.register('/evil')")

    def test_fails_on_missing_trusted_navigation(self):
        with self.assertRaises(m.Blocked):
            m.assemble_html(self.portable.replace(m.NAV.encode(),b"unsafe"))

    def test_fails_on_modified_storage_boundary(self):
        with self.assertRaises(m.Blocked):
            m.assemble_html(self.portable.replace(m.ARCHIVE_BEFORE.encode(),b"unsafe"))

    def test_fails_on_icon_dimensions(self):
        fake=bytearray(self.assets[m.ICON_PATHS[0]])
        fake[16:20]=b"\x00\x00\x00\x05"
        with self.assertRaises(m.Blocked):
            m.png(bytes(fake),192)

    def test_byte_identity_of_rebuild(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            for key,value in self.assets.items():
                p=out/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
            for key,value in m.produce().items():
                self.assertEqual((out/key).read_bytes(),value,key)
            (out/"index.html").write_bytes(b"tamper")
            self.assertNotEqual((out/"index.html").read_bytes(),self.assets["index.html"])

if __name__=="__main__":
    unittest.main(verbosity=2)
