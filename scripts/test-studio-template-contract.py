#!/usr/bin/env python3
"""Regression checks for fail-closed Studio source and public package assembly."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from studio_template_contract import replace_exact

MODULE = importlib.util.spec_from_file_location("nexus_studio_static_builder", HERE / "build-studio-static.py")
assert MODULE is not None and MODULE.loader is not None
static_builder = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(static_builder)


class TemplateContractTests(unittest.TestCase):
    def test_anchor_is_required_unique_and_never_silently_skipped(self):
        self.assertEqual(replace_exact("a SLOT z", "SLOT", "B"), "a B z")
        self.assertEqual(replace_exact("SLOT x SLOT", "SLOT", "B", expected=2), "B x B")
        for source in ("no anchor", "SLOT and SLOT"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                replace_exact(source, "SLOT", "B")
        with self.assertRaises(ValueError):
            replace_exact("SLOT", "SLOT", "B", expected=2)
        for needle, expected in (("", 1), ("SLOT", 0)):
            with self.assertRaises(ValueError):
                replace_exact("SLOT", needle, "B", expected=expected)

    def test_static_public_shell_matches_checked_in_package_byte_for_byte(self):
        compiled = static_builder.render_public_shell(
            (ROOT / "web/studio.html").read_text(),
            (ROOT / "web/device/device-panel.html").read_text(),
        )
        self.assertEqual(compiled, (ROOT / "public/studio/index.html").read_bytes())

    def test_public_shell_fails_closed_if_integration_anchor_is_missing_or_duplicated(self):
        source = (ROOT / "web/studio.html").read_text()
        panel = (ROOT / "web/device/device-panel.html").read_text()
        for anchor in ("script-src 'unsafe-inline'", "worker-src blob:",
                       "img-src 'none'", "<title>", "</style>", "</header>",
                       "</main>", 'value="2048"></details>',
                       '<label for="gateway"', "</body>"):
            with self.subTest(anchor=anchor, kind="missing"):
                changed = source.replace(anchor, "", 1)
                with self.assertRaises(ValueError):
                    static_builder.render_public_shell(changed, panel)
            with self.subTest(anchor=anchor, kind="duplicate"):
                changed = source + anchor
                with self.assertRaises(ValueError):
                    static_builder.render_public_shell(changed, panel)

    def test_worker_template_tokens_must_remain_unique(self):
        for token in ("__DIGEST__", "__INDEX_BYTES__", "__CODE_ASSETS__", "__PACKAGE_ID__"):
            with self.subTest(token=token):
                self.assertEqual(static_builder.WORKER.count(token), 1)
                with self.assertRaises(ValueError):
                    replace_exact(static_builder.WORKER.replace(token, ""), token, "x")
                with self.assertRaises(ValueError):
                    replace_exact(static_builder.WORKER + token, token, "x")

    def test_optimized_python_cannot_omit_required_studio_module(self):
        with tempfile.TemporaryDirectory(prefix="nexus-studio-template-guard-") as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            shutil.copytree(ROOT / "web", root / "web")
            for name in ("build-studio.py", "studio_template_contract.py"):
                shutil.copy2(HERE / name, root / "scripts" / name)
            command = [sys.executable, "-O", str(root / "scripts/build-studio.py"), "--check"]
            baseline = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(baseline.returncode, 0, baseline.stderr + baseline.stdout)
            shell_path = root / "web/studio-shell.html"
            original = shell_path.read_text()
            marker = "/*STUDIO_APP*/"
            self.assertEqual(original.count(marker), 1)
            for altered in (original.replace(marker, ""), original.replace(marker, marker * 2),
                            original + "\n/*STUDIO_UNREGISTERED*/\n"):
                shell_path.write_text(altered)
                failure = subprocess.run(command, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(failure.returncode, 0)
                self.assertIn("ValueError", failure.stderr)
            self.assertEqual((root / "web/studio.html").read_bytes(),
                             (ROOT / "web/studio.html").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)

