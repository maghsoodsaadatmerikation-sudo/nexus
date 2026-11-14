#!/usr/bin/env python3
"""Negative and reproducibility tests for the public, data-free mobile ZIP."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("build-mobile-offline-kit.py")
spec = importlib.util.spec_from_file_location("mobile_kit", SCRIPT)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

REVISION = "a" * 40


def replace_zip(original, changes=None, addition=None, *, symlink=None):
    changes = changes or {}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as base, zipfile.ZipFile(
            out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as dest:
        for info in base.infolist():
            body = changes.get(info.filename, base.read(info.filename))
            item = copy.copy(info)
            if symlink == info.filename:
                item.external_attr = 0o120777 << 16
            dest.writestr(item, body)
        if addition is not None:
            dest.writestr(addition, b"bad")
    return out.getvalue()


class MobileKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = kit.SOURCE.read_bytes()
        cls.original = kit.build_bytes(cls.source, REVISION)

    def valid(self, archive=None):
        return kit.inspect_bytes(archive if archive is not None else self.original,
                                 self.source, REVISION)

    def blocked(self, archive, sha=REVISION):
        with self.assertRaises((kit.PackageBlocked, ValueError, UnicodeError)):
            kit.inspect_bytes(archive, self.source, sha)

    def test_exact_three_files_and_release_disclaimer(self):
        report = self.valid()
        self.assertEqual(report["file_count"], 3)
        self.assertEqual(report["status"], "VERIFIED_PUBLIC_SINGLE_FILE_KIT")
        self.assertFalse(report["production_verified"])
        self.assertFalse(report["personal_data_included"])
        self.assertFalse(report["release_authorized"])
        self.assertEqual(report["authority"], "none")
        with zipfile.ZipFile(io.BytesIO(self.original)) as z:
            self.assertEqual(set(z.namelist()), kit.ALLOWED)
            self.assertEqual(z.read(kit.APP), self.source)
            self.assertIn("فارسی".encode(), z.read(kit.README))

    def test_deterministic_zip_bytes_same_source_and_commit(self):
        self.assertEqual(self.original, kit.build_bytes(self.source, REVISION))
        self.assertEqual(self.valid()["zip_sha256"],
                         hashlib.sha256(self.original).hexdigest())

    def test_another_commit_requires_its_own_manifest(self):
        another = kit.build_bytes(self.source, "b" * 40)
        self.assertNotEqual(self.original, another)
        self.blocked(another)

    def test_corrupted_html_is_refused_even_if_zip_crc_is_recomputed(self):
        changed = self.source.replace(b"<title", b"<TITLE", 1)
        self.assertNotEqual(changed, self.source)
        self.blocked(replace_zip(self.original, {kit.APP: changed}))

    def test_modified_readme_is_refused(self):
        self.blocked(replace_zip(self.original,
                                {kit.README: b"unreviewed usage instructions"}))

    def test_manifest_cannot_claim_release_or_real_backup(self):
        with zipfile.ZipFile(io.BytesIO(self.original)) as z:
            original = json.loads(z.read(kit.MANIFEST))
        for field in ("production_verified", "production_backup",
                      "release_authorized", "contains_user_data"):
            modified = dict(original, **{field: True})
            encoded = json.dumps(modified).encode()
            with self.subTest(field=field):
                self.blocked(replace_zip(self.original, {kit.MANIFEST: encoded}))

    def test_extra_entries_and_traversal_are_refused(self):
        for extra in ("../escape.txt", "private-record.json", "/root/secret",
                      "NEXUS-offline.html/copy"):
            with self.subTest(name=extra):
                self.blocked(replace_zip(self.original, addition=extra))

    def test_duplicate_archive_member_is_refused(self):
        self.blocked(replace_zip(self.original, addition=kit.APP))

    def test_symlinked_entry_is_refused(self):
        self.blocked(replace_zip(self.original, symlink=kit.APP))

    def test_invalid_duplicate_json_keys_are_refused(self):
        self.blocked(replace_zip(self.original, {
            kit.MANIFEST: b'{"schema":"valid","schema":"evil"}'
        }))

    def test_unexpected_package_format_and_wrong_source_are_refused(self):
        self.blocked(b"not a zip")
        with self.assertRaises(kit.PackageBlocked):
            kit.build_bytes(b"<html>not the reviewed NEXUS app</html>", REVISION)
        with self.assertRaises(kit.PackageBlocked):
            kit.build_bytes(self.source, "bad-sha")

    def test_oversize_package_does_not_decompress(self):
        self.blocked(b"Q" * (kit.MAX_ZIP + 1))

    def test_no_replace_and_readback_verification(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "nexus-offline-mobile.zip"
            kit.publish_no_replace(file, self.original)
            self.assertEqual(kit.read_archive(file), self.original)
            with self.assertRaises((kit.PackageBlocked, FileExistsError)):
                kit.publish_no_replace(file, b"not-a-zip")
            self.assertEqual(file.read_bytes(), self.original)

    def test_symlinked_archive_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            file = parent / "normal.zip"
            file.write_bytes(self.original)
            alias = parent / "alias.zip"
            alias.symlink_to(file)
            with self.assertRaises(OSError):
                kit.read_archive(alias)

    def test_hardlinked_archive_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            file = parent / "normal.zip"
            file.write_bytes(self.original)
            alias = parent / "alias.zip"
            alias.hardlink_to(file)
            with self.assertRaises(kit.PackageBlocked):
                kit.read_archive(file)


if __name__ == "__main__":
    unittest.main()
