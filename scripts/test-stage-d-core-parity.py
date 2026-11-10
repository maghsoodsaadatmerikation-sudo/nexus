#!/usr/bin/env python3
"""Synthetic and original-checkout regression for exact pinned Rust source parity.

These tests copy PUBLIC source files to disposable directories; no provider
credentials, original volume files, private workspace content or network.
"""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).with_name("stage-d-core-parity.py")
spec = importlib.util.spec_from_file_location("nexus_stage_d_core_parity", SCRIPT)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


class CoreSourceParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-parity-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.copy = Path(self.tmp.name) / "source"
        self.copy.mkdir()
        for relative in parity.SOURCE_BLOBS:
            target = self.copy / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def test_known_original_railway_deployed_sources_match_current_checkout(self):
        self.assertEqual(parity.check(ROOT, parity.DEPLOYED_COMMIT),
                         len(parity.SOURCE_BLOBS))

    def test_disposable_valid_source_copy_passes(self):
        self.assertEqual(parity.check(self.copy, parity.DEPLOYED_COMMIT),
                         len(parity.SOURCE_BLOBS))

    def test_changed_workspace_serialization_fails(self):
        with (self.copy / "src/workspace.rs").open("ab") as file:
            file.write(b"\n// synthetic tamper\n")
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, parity.DEPLOYED_COMMIT)

    def test_changed_human_judgment_model_fails(self):
        with (self.copy / "src/epistemic.rs").open("ab") as file:
            file.write(b"\n// synthetic tamper\n")
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, parity.DEPLOYED_COMMIT)

    def test_changed_toolchain_fails(self):
        (self.copy / "rust-toolchain.toml").write_text('channel = "new"\n')
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, parity.DEPLOYED_COMMIT)

    def test_missing_source_fails(self):
        (self.copy / "src/workspace_persistence.rs").unlink()
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, parity.DEPLOYED_COMMIT)

    def test_symlinked_source_fails(self):
        file = self.copy / "src/analysis.rs"
        real = self.copy / "analysis-original"
        file.rename(real)
        file.symlink_to(real)
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, parity.DEPLOYED_COMMIT)

    def test_other_even_valid_looking_40_hex_commit_fails(self):
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, "a" * 40)

    def test_missing_commit_fails(self):
        with self.assertRaises(parity.ParityError):
            parity.check(self.copy, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
