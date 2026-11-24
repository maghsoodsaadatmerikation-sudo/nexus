#!/usr/bin/env python3
"""Regression checks for fail-closed Studio source and public package assembly."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from png_pixels import pixel_digest
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

    def test_public_composer_is_hash_bound_and_standalone_preserved(self):
        import hashlib
        composer = (ROOT / "web/studio-composer-ui.js").read_bytes()
        integrity = base64.b64encode(hashlib.sha256(composer).digest())
        public = (ROOT / "public/studio/index.html").read_bytes()
        self.assertIn(b'<script src="./studio-composer-ui.js" integrity="sha256-' + integrity + b'"></script>', public)
        self.assertNotIn(composer, public)
        self.assertEqual(composer, (ROOT / "public/studio/studio-composer-ui.js").read_bytes())
        self.assertIn(composer, (ROOT / "web/studio.html").read_bytes())

    def test_public_shell_fails_closed_if_integration_anchor_is_missing_or_duplicated(self):
        source = (ROOT / "web/studio.html").read_text()
        panel = (ROOT / "web/device/device-panel.html").read_text()
        for anchor in ("script-src 'unsafe-inline'", "frame-src 'self' blob:; worker-src blob:",
                       "img-src data:", "<title>", "</style>", "</header>",
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

    def test_approved_logo_matches_source_and_every_package(self):
        subprocess.run([sys.executable, str(HERE / "build-nexus-icons.py"), "--check"],
                       check=True, timeout=15)
        studio = (ROOT / "public/studio/index.html").read_text()
        self.assertIn('src="data:image/png;base64,' + base64.b64encode(
            (ROOT / "web/nexus-brand-icon.png").read_bytes()).decode("ascii") + '"', studio)
        self.assertIn('rel="apple-touch-icon" href="./icons/nexus-192.png"', studio)
        for size in (192, 512):
            name = f"icons/nexus-{size}.png"
            packaged = (ROOT / "public/studio" / name).read_bytes()
            self.assertEqual(packaged, (ROOT / "public" / name).read_bytes())
            self.assertLess(len(packaged), 10_000)  # Legacy offline install gate
            self.assertEqual(len(pixel_digest(packaged, size, size)), 64)

    def test_public_page_leaves_the_opaque_lab_module_intact(self):
        compiled = static_builder.render_public_shell(
            (ROOT / "web/studio.html").read_text(),
            (ROOT / "web/device/device-panel.html").read_text(),
        )
        self.assertIn(b"frame-src 'self' blob:; worker-src 'self' blob:", compiled)
        self.assertIn((ROOT / "web/studio-lab.js").read_bytes(), compiled)

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
            for name in ("build-studio.py", "studio_template_contract.py", "studio_module_graph.py"):
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


class StudioMaintenanceTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="nexus-studio-maintenance-test-")
        self.addCleanup(scratch.cleanup)
        self.repo = Path(scratch.name)
        for dirname in ("web", "public/studio", "public/icons"):
            shutil.copytree(ROOT / dirname, self.repo / dirname)
        (self.repo / "scripts").mkdir()
        for name in ("build-studio.py", "build-device-model.py", "build-studio-static.py",
                     "studio-maintenance.py", "studio_module_graph.py", "studio_template_contract.py",
                     "studio_public_assets.py"):
            shutil.copy2(HERE / name, self.repo / "scripts" / name)
        self.unrelated = self.repo / "notes.txt"
        self.unrelated.write_text("original notes\n")
        self.command("git", "init", "-q")
        self.commit("Fixture")

    def command(self, *args, expected=0):
        result = subprocess.run(args, cwd=self.repo, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout.strip()

    def commit(self, message):
        self.command("git", "add", "-A")
        self.command("git", "-c", "user.name=Maintenance Fixture", "-c",
                     "user.email=fixture@example.invalid", "commit", "-qm", message)

    def audit(self, *args, expected=0):
        return json.loads(self.command(sys.executable, "scripts/studio-maintenance.py",
                                       *args, expected=expected))

    def test_audit_and_repair_stale_and_missing_assets(self):
        healthy = self.audit()
        self.assertEqual(healthy["status"], "healthy")
        standalone = self.repo / "web/studio.html"
        worker = self.repo / "public/studio/service-worker.js"
        original_standalone, original_worker = standalone.read_bytes(), worker.read_bytes()
        standalone.write_text("stale standalone")
        worker.unlink()
        self.assertEqual(self.audit("--repair", expected=2)["status"], "blocked")

        self.commit("Introduce generated drift")
        drift = self.audit(expected=1)
        self.assertEqual(drift["status"], "drift")
        self.assertEqual(drift["changed_files"], ["public/studio/service-worker.js", "web/studio.html"])
        self.assertEqual(standalone.read_text(), "stale standalone")
        self.assertFalse(worker.exists())
        self.assertEqual(self.command("git", "status", "--porcelain"), "")

        repair = self.audit("--repair")
        self.assertEqual(repair, {**drift, "status": "repaired"})
        self.assertEqual(standalone.read_bytes(), original_standalone)
        self.assertEqual(worker.read_bytes(), original_worker)
        self.assertEqual(self.unrelated.read_text(), "original notes\n")
        self.assertEqual(self.command("git", "rev-parse", "HEAD"), drift["base_commit"])

    def test_render_build_check_blocks_unreviewed_files_and_links(self):
        published = self.repo / "public/studio"
        self.command(sys.executable, "scripts/build-studio-static.py", "--check")
        extra = published / "unexpected.txt"
        extra.write_text("synthetic private fixture\n")
        result = subprocess.run(
            [sys.executable, "scripts/build-studio-static.py", "--check"],
            cwd=self.repo, capture_output=True, text=True, timeout=45,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unreviewed or unsupported asset", result.stderr)
        extra.unlink()
        extra.symlink_to(self.unrelated)
        result = subprocess.run(
            [sys.executable, "scripts/build-studio-static.py", "--check"],
            cwd=self.repo, capture_output=True, text=True, timeout=45,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unreviewed or unsupported asset", result.stderr)
        self.assertNotIn("original notes", result.stderr)

    def test_verifier_side_effect_is_blocked_before_patch(self):
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        standalone = self.repo / "web/studio.html"
        standalone.write_text("stale")
        builder = self.repo / "scripts/build-studio-static.py"
        with builder.open("a") as handle:
            handle.write("\nif '--check' in sys.argv:\n"
                         "    (ROOT / 'notes.txt').write_text('verification side effect')\n")
        self.commit("Introduce drift and an out-of-scope verifier side effect")

        blocked = self.audit("--repair", expected=2)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("notes.txt", blocked["reason"])
        self.assertEqual(self.unrelated.read_text(), "original notes\n")
        self.assertEqual(standalone.read_text(), "stale")
        self.assertEqual(self.command("git", "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

