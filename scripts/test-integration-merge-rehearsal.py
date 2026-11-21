#!/usr/bin/env python3
"""Independent no-network parser/authority regressions for merge rehearsal."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "mergerehearsal", Path(__file__).with_name("integration-merge-rehearsal.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = b"a" * 40


class MergeParserTests(unittest.TestCase):
    def test_clean(self):
        report = m.parse_merge_tree(SHA + b"\x00", 0)
        self.assertEqual(report["status"], "CLEAN_MERGE_REHEARSAL_ONLY")
        self.assertEqual(report["conflict_paths"], [])
        self.assertEqual(report["result_tree_sha"], "a" * 40)

    def test_conflict_paths_without_diagnostics(self):
        raw = SHA + b"\x00src/policy.rs\x00src/workspace.rs\x00\x001\x00secret error message"
        report = m.parse_merge_tree(raw, 1)
        self.assertEqual(report["status"], "BLOCKED_BY_MERGE_CONFLICT")
        self.assertEqual(report["conflict_paths"], ["src/policy.rs", "src/workspace.rs"])
        self.assertNotIn("secret", repr(report))

    def test_parse_fails_closed(self):
        for data, code in [
            (b"", 0), (b"bad\x00", 0), (SHA + b"\x00x", 0),
            (SHA + b"\x00", 1), (SHA + b"\x00foo\x00\x00", 128),
            (SHA + b"\x00../private\x00\x00diagnostic", 1),
            (SHA + b"\x00evil\npath\x00\x00diagnostic", 1),
            (SHA + b"\x00a" * 300000, 1),
        ]:
            with self.subTest(data=data[:40], code=code):
                with self.assertRaises(ValueError):
                    m.parse_merge_tree(data, code)


if __name__ == "__main__":
    unittest.main()
