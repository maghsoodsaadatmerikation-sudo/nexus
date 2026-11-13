#!/usr/bin/env python3
"""Stage 24 adversarial publication and read-only public observer fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "nexus_stage24", ROOT / "scripts" / "stage24-static-publish-check.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
builder = p.stage23_builder()


class Stage24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = builder.produce()

    @staticmethod
    def populate(root, files):
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def test_all_reviewed_assets_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            result = p.validate_site(root, self.files)
            self.assertEqual(result["status"], "LOCAL_STATIC_BYTES_PASS")
            self.assertEqual(result["file_count"], 7)
            self.assertFalse(result["verified_public_https"])
            self.assertEqual(result["index_sha256"],
                             hashlib.sha256(self.files["index.html"]).hexdigest())

    def test_exact_source_reproducible(self):
        self.assertEqual(self.files, builder.produce())
        self.assertTrue(all(len(v) == 40 for v in p.SOURCE_PINS.values()))

    def test_orphan_snapshot_contains_only_reviewed_files(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(root), *args],
                    text=True, stderr=subprocess.STDOUT).strip()
            git("init", "-q")
            git("config", "user.email", "stage24@example.invalid")
            git("config", "user.name", "Synthetic Stage24")
            (root / "Cargo.toml").write_text("must-not-publish")
            git("add", "Cargo.toml")
            git("commit", "-qm", "synthetic parent source")
            git("switch", "--orphan", "nexus-mobile-site-v24")
            self.assertEqual(git("ls-files"), "")
            self.populate(root, self.files)
            approved = sorted(self.files)
            git("add", "-f", "--", *approved)
            self.assertEqual(set(git("diff", "--cached", "--name-only").splitlines()),
                             set(approved))
            git("commit", "-qm", "synthetic isolated snapshot")
            self.assertEqual(git("log", "-1", "--format=%P"), "")
            self.assertEqual(set(git("ls-tree", "-r", "--name-only", "HEAD").splitlines()),
                             set(approved))
            self.assertNotIn("Cargo.toml", git("ls-tree", "-r", "--name-only", "HEAD"))

    def test_no_app_source_leaked_to_static_branch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            (root / "Cargo.toml").write_text("leaked rust configuration")
            with self.assertRaises(p.Refused):
                p.validate_site(root, self.files)

    def test_no_unreviewed_extra_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            (root / "credentials.txt").write_text("fake string")
            with self.assertRaises(p.Refused):
                p.validate_site(root, self.files)

    def test_no_missing_icon(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            (root / "icons/nexus-512.png").unlink()
            with self.assertRaises(p.Refused):
                p.validate_site(root, self.files)

    def test_no_tampered_html(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            (root / "index.html").write_bytes(self.files["index.html"] + b"<script>evil</script>")
            with self.assertRaises(p.Refused):
                p.validate_site(root, self.files)

    def test_symlinks_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.populate(root, self.files)
            (root / "leak").symlink_to(root / "index.html")
            with self.assertRaises(p.Refused):
                p.validate_site(root, self.files)

    def test_no_http_redirect_or_failure(self):
        expected = b"reviewed bytes"
        for code in (301, 302, 304, 403, 404, 500):
            with self.subTest(code=code), self.assertRaises(p.Refused):
                p.verify_response(code, "text/html", expected, "index.html", expected)

    def test_no_wrong_mime_or_bytes(self):
        good = p.verify_response(200,"text/html; charset=utf-8",b"reviewed",
                                 "index.html",b"reviewed")
        self.assertTrue(good["exact_byte_match"])
        for mime, body in (("application/json", b"reviewed"),
                           ("text/html", b"tampered"),
                           ("text/html", b"")):
            with self.subTest(mime=mime, body=body), self.assertRaises(p.Refused):
                p.verify_response(200, mime, body, "index.html", b"reviewed")

    def test_no_unapproved_path(self):
        with self.assertRaises(p.Refused):
            p.verify_response(200,"text/html",b"data","../secret",b"data")
        with self.assertRaises(p.Refused):
            p.verified_url("../secret")
        with self.assertRaises(p.Refused):
            p.verified_url("https://evil.example/")

    def test_public_urls_are_fixed_https_subpaths(self):
        for name in p.PUBLIC_FILES:
            self.assertEqual(p.verified_url(name),
                             "https://maghsoodsaadatmerikation-sudo.github.io/nexus/"+name)

    def test_privileged_publish_only_after_read_only_pr_verification(self):
        workflow = (ROOT / ".github/workflows/stage24-static-site.yml").read_text()
        self.assertIn("needs: verify-snapshot", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("refs/heads/feat/work-mode-20261113", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("    permissions:\n      contents: write", workflow)
        self.assertIn("git switch --orphan", workflow)
        self.assertNotIn("git push --force", workflow)
        self.assertIn("test -z \"$(git ls-remote --heads origin", workflow)

    def test_icon_binary_not_embedded_in_private_log(self):
        for name in ["icons/nexus-192.png","icons/nexus-512.png"]:
            x = self.files[name]
            proof = p.verify_response(200, "image/png", x, name, x)
            self.assertEqual(proof["sha256"], hashlib.sha256(x).hexdigest())
            self.assertNotIn("data", proof)

    def test_public_observer_separates_live_from_static(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.populate(root,self.files)
            result=p.validate_site(root,self.files)
            self.assertNotIn("PUBLIC_STATIC_BYTES_PASS",result.values())
            self.assertIs(result["railway_original_volume_recovery_proven"],False)
            self.assertIs(result["owner_android_tested"],False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
