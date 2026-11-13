#!/usr/bin/env python3
"""Adversarial tests for Stage 22's deterministic offline-only assembly."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("portable_builder", HERE / "build-work-mode-portable.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class PortableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = M.PAGE.read_text(encoding="utf-8")
        cls.core = M.CORE.read_text(encoding="utf-8")

    def fail_build(self, page=None, core=None):
        with self.assertRaises(M.BuildBlocked):
            M.assemble(self.page if page is None else page,
                       self.core if core is None else core)

    def test_reproducible(self):
        self.assertEqual(M.assemble(self.page, self.core),
                         M.assemble(self.page, self.core))

    def test_offline_content_security_policy(self):
        data = M.assemble(self.page, self.core).decode()
        self.assertIn("connect-src 'none'", data)
        self.assertNotIn("connect-src 'self'", data)
        self.assertNotIn("fetch(", data)
        self.assertNotIn("<script src=", data)
        self.assertNotIn("<link rel=", data)
        self.assertNotIn("<iframe", data)
        self.assertNotIn("<form ", data)

    def test_assistant_inaccessible_offline(self):
        data = M.assemble(self.page, self.core).decode()
        self.assertIn('hidden aria-hidden="true"><h2 data-k="assist">', data)
        self.assertIn("$('send').onclick=()=>status('chatFailed');", data)
        self.assertNotIn("$('send').onclick=async()=>", data)

    def test_private_archive_maintained(self):
        data = M.assemble(self.page, self.core).decode()
        for marker in ("indexedDB", "vault.create", "vault.backup", "vault.save",
                       "vault.restore", "vault.unlock", "vault.lock",
                       "NexusWorkMode", 'id="file"', 'id="tasks"'):
            self.assertIn(marker, data)

    def test_mobile_bilingual_banner(self):
        data = M.assemble(self.page, self.core).decode()
        self.assertIn('id="portable-mode"', data)
        self.assertIn('lang="fa"', data)
        self.assertIn("No account, server", data)
        self.assertNotIn('href="/research-chat"', data)
        self.assertNotIn('href="/connections"', data)

    def test_manifest_truthfulness(self):
        data = M.assemble(self.page, self.core)
        manifest = M.make_manifest(data, self.page.encode(), self.core.encode())
        self.assertEqual(manifest["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest["bytes"], len(data))
        for key in ("external_providers", "production_deployment", "release_seal",
                    "railway_volume_captured"):
            self.assertFalse(manifest[key])

    def test_added_remote_request_fails_closed(self):
        self.fail_build(page=self.page + "fetch('/unreviewed')")

    def test_missing_handler_fails_closed(self):
        self.fail_build(page=self.page.replace(M.CHAT_BEGIN, "unreviewed()=>{"))

    def test_changed_csp_fails_closed(self):
        self.fail_build(page=self.page.replace(M.CSP_OLD, "connect-src https:"))

    def test_modified_core_script_boundary_fails_closed(self):
        self.fail_build(core=self.core + "</script>")

    def test_missing_core_binding_fails_closed(self):
        self.fail_build(page=self.page.replace(M.SCRIPT_TAG, "<script src='elsewhere'></script>"))

    def test_missing_assist_section_fails_closed(self):
        self.fail_build(page=self.page.replace(M.ASSIST_BEGIN, "<section>unknown"))

    def test_oversized_core_fails_closed(self):
        self.fail_build(core=self.core + "\n" * 60_000)

if __name__ == "__main__":
    unittest.main(verbosity=2)
